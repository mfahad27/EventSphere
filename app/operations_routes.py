"""Isolated Milestone 3/4 APIs, financial operations, analytics and reports."""
from datetime import date, datetime, timedelta
import csv
from io import StringIO

from flask import Blueprint, Response, abort, flash, jsonify, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Attendee, Event, EventResource, Resource, Vendor, VendorRating
from app.operations_models import ApprovalRequest, AutomationLog, EventBudget, EventReminder, Expense, Sponsorship
from app.operations_services import forecast_attendance, make_basic_pdf, money_summary

operations = Blueprint("operations", __name__, url_prefix="/operations")
api = Blueprint("api", __name__, url_prefix="/api/v1")
CATEGORIES = ("Venue", "Catering", "Staffing", "Marketing", "Logistics", "Equipment", "Other")
APPROVAL_STATUSES = ("Pending", "Approved", "Rejected")


def _event(event_id): return Event.query.get_or_404(event_id)
def _amount(value, label="Amount"):
    try: amount = float(value)
    except (TypeError, ValueError): raise ValueError(f"{label} must be a valid amount.")
    if amount < 0: raise ValueError(f"{label} cannot be negative.")
    return amount
def _date(value, label="Date"):
    try: return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError: raise ValueError(f"{label} must be valid.")
def _event_summary(event):
    budget = EventBudget.query.filter_by(event_id=event.event_id).first()
    expenses = Expense.query.filter_by(event_id=event.event_id).all(); sponsors = Sponsorship.query.filter_by(event_id=event.event_id).all()
    return money_summary(budget.planned_amount if budget else event.budget, expenses, sponsors)
def _log(event_id, action, details): db.session.add(AutomationLog(event_id=event_id, action=action, details=details))


@operations.route("/")
def hub():
    events = Event.query.order_by(Event.date.desc()).all()
    summaries = {event.event_id: _event_summary(event) for event in events}
    return render_template("operations/hub.html", events=events, summaries=summaries,
        pending_approvals=ApprovalRequest.query.filter_by(status="Pending").count(), scheduled_reminders=EventReminder.query.filter_by(status="Scheduled").count())


@operations.route("/events/<int:event_id>/finance", methods=["GET", "POST"])
def finance(event_id):
    event = _event(event_id); budget = EventBudget.query.filter_by(event_id=event_id).first()
    if request.method == "POST":
        try:
            amount = _amount(request.form.get("planned_amount"));
            if budget: budget.planned_amount = amount
            else: db.session.add(EventBudget(event_id=event_id, planned_amount=amount))
            db.session.commit(); flash("Event budget saved.", "success")
        except ValueError as error: flash(str(error), "danger")
        return redirect(url_for("operations.finance", event_id=event_id))
    expenses = Expense.query.filter_by(event_id=event_id).order_by(Expense.expense_date.desc()).all()
    sponsors = Sponsorship.query.filter_by(event_id=event_id).order_by(Sponsorship.sponsorship_id.desc()).all()
    return render_template("operations/finance.html", event=event, budget=budget, expenses=expenses, sponsors=sponsors, summary=_event_summary(event), categories=CATEGORIES)


@operations.route("/events/<int:event_id>/expenses", methods=["POST"])
def add_expense(event_id):
    _event(event_id)
    try:
        category = request.form.get("category", "")
        if category not in CATEGORIES: raise ValueError("Select a valid expense category.")
        description = request.form.get("description", "").strip()
        if not description: raise ValueError("Expense description is required.")
        expense = Expense(event_id=event_id, category=category, description=description, amount=_amount(request.form.get("amount")), expense_date=_date(request.form.get("expense_date")), status="Pending")
        db.session.add(expense); db.session.commit(); _log(event_id, "Expense submitted", f"{category}: ₹{expense.amount:,.2f} awaiting approval"); db.session.commit(); flash("Expense submitted for approval.", "success")
    except (ValueError, IntegrityError) as error: db.session.rollback(); flash(str(error), "danger")
    return redirect(url_for("operations.finance", event_id=event_id))


@operations.route("/events/<int:event_id>/sponsorships", methods=["POST"])
def add_sponsorship(event_id):
    _event(event_id)
    try:
        name = request.form.get("sponsor_name", "").strip()
        if not name: raise ValueError("Sponsor name is required.")
        status = request.form.get("status", "Pledged")
        if status not in ("Pledged", "Received"): raise ValueError("Select a valid sponsorship status.")
        db.session.add(Sponsorship(event_id=event_id, sponsor_name=name, amount=_amount(request.form.get("amount")), status=status, received_date=date.today() if status == "Received" else None)); db.session.commit(); flash("Sponsorship recorded.", "success")
    except ValueError as error: db.session.rollback(); flash(str(error), "danger")
    return redirect(url_for("operations.finance", event_id=event_id))


