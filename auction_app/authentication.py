"""Authentication dependency for protected auction write operations."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from auction_app.config import ALGORITHM, SECRET_KEY
from auction_app.db.database import SessionLocal
from auction_app.db.models import UserProfile

bearer = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(bearer)) -> UserProfile:
    try:
        claims = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
        username = claims.get("sub")
        if (
            claims.get("type") != "access"
            or not isinstance(username, str)
            or not username
        ):
            raise ValueError("Invalid access token claims")
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    with SessionLocal() as db:
        user = db.query(UserProfile).filter(UserProfile.username == username).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User no longer exists",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Return only fields needed by authorization; detached ORM entity is
        # safe for already-loaded scalar id, username and role attributes.
        return user
