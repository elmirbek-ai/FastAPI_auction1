# FastAPI Auction

A FastAPI backend prototype for vehicle listings, timed auctions, bids and seller feedback. The application exposes authentication, car, auction, bid and feedback API routers.

> **Status: development / integration complete, production deployment NOT approved.** Security and concurrency changes from PR #4 have been merged into `main`, but real client compatibility, existing database migration, credential rotation and production infrastructure still require verification.

## Stack

- Python, FastAPI, SQLAlchemy, Pydantic
- PostgreSQL and Alembic
- Redis for API rate limiting
- JWT access/refresh authentication
- Optional, authenticated, **read-only** SQLAdmin
- GitHub Actions integration and security regression tests

## Project layout

- `auction_app/main.py`: FastAPI app, startup and router registration
- `auction_app/api/endpoints/`: authentication, cars, auctions, bids, feedback
- `auction_app/db/`: SQLAlchemy database and models
- `auction_app/admin/`: optional SQLAdmin setup
- `migrations/`: Alembic migration history
- `tests/`: unit, HTTP authentication, security and PostgreSQL/Redis integration tests
- `docs/`: API consumer migration guidance and production release checks

## Configuration

Create a **local, untracked** `.env` using `.env.example` as a guide. Replace every placeholder with environment-specific values. Required settings include:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL |
| `REDIS_URL` | Redis endpoint for rate limiting |
| `SECRET_KEY` | Unique JWT signing secret, minimum 32 characters |
| `SESSION_SECRET_KEY` | Separate random session secret, minimum 32 characters |
| `APP_ENV` | `development` for local work; `production` only behind a properly configured HTTPS proxy |
| `ALLOWED_HOSTS` | Explicit allowed hostnames when `APP_ENV=production` |
| `ENABLE_SQLADMIN` | Disabled by default; only enable after reviewing `docs/ADMIN_SECURITY.md` |

**Never commit `.env`, passwords or signing secrets.** Removing secrets from current code does not remove values previously recorded in Git history. Audit and rotate exposed credentials before any real deployment.

The app object is `auction_app` in `auction_app/main.py`. Its development entry point binds to `127.0.0.1:8001`. Application startup expects reachable Redis. Install compatible dependencies in an isolated environment; a fully reproducible, audited production lockfile and deployment recipe have **not** been established by this security integration. Do not assume that a fresh production installation is validated merely by passing CI.

## Authentication and API behavior

- `POST /auth/login` uses form-encoded username/password.
- Protected writes require `Authorization: Bearer <access_token>`.
- `POST /auth/refresh/` uses JSON `{"refresh_token":"..."}`; refresh tokens rotate and old ones cannot be reused.
- `POST /auth/logout` revokes the submitted refresh token; already-issued access tokens remain valid until expiry.
- Server-generated resource IDs and ownership fields cannot be supplied in write payloads.
- Auction bids enforce seller/buyer permissions, active time windows and increasing bid amounts. Accepted bids are immutable.
- Auction timestamps use UTC normalization; see the client guide for the API's current UTC-naive readback behavior.

See [API client migration](docs/API_CLIENT_MIGRATION.md) before updating any frontend, bot or mobile application. The interactive OpenAPI interface is available at `/docs` once the API starts successfully.

## Validation

PR #4 was merged with three successful CI workflows on its reviewed head commit:

1. Security configuration checks
2. JWT and authentication regression tests
3. PostgreSQL + Redis authentication integration, including Alembic and targeted concurrency tests

These tests use disposable infrastructure. They do **not** prove readiness for a populated legacy database, full multi-worker load or a deployed client ecosystem.

## Release gates

**Merge to `main` is complete; production release is not.** Before deployment:

1. Audit Git history and rotate potentially exposed credentials.
2. Test every real frontend, bot, mobile or third-party API consumer against the changed authentication and write contracts.
3. Back up the current database and audit its schema/Alembic revision before applying any migration to existing data.
4. Configure and verify HTTPS, reverse proxy, explicit hosts, secret storage, administrator restrictions, monitoring and backups.
5. Review auction business rules and run repeatable production-like multi-worker race/load tests.

Details: [merge and deployment decision](docs/PR_MERGE_DECISION.md), [security release checklist](docs/SECURITY_RELEASE_CHECKLIST.md), and [SQLAdmin runbook](docs/ADMIN_SECURITY.md).

## PR history

Security consolidation: [PR #4](https://github.com/elmirbek-ai/FastAPI_auction1/pull/4) (merged). Earlier PR #2 is also merged; superseded PR #3 and outdated documentation PR #1 were closed without separate merges.
