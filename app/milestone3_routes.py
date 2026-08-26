"""Routes for additive Milestone 3 features. Existing route module is untouched."""

from datetime import date

from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Attendee, Event, Vendor, VendorAssignment, VendorRating
from app.milestone3_models import AttendeeInterest, Certificate, Connection, Feedback
from app.milestone3_services import analyse_sentiment, build_certificate_pdf, build_xlsx

milestone3 = Blueprint("milestone3", __name__, url_prefix="/milestone-3")


def _next_code(prefix, model, field):
    number = 1001
    while model.query.filter(field == f"{prefix}{number}").first(): number += 1
    return f"{prefix}{number}"


def _registration_or_404(registration_id):
    attendee = Attendee.query.filter_by(registration_id=registration_id).first_or_404()
    if not attendee.event_id:
        from flask import abort
        abort(400, "This registration is not associated with an event.")
    return attendee


def _vendor_recommendations():
    entries = []
    for vendor in Vendor.query.filter_by(availability="Available").order_by(Vendor.vendor_name).all():
        ratings = [rating.overall_rating for rating in vendor.ratings]
        cost_ratings = [rating.cost for rating in vendor.ratings]
        average_rating = sum(ratings) / len(ratings) if ratings else 3.0
        cost_score = sum(cost_ratings) / len(cost_ratings) if cost_ratings else 3.0
        score = round((average_rating / 5 * 60) + 25 + (cost_score / 5 * 15), 1)
        entries.append({"vendor": vendor, "average_rating": average_rating, "cost_score": cost_score, "score": score})
    return sorted(entries, key=lambda item: item["score"], reverse=True)


@milestone3.route("/participant-access", methods=["GET", "POST"])
def participant_access():
    """Private entry page for participant-only Milestone 3 tools."""
    if request.method == "POST":
        registration_id = request.form.get("registration_id", "").strip().upper()
        attendee = Attendee.query.filter_by(registration_id=registration_id).first()
        if attendee and attendee.event_id:
            return redirect(url_for("milestone3.participant_hub", registration_id=registration_id))
        flash("Enter a valid event registration ID to continue.", "danger")
    return render_template("milestone3/participant_access.html")


