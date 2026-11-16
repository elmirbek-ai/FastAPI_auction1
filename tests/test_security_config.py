"""Static checks for secrets and security configuration.

These tests do not require PostgreSQL, Redis or application imports.
Run: python -m unittest discover -s tests -v
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SecurityConfigurationTests(unittest.TestCase):
    def test_no_literal_database_url_in_python_modules(self):
        for path in (ROOT / "auction_app").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotRegex(
                        node.value,
                        r"(?i)(?:postgres(?:ql)?|mysql(?:\+\w+)?)://[^\s]+",
                        f"Embedded database connection in {path.relative_to(ROOT)}",
                    )

    def test_alembic_configuration_has_no_embedded_password(self):
        content = (ROOT / "alembic.ini").read_text(encoding="utf-8")
        match = re.search(r"(?m)^sqlalchemy\.url\s*=\s*(.+)$", content)
        self.assertIsNotNone(match)
        self.assertNotIn("@", match.group(1), "Alembic URL must not contain credentials")

    def test_db_url_comes_from_environment(self):
        content = (ROOT / "auction_app/db/database.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("DATABASE_URL")', content)
        self.assertIn("raise RuntimeError", content)

    def test_session_secret_is_required(self):
        content = (ROOT / "auction_app/main.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("SESSION_SECRET_KEY")', content)
        self.assertIn("len(session_secret) < 32", content)
        self.assertNotIn("secret_key='SECRET_KEY'", content)

    def test_session_secret_placeholder_is_rejected(self):
        source = (ROOT / "auction_app/main.py").read_text(encoding="utf-8")
        self.assertIn(
            'session_secret == "REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_CHARACTERS"',
            source,
        )

    def test_python_modules_compile(self):
        for path in (ROOT / "auction_app").rglob("*.py"):
            with self.subTest(file=str(path.relative_to(ROOT))):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


if __name__ == "__main__":
    unittest.main()
