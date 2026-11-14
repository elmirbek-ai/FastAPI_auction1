import os
from contextlib import asynccontextmanager

import fastapi
import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
from fastapi_pagination import add_pagination
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from auction_app.admin.setup import setup_admin
from auction_app.api.endpoints import auth, car, auction, bid, feedback
from auction_app.db.database import SessionLocal


async def init_redis():
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost"),
        encoding="utf-8",
        decode_responses=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = await init_redis()
    try:
        await FastAPILimiter.init(redis_client)
        yield
    finally:
        await redis_client.aclose()


async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


session_secret = os.getenv("SESSION_SECRET_KEY")
if (
    not session_secret
    or len(session_secret) < 32
    or session_secret == "REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_CHARACTERS"
):
    raise RuntimeError(
        "SESSION_SECRET_KEY must be a random secret of at least 32 characters"
    )

auction_app = fastapi.FastAPI(title="Auction site", lifespan=lifespan)
# Secure session cookies and deny arbitrary Host headers in production.
is_production = os.getenv("APP_ENV", "development").lower() == "production"
allowed_hosts = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
if is_production and (not allowed_hosts or "*" in allowed_hosts):
    raise RuntimeError("ALLOWED_HOSTS must list explicit hosts in production")
if is_production:
    auction_app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts,
    )
auction_app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    https_only=is_production,
    same_site="lax",
)

setup_admin(auction_app)
add_pagination(auction_app)
auction_app.include_router(auth.auth_router)
auction_app.include_router(car.car_router)
auction_app.include_router(auction.auction_router)
auction_app.include_router(bid.bid_router)
auction_app.include_router(feedback.feedback_router)


if __name__ == "__main__":
    uvicorn.run(auction_app, host="127.0.0.1", port=8001)
