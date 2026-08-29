# EventSphere Architecture

EventSphere is a Flask application using server-rendered Jinja templates, SQLAlchemy models, and SQLite for local development.

## Layers

- **Frontend:** Responsive Jinja templates in `app/templates` and shared CSS/JavaScript under `app/static`.
- **Feature routes:** Existing Milestone 1/2 routes remain in `app/routes.py`. Additive feedback features are in `app/milestone3_routes.py`; finance, automation, analytics, optimization and REST APIs are in `app/operations_routes.py`.
- **Data:** Existing models live in `app/models.py`. New functionality uses only new tables declared in `milestone3_models.py` and `operations_models.py`.
- **Automation:** Reminders, approval decisions, and operational actions are persisted in their dedicated tables and `automation_logs`.

## Safety boundary

The original Milestone 1/2 model fields and business routes are retained. Operations modules refer to existing event, attendee, vendor, and resource identifiers with new foreign keys only.
