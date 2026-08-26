from datetime import date, datetime
import os
import re

from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    Attendee, Event, EventResource, Notification, Resource, Ticket, Vendor,
    VendorAssignment, VendorRating, Venue,
)

main = Blueprint("main", __name__)
EVENT_STATUSES = ("Planning", "Scheduled", "Completed", "Cancelled")
RESOURCE_STATUSES = ("Available", "In Use", "Maintenance", "Unavailable")
ATTENDEE_STATUSES = ("Registered", "Checked In", "Absent", "Cancelled")
VENDOR_AVAILABILITY = ("Available", "Unavailable")
VENDOR_ASSIGNMENT_STATUSES = ("Assigned", "Confirmed", "Completed", "Cancelled")


def _required(form, name, label):
    value = form.get(name, "").strip()
    if not value:
        raise ValueError(f"{label} is required.")
    return value


def _integer(form, name, label, minimum=0):
    try:
        value = int(form.get(name, ""))
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if value < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")
    return value


def _event_values(form, event_id=None):
    name, kind = _required(form, "event_name", "Event name"), _required(form, "event_type", "Event type")
    try:
        event_date = datetime.strptime(_required(form, "date", "Date"), "%Y-%m-%d").date()
        start = datetime.strptime(_required(form, "start_time", "Start time"), "%H:%M").time()
        end = datetime.strptime(_required(form, "end_time", "End time"), "%H:%M").time()
        budget = float(form.get("budget", "0") or 0)
    except ValueError:
        raise ValueError("Enter a valid date, time, and budget.")
    if end <= start:
        raise ValueError("End time must be later than start time.")
    if budget < 0:
        raise ValueError("Budget cannot be negative.")
    venue_id = form.get("venue_id", "").strip()
    venue = db.session.get(Venue, int(venue_id)) if venue_id.isdigit() else None
    if venue_id and not venue:
        raise ValueError("Select a valid venue.")
    if venue and venue.capacity < _integer(form, "expected_participants", "Expected participants"):
        raise ValueError(f"{venue.venue_name} can accommodate only {venue.capacity} participants.")
    if venue:
        conflict_query = Event.query.filter(
            Event.venue_id == venue.venue_id,
            Event.date == event_date,
            Event.status != "Cancelled",
            Event.start_time < end,
            Event.end_time > start,
        )
        if event_id is not None:
            conflict_query = conflict_query.filter(Event.event_id != event_id)
        if conflict_query.first():
            raise ValueError("This venue is already booked for an overlapping event time.")
    status = form.get("status", "Planning")
    if status not in EVENT_STATUSES:
        raise ValueError("Select a valid event status.")
    return dict(event_name=name, event_type=kind, date=event_date, start_time=start, end_time=end,
                expected_participants=_integer(form, "expected_participants", "Expected participants"),
                budget=budget, venue_id=venue.venue_id if venue else None, status=status)


def _resource_values(form):
    status = form.get("status", "Available")
    if status not in RESOURCE_STATUSES:
        raise ValueError("Select a valid resource status.")
    return dict(resource_name=_required(form, "resource_name", "Resource name"),
                resource_type=_required(form, "resource_type", "Resource type"),
                quantity=_integer(form, "quantity", "Quantity"),
                location=_required(form, "location", "Location"), status=status,
                description=form.get("description", "").strip() or None)


def _attendee_values(form):
    email = _required(form, "email", "Email")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")
    event_id = form.get("event_id", "").strip()
    event = db.session.get(Event, int(event_id)) if event_id.isdigit() else None
    if event_id and not event:
        raise ValueError("Select a valid event.")
    status = form.get("status", "Registered")
    if status not in ATTENDEE_STATUSES:
        raise ValueError("Select a valid attendee status.")
    return dict(name=_required(form, "name", "Name"), email=email, phone=form.get("phone", "").strip() or None,
                organization=form.get("organization", "").strip() or None,
                event_id=event.event_id if event else None, status=status)


