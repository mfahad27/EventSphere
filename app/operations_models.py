"""Additive Milestone 3/4 finance, automation and analytics data models."""

from app import db


class EventBudget(db.Model):
    __tablename__ = "event_budgets"

    budget_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False, unique=True)
    planned_amount = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())


class Expense(db.Model):
    __tablename__ = "expenses"

    expense_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(250), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())


class Sponsorship(db.Model):
    __tablename__ = "sponsorships"

    sponsorship_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    sponsor_name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pledged")
    received_date = db.Column(db.Date, nullable=True)


class ApprovalRequest(db.Model):
    __tablename__ = "approval_requests"

    approval_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    request_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    amount = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    reviewed_at = db.Column(db.DateTime, nullable=True)


class EventReminder(db.Model):
    __tablename__ = "event_reminders"

    reminder_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=False)
    audience = db.Column(db.String(30), nullable=False)
    message = db.Column(db.Text, nullable=False)
    scheduled_for = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Scheduled")
    sent_at = db.Column(db.DateTime, nullable=True)


class AutomationLog(db.Model):
    __tablename__ = "automation_logs"

    automation_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.event_id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Completed")
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
