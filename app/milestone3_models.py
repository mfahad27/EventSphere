"""Additive database models for EventSphere Milestone 3.

These models deliberately have no relationships declared on Milestone 1/2 models,
so the existing model definitions and tables remain unchanged.
"""

from app import db


class Feedback(db.Model):
    __tablename__ = "feedback"

    feedback_id = db.Column(db.String(30), primary_key=True)
    registration_id = db.Column(db.String(30), db.ForeignKey("attendees.registration_id"), nullable=False, unique=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comments = db.Column(db.Text, nullable=True)
    sentiment = db.Column(db.String(10), nullable=False, default="Neutral")
    submitted_date = db.Column(db.DateTime, nullable=False, default=db.func.now())


class Certificate(db.Model):
    __tablename__ = "certificates"

    certificate_id = db.Column(db.String(30), primary_key=True)
    registration_id = db.Column(db.String(30), db.ForeignKey("attendees.registration_id"), nullable=False, unique=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)


class AttendeeInterest(db.Model):
    __tablename__ = "attendee_interests"

    interest_id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.String(30), db.ForeignKey("attendees.registration_id"), nullable=False, unique=True)
    interest_tags = db.Column(db.String(500), nullable=False)
    share_contact = db.Column(db.Boolean, nullable=False, default=False)


class Connection(db.Model):
    __tablename__ = "connections"

    connection_id = db.Column(db.Integer, primary_key=True)
    requester_registration_id = db.Column(db.String(30), db.ForeignKey("attendees.registration_id"), nullable=False)
    recipient_registration_id = db.Column(db.String(30), db.ForeignKey("attendees.registration_id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("requester_registration_id", "recipient_registration_id", "event_id", name="uq_connection_direction"),
    )
