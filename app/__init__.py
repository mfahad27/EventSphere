import os
import shutil
from datetime import date, time

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect

db = SQLAlchemy()

EXPECTED_SCHEMA = {
    "venues": {"venue_id", "venue_name", "capacity", "location", "availability"},
    "events": {"event_id", "event_name", "event_type", "date", "start_time", "end_time", "expected_participants", "budget", "status", "venue_id"},
    "resources": {"resource_id", "resource_name", "resource_type", "quantity", "location", "status", "description"},
    "attendees": {"attendee_id", "name", "email", "phone", "organization", "registration_id", "college", "department", "event_id", "status", "ticket_id"},
    "tickets": {"ticket_id", "event_id", "registration_id", "qr_code", "issue_date"},
    "vendors": {"vendor_id", "vendor_name", "service_type", "contact_number", "email", "availability"},
    "vendor_assignments": {"assignment_id", "event_id", "vendor_id", "service", "status"},
    "vendor_ratings": {"rating_id", "assignment_id", "vendor_id", "quality", "timeliness", "cost", "communication", "overall_rating"},
    "notifications": {"notification_id", "event_id", "title", "message", "audience", "created_at"},
}


def _schema_is_current():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    return all(table in tables and set(column["name"] for column in inspector.get_columns(table)) == columns
               for table, columns in EXPECTED_SCHEMA.items())


def _seed_development_data():
    from app.models import Attendee, Event, Resource, Vendor, Venue
    if Venue.query.count() or Event.query.count() or Resource.query.count() or Attendee.query.count():
        return
    venues = [
        Venue(venue_name="Grand Ballroom", capacity=350, location="Central Avenue", availability="Available"),
        Venue(venue_name="Riverside Hall", capacity=180, location="Riverside District", availability="Available"),
        Venue(venue_name="Innovation Studio", capacity=75, location="Tech Park", availability="Unavailable"),
    ]
    resources = [
        Resource(resource_name="Wireless Microphone", resource_type="Audio", quantity=12, location="Equipment Room A", status="Available", description="Handheld wireless microphones"),
        Resource(resource_name="Projector", resource_type="Visual", quantity=4, location="Equipment Room B", status="In Use", description="Full HD presentation projector"),
        Resource(resource_name="Banquet Chairs", resource_type="Furniture", quantity=250, location="Storage Hall", status="Available", description="Stackable banquet chairs"),
        Resource(resource_name="Registration Tablets", resource_type="Technology", quantity=6, location="IT Cabinet", status="Maintenance", description="Tablets for attendee check-in"),
    ]
    db.session.add_all(venues + resources)
    db.session.flush()
    events = [
        Event(event_name="Leadership Summit", event_type="Conference", date=date(2026, 9, 12), start_time=time(9), end_time=time(17), expected_participants=220, budget=185000, status="Scheduled", venue=venues[0]),
        Event(event_name="Design Workshop", event_type="Workshop", date=date(2026, 9, 20), start_time=time(10), end_time=time(15), expected_participants=45, budget=28000, status="Planning", venue=venues[2]),
        Event(event_name="Partner Dinner", event_type="Networking", date=date(2026, 7, 18), start_time=time(19), end_time=time(22), expected_participants=80, budget=65000, status="Completed", venue=venues[1]),
    ]
    db.session.add_all(events)
    db.session.flush()
    db.session.add_all([
        Attendee(name="Aarav Sharma", email="aarav@example.com", phone="9876543210", organization="Northstar Labs", college="Northstar Labs", department="Computer Science", event=events[0], status="Registered"),
        Attendee(name="Maya Iyer", email="maya@example.com", organization="Studio Nine", event=events[1], status="Registered"),
        Attendee(name="Kabir Khan", email="kabir@example.com", phone="9123456789", organization="Horizon Co.", event=events[0], status="Checked In"),
    ])
    db.session.add_all([
        Vendor(vendor_name="Lens & Light Studio", service_type="Photography", contact_number="9876501234", email="hello@lenslight.example", availability="Available"),
        Vendor(vendor_name="Flavour Street Catering", service_type="Catering", contact_number="9876505678", email="team@flavourstreet.example", availability="Available"),
    ])
    db.session.commit()


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.update(SECRET_KEY="eventsphere-development-key", SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(app.instance_path, "eventsphere.db"), SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    from app import models  # Ensure metadata is populated before initialization.
    from app import milestone3_models  # Additive Milestone 3 tables.
    from app import operations_models  # Additive finance and automation tables.
    with app.app_context():
        database_path = os.path.join(app.instance_path, "eventsphere.db")
        if os.path.exists(database_path) and not _schema_is_current():
            backup_path = database_path + ".pre_milestone1_backup"
            if not os.path.exists(backup_path):
                shutil.copy2(database_path, backup_path)
            db.session.remove()
            db.engine.dispose()
            os.remove(database_path)
        db.create_all()
        _seed_development_data()
    from app.routes import main
    from app.milestone3_routes import milestone3
    from app.operations_routes import operations, api
    app.register_blueprint(main)
    app.register_blueprint(milestone3)
    app.register_blueprint(operations)
    app.register_blueprint(api)
    return app
