"""Full app startup smoke checks against disposable CI PostgreSQL and Redis."""
import os
import unittest

from fastapi.testclient import TestClient

if os.getenv("RUN_SERVICE_INTEGRATION_TESTS") != "1":
    raise unittest.SkipTest("Requires disposable PostgreSQL and Redis CI services")

from auction_app.main import auction_app  # noqa: E402
from auction_app.admin.setup import setup_admin  # noqa: E402
from fastapi import FastAPI  # noqa: E402


class FullApplicationStartupTests(unittest.TestCase):
    def test_startup_openapi_and_admin_not_exposed(self):
        with TestClient(auction_app) as client:
            response = client.get("/openapi.json")
            self.assertEqual(response.status_code, 200, response.text)
            endpoints = response.json()["paths"]
            self.assertIn("/auth/register/", endpoints)
            self.assertIn("/auth/login", endpoints)
            # SQLAdmin was previously mounted without authentication.
            self.assertEqual(client.get("/admin").status_code, 404)

    def test_unprotected_admin_cannot_be_enabled(self):
        original = os.environ.get("ENABLE_SQLADMIN")
        try:
            os.environ["ENABLE_SQLADMIN"] = "true"
            with self.assertRaisesRegex(RuntimeError, "authenticated admin"):
                setup_admin(FastAPI())
        finally:
            if original is None:
                os.environ.pop("ENABLE_SQLADMIN", None)
            else:
                os.environ["ENABLE_SQLADMIN"] = original


if __name__ == "__main__":
    unittest.main()
