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

from auction_app.api.endpoints import auth, car, auction, bid, feedback  # noqa: E402
from auction_app.db.database import Base, engine, SessionLocal  # noqa: E402
from auction_app.db import models  # noqa: F401,E402
from datetime import datetime, timezone  # noqa: E402


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
        application.include_router(car.car_router)
        application.include_router(auction.auction_router)
        application.include_router(bid.bid_router)
        application.include_router(feedback.feedback_router)

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

    def test_all_mutation_routes_require_access_token(self):
        # No request body is needed for deletes; this distinguishes auth failures
        # from body validation errors.
        for route in ("/car/777", "/auction/777", "/bid/777", "/feedback/777"):
            response = self.client.delete(route)
            self.assertEqual(response.status_code, 401, (route, response.text))

    def test_invalid_refresh_token_cannot_authorize_write(self):
        response = self.client.delete(
            "/car/777",
            headers={"Authorization": "Bearer malformed-token"},
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_refresh_jwt_cannot_authorize_write(self):
        self.assertEqual(self.register().status_code, 200)
        refresh_token = self.login().json()["refresh_token"]
        response = self.client.delete(
            "/car/777",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_authenticated_user_cannot_delete_another_sellers_car(self):
        with self.Session() as db:
            owner = models.UserProfile(
                username="seller_owner",
                email="seller-owner@example.com",
                hashed_password="not-used-in-this-test",
                role=models.RoleChoices.seller,
            )
            other = models.UserProfile(
                username="other_seller",
                email="other-seller@example.com",
                hashed_password="not-used-in-this-test",
                role=models.RoleChoices.seller,
            )
            db.add_all([owner, other])
            db.flush()
            vehicle = models.Car(
                brand="Test", model="Car", year=datetime(2024, 1, 1),
                fuel_type=models.FuelType.petrol,
                transmission=models.Transmission.auto,
                mileage=100, price=1000,
                description="Isolated test vehicle", image="test-image",
                seller_id=owner.id,
            )
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)
            car_id = vehicle.id
        access = auth.create_access_token({"sub": "other_seller"})
        response = self.client.delete(
            f"/car/{car_id}",
            headers={"Authorization": f"Bearer {access}"},
        )
        self.assertEqual(response.status_code, 403, response.text)
        with self.Session() as db:
            self.assertIsNotNone(
                db.query(models.Car).filter(models.Car.id == car_id).first()
            )

    def test_bid_creator_cannot_impersonate_another_user(self):
        with self.Session() as db:
            seller = models.UserProfile(
                username="auction_seller",
                email="auction-seller@example.com",
                hashed_password="unused-test-hash",
                role=models.RoleChoices.seller,
            )
            buyer = models.UserProfile(
                username="auction_buyer",
                email="auction-buyer@example.com",
                hashed_password="unused-test-hash",
                role=models.RoleChoices.buyer,
            )
            db.add_all([seller, buyer])
            db.flush()
            car = models.Car(
                brand="Test", model="Vehicle", year=datetime(2024, 1, 1),
                fuel_type=models.FuelType.petrol,
                transmission=models.Transmission.auto,
                mileage=123, price=1000,
                description="Test car", image="test.jpg",
                seller_id=seller.id,
            )
            db.add(car)
            db.flush()
            sale = models.Auction(
                car_id=car.id,
                start_price=1000,
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2030, 1, 1),
                status=models.StatusCar.active,
            )
            db.add(sale)
            db.commit()
            db.refresh(sale)
            auction_id, seller_id, buyer_id = sale.id, seller.id, buyer.id

        buyer_access = auth.create_access_token({"sub": "auction_buyer"})
        created = self.client.post(
            "/bid/",
            headers={"Authorization": f"Bearer {buyer_access}"},
            json={
                "id": 777,
                "auction_id": auction_id,
                "user_id": seller_id,
                "amount": 1200,
                "date_registered": "2026-11-14T12:00:00",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["user_id"], buyer_id)
        bid_id = created.json()["id"]
        seller_access = auth.create_access_token({"sub": "auction_seller"})
        denied = self.client.delete(
            f"/bid/{bid_id}",
            headers={"Authorization": f"Bearer {seller_access}"},
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        deleted = self.client.delete(
            f"/bid/{bid_id}",
            headers={"Authorization": f"Bearer {buyer_access}"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)

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