@milestone3.route("/feedback/<registration_id>", methods=["GET", "POST"])
def feedback_form(registration_id):
    attendee = _registration_or_404(registration_id); event = attendee.event
    if event.status != "Completed":
        flash("Feedback becomes available after the event is marked completed.", "danger")
        return redirect(url_for("milestone3.participant_hub", registration_id=registration_id))
    feedback = Feedback.query.filter_by(registration_id=registration_id).first()
    if request.method == "POST":
        try:
            rating = int(request.form.get("rating", "0"))
            if not 1 <= rating <= 5: raise ValueError("Choose a rating from 1 to 5.")
            if feedback: raise ValueError("Feedback has already been submitted for this registration.")
            comments = request.form.get("comments", "").strip()
            db.session.add(Feedback(feedback_id=_next_code("FDB", Feedback, Feedback.feedback_id), registration_id=registration_id, event_id=event.event_id, rating=rating, comments=comments or None, sentiment=analyse_sentiment(comments)))
            db.session.commit(); flash("Thank you. Your feedback has been recorded.", "success")
            return redirect(url_for("milestone3.participant_hub", registration_id=registration_id))
        except (ValueError, IntegrityError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("milestone3/feedback_form.html", attendee=attendee, event=event, feedback=feedback)


@milestone3.route("/participants/<registration_id>")
def participant_hub(registration_id):
    attendee = _registration_or_404(registration_id)
    return render_template("milestone3/participant_hub.html", attendee=attendee, event=attendee.event, feedback=Feedback.query.filter_by(registration_id=registration_id).first(), certificate=Certificate.query.filter_by(registration_id=registration_id).first(), interest=AttendeeInterest.query.filter_by(registration_id=registration_id).first())


@milestone3.route("/certificates/<registration_id>", methods=["POST"])
def generate_certificate(registration_id):
    attendee = _registration_or_404(registration_id)
    if attendee.status != "Checked In":
        flash("Certificates are available only to participants with Checked In attendance.", "danger")
        return redirect(url_for("milestone3.participant_hub", registration_id=registration_id))
    certificate = Certificate.query.filter_by(registration_id=registration_id).first()
    if not certificate:
        certificate = Certificate(certificate_id=_next_code("CERT", Certificate, Certificate.certificate_id), registration_id=registration_id, event_id=attendee.event_id, issue_date=date.today())
        db.session.add(certificate); db.session.commit()
    return redirect(url_for("milestone3.certificate_view", certificate_id=certificate.certificate_id))


@milestone3.route("/certificates/<certificate_id>")
def certificate_view(certificate_id):
    certificate = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404(); attendee = _registration_or_404(certificate.registration_id)
    return render_template("milestone3/certificate.html", certificate=certificate, attendee=attendee, event=attendee.event)


@milestone3.route("/certificates/<certificate_id>/download")
def certificate_download(certificate_id):
    certificate = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404(); attendee = _registration_or_404(certificate.registration_id)
    response = make_response(build_certificate_pdf(attendee.name, attendee.event.event_name, attendee.event.date.strftime("%d %B %Y"), certificate.certificate_id))
    response.headers["Content-Type"] = "application/pdf"; response.headers["Content-Disposition"] = f'attachment; filename="{certificate.certificate_id}.pdf"'
    return response


@milestone3.route("/admin")
def admin_dashboard():
    total = Attendee.query.count(); checked_in = Attendee.query.filter_by(status="Checked In").count(); sentiments = {label: Feedback.query.filter_by(sentiment=label).count() for label in ("Positive", "Neutral", "Negative")}; feedback_count = sum(sentiments.values())
    events = Event.query.order_by(Event.date.desc()).all()
    event_sentiments = {}
    for event in events:
        counts = {label: Feedback.query.filter_by(event_id=event.event_id, sentiment=label).count() for label in sentiments}
        count = sum(counts.values())
        event_sentiments[event.event_id] = {label: round(value / count * 100) if count else 0 for label, value in counts.items()}
    return render_template("milestone3/admin_dashboard.html", total_events=Event.query.count(), total_registrations=total, checked_in_percentage=round(checked_in / total * 100, 1) if total else 0, total_revenue=0, average_vendor_rating=db.session.query(db.func.avg(VendorRating.overall_rating)).scalar() or 0, average_feedback_rating=db.session.query(db.func.avg(Feedback.rating)).scalar() or 0, sentiments=sentiments, sentiment_percentages={key: round(value / feedback_count * 100) if feedback_count else 0 for key, value in sentiments.items()}, events=events, event_sentiments=event_sentiments)


@milestone3.route("/events/<int:event_id>/vendors", methods=["GET", "POST"])
def vendor_recommendations(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == "POST":
        try:
            vendor = Vendor.query.filter_by(vendor_id=int(request.form.get("vendor_id", "")), availability="Available").first()
            service = request.form.get("service", "").strip()
            if not vendor or not service: raise ValueError("Choose an available vendor and enter the required service.")
            db.session.add(VendorAssignment(event_id=event_id, vendor_id=vendor.vendor_id, service=service, status="Assigned")); db.session.commit()
            flash("Vendor assigned. The recommendation did not restrict your choice.", "success"); return redirect(url_for("milestone3.vendor_recommendations", event_id=event_id))
        except (ValueError, IntegrityError) as error: db.session.rollback(); flash(str(error), "danger")
    return render_template("milestone3/vendor_recommendations.html", event=event, recommendations=_vendor_recommendations())


@milestone3.route("/networking/<registration_id>", methods=["GET", "POST"])
def attendees_directory(registration_id):
    attendee = _registration_or_404(registration_id); interest = AttendeeInterest.query.filter_by(registration_id=registration_id).first()
    if request.method == "POST":
        tags = request.form.get("interest_tags", "").strip()
        if not tags: flash("Add at least one interest tag.", "danger")
        else:
            if not interest:
                interest = AttendeeInterest(registration_id=registration_id, interest_tags=tags, share_contact=request.form.get("share_contact") == "yes"); db.session.add(interest)
            else: interest.interest_tags, interest.share_contact = tags, request.form.get("share_contact") == "yes"
            db.session.commit(); flash("Your networking preferences have been saved.", "success")
        return redirect(url_for("milestone3.attendees_directory", registration_id=registration_id))
    tags = {tag.strip().lower() for tag in (interest.interest_tags if interest else "").split(",") if tag.strip()}; directory = []
    query = AttendeeInterest.query.join(Attendee, Attendee.registration_id == AttendeeInterest.registration_id).filter(Attendee.event_id == attendee.event_id, AttendeeInterest.registration_id != registration_id)
    for other_interest in query.all():
        other = Attendee.query.filter_by(registration_id=other_interest.registration_id).first(); common = tags & {tag.strip().lower() for tag in other_interest.interest_tags.split(",") if tag.strip()}
        directory.append({"attendee": other, "interest": other_interest, "common": common})
    directory.sort(key=lambda item: len(item["common"]), reverse=True)
    return render_template("milestone3/directory.html", attendee=attendee, event=attendee.event, interest=interest, directory=directory)


@milestone3.route("/networking/<registration_id>/connect/<recipient_id>", methods=["POST"])
def request_connection(registration_id, recipient_id):
    attendee = _registration_or_404(registration_id); recipient = _registration_or_404(recipient_id)
    try:
        if attendee.event_id != recipient.event_id or registration_id == recipient_id: raise ValueError("Connections are limited to other attendees at the same event.")
        db.session.add(Connection(requester_registration_id=registration_id, recipient_registration_id=recipient_id, event_id=attendee.event_id, status="Pending")); db.session.commit(); flash("Connection request sent. Contact information remains private until it is accepted.", "success")
    except (ValueError, IntegrityError) as error: db.session.rollback(); flash(str(error), "danger")
    return redirect(url_for("milestone3.attendees_directory", registration_id=registration_id))


@milestone3.route("/reports/<report_name>.xlsx")
def export_report(report_name):
    if report_name == "attendees":
        headers = ["Registration ID", "Name", "Email", "Event", "Status"]
        rows = [[a.registration_id, a.name, a.email, a.event.event_name if a.event else "", a.status] for a in Attendee.query.order_by(Attendee.name).all()]
    elif report_name == "attendance":
        headers = ["Event", "Registration ID", "Name", "Attendance Status"]
        rows = [[a.event.event_name if a.event else "", a.registration_id, a.name, a.status] for a in Attendee.query.order_by(Attendee.event_id, Attendee.name).all()]
    elif report_name == "vendors":
        headers = ["Vendor", "Service", "Event", "Assignment Status", "Overall Rating"]
        rows = [[a.vendor.vendor_name, a.service, a.event.event_name, a.status, a.rating.overall_rating if a.rating else ""] for a in VendorAssignment.query.order_by(VendorAssignment.event_id).all()]
    else:
        from flask import abort
        abort(404)
    response = make_response(build_xlsx(headers, rows))
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-Disposition"] = f'attachment; filename="{report_name}-report.xlsx"'
    return response
