from app import db


class Venue(db.Model):
    __tablename__ = "venues"

    venue_id = db.Column(db.Integer, primary_key=True)
    venue_name = db.Column(db.String(100), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    availability = db.Column(db.String(30), nullable=False, default="Available")

    events = db.relationship("Event", back_populates="venue", lazy=True)

    def __repr__(self):
        return f"<Venue {self.venue_name}>"


class Event(db.Model):
    __tablename__ = "events"

    event_id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(150), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    expected_participants = db.Column(db.Integer, nullable=False)
    budget = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="Planning")
    venue_id = db.Column(db.Integer, db.ForeignKey("venues.venue_id"), nullable=True)

    venue = db.relationship("Venue", back_populates="events")
    attendees = db.relationship(
        "Attendee", back_populates="event", cascade="all, delete-orphan", lazy=True
    )
    resource_assignments = db.relationship(
        "EventResource", back_populates="event", cascade="all, delete-orphan", lazy=True
    )
    vendor_assignments = db.relationship(
        "VendorAssignment", back_populates="event", cascade="all, delete-orphan", lazy=True
    )
    tickets = db.relationship("Ticket", back_populates="event", cascade="all, delete-orphan", lazy=True)
    notifications = db.relationship("Notification", back_populates="event", cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f"<Event {self.event_name}>"


class Resource(db.Model):
    __tablename__ = "resources"

    resource_id = db.Column(db.Integer, primary_key=True)
    resource_name = db.Column(db.String(150), nullable=False)
    resource_type = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    location = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Available")
    description = db.Column(db.Text, nullable=True)
    assignments = db.relationship(
        "EventResource", back_populates="resource", cascade="all, delete-orphan", lazy=True
    )

    def __repr__(self):
        return f"<Resource {self.resource_name}>"


class EventResource(db.Model):
    __tablename__ = "event_resources"

    assignment_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.resource_id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    event = db.relationship("Event", back_populates="resource_assignments")
    resource = db.relationship("Resource", back_populates="assignments")


class Attendee(db.Model):
    __tablename__ = "attendees"

    attendee_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    organization = db.Column(db.String(150), nullable=True)
    registration_id = db.Column(db.String(30), unique=True, nullable=True)
    college = db.Column(db.String(150), nullable=True)
    department = db.Column(db.String(150), nullable=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Registered")
    ticket_id = db.Column(db.String(30), unique=True, nullable=True)

    event = db.relationship("Event", back_populates="attendees")
    ticket = db.relationship("Ticket", back_populates="attendee", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Attendee {self.name}>"


class Ticket(db.Model):
    __tablename__ = "tickets"

    ticket_id = db.Column(db.String(30), primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    registration_id = db.Column(db.String(30), db.ForeignKey("attendees.registration_id"), unique=True, nullable=False)
    qr_code = db.Column(db.String(300), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)

    event = db.relationship("Event", back_populates="tickets")
    attendee = db.relationship("Attendee", back_populates="ticket", foreign_keys=[registration_id])


class Vendor(db.Model):
    __tablename__ = "vendors"

    vendor_id = db.Column(db.Integer, primary_key=True)
    vendor_name = db.Column(db.String(150), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    contact_number = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    availability = db.Column(db.String(30), nullable=False, default="Available")

    assignments = db.relationship("VendorAssignment", back_populates="vendor", cascade="all, delete-orphan", lazy=True)
    ratings = db.relationship("VendorRating", back_populates="vendor", cascade="all, delete-orphan", lazy=True)


class VendorAssignment(db.Model):
    __tablename__ = "vendor_assignments"

    assignment_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.vendor_id"), nullable=False)
    service = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Assigned")

    event = db.relationship("Event", back_populates="vendor_assignments")
    vendor = db.relationship("Vendor", back_populates="assignments")
    rating = db.relationship("VendorRating", back_populates="assignment", uselist=False, cascade="all, delete-orphan")


class VendorRating(db.Model):
    __tablename__ = "vendor_ratings"

    rating_id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("vendor_assignments.assignment_id"), unique=True, nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.vendor_id"), nullable=False)
    quality = db.Column(db.Integer, nullable=False)
    timeliness = db.Column(db.Integer, nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    communication = db.Column(db.Integer, nullable=False)
    overall_rating = db.Column(db.Float, nullable=False)

    assignment = db.relationship("VendorAssignment", back_populates="rating")
    vendor = db.relationship("Vendor", back_populates="ratings")


class Notification(db.Model):
    __tablename__ = "notifications"

    notification_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    audience = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    event = db.relationship("Event", back_populates="notifications")