@operations.route("/expenses/<int:expense_id>/approval", methods=["POST"])
def approve_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id); decision = request.form.get("status", "")
    if decision in ("Approved", "Rejected"):
        expense.status = decision; _log(expense.event_id, f"Expense {decision.lower()}", expense.description); db.session.commit(); flash(f"Expense {decision.lower()}.", "success")
    return redirect(url_for("operations.finance", event_id=expense.event_id))


@operations.route("/approvals", methods=["GET", "POST"])
def approvals():
    if request.method == "POST":
        try:
            event_id = int(request.form.get("event_id", "")); _event(event_id); title = request.form.get("title", "").strip()
            if not title: raise ValueError("Approval title is required.")
            db.session.add(ApprovalRequest(event_id=event_id, request_type=request.form.get("request_type", "Operational"), title=title, amount=_amount(request.form.get("amount") or 0))); db.session.commit(); flash("Approval request created.", "success")
        except (ValueError, IntegrityError) as error: db.session.rollback(); flash(str(error), "danger")
        return redirect(url_for("operations.approvals"))
    return render_template("operations/approvals.html", requests=ApprovalRequest.query.order_by(ApprovalRequest.created_at.desc()).all(), events=Event.query.order_by(Event.date.desc()).all(), statuses=APPROVAL_STATUSES)


@operations.route("/approvals/<int:approval_id>", methods=["POST"])
def decide_approval(approval_id):
    approval = ApprovalRequest.query.get_or_404(approval_id); status = request.form.get("status", "")
    if status in ("Approved", "Rejected"):
        approval.status, approval.reviewed_at = status, datetime.now(); _log(approval.event_id, f"Approval {status.lower()}", approval.title); db.session.commit(); flash(f"Request {status.lower()}.", "success")
    return redirect(url_for("operations.approvals"))


@operations.route("/reminders", methods=["GET", "POST"])
def reminders():
    if request.method == "POST":
        try:
            event_id = int(request.form.get("event_id", "")); event = _event(event_id); audience = request.form.get("audience", "")
            if audience not in ("Participants", "Vendors", "Everyone"): raise ValueError("Select a valid audience.")
            message = request.form.get("message", "").strip() or f"Reminder: {event.event_name} is scheduled for {event.date.strftime('%d %b %Y')}."
            scheduled = datetime.strptime(request.form.get("scheduled_for"), "%Y-%m-%dT%H:%M")
            db.session.add(EventReminder(event_id=event_id, audience=audience, message=message, scheduled_for=scheduled)); db.session.commit(); flash("Reminder scheduled.", "success")
        except (ValueError, IntegrityError) as error: db.session.rollback(); flash(str(error), "danger")
        return redirect(url_for("operations.reminders"))
    return render_template("operations/reminders.html", reminders=EventReminder.query.order_by(EventReminder.scheduled_for.desc()).all(), events=Event.query.order_by(Event.date.desc()).all())


@operations.route("/reminders/<int:reminder_id>/send", methods=["POST"])
def send_reminder(reminder_id):
    reminder = EventReminder.query.get_or_404(reminder_id)
    if reminder.status == "Scheduled":
        reminder.status, reminder.sent_at = "Sent", datetime.now(); _log(reminder.event_id, "Reminder sent", reminder.message); db.session.commit(); flash("Reminder marked as sent.", "success")
    return redirect(url_for("operations.reminders"))


@operations.route("/analytics")
def analytics():
    events = Event.query.order_by(Event.date.desc()).all(); registrations = Attendee.query.count(); checked = Attendee.query.filter_by(status="Checked In").count()
    resources = Resource.query.all(); assigned = {row[0] for row in db.session.query(EventResource.resource_id).distinct().all()}
    resource_utilization = round(len(assigned) / len(resources) * 100, 1) if resources else 0
    finance = {event.event_id: _event_summary(event) for event in events}
    comparison = [{"name": event.event_name, "registered": Attendee.query.filter_by(event_id=event.event_id).count(), "checked": Attendee.query.filter_by(event_id=event.event_id, status="Checked In").count(), "utilization": finance[event.event_id]["utilization"]} for event in events]
    return render_template("operations/analytics.html", events=events, registrations=registrations, checked=checked,
      attendance_rate=round(checked / registrations * 100, 1) if registrations else 0, resource_utilization=resource_utilization,
      forecast=forecast_attendance(events), comparison=comparison, finance=finance,
      vendor_rating=db.session.query(db.func.avg(VendorRating.overall_rating)).scalar() or 0)


