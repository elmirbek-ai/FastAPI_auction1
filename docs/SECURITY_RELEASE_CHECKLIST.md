# Security release review checklist

This branch consolidates the earlier security PR #2 and JWT/auth PR #3.
Review and merge **PR #4** rather than merging #2 and #3 separately.

## Verified by CI (disposable infrastructure)

- Environment-backed DB and signing key validation
- SQLAlchemy smoke tests
- JWT signature/type/expiry checks and unique JWT IDs
- Registration, login, one-time refresh token rotation and logout tests
- Two immediate logins without a duplicate refresh-token database error
- PostgreSQL 16, Redis 7, rate limiter, and Alembic upgrade/check
- FastAPI app startup and SQLAdmin login/logout
- Auction bid creation: open auction window, strict increase over highest bid,
  seller self-bidding prohibition, transactional PostgreSQL auction-row lock
- Immutable accepted bids; protect auction and car deletion after bidding
- Reject forged bid owner ID, record ID and bid timestamps in request bodies


## Required before production

- [ ] Rotate potentially exposed PostgreSQL, JWT/session, Redis or OAuth/API
      secrets. Changing current source files does **not** remove Git history.
- [ ] Review how login, refresh, and logout are consumed by existing clients.
      The registration input schema changed; old refresh tokens are invalidated.
      Every successful refresh now rotates the refresh token; clients must
      replace their stored token with the new `refresh_token` in the response.
      Reuse of the old token returns HTTP 401. This change is breaking.
- [x] Refresh/logout now accept a JSON body rather than URL query credentials.
      Update every API client to send `{"refresh_token":"..."}` in the body.
      Old query-only clients now receive HTTP 422; confirm rollout compatibility.
- [ ] Configure HTTPS termination, APP_ENV=production, explicit ALLOWED_HOSTS,
      admin network restrictions, audit logs and strong administrator credentials.
      Production sets Secure session cookies and validates Host headers, but
      TLS enforcement must also be verified at the reverse proxy.
- [ ] Review RBAC and object ownership end-to-end. Car/auction/bid/feedback
      writes now require JWT authentication and owner checks, but workflows,
      bid rules, role transitions and business validation need full testing.
- [ ] Update car, auction and feedback clients: request bodies now use
      strict write schemas, rejecting database IDs, record ownership fields,
      and server-generated timestamps. Car price must be positive; feedback
      rating must be 1–5, with an existing seller target and no self-review.
      These are breaking changes and require client contract testing.
- [ ] Update bid clients: POST /bid/ now accepts only `auction_id` and
      `amount` (positive integer); bidder and bid timestamp are server-owned.
      Closed, future and completed auctions reject bids; accepted bids are
      immutable and cannot be deleted through the API.
- [ ] Confirm business policy for auction start-price strictness, bid increments,
      seller/buyer roles, cancellation, ties, clock behavior, completed auctions,
      payouts, disputes and audit retention before production.
- [x] Add a two-request PostgreSQL concurrency regression proving only one
      identical highest bid can be accepted under the parent auction row lock.
- [ ] Run higher-concurrency, repeatable staging load tests with independent
      client sessions, realistic connection pools, and production-like latency.
      A two-request CI regression is not a full performance or race audit.
- [ ] Review auction create/update/delete synchronization with competing bids
      and confirm the application-level rules in end-to-end staging tests.
- [ ] Verify frontend/API consumers send access Bearer tokens for write routes;
      unauthenticated writes now return HTTP 401.
- [ ] Test the intended production dependency versions and startup/deployment
      configuration. CI is deliberately limited to selected supported versions.
- [ ] Check clean and existing-database migration paths and make a backup
      before production migration. CI tests a disposable fresh database.
- [ ] Verify required branch protections, reviews and operational monitoring.

## PR cleanup (after final acceptance)

- Keep **PR #4** as the sole integration candidate.
- Keep PR #1 (documentation) separate, because it affects only README.
- PR #2 is an ancestor of PR #4 and should not be merged separately.
- PR #3 changes are included in PR #4; do not merge it separately.
- Close old drafts only after confirming the merged implementation and preserving
  any review discussion or useful comments.

- [ ] Verify that read-only user schemas never return password hashes.

CI passing is not an assertion that this application is production-ready.
