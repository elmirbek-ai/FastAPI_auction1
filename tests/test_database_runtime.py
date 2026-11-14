"""Runtime smoke checks for the isolated SQLAlchemy database module.

Uses an in-memory SQLite database only. No real credentials or external DB.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_database_snippet(source, database_url):
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["SECRET_KEY"] = "test-only-signing-key-for-database-tests-123456"
    env["DATABASE_URL"] = database_url
    # Prevent accidental loading of local developer .env credentials.
    env["PYTHON_DOTENV_DISABLED"] = "1"
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


class DatabaseRuntimeTests(unittest.TestCase):
    def test_sqlite_engine_opens_a_real_connection(self):
        code = (
            "from sqlalchemy import text\n"
            "from auction_app.db.database import engine, SessionLocal\n"
            "with engine.connect() as connection:\n"
            "    assert connection.execute(text('SELECT 1')).scalar_one() == 1\n"
            "with SessionLocal() as session:\n"
            "    assert session.execute(text('SELECT 2')).scalar_one() == 2\n"
        )
        result = run_database_snippet(code, "sqlite+pysqlite:///:memory:")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_database_url_fails_before_engine_creation(self):
        result = run_database_snippet(
            "from auction_app.db import database\n",
            "",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL must be set", result.stderr)


if __name__ == "__main__":
    unittest.main()