def _next_code(prefix, model, column):
    """Return a readable unique development identifier such as REG1001 or TKT1001."""
    number = 1001
    while db.session.query(model).filter(column == f"{prefix}{number}").first():
        number += 1
    return f"{prefix}{number}"


def _registration_values(form):
    email = _required(form, "email", "Email").lower()
    phone = _required(form, "phone", "Phone number")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    event_id = _integer(form, "event_id", "Event")
    event = db.session.get(Event, event_id)
    if not event:
        raise ValueError("Select a valid event.")
    duplicate = Attendee.query.filter(
        Attendee.event_id == event_id,
        db.or_(Attendee.email == email, Attendee.phone == phone),
    ).first()
    if duplicate:
        raise ValueError("This email address or phone number is already registered for the selected event.")
    return dict(
        registration_id=_next_code("REG", Attendee, Attendee.registration_id),
        name=_required(form, "name", "Student name"), email=email, phone=phone,
        college=_required(form, "college", "College name"),
        organization=form.get("college", "").strip(),
        department=_required(form, "department", "Department"),
        event_id=event_id, status="Registered",
    )


def _vendor_values(form):
    email = _required(form, "email", "Email").lower()
    phone = _required(form, "contact_number", "Contact number")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    availability = form.get("availability", "Available")
    if availability not in VENDOR_AVAILABILITY:
        raise ValueError("Select a valid availability status.")
    return dict(vendor_name=_required(form, "vendor_name", "Vendor name"),
                service_type=_required(form, "service_type", "Service type"),
                contact_number=phone, email=email, availability=availability)


def _generate_ticket(attendee):
    ticket_id = _next_code("TKT", Ticket, Ticket.ticket_id)
    qr_payload = f"{ticket_id}|{attendee.registration_id}|{attendee.attendee_id}"
    ticket_dir = os.path.join(current_app.static_folder, "tickets")
    os.makedirs(ticket_dir, exist_ok=True)
    import qrcode
    qrcode.make(qr_payload).save(os.path.join(ticket_dir, f"{ticket_id}.png"))
    attendee.ticket_id = ticket_id
    ticket = Ticket(ticket_id=ticket_id, event_id=attendee.event_id,
                    registration_id=attendee.registration_id, qr_code=qr_payload,
                    issue_date=date.today())
    db.session.add(ticket)
    return ticket


@main.route("/")
def dashboard():
    today = datetime.today().date()
    return render_template("dashboard.html", total_events=Event.query.count(),
        upcoming_events=Event.query.filter(Event.date >= today, Event.status.in_(("Planning", "Scheduled"))).count(),
        completed_events=Event.query.filter_by(status="Completed").count(), cancelled_events=Event.query.filter_by(status="Cancelled").count(),
        total_venues=Venue.query.count(), available_venues=Venue.query.filter_by(availability="Available").count(),
        total_resources=Resource.query.count(), available_resources=Resource.query.filter_by(status="Available").count(),
        total_attendees=Attendee.query.count(), total_budget=db.session.query(db.func.sum(Event.budget)).scalar() or 0,
        upcoming_event_list=Event.query.filter(Event.date >= today, Event.status.in_(("Planning", "Scheduled"))).order_by(Event.date, Event.start_time).limit(5).all(),
        recent_events=Event.query.order_by(Event.event_id.desc()).limit(5).all())


@main.route("/events")
def events():
    search, status = request.args.get("search", "").strip(), request.args.get("status", "").strip()
    query = Event.query
    if search: query = query.filter(db.or_(Event.event_name.ilike(f"%{search}%"), Event.event_type.ilike(f"%{search}%")))
    if status in EVENT_STATUSES: query = query.filter_by(status=status)
    return render_template("events/list.html", events=query.order_by(Event.date, Event.start_time).all(), search=search, selected_status=status, event_statuses=EVENT_STATUSES)


