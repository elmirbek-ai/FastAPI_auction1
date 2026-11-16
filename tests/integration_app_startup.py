"""Full app startup smoke checks against disposable CI PostgreSQL and Redis."""
import os
import subprocess
import sys
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

    def test_production_rejects_missing_host_allowlist(self):
        env = dict(os.environ)
        env["APP_ENV"] = "production"
        env.pop("ALLOWED_HOSTS", None)
        result = subprocess.run(
            [sys.executable, "-c", "import auction_app.main"],
            env=env, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ALLOWED_HOSTS", result.stderr)

    def test_session_and_jwt_secrets_must_be_independent(self):
        env = dict(os.environ)
        env["SESSION_SECRET_KEY"] = env["SECRET_KEY"]
        result = subprocess.run(
            [sys.executable, "-c", "import auction_app.main"],
            env=env, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be different", result.stderr)

    def test_production_trusted_hosts_reject_unlisted_host(self):
        env = dict(os.environ)
        env["APP_ENV"] = "production"
        env["ALLOWED_HOSTS"] = "auction.example.org"
        script = (
            "from auction_app.main import auction_app; "
            "from fastapi.testclient import TestClient; "
            "client = TestClient(auction_app); "
            "a = client.get('/openapi.json', headers={'Host': 'bad.example.org'}); "
            "b = client.get('/openapi.json', headers={'Host': 'auction.example.org'}); "
            "assert a.status_code == 400, a.status_code; "
            "assert b.status_code == 200, b.status_code"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_admin_view_is_read_only(self):
        from auction_app.admin.view import (
            UserProfileAdmin, CarAdmin, AuctionAdmin, BidAdmin, FeedbackAdmin
        )
        for view in (
            UserProfileAdmin, CarAdmin, AuctionAdmin, BidAdmin, FeedbackAdmin
        ):
            with self.subTest(view=view.__name__):
                self.assertFalse(view.can_create)
                self.assertFalse(view.can_edit)
                self.assertFalse(view.can_delete)
                self.assertFalse(view.can_export)
                self.assertFalse(view.can_import)

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