@operations.route("/optimization")
def optimization():
    suggestions = []
    for resource in Resource.query.order_by(Resource.resource_name).all():
        assignments = EventResource.query.filter_by(resource_id=resource.resource_id).all(); allocated = sum(item.quantity for item in assignments)
        utilization = round(allocated / resource.quantity * 100, 1) if resource.quantity else 0
        if not assignments: action = "Unused: consider assigning this resource to an upcoming event."
        elif utilization < 50: action = "Underutilized: available capacity may serve overlapping demand."
        elif utilization > 100: action = "Overcommitted: review allocations before the event date."
        else: action = "Allocation level is healthy."
        suggestions.append({"resource": resource, "allocated": allocated, "utilization": utilization, "action": action})
    return render_template("operations/optimization.html", suggestions=suggestions, forecast=forecast_attendance(Event.query.all()))


@operations.route("/reports/<int:event_id>/<format>")
def event_report(event_id, format):
    event = _event(event_id); summary = _event_summary(event); attendees = Attendee.query.filter_by(event_id=event_id).all()
    rows = [("Event", event.event_name), ("Date", event.date.strftime("%d %b %Y")), ("Registrations", len(attendees)), ("Checked in", sum(a.status == "Checked In" for a in attendees)), ("Budget", f"₹{summary['planned']:,.2f}"), ("Approved expenses", f"₹{summary['committed']:,.2f}"), ("Remaining budget", f"₹{summary['remaining']:,.2f}"), ("Sponsorship received", f"₹{summary['received']:,.2f}")]
    if format == "pdf":
        response = make_response(make_basic_pdf(f"EventSphere Event Report: {event.event_name}", rows)); response.headers["Content-Type"]="application/pdf"; response.headers["Content-Disposition"]=f'attachment; filename="event-{event_id}-report.pdf"'; return response
    if format == "csv":
        output = StringIO(); writer = csv.writer(output); writer.writerow(["Metric", "Value"]); writer.writerows(rows)
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="event-{event_id}-report.csv"'})
    abort(404)


def _event_data(event): return {"id": event.event_id, "name": event.event_name, "type": event.event_type, "date": event.date.isoformat(), "status": event.status, "expected_participants": event.expected_participants}
@api.route("/events")
def api_events(): return jsonify({"data": [_event_data(event) for event in Event.query.order_by(Event.date).all()]})
@api.route("/events/<int:event_id>")
def api_event(event_id): return jsonify({"data": _event_data(_event(event_id))})
@api.route("/attendees")
def api_attendees(): return jsonify({"data": [{"registration_id": a.registration_id, "name": a.name, "email": a.email, "event_id": a.event_id, "status": a.status} for a in Attendee.query.order_by(Attendee.attendee_id).all()]})
@api.route("/resources")
def api_resources(): return jsonify({"data": [{"id": r.resource_id, "name": r.resource_name, "quantity": r.quantity, "status": r.status} for r in Resource.query.all()]})
@api.route("/vendors")
def api_vendors(): return jsonify({"data": [{"id": v.vendor_id, "name": v.vendor_name, "service_type": v.service_type, "availability": v.availability} for v in Vendor.query.all()]})
@api.route("/events/<int:event_id>/budget")
def api_budget(event_id): return jsonify({"data": _event_summary(_event(event_id))})


@api.route("/expenses", methods=["POST"])
def api_create_expense():
    payload = request.get_json(silent=True) or {}
    try:
        event_id = int(payload.get("event_id")); _event(event_id)
        category = payload.get("category", "")
        if category not in CATEGORIES: raise ValueError("category must be a supported expense category")
        description = str(payload.get("description", "")).strip()
        if not description: raise ValueError("description is required")
        expense = Expense(event_id=event_id, category=category, description=description, amount=_amount(payload.get("amount")), expense_date=_date(payload.get("expense_date")), status="Pending")
        db.session.add(expense); _log(event_id, "Expense submitted via API", description); db.session.commit()
        return jsonify({"data": {"id": expense.expense_id, "status": expense.status}}), 201
    except (ValueError, TypeError):
        db.session.rollback(); return jsonify({"error": "Invalid expense payload."}), 400


@api.route("/sponsorships", methods=["POST"])
def api_create_sponsorship():
    payload = request.get_json(silent=True) or {}
    try:
        event_id = int(payload.get("event_id")); _event(event_id); name = str(payload.get("sponsor_name", "")).strip(); status = payload.get("status", "Pledged")
        if not name or status not in ("Pledged", "Received"): raise ValueError
        item = Sponsorship(event_id=event_id, sponsor_name=name, amount=_amount(payload.get("amount")), status=status, received_date=date.today() if status == "Received" else None)
        db.session.add(item); db.session.commit(); return jsonify({"data": {"id": item.sponsorship_id, "status": item.status}}), 201
    except (ValueError, TypeError):
        db.session.rollback(); return jsonify({"error": "Invalid sponsorship payload."}), 400
