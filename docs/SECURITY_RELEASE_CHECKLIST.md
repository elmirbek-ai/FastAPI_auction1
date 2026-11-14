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
