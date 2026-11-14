"""SQLAdmin registration.

Until a verified authentication backend is implemented, the administrative
interface must not be exposed. This check is deliberately fail-closed.
"""
import os


def setup_admin(app):
    enabled = os.getenv("ENABLE_SQLADMIN", "").strip().lower() in ("1", "true", "yes")
    if enabled:
        raise RuntimeError(
            "SQLAdmin must not be enabled without an authenticated admin backend. "
            "Implement and test admin authentication before enabling it."
        )
    # Intentionally do not mount the unauthenticated admin interface.
    return None
