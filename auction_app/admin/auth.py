"""Optional SQLAdmin authentication, configured without storing plaintext passwords.

By default SQLAdmin is not mounted. A configured administrator uses a PBKDF2
password hash from the environment and a signed browser session.
"""
import hmac
import os

from passlib.hash import pbkdf2_sha256
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request


class AdminAuthentication(AuthenticationBackend):
    def __init__(self, *, username: str, password_hash: str, secret_key: str):
        super().__init__(secret_key=secret_key)
        self.username = username
        self.password_hash = password_hash

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
        try:
            password_ok = pbkdf2_sha256.verify(password, self.password_hash)
        except (ValueError, TypeError):
            password_ok = False
        username_ok = hmac.compare_digest(username, self.username)
        if not (password_ok and username_ok):
            return False
        request.session.clear()
        request.session["auction_admin"] = self.username
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        session_username = request.session.get("auction_admin")
        return isinstance(session_username, str) and hmac.compare_digest(
            session_username, self.username
        )

    async def get_user_id(self, request: Request):
        return self.username if await self.authenticate(request) else None


def admin_from_environment():
    """Return a configured backend or raise on incomplete/unsafe opt-in."""
    if os.getenv("ENABLE_SQLADMIN", "").strip().lower() not in ("1", "true", "yes"):
        return None

    username = os.getenv("ADMIN_USERNAME", "").strip()
    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    secret = os.getenv("SESSION_SECRET_KEY", "")
    if not username or not password_hash or len(secret) < 32:
        raise RuntimeError(
            "SQLAdmin requires ADMIN_USERNAME, ADMIN_PASSWORD_HASH, "
            "and SESSION_SECRET_KEY (at least 32 characters)"
        )
    if not password_hash.startswith("$pbkdf2-sha256$"):
        raise RuntimeError("ADMIN_PASSWORD_HASH must be a PBKDF2-SHA256 hash")
    try:
        pbkdf2_sha256.from_string(password_hash)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("ADMIN_PASSWORD_HASH must be valid") from exc
    return AdminAuthentication(
        username=username, password_hash=password_hash, secret_key=secret
    )
