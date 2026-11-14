# SQLAdmin access — security runbook

The SQLAdmin interface is **disabled by default**. Enabling it without
valid credentials raises a startup error instead of mounting an anonymous
administration panel.

## Opt-in configuration

Only enable administration on an HTTPS deployment with suitable network
access restrictions. Put the following in an untracked environment or secret
manager; **never commit actual values**:

- `ENABLE_SQLADMIN=true`
- `ADMIN_USERNAME`: a dedicated account name (not a normal API user)
- `ADMIN_PASSWORD_HASH`: a PBKDF2-SHA256 hash of a strong, unique password
- `SESSION_SECRET_KEY`: an independent random secret, at least 32 characters

Generate a password hash locally, without placing the plaintext password in
the shell command history:

```bash
python -c "from getpass import getpass; from passlib.hash import pbkdf2_sha256; print(pbkdf2_sha256.hash(getpass('Admin password: ')))"
```

Do **not** use the JWT `SECRET_KEY` as the session secret. For production,
configure secure HTTPS cookies and reverse-proxy transport security. Rotating
the session signing key invalidates existing sessions. Credentials and session
secrets may need to be rotated if previously exposed.

## Access controls

- SQLAdmin login validates a password against `ADMIN_PASSWORD_HASH`, and
  access is checked using a signed browser session.
- Logout clears the admin session.
- The user-account listing is read-only, excludes password hashes from its
  listed and detailed fields, and disables user record export and import.
- By default SQLAdmin routes are absent entirely.
- The remaining administration views have broad authority **after login**;
  use a dedicated administrator and restrict access by VPN/IP or an
  authenticated reverse proxy when appropriate.

## Validation scope

Disposable PostgreSQL/Redis CI tests verify admin opt-in, invalid/valid
login, logout and default-deny behavior. They do not establish operational
security for a deployment, including MFA, password rotation procedures,
account lockout, TLS, proxy rules, monitoring and incident response.
