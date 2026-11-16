"""Signing-key configuration checks independent of the full API."""
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

CONFIG = Path(__file__).resolve().parents[1] / "auction_app" / "config.py"


def load_config(secret):
    with patch.dict(os.environ, {"SECRET_KEY": secret}, clear=True):
        with patch("dotenv.load_dotenv", return_value=False):
            return runpy.run_path(str(CONFIG))


class JwtConfigurationTests(unittest.TestCase):
    def test_missing_key_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            load_config("")

    def test_short_key_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            load_config("tiny")

    def test_placeholder_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            load_config("REPLACE_WITH_A_SEPARATE_RANDOM_JWT_SIGNING_SECRET")

    def test_long_test_key_accepted(self):
        secret = "test-only-random-looking-string-not-production-12345"
        self.assertEqual(load_config(secret)["SECRET_KEY"], secret)


if __name__ == "__main__":
    unittest.main()
