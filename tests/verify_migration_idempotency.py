"""Verify migration replay preserves a pre-existing record in disposable CI DB.

Only runs AFTER an initial 'alembic upgrade head'. This does not validate
unversioned historical databases and must never run against production.
"""
import os
import subprocess
import sys
from pathlib import Path

# Direct script invocation otherwise places tests/, not repository root, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if os.getenv("RUN_SERVICE_INTEGRATION_TESTS") != "1":
    raise SystemExit("Requires isolated CI services")
url = os.getenv("DATABASE_URL", "")
if "localhost" not in url or "/auction_ci" not in url:
    raise SystemExit("Refusing non-disposable PostgreSQL database")

from sqlalchemy import select, text
from auction_app.db.database import SessionLocal
from auction_app.db.models import RoleChoices, UserProfile

sample_username = "migration-preservation-ci"
with SessionLocal() as db:
    current = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    sample = UserProfile(
        username=sample_username,
        email="migration-preservation-ci@example.invalid",
        hashed_password="no-real-credentials",
        role=RoleChoices.buyer,
    )
    db.add(sample)
    db.commit()
    sample_id = sample.id

subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    check=True,
)

with SessionLocal() as db:
    assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == current
    sample = db.execute(
        select(UserProfile).where(UserProfile.id == sample_id)
    ).scalar_one()
    assert sample.username == sample_username
    assert sample.email == "migration-preservation-ci@example.invalid"

print("Versioned migration re-run preserved an existing user record.")
