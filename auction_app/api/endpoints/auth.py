from auction_app.config import (SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, ALGORITHM)
from auction_app.token_security import issue_token, validate_refresh_token
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from fastapi_limiter.depends import RateLimiter
from auction_app.db.database import SessionLocal
from typing import Optional
from auction_app.db.schema import UserRegistrationSchema
from auction_app.db.models import UserProfile, RefreshToken
from fastapi import Depends, HTTPException, status, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field

auth_router = APIRouter(prefix='/auth')

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


oauth2_schema = OAuth2PasswordBearer(tokenUrl='/auth/login/')
password_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    return issue_token(
        data["sub"],
        token_type="access",
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
        lifetime=expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(data: dict):
    return issue_token(
        data["sub"],
        token_type="refresh",
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
        lifetime=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


def verify_password(plain_password, hash_password):
    return password_context.verify(plain_password, hash_password)


def get_password_hash(password):
    return password_context.hash(password)


@auth_router.post(
    '/register/',
    dependencies=[Depends(RateLimiter(times=5, seconds=180))],
    tags=['Авторизация'],
    summary='Регистрация',
)
async def register(user: UserRegistrationSchema, db: Session = Depends(get_db)):
    if db.query(UserProfile.id).filter(UserProfile.username == user.username).first():
        raise HTTPException(status_code=409, detail="Username already registered")
    if db.query(UserProfile.id).filter(UserProfile.email == user.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = UserProfile(
        username=user.username,
        email=user.email,
        phone_number=user.phone_number,
        role=user.role,
        hashed_password=get_password_hash(user.password),
    )
    try:
        db.add(new_user)
        db.commit()
    except IntegrityError as exc:
        # The unique constraints remain the final authority when two
        # registrations race after the explicit checks above.
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Username or email already registered"
        ) from exc
    db.refresh(new_user)
    return {"message": "User successfully registered"}


@auth_router.post('/login', dependencies=[Depends(RateLimiter(times=5, seconds=180))],
                  tags=['Авторизация'], summary='Авторизация')
async def login(from_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.username == from_data.username).first()
    if not user or not verify_password(from_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Маалымат туура эмес')
    access_token = create_access_token({'sub': user.username})
    refresh_token = create_refresh_token({'sub': user.username})
    token_db = RefreshToken(token=refresh_token, user_id=user.id)
    db.add(token_db)
    db.commit()
    return {'access_token': access_token, 'refresh_token': refresh_token, 'token_type': 'bearer'}


@auth_router.post('/logout', tags=['Авторизация'], summary='выход из системы')
async def logout(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    refresh_token = payload.refresh_token
    stored_token = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if not stored_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Маалымат туура эмес')
    db.delete(stored_token)
    db.commit()
    return {'message': 'Вышли'}


@auth_router.post(
    '/refresh/',
    dependencies=[Depends(RateLimiter(times=10, seconds=180))],
    tags=['Авторизация'],
    summary='Рефреш токен',
)
async def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    refresh_token = payload.refresh_token
    token_entry = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if not token_entry:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Маалымат туура эмес')
    try:
        username = validate_refresh_token(
            refresh_token, secret_key=SECRET_KEY, algorithm=ALGORITHM
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Refresh token жараксыз же мөөнөтү бүткөн',
        ) from error
    if token_entry.user is None or token_entry.user.username != username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Refresh token колдонуучуга туура келбейт',
        )
    # Rotate the persisted refresh token atomically. A conditional UPDATE makes
    # replays of the old token fail, including requests racing concurrently.
    new_refresh_token = create_refresh_token({'sub': username})
    updated = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.id == token_entry.id,
            RefreshToken.token == refresh_token,
        )
        .update({RefreshToken.token: new_refresh_token}, synchronize_session=False)
    )
    if updated != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Refresh token already used or revoked',
        )
    db.commit()
    access_token = create_access_token({'sub': username})
    return {
        'access_token': access_token,
        'refresh_token': new_refresh_token,
        'token_type': 'bearer',
    }
