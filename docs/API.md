# EventSphere API Reference

All API responses are JSON. Read APIs return a top-level `data` property.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/v1/events` | GET | List events |
| `/api/v1/events/<id>` | GET | Get an event |
| `/api/v1/attendees` | GET | List attendee registrations and status |
| `/api/v1/resources` | GET | List resources |
| `/api/v1/vendors` | GET | List vendors |
| `/api/v1/events/<id>/budget` | GET | Get planned/spent/remaining finance summary |
| `/api/v1/expenses` | POST | Submit an expense for approval |
| `/api/v1/sponsorships` | POST | Record a sponsorship |

## Expense request example

```json
{"event_id": 1, "category": "Catering", "description": "Lunch service", "amount": 25000, "expense_date": "2026-09-12"}
```

Successful create responses use `201`; malformed requests return `400`; missing records return `404`.
