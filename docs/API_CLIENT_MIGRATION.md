# API client migration notes (PR #4)

This is a breaking backend release. Update every first-party and third-party
client before enabling it in production. This repository contains the backend,
not an attached frontend implementation; these are contract examples, **not**
proof that any deployed client was migrated.

## Authentication

- `POST /auth/login` uses form-encoded `username` and `password`.
- Send the returned access token as `Authorization: Bearer <access_token>`
  on car, auction, bid and feedback **write** requests.
- `POST /auth/refresh/` accepts JSON
  `{"refresh_token":"<current_refresh_token>"}`.
- On every successful refresh, atomically replace the client's locally stored
  refresh token with the newly returned `refresh_token`. Do not reuse old
  tokens. Old-token reuse returns 401; incorrect/missing JSON body returns 422.
- `POST /auth/logout` accepts the same JSON body with the current refresh
  token. A successful logout revokes refresh privileges; existing short-lived
  access tokens are **not** immediately revoked by this operation.
- Failed or expired refresh attempts must not trigger infinite retries. If
  refreshing returns 401, clear local credentials and require a new login.
- Never place refresh tokens in URL query strings, logs or analytics events.

## New write request bodies

These payloads illustrate only required fields and representative values.
Exact enum options are published in `/openapi.json`.

**Create car:** `POST /car/`

```json
{
  "brand": "Toyota",
  "model": "Camry",
  "year": "2020-01-01",
  "fuel_type": "Бензин",
  "transmission": "автомат",
  "mileage": 20000,
  "price": 500000,
  "description": "Example listing",
  "image": "https://example.invalid/car.jpg"
}
```

**Create auction:** `POST /auction/`

```json
{
  "car_id": 123,
  "start_price": 1000,
  "min_price": null,
  "start_time": "2026-11-20T10:00:00",
  "end_time": "2026-11-21T10:00:00",
  "status": "active"
}
```

Auction times are normalized to **UTC** before they are stored in legacy
UTC-naive PostgreSQL `DateTime` columns. Send explicit RFC 3339 offsets or
`Z` (recommended); offset-free times are interpreted as UTC. API readback
currently returns naive ISO datetimes that represent UTC, not local time.
Clients must not reinterpret them as device-local timestamps.

**Place bid:** `POST /bid/`

```json
{"auction_id": 123, "amount": 1500}
```

**Create feedback:** `POST /feedback/`

```json
{"seller_feedback_id": 456, "rating": 5, "text": "Example review"}
```

The server owns identifiers and attribution. Do not send `id`, `seller_id`,
`user_id`, `bayer_id`, `date_registered` or `create_date` in create
payloads. Some write endpoints also disallow modifications when an auction has
accepted bids. `DELETE /bid/{id}` returns 409 for an accepted bid.

## Handling responses

- `401`: no valid access/refresh credentials; authenticate or re-login.
- `403`: authenticated, but cannot perform this action or access this owner's
  resource.
- `404`: referenced resource does not exist.
- `409`: uniqueness conflict, closed auction, insufficient bid, immutable
  bid history or competing update; display a recoverable domain error.
- `422`: malformed, missing or forbidden payload fields.

## Rollout checklist

1. Identify each frontend, mobile app, bot and external API consumer.
2. Verify login, refresh rotation, logout, protected writes, seller/buyer roles
   and immutable-bid behavior with the exact client versions to be deployed.
3. Prevent concurrent refresh requests from racing within a single client
   session (serialize refresh calls and update stored credentials once).
4. Run staged contract tests with HTTPS and configured allowed hosts.
5. Prepare a user re-login plan if old refresh tokens become unusable.
6. Only after review, coordinate backend and client rollout; preserve a
   rollback plan and do not log bearer credentials.
