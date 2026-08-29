"""Integration checks spanning the original system and Milestone 3/4 modules."""
import unittest

from app import create_app


class EventSphereIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_core_and_operations_pages_load(self):
        paths = ["/", "/events", "/register", "/check-in", "/vendors", "/reports",
                 "/operations/", "/operations/analytics", "/operations/optimization",
                 "/operations/approvals", "/operations/reminders", "/operations/events/1/finance",
                 "/milestone-3/admin", "/milestone-3/participant-access"]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_read_apis_return_json(self):
        for path in ["/api/v1/events", "/api/v1/events/1", "/api/v1/attendees", "/api/v1/resources", "/api/v1/vendors", "/api/v1/events/1/budget"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("data", response.get_json())

    def test_api_rejects_invalid_finance_payload(self):
        response = self.client.post("/api/v1/expenses", json={"event_id": 1, "category": "Invalid"})
        self.assertEqual(response.status_code, 400)

    def test_reports_are_downloadable(self):
        self.assertEqual(self.client.get("/operations/reports/1/csv").status_code, 200)
        response = self.client.get("/operations/reports/1/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
