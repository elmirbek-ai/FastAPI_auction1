"""HTTP auth flow tests with an isolated temporary SQLite database.

Only the authentication router is mounted: no Redis, SQLAdmin, PostgreSQL, or
external services are contacted. This is an integration test of FastAPI,
SQLAlchemy and JWT handling, not a production environment test.
"""
import os
import sys
import types
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure auth imports never touch the legacy hard-coded PostgreSQL settings
# on main. SQLAlchemy ORM models use this in-process SQLite engine instead.
os.environ["SECRET_KEY"] = "test-only-signing-key-not-for-production-12345678"
isolated_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
IsolatedBase = declarative_base()
IsolatedSession = sessionmaker(bind=isolated_engine)
db_stub = types.ModuleType("auction_app.db.database")
db_stub.engine = isolated_engine
db_stub.Base = IsolatedBase
db_stub.SessionLocal = IsolatedSession
sys.modules["auction_app.db.database"] = db_stub

from auction_app.api.endpoints import auth  # noqa: E402
from auction_app.db.database import Base  # noqa: E402
from auction_app.db import models  # noqa: F401,E402


class AuthenticationFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = isolated_engine
        cls.Session = IsolatedSession
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
