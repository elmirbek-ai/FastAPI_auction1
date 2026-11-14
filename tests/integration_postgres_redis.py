"""Integration tests against disposable PostgreSQL and Redis services.

Run only in the dedicated GitHub Actions integration job, never against an
existing user/production database. No external APIs or production secrets.
"""
import os
import unittest
from contextlib import asynccontextmanager

import redis
import redis.asyncio as async_redis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_limiter import FastAPILimiter

if os.getenv("RUN_SERVICE_INTEGRATION_TESTS") != "1":
    raise unittest.SkipTest("Requires disposable PostgreSQL and Redis services")

db_url = os.getenv("DATABASE_URL", "")
if "auction_ci" not in db_url or "localhost" not in db_url:
    raise RuntimeError("Refusing integration tests outside isolated local auction_ci database")

from auction_app.api.endpoints.auth import auth_router  # noqa: E402
from auction_app.db.database import Base, engine  # noqa: E402
from auction_app.db import models  # noqa: F401,E402


@asynccontextmanager
async def test_lifespan(app: FastAPI):
    client = async_redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=False,
    )
    try:
        await client.ping()
        await FastAPILimiter.init(client, prefix="auction-integration-ci")
        yield
    finally:
        await client.aclose()


class PostgreSQLRedisAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        app = FastAPI(lifespan=test_lifespan)
        app.include_router(auth_router)
        cls._context = TestClient(app)
        cls.client = cls._context.__enter__()

    @classmethod
    def tearDownClass(cls):
        try:
            cls._context.__exit__(None, None, None)
        finally:
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    def setUp(self):
        # Clear rate-limit state between tests in the dedicated disposable CI Redis.
        # This suite is explicitly guarded against non-local service URLs.
        redis_url = os.getenv("REDIS_URL", "")
        if "localhost" not in redis_url and "127.0.0.1" not in redis_url:
            raise RuntimeError("Refusing to clear a non-local Redis database")
        redis.Redis.from_url(redis_url).flushdb()

    def test_registration_login_refresh_logout_in_real_services(self):
        registration = self.client.post(
            "/auth/register/",
            json={
                "username": "pg_ci_user",
                "email": "postgres-ci@example.com",
                "password": "IntegrationTest123!",
                "role": "buyer",
            },
        )
        self.assertEqual(registration.status_code, 200, registration.text)
        login = self.client.post(
            "/auth/login",
            data={"username": "pg_ci_user", "password": "IntegrationTest123!"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        tokens = login.json()
        self.assertIn("access_token", tokens)
        self.assertIn("refresh_token", tokens)

        # A second immediate login must create a distinct persisted refresh
        # token rather than violating the database unique constraint.
        repeat = self.client.post(
            "/auth/login",
            data={"username": "pg_ci_user", "password": "IntegrationTest123!"},
        )
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertNotEqual(
            repeat.json()["refresh_token"], tokens["refresh_token"]
        )

        refresh = self.client.post(
            "/auth/refresh/",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(refresh.status_code, 200, refresh.text)
        replacement = refresh.json()["refresh_token"]
        self.assertNotEqual(replacement, tokens["refresh_token"])
        replay = self.client.post(
            "/auth/refresh/",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(replay.status_code, 401, replay.text)
        second = self.client.post(
            "/auth/refresh/", json={"refresh_token": replacement}
        )
        self.assertEqual(second.status_code, 200, second.text)
        replacement = second.json()["refresh_token"]

        logout = self.client.post(
            "/auth/logout",
            json={"refresh_token": replacement},
        )
        self.assertEqual(logout.status_code, 200, logout.text)
        reused = self.client.post(
            "/auth/refresh/",
            json={"refresh_token": replacement},
        )
        self.assertEqual(reused.status_code, 401, reused.text)

    def test_duplicate_account_constraints_return_409_in_postgres(self):
        first = self.client.post(
            "/auth/register/",
            json={
                "username": "unique_ci",
                "email": "unique-ci@example.com",
                "password": "IntegrationTest123!",
            },
        )
        self.assertEqual(first.status_code, 200, first.text)
        same_username = self.client.post(
            "/auth/register/",
            json={
                "username": "unique_ci",
                "email": "different-ci@example.com",
                "password": "IntegrationTest123!",
            },
        )
        self.assertEqual(same_username.status_code, 409, same_username.text)
        same_email = self.client.post(
            "/auth/register/",
            json={
                "username": "other_ci",
                "email": "unique-ci@example.com",
                "password": "IntegrationTest123!",
            },
        )
        self.assertEqual(same_email.status_code, 409, same_email.text)

    def test_registration_rate_limit_enforced(self):
        statuses = []
        for _ in range(7):
            response = self.client.post(
                "/auth/register/",
                json={
                    "username": "x",
                    "email": "bad-email",
                    "password": "short",
                },
            )
            statuses.append(response.status_code)
        self.assertIn(429, statuses, statuses)

    def test_refresh_rate_limit_enforced(self):
        statuses = []
        for _ in range(12):
            response = self.client.post(
                "/auth/refresh/",
                json={"refresh_token": "unknown-invalid-ci-token"},
            )
            statuses.append(response.status_code)
        self.assertIn(429, statuses, statuses)

    def test_redis_rate_limit_applies_to_login(self):
        statuses = []
        for _ in range(7):
            result = self.client.post(
                "/auth/login",
                data={"username": "nonexistent_ci_user", "password": "incorrect"},
            )
            statuses.append(result.status_code)
        self.assertIn(429, statuses, statuses)


if __name__ == "__main__":
    unittest.main()
