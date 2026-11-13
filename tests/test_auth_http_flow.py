"""HTTP auth flow tests with an isolated temporary SQLite database.

Only the authentication router is mounted: no Redis, SQLAdmin, PostgreSQL, or
external services are contacted. This is an integration test of FastAPI,
SQLAlchemy and JWT handling, not a production environment test.
"""
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Configuration is required before auth modules are imported.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-only-signing-key-not-for-production-12345678"

from auction_app.api.endpoints import auth  # noqa: E402
from auction_app.db.database import Base  # noqa: E402
from auction_app.db import models  # noqa: F401,E402


class AuthenticationFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(bind=cls.engine)
        application = FastAPI()
        application.include_router(auth.auth_router)

        def local_db():
            with cls.Session() as session:
                yield session

        application.dependency_overrides[auth.get_db] = local_db

        # The login rate-limit dependency requires a live Redis instance.
        # Override only that dependency; keep the real route and DB/JWT logic.
        from fastapi_limiter.depends import RateLimiter
        for route in application.routes:
            if getattr(route, "path", None) == "/auth/login":
                for dependency in route.dependant.dependencies:
                    if isinstance(dependency.call, RateLimiter):
                        application.dependency_overrides[dependency.call] = lambda: None

        cls.client = TestClient(application)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def register(self):
        return self.client.post(
            "/auth/register/",
            json={
                "username": "testuser",
                "email": "test@example.invalid",
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
            params={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(refresh.status_code, 200, refresh.text)
        self.assertIn("access_token", refresh.json())

        logout = self.client.post(
            "/auth/logout",
            params={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(logout.status_code, 200, logout.text)
        reused = self.client.post(
            "/auth/refresh/",
            params={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(reused.status_code, 401, reused.text)

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
        result = self.client.post("/auth/refresh/", params={"refresh_token": token})
        self.assertEqual(result.status_code, 401, result.text)


if __name__ == "__main__":
    unittest.main()
