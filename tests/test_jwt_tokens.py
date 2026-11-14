"""JWT behavior regression tests; no DB, Redis, or FastAPI runtime needed."""
from datetime import datetime, timedelta, timezone
import unittest

from jose import jwt

from auction_app.token_security import issue_token, validate_refresh_token

KEY = "test-only-key-not-for-real-deployment-1234"
ALGORITHM = "HS256"


class TokenValidationTests(unittest.TestCase):
    def test_refresh_token_accepts_valid_signed_subject(self):
        token = issue_token(
            "alice", token_type="refresh", secret_key=KEY,
            algorithm=ALGORITHM, lifetime=timedelta(minutes=10),
        )
        self.assertEqual(
            validate_refresh_token(token, secret_key=KEY, algorithm=ALGORITHM),
            "alice",
        )

    def test_two_refresh_tokens_in_same_second_are_distinct(self):
        first = issue_token(
            "alice", token_type="refresh", secret_key=KEY,
            algorithm=ALGORITHM, lifetime=timedelta(minutes=10),
        )
        second = issue_token(
            "alice", token_type="refresh", secret_key=KEY,
            algorithm=ALGORITHM, lifetime=timedelta(minutes=10),
        )
        self.assertNotEqual(first, second)
        claims_a = jwt.decode(first, KEY, algorithms=[ALGORITHM])
        claims_b = jwt.decode(second, KEY, algorithms=[ALGORITHM])
        self.assertNotEqual(claims_a["jti"], claims_b["jti"])
        self.assertEqual(validate_refresh_token(second, secret_key=KEY, algorithm=ALGORITHM), "alice")

    def test_access_token_cannot_be_used_for_refresh(self):
        token = issue_token(
            "alice", token_type="access", secret_key=KEY,
            algorithm=ALGORITHM, lifetime=timedelta(minutes=10),
        )
        with self.assertRaises(ValueError):
            validate_refresh_token(token, secret_key=KEY, algorithm=ALGORITHM)

    def test_expired_token_is_rejected(self):
        token = jwt.encode(
            {
                "sub": "alice", "type": "refresh",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            KEY, algorithm=ALGORITHM,
        )
        with self.assertRaises(ValueError):
            validate_refresh_token(token, secret_key=KEY, algorithm=ALGORITHM)

    def test_missing_expiry_is_rejected(self):
        token = jwt.encode({"sub": "alice", "type": "refresh"}, KEY, algorithm=ALGORITHM)
        with self.assertRaises(ValueError):
            validate_refresh_token(token, secret_key=KEY, algorithm=ALGORITHM)

    def test_wrong_signing_key_is_rejected(self):
        token = issue_token(
            "alice", token_type="refresh", secret_key=KEY,
            algorithm=ALGORITHM, lifetime=timedelta(minutes=10),
        )
        with self.assertRaises(ValueError):
            validate_refresh_token(token, secret_key="another-key", algorithm=ALGORITHM)

    def test_token_without_type_is_rejected(self):
        token = jwt.encode(
            {"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
            KEY, algorithm=ALGORITHM,
        )
        with self.assertRaises(ValueError):
            validate_refresh_token(token, secret_key=KEY, algorithm=ALGORITHM)


if __name__ == "__main__":
    unittest.main()
