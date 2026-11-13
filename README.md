# FastAPI Auction — Prototype

An auction application backend using FastAPI. The current application registers routers for authentication, cars, auctions, bids and feedback, and includes an admin setup.

> **Status:** Development prototype. The checked-in configuration contains **insecure hard-coded database credentials and a static session secret**. **Do not expose this version publicly or reuse those credentials.** Rotate any real credentials that match values previously committed.

## Technology

- Python, FastAPI, SQLAlchemy
- PostgreSQL
- Redis and fastapi-limiter
- Alembic migrations
- FastAPI pagination

## Repository structure

- `auction_app/main.py` — application entry point, lifespan and routers
- `auction_app/api/endpoints/` — authentication, cars, auctions, bids, feedback
- `auction_app/db/` — database setup
- `auction_app/admin/` — admin integration
- `migrations/` — database schema migrations

## Before running locally

The current repository must be configured and hardened before normal use:

1. Create an isolated PostgreSQL database and Redis instance for development.
2. Move the PostgreSQL connection string and session secret out of the source code into environment-based configuration.
3. Rotate any real exposed credentials before connecting to existing services.
4. Install the project's runtime dependencies in a virtual environment. A verified dependency lockfile and reproducible setup procedure have **not** been established in this audit.
5. Review database migrations and authentication/session behavior before starting the API.

The FastAPI application object is `auction_app` in `auction_app/main.py`, with a local development entry point on port 8001. The lifespan hook currently expects Redis at `localhost`.

## API

The application includes routers for authentication, cars, auctions, bids, and feedback. Explore `/docs` after a securely configured local startup to confirm exact paths and schemas.

## Production readiness

Not production ready in the audited state. Security remediation, dependency verification, tests, authorization review, safe configuration, and deployment documentation are required.

This README documents the existing code and known limitations; it does not imply that the application has passed tests or a security audit.
