"""Full app startup smoke checks against disposable CI PostgreSQL and Redis."""
import os
import unittest

from fastapi.testclient import TestClient
from unittest.mock import patch
from passlib.hash import pbkdf2_sha256

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

    def test_admin_opt_in_rejects_missing_credentials(self):
        with patch.dict(os.environ, {"ENABLE_SQLADMIN": "true"}, clear=False):
            os.environ.pop("ADMIN_USERNAME", None)
            os.environ.pop("ADMIN_PASSWORD_HASH", None)
            with self.assertRaisesRegex(RuntimeError, "ADMIN_USERNAME"):
                setup_admin(FastAPI())

    def test_admin_login_protected_by_hashed_credentials(self):
        from starlette.middleware.sessions import SessionMiddleware
        from auction_app.db.database import engine
        test_env = {
            "ENABLE_SQLADMIN": "true",
            "ADMIN_USERNAME": "ci-admin",
            "ADMIN_PASSWORD_HASH": pbkdf2_sha256.hash("ci-only-password-123"),
            "SESSION_SECRET_KEY": "test-only-session-key-never-use-in-production-123456",
        }
        with patch.dict(os.environ, test_env):
            app = FastAPI()
            app.add_middleware(
                SessionMiddleware,
                secret_key=test_env["SESSION_SECRET_KEY"],
            )
            admin = setup_admin(app)
            self.assertIsNotNone(admin)
            with TestClient(app, follow_redirects=False) as client:
                guest = client.get("/admin/")
                self.assertIn(guest.status_code, (302, 307))
                self.assertIn("login", guest.headers.get("location", ""))

                bad = client.post(
                    "/admin/login",
                    data={"username": "ci-admin", "password": "wrong"},
                )
                self.assertEqual(bad.status_code, 400, bad.text)

                valid = client.post(
                    "/admin/login",
                    data={"username": "ci-admin", "password": "ci-only-password-123"},
                )
                self.assertIn(valid.status_code, (302, 303), valid.text)
                authorized = client.get("/admin/")
                self.assertEqual(authorized.status_code, 200, authorized.text)
                logout = client.get("/admin/logout")
                self.assertIn(logout.status_code, (302, 303), logout.text)
                after_logout = client.get("/admin/")
                self.assertIn(after_logout.status_code, (302, 307))


if __name__ == "__main__":
    unittest.main()