@main.route("/events/create", methods=["GET", "POST"])
def create_event():
    if request.method == "POST":
        try:
            db.session.add(Event(**_event_values(request.form))); db.session.commit()
            flash("Event created successfully!", "success"); return redirect(url_for("main.events"))
        except (ValueError, IntegrityError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("events/create.html", venues=Venue.query.order_by(Venue.venue_name).all(), event_statuses=EVENT_STATUSES)


@main.route("/events/<int:event_id>")
def event_detail(event_id):
    event = db.get_or_404(Event, event_id)
    return render_template("events/detail.html", event=event,
        resources=Resource.query.order_by(Resource.resource_name).all())


@main.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
def edit_event(event_id):
    event = db.get_or_404(Event, event_id)
    if request.method == "POST":
        try:
            for key, value in _event_values(request.form, event_id).items(): setattr(event, key, value)
            db.session.commit(); flash("Event updated successfully!", "success"); return redirect(url_for("main.event_detail", event_id=event_id))
        except (ValueError, IntegrityError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("events/edit.html", event=event, venues=Venue.query.order_by(Venue.venue_name).all(), event_statuses=EVENT_STATUSES)


@main.route("/events/<int:event_id>/delete", methods=["POST"])
def delete_event(event_id):
    db.session.delete(db.get_or_404(Event, event_id)); db.session.commit(); flash("Event deleted successfully!", "success")
    return redirect(url_for("main.events"))


@main.route("/venues")
def venues():
    search = request.args.get("search", "").strip(); query = Venue.query
    if search: query = query.filter(db.or_(Venue.venue_name.ilike(f"%{search}%"), Venue.location.ilike(f"%{search}%")))
    return render_template("venues/list.html", venues=query.order_by(Venue.venue_name).all(), search=search)


@main.route("/venues/create", methods=["GET", "POST"])
def create_venue():
    if request.method == "POST":
        try:
            availability = request.form.get("availability", "Available")
            if availability not in ("Available", "Unavailable"): raise ValueError("Select a valid availability.")
            db.session.add(Venue(venue_name=_required(request.form, "venue_name", "Venue name"), capacity=_integer(request.form, "capacity", "Capacity", 1), location=_required(request.form, "location", "Location"), availability=availability)); db.session.commit()
            flash("Venue created successfully!", "success"); return redirect(url_for("main.venues"))
        except (ValueError, IntegrityError) as error: db.session.rollback(); flash("Venue name must be unique." if isinstance(error, IntegrityError) else str(error), "danger")
    return render_template("venues/create.html")


@main.route("/venues/<int:venue_id>")
def venue_detail(venue_id): return render_template("venues/detail.html", venue=db.get_or_404(Venue, venue_id))


@main.route("/venues/<int:venue_id>/edit", methods=["GET", "POST"])
def edit_venue(venue_id):
    venue = db.get_or_404(Venue, venue_id)
    if request.method == "POST":
        try:
            availability = request.form.get("availability", "Available")
            if availability not in ("Available", "Unavailable"): raise ValueError("Select a valid availability.")
            venue.venue_name, venue.capacity, venue.location, venue.availability = _required(request.form, "venue_name", "Venue name"), _integer(request.form, "capacity", "Capacity", 1), _required(request.form, "location", "Location"), availability
            db.session.commit(); flash("Venue updated successfully!", "success"); return redirect(url_for("main.venue_detail", venue_id=venue_id))
        except (ValueError, IntegrityError) as error: db.session.rollback(); flash("Venue name must be unique." if isinstance(error, IntegrityError) else str(error), "danger")
    return render_template("venues/edit.html", venue=venue)


@main.route("/venues/<int:venue_id>/delete", methods=["POST"])
def delete_venue(venue_id):
    venue = db.get_or_404(Venue, venue_id)
    if venue.events: flash("This venue cannot be deleted while events are assigned to it.", "danger")
    else: db.session.delete(venue); db.session.commit(); flash("Venue deleted successfully!", "success")
    return redirect(url_for("main.venues"))


@main.route("/resources")
def resources():
    search, status = request.args.get("search", "").strip(), request.args.get("status", "").strip(); query = Resource.query
    if search: query = query.filter(db.or_(Resource.resource_name.ilike(f"%{search}%"), Resource.resource_type.ilike(f"%{search}%"), Resource.location.ilike(f"%{search}%")))
    if status in RESOURCE_STATUSES: query = query.filter_by(status=status)
    return render_template("resources/list.html", resources=query.order_by(Resource.resource_name).all(), search=search, selected_status=status, resource_statuses=RESOURCE_STATUSES)


@main.route("/resources/create", methods=["GET", "POST"])
def create_resource():
    if request.method == "POST":
        try: db.session.add(Resource(**_resource_values(request.form))); db.session.commit(); flash("Resource created successfully!", "success"); return redirect(url_for("main.resources"))
        except ValueError as error: db.session.rollback(); flash(str(error), "danger")
    return render_template("resources/create.html", resource_statuses=RESOURCE_STATUSES)


@main.route("/resources/<int:resource_id>")
def resource_detail(resource_id): return render_template("resources/detail.html", resource=db.get_or_404(Resource, resource_id))


@main.route("/resources/<int:resource_id>/edit", methods=["GET", "POST"])
def edit_resource(resource_id):
    resource = db.get_or_404(Resource, resource_id)
    if request.method == "POST":
        try:
            for key, value in _resource_values(request.form).items(): setattr(resource, key, value)
            db.session.commit(); flash("Resource updated successfully!", "success"); return redirect(url_for("main.resource_detail", resource_id=resource_id))
        except ValueError as error: db.session.rollback(); flash(str(error), "danger")
    return render_template("resources/edit.html", resource=resource, resource_statuses=RESOURCE_STATUSES)


@main.route("/resources/<int:resource_id>/delete", methods=["POST"])
def delete_resource(resource_id): db.session.delete(db.get_or_404(Resource, resource_id)); db.session.commit(); flash("Resource deleted successfully!", "success"); return redirect(url_for("main.resources"))


def _overlapping_resource_quantity(resource_id, event, exclude_assignment_id=None):
    query = db.session.query(db.func.coalesce(db.func.sum(EventResource.quantity), 0)).join(Event).filter(
        EventResource.resource_id == resource_id,
        Event.date == event.date,
        Event.status != "Cancelled",
        Event.start_time < event.end_time,
        Event.end_time > event.start_time,
    )
    if exclude_assignment_id is not None:
        query = query.filter(EventResource.assignment_id != exclude_assignment_id)
    return query.scalar() or 0


@main.route("/events/<int:event_id>/resources/add", methods=["POST"])
def assign_resource(event_id):
    event = db.get_or_404(Event, event_id)
    try:
        resource_id = _integer(request.form, "resource_id", "Resource")
        quantity = _integer(request.form, "quantity", "Quantity", 1)
        resource = db.session.get(Resource, resource_id)
        if not resource:
            raise ValueError("Select a valid resource.")
        if resource.status != "Available":
            raise ValueError(f"{resource.resource_name} is currently marked {resource.status}.")
        assignment = EventResource.query.filter_by(event_id=event.event_id, resource_id=resource_id).first()
        requested_total = quantity + (assignment.quantity if assignment else 0)
        already_reserved = _overlapping_resource_quantity(resource_id, event, assignment.assignment_id if assignment else None)
        if already_reserved + requested_total > resource.quantity:
            raise ValueError(f"Only {max(resource.quantity - already_reserved, 0)} {resource.resource_name} item(s) are available at this time.")
        if assignment:
            assignment.quantity = requested_total
        else:
            db.session.add(EventResource(event=event, resource=resource, quantity=quantity))
        db.session.commit(); flash("Resource allocated to the event.", "success")
    except ValueError as error:
        db.session.rollback(); flash(str(error), "danger")
    return redirect(url_for("main.event_detail", event_id=event_id))


@main.route("/events/<int:event_id>/resources/<int:assignment_id>/delete", methods=["POST"])
def remove_resource_assignment(event_id, assignment_id):
    assignment = db.get_or_404(EventResource, assignment_id)
    if assignment.event_id != event_id:
        flash("Resource allocation not found for this event.", "danger")
    else:
        db.session.delete(assignment); db.session.commit(); flash("Resource allocation removed.", "success")
    return redirect(url_for("main.event_detail", event_id=event_id))


@main.route("/attendees")
def attendees():
    search = request.args.get("search", "").strip(); query = Attendee.query
    if search: query = query.filter(db.or_(Attendee.name.ilike(f"%{search}%"), Attendee.email.ilike(f"%{search}%"), Attendee.organization.ilike(f"%{search}%")))
    return render_template("attendees/list.html", attendees=query.order_by(Attendee.name).all(), search=search)


@main.route("/attendees/create", methods=["GET", "POST"])
def create_attendee():
    if request.method == "POST":
        try: db.session.add(Attendee(**_attendee_values(request.form))); db.session.commit(); flash("Attendee created successfully!", "success"); return redirect(url_for("main.attendees"))
        except ValueError as error: db.session.rollback(); flash(str(error), "danger")
    return render_template("attendees/create.html", events=Event.query.order_by(Event.date).all(), attendee_statuses=ATTENDEE_STATUSES)


@main.route("/attendees/<int:attendee_id>")
def attendee_detail(attendee_id): return render_template("attendees/detail.html", attendee=db.get_or_404(Attendee, attendee_id))


@main.route("/attendees/<int:attendee_id>/edit", methods=["GET", "POST"])
def edit_attendee(attendee_id):
    attendee = db.get_or_404(Attendee, attendee_id)
    if request.method == "POST":
        try:
            for key, value in _attendee_values(request.form).items(): setattr(attendee, key, value)
            db.session.commit(); flash("Attendee updated successfully!", "success"); return redirect(url_for("main.attendee_detail", attendee_id=attendee_id))
        except ValueError as error: db.session.rollback(); flash(str(error), "danger")
    return render_template("attendees/edit.html", attendee=attendee, events=Event.query.order_by(Event.date).all(), attendee_statuses=ATTENDEE_STATUSES)


@main.route("/attendees/<int:attendee_id>/delete", methods=["POST"])
def delete_attendee(attendee_id): db.session.delete(db.get_or_404(Attendee, attendee_id)); db.session.commit(); flash("Attendee deleted successfully!", "success"); return redirect(url_for("main.attendees"))


@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            attendee = Attendee(**_registration_values(request.form))
            db.session.add(attendee)
            db.session.flush()
            ticket = _generate_ticket(attendee)
            db.session.add(Notification(
                event_id=attendee.event_id,
                title="Registration Confirmation",
                message=f"{attendee.name} has been registered and issued ticket {ticket.ticket_id}.",
                audience="Participants",
            ))
            db.session.commit()
            flash("Registration confirmed. Your digital ticket is ready!", "success")
            return redirect(url_for("main.ticket_detail", ticket_id=ticket.ticket_id))
        except (ValueError, IntegrityError) as error:
            db.session.rollback()
            flash("Registration could not be completed. Please check your details." if isinstance(error, IntegrityError) else str(error), "danger")
    selected_event_id = request.args.get("event_id", type=int)
    return render_template("registration/create.html", events=Event.query.filter(Event.status != "Cancelled").order_by(Event.date).all(),
                           selected_event_id=selected_event_id,
                           next_registration_id=_next_code("REG", Attendee, Attendee.registration_id))


@main.route("/tickets/<ticket_id>")
def ticket_detail(ticket_id):
    ticket = db.get_or_404(Ticket, ticket_id)
    return render_template("tickets/detail.html", ticket=ticket, attendee=ticket.attendee, event=ticket.event)


@main.route("/tickets/<ticket_id>/download")
def download_ticket(ticket_id):
    ticket = db.get_or_404(Ticket, ticket_id)
    html = render_template("tickets/download.html", ticket=ticket, attendee=ticket.attendee, event=ticket.event)
    response = make_response(html)
    response.headers["Content-Disposition"] = f'attachment; filename="{ticket.ticket_id}.html"'
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


@main.route("/check-in", methods=["GET", "POST"])
def check_in():
    result = None
    if request.method == "POST":
        value = request.form.get("ticket_value", "").strip()
        ticket_id = value.split("|")[0] if "|" in value else value.upper()
        ticket = db.session.get(Ticket, ticket_id)
        if not ticket:
            flash("Ticket could not be verified.", "danger")
        elif ticket.attendee.status == "Checked In":
            flash("This ticket has already been checked in and cannot be reused.", "danger")
            result = ticket
        elif ticket.attendee.status in ("Cancelled", "Absent"):
            flash(f"This attendee is marked {ticket.attendee.status.lower()} and cannot be checked in.", "danger")
            result = ticket
        else:
            ticket.attendee.status = "Checked In"
            db.session.commit()
            flash(f"Welcome {ticket.attendee.name}! Check-in completed.", "success")
            result = ticket
    return render_template("checkin/index.html", result=result)


@main.route("/events/<int:event_id>/attendance")
def attendance_report(event_id):
    event = db.get_or_404(Event, event_id)
    return render_template("attendance/list.html", event=event,
                           attendees=Attendee.query.filter_by(event_id=event_id).order_by(Attendee.name).all(),
                           attendee_statuses=ATTENDEE_STATUSES)


@main.route("/attendees/<int:attendee_id>/attendance", methods=["POST"])
def update_attendance(attendee_id):
    attendee = db.get_or_404(Attendee, attendee_id)
    status = request.form.get("status", "")
    if status in ATTENDEE_STATUSES:
        attendee.status = status
        db.session.commit()
        flash("Attendance status updated.", "success")
    else:
        flash("Select a valid attendance status.", "danger")
    return redirect(url_for("main.attendance_report", event_id=attendee.event_id))


@main.route("/vendors")
def vendors():
    return render_template("vendors/list.html", vendors=Vendor.query.order_by(Vendor.vendor_name).all())


@main.route("/vendors/onboard", methods=["GET", "POST"])
def onboard_vendor():
    if request.method == "POST":
        try:
            if request.form.get("verified") != "yes":
                raise ValueError("Confirm that the vendor details have been verified before onboarding.")
            db.session.add(Vendor(**_vendor_values(request.form)))
            db.session.commit()
            flash("Verified vendor onboarded successfully.", "success")
            return redirect(url_for("main.vendors"))
        except (ValueError, IntegrityError) as error:
            db.session.rollback()
            flash(str(error), "danger")
    return render_template("vendors/onboard.html", availability_options=VENDOR_AVAILABILITY)


@main.route("/vendors/<int:vendor_id>")
def vendor_detail(vendor_id):
    return render_template("vendors/detail.html", vendor=db.get_or_404(Vendor, vendor_id))


@main.route("/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
def edit_vendor(vendor_id):
    vendor = db.get_or_404(Vendor, vendor_id)
    if request.method == "POST":
        try:
            for key, value in _vendor_values(request.form).items():
                setattr(vendor, key, value)
            db.session.commit()
            flash("Vendor updated successfully.", "success")
            return redirect(url_for("main.vendor_detail", vendor_id=vendor_id))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
    return render_template("vendors/edit.html", vendor=vendor, availability_options=VENDOR_AVAILABILITY)


@main.route("/vendors/<int:vendor_id>/delete", methods=["POST"])
def delete_vendor(vendor_id):
    vendor = db.get_or_404(Vendor, vendor_id)
    if vendor.assignments:
        flash("This vendor cannot be deleted while event assignments exist.", "danger")
    else:
        db.session.delete(vendor)
        db.session.commit()
        flash("Vendor deleted successfully.", "success")
    return redirect(url_for("main.vendors"))


@main.route("/events/<int:event_id>/vendors", methods=["GET", "POST"])
def vendor_assignments(event_id):
    event = db.get_or_404(Event, event_id)
    if request.method == "POST":
        try:
            vendor = db.session.get(Vendor, _integer(request.form, "vendor_id", "Vendor"))
            if not vendor:
                raise ValueError("Select a valid vendor.")
            if vendor.availability != "Available":
                raise ValueError(f"{vendor.vendor_name} is currently unavailable.")
            db.session.add(VendorAssignment(event=event, vendor=vendor,
                           service=_required(request.form, "service", "Service"), status="Assigned"))
            db.session.commit()
            flash("Vendor assigned to the event.", "success")
        except (ValueError, IntegrityError) as error:
            db.session.rollback()
            flash(str(error), "danger")
    return render_template("vendors/assignments.html", event=event,
                           vendors=Vendor.query.filter_by(availability="Available").order_by(Vendor.vendor_name).all(),
                           assignment_statuses=VENDOR_ASSIGNMENT_STATUSES)


@main.route("/vendor-assignments/<int:assignment_id>/status", methods=["POST"])
def update_vendor_assignment(assignment_id):
    assignment = db.get_or_404(VendorAssignment, assignment_id)
    status = request.form.get("status", "")
    if status in VENDOR_ASSIGNMENT_STATUSES:
        assignment.status = status
        db.session.commit()
        flash("Vendor assignment status updated.", "success")
    return redirect(url_for("main.vendor_assignments", event_id=assignment.event_id))


@main.route("/vendor-assignments/<int:assignment_id>/rate", methods=["POST"])
def rate_vendor(assignment_id):
    assignment = db.get_or_404(VendorAssignment, assignment_id)
    try:
        values = {field: _integer(request.form, field, field.replace("_", " ").title(), 1) for field in ("quality", "timeliness", "cost", "communication")}
        if any(value > 5 for value in values.values()):
            raise ValueError("Ratings must be between 1 and 5 stars.")
        rating = assignment.rating or VendorRating(assignment=assignment, vendor=assignment.vendor, **values)
        if assignment.rating:
            for key, value in values.items(): setattr(rating, key, value)
        rating.overall_rating = round(sum(values.values()) / len(values), 1)
        db.session.add(rating)
        db.session.commit()
        flash("Vendor performance rating saved.", "success")
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "danger")
    return redirect(url_for("main.vendor_assignments", event_id=assignment.event_id))


@main.route("/notifications", methods=["GET", "POST"])
def notifications():
    if request.method == "POST":
        try:
            event_id = request.form.get("event_id", "").strip()
            if event_id and not db.session.get(Event, int(event_id)):
                raise ValueError("Select a valid event.")
            audience = request.form.get("audience", "")
            if audience not in ("Participants", "Vendors", "Everyone"):
                raise ValueError("Select who should receive the notification.")
            db.session.add(Notification(event_id=int(event_id) if event_id else None,
                           title=_required(request.form, "title", "Title"),
                           message=_required(request.form, "message", "Message"), audience=audience))
            db.session.commit()
            flash("Notification published to the selected audience.", "success")
            return redirect(url_for("main.notifications"))
        except (ValueError, IntegrityError) as error:
            db.session.rollback()
            flash(str(error), "danger")
    return render_template("notifications/index.html", notifications=Notification.query.order_by(Notification.created_at.desc()).all(),
                           events=Event.query.order_by(Event.date.desc()).all())


@main.route("/reports")
def reports():
    return render_template("reports/index.html", total_events=Event.query.count(), total_venues=Venue.query.count(), total_resources=Resource.query.count(), total_attendees=Attendee.query.count(), total_budget=db.session.query(db.func.sum(Event.budget)).scalar() or 0,
        event_breakdown={status: Event.query.filter_by(status=status).count() for status in EVENT_STATUSES}, venue_breakdown={status: Venue.query.filter_by(availability=status).count() for status in ("Available", "Unavailable")}, resource_breakdown={status: Resource.query.filter_by(status=status).count() for status in RESOURCE_STATUSES}, attendee_breakdown={status: Attendee.query.filter_by(status=status).count() for status in ATTENDEE_STATUSES},
        allocated_resources=db.session.query(db.func.coalesce(db.func.sum(EventResource.quantity), 0)).scalar() or 0,
        allocated_resource_types=db.session.query(EventResource.resource_id).distinct().count())
