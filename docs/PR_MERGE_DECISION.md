# Pull Request #4 — merge readiness and release gate

Last reviewed: 2026-11-16. Head SHA should be re-checked at decision time.

## Scope and decision

PR #4 consolidates security work from PRs #2 and #3 and adds auth,
ownership, bidding, SQLAdmin read-only controls, concurrency tests,
documentation, and disposable PostgreSQL/Redis CI. It is a **large change**
(30+ files, over 100 commits): green CI is necessary but not a substitute
for human code review.

**Code merge:** CONDITIONAL — request a human reviewer, re-check current
head SHA and all three CI jobs, verify required repository rules, evaluate
breaking API contracts, and approve the actual diff. Do not merge while
Draft. No automated process should close or merge the older PRs before
this review and the merge decision.

**Production deployment:** NO-GO until all external conditions below
are verified. Merge eligibility and deployment eligibility are separate.

## CI evidence expected on exact final commit

- JWT and authentication regression tests: success.
- Security configuration checks: success.
- PostgreSQL 16 + Redis 7 integration, Alembic migration and replay:
  success.
- Auction offset-aware time normalization, auction/bid race tests,
  SQLAdmin read-only checks and token rotation/logout: covered in CI.

Verify each workflow result against the **current HEAD**, not an
earlier successful commit. CI uses disposable databases and synthetic
secrets and does not prove compatibility with production state.

## Unresolved blockers before deployment

1. **Secrets:** audit Git history and deployed credentials; rotate any
   potentially exposed database, JWT signing, browser session,
   OAuth/API/admin and Redis credentials. Confirm production keys are
   independent and stored outside source.
2. **Client contracts:** update/test every frontend, bot, mobile and
   third-party API consumer using `docs/API_CLIENT_MIGRATION.md`. Refresh
   token rotation and write authentication are breaking changes.
3. **Legacy data:** audit current live database schema and Alembic state.
   The repository contains an initial Alembic revision; the replay CI
   only covers a previously **versioned** disposable database.
   Never stamp or upgrade an unversioned populated database without a
   verified backup, schema parity audit and reviewed migration plan.
4. **Infrastructure:** verify TLS, reverse proxy trust boundaries, host
   allowlist, Secure cookies, SQLAdmin network restrictions, observability,
   logging without tokens, alerting and verified backup/restore.
5. **Business rules:** review disputes, cancellation, minimum increments,
   auction lifecycle transitions, winner determination, client time-zone
   handling, bid immutability and audit retention.
6. **Load tests:** run repeatable parallel bid and auction/vehicle mutation
   tests against a production-like staging environment and inspect
   deadlocks, response latency and DB connection saturation.

## PR cleanup policy

- **PR #1** is documentation-only; review independently.
- **PR #2** and **PR #3** overlap with PR #4; avoid separate merges.
- Keep old PRs until the accepted PR #4 content is merged, review
  discussion is preserved, and redundant drafts can be closed safely.
- GitHub branch protection visibility may be permission-restricted.
  Confirm the real protection and required-review rules in repository
  settings using an authorized repository administrator.
