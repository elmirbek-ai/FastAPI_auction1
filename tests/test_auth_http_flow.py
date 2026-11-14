"""HTTP auth flow tests with an isolated temporary SQLite database.

Only the authentication router is mounted: no Redis, SQLAdmin, PostgreSQL, or
external services are contacted. This is an integration test of FastAPI,
SQLAlchemy and JWT handling, not a production environment test.
"""
import os
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Use the *real* application database module with an isolated SQLite file.
# A file-backed DB permits TestClient requests to run on separate threads.
test_dir = tempfile.TemporaryDirectory(prefix="auction-auth-test-")
test_db = Path(test_dir.name) / "auth.sqlite3"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///" + test_db.as_posix()
os.environ["SECRET_KEY"] = "test-only-signing-key-not-for-production-12345678"

from auction_app.api.endpoints import auth  # noqa: E402
from auction_app.db.database import Base, engine, SessionLocal  # noqa: E402
from auction_app.db import models  # noqa: F401,E402


class AuthenticationFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = engine
        cls.Session = SessionLocal
        application = FastAPI()
        # Mount the real endpoint callables directly, omitting only the router's
        # Redis rate-limit wrapper. This tests HTTP validation, DB and JWT flow.
        application.post("/auth/register/")(auth.register)
        application.post("/auth/login")(auth.login)
        application.post("/auth/refresh/")(auth.refresh)
        application.post("/auth/logout")(auth.logout)

        def local_db():
            with cls.Session() as session:
                yield session

        application.dependency_overrides[auth.get_db] = local_db
        cls.client = TestClient(application)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.engine.dispose()
        test_dir.cleanup()

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def register(self):
        return self.client.post(
            "/auth/register/",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "TestPassword123!",
                "role": "buyer",
            },
        )

    def login(self, password="TestPassword123!"):
        return self.client.post(
            "/auth/login",
            data={"username": "testuser", "password": password},
        )

    def test_register_login_refresh_logout(self):
        register = self.register()
        self.assertEqual(register.status_code, 200, register.text)
        login = self.login()
        self.assertEqual(login.status_code, 200, login.text)
        tokens = login.json()
        self.assertEqual(tokens["token_type"], "bearer")
        self.assertNotEqual(tokens["access_token"], tokens["refresh_token"])

        refresh = self.client.post(
            "/auth/refresh/",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(refresh.status_code, 200, refresh.text)
        self.assertIn("access_token", refresh.json())
        rotated_token = refresh.json()["refresh_token"]
        self.assertNotEqual(rotated_token, tokens["refresh_token"])
        self.assertEqual(
            self.client.post(
                "/auth/refresh/",
                json={"refresh_token": tokens["refresh_token"]},
            ).status_code,
            401,
        )
        again = self.client.post(
            "/auth/refresh/", json={"refresh_token": rotated_token}
        )
        self.assertEqual(again.status_code, 200, again.text)
        rotated_token = again.json()["refresh_token"]

        logout = self.client.post(
            "/auth/logout",
            json={"refresh_token": rotated_token},
        )
        self.assertEqual(logout.status_code, 200, logout.text)
        reused = self.client.post(
            "/auth/refresh/",
            json={"refresh_token": rotated_token},
        )
        self.assertEqual(reused.status_code, 401, reused.text)

    def test_refresh_and_logout_reject_query_only_tokens(self):
        self.assertEqual(self.register().status_code, 200)
        tokens = self.login().json()
        for route in ("/auth/refresh/", "/auth/logout"):
            response = self.client.post(
                route, params={"refresh_token": tokens["refresh_token"]}
            )
            self.assertEqual(response.status_code, 422, response.text)

    def test_duplicate_username_returns_conflict(self):
        self.assertEqual(self.register().status_code, 200)
        again = self.register()
        self.assertEqual(again.status_code, 409, again.text)

    def test_duplicate_email_returns_conflict_without_creating_account(self):
        self.assertEqual(self.register().status_code, 200)
        result = self.client.post(
            "/auth/register/",
            json={
                "username": "anotheruser",
                "email": "test@example.com",
                "password": "AnotherPassword123!",
            },
        )
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(
            self.client.post(
                "/auth/login",
                data={"username": "anotheruser", "password": "AnotherPassword123!"},
            ).status_code,
            401,
        )

    def test_bad_password_is_rejected(self):
        self.assertEqual(self.register().status_code, 200)
        bad = self.login(password="incorrect-password")
        self.assertEqual(bad.status_code, 401, bad.text)

    def test_invalid_registration_rejected(self):
        result = self.client.post(
            "/auth/register/",
            json={"username": "x", "email": "invalid", "password": "short"},
        )
        self.assertEqual(result.status_code, 422, result.text)

    def test_refresh_token_must_be_persisted(self):
        self.assertEqual(self.register().status_code, 200)
        token = auth.create_refresh_token({"sub": "testuser"})
        result = self.client.post("/auth/refresh/", json={"refresh_token": token})
        self.assertEqual(result.status_code, 401, result.text)


if __name__ == "__main__":
    unittest.main()
