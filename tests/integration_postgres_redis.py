"""Integration tests against disposable PostgreSQL and Redis services.

Run only in the dedicated GitHub Actions integration job, never against an
existing user/production database. No external APIs or production secrets.
"""
import os
import unittest
from contextlib import asynccontextmanager

import redis.asyncio as redis
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
    client = redis.Redis.from_url(
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

        refresh = self.client.post(
            "/auth/refresh/",
            params={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(refresh.status_code, 200, refresh.text)

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
