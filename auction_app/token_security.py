"""Signed JWT token issuance and strict refresh-token validation."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt


def issue_token(
    subject: str,
    *,
    token_type: str,
    secret_key: str,
    algorithm: str,
    lifetime: timedelta,
) -> str:
    if not secret_key:
        raise ValueError("A JWT signing secret is required")
    if token_type not in ("access", "refresh"):
        raise ValueError("Invalid JWT token type")
    if lifetime.total_seconds() <= 0:
        raise ValueError("Token lifetime must be positive")
    return jwt.encode(
        {
            "sub": str(subject),
            "type": token_type,
            "jti": uuid4().hex,
            "exp": datetime.now(timezone.utc) + lifetime,
        },
        secret_key,
        algorithm=algorithm,
    )


def validate_refresh_token(token: str, *, secret_key: str, algorithm: str) -> str:
    if not secret_key:
        raise ValueError("A JWT signing secret is required")
    try:
        claims = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired refresh token") from exc
    subject = claims.get("sub")
    if claims.get("type") != "refresh" or not isinstance(subject, str) or not subject:
        raise ValueError("JWT is not a refresh token")
    return subject
