# Security & Data Protection

## Goal

Ensure that the application is resistant to common web vulnerabilities,
enforces strict access controls, protects sensitive ZUS case data at rest and
in transit, and provides safe password management. This spec applies to the
entire application and must be satisfied before any production deployment.

## User Stories

- As a user, I want my password to be stored securely so that it cannot be
  recovered even if the database is compromised.
- As an admin, I want to be the only person who can reset another user's
  password so that accounts cannot be hijacked by colleagues.
- As a user, I want my session to expire automatically after inactivity so
  that an unattended computer cannot be used to access my cases.
- As any user, I want all data transmitted over HTTPS so that my credentials
  and case data are not intercepted on the network.
- As an admin, I want login attempts to be rate-limited so that brute-force
  attacks are mitigated.
- As a user, I want the application to prevent me from accessing pages or API
  endpoints I am not authorised for, even if I construct URLs manually.

## Acceptance Criteria

### Authentication & Session Security
- [ ] All passwords are hashed with **bcrypt** (cost factor ≥ 12); plain-text
      passwords are never stored or logged
- [ ] JWTs are signed with HS256 and expire after **60 minutes** of issue time
- [ ] `JWT_SECRET_KEY` must be set via environment variable in production;
      the default dev key (`dev-secret-key-…`) must be rejected if `ENV=production`
- [ ] Tokens are stored in `localStorage` on the client; the app clears the
      token and redirects to `/login` on any `401` response
- [ ] `GET /api/me` is called on page load to validate the token; a `401`
      triggers immediate logout
- [ ] There is no "remember me" or token refresh — users must re-authenticate
      after expiry
- [ ] `POST /api/login` is rate-limited to **10 requests per minute per IP**;
      excess requests return `429 Too Many Requests`

### Authorisation
- [ ] Every protected API endpoint checks the JWT and the user's role before
      processing the request
- [ ] A missing, malformed, or expired token on any protected endpoint returns
      `401`
- [ ] Accessing a resource owned by another user (and not covered by role
      permissions) returns `403` — never `404` (which would reveal existence)
- [ ] Date fields (`deadline`, `date_filed`) on cases can only be modified by
      `admin` role users; any other role attempting this receives `403`
- [ ] The admin user management endpoints (`/api/admin/*`) are inaccessible to
      `supervisor` and `user` roles

### Transport Security
- [ ] In production, the application must be served exclusively over **HTTPS**
      (TLS 1.2 minimum, TLS 1.3 preferred)
- [ ] HTTP → HTTPS redirect must be enforced at the reverse proxy level
- [ ] The `Strict-Transport-Security` (HSTS) header must be set with
      `max-age ≥ 31536000` and `includeSubDomains`
- [ ] CORS is configured to allow only the production frontend origin; the dev
      origins (`localhost:5173`) must not appear in production config
- [ ] The `CORS_ORIGINS` environment variable is used — no origins are
      hardcoded in source

### Response & Input Security
- [ ] The API sets the following security headers on every response:
      - `X-Content-Type-Options: nosniff`
      - `X-Frame-Options: DENY`
      - `Referrer-Policy: strict-origin-when-cross-origin`
      - `Content-Security-Policy` (minimum: `default-src 'self'`)
- [ ] All user-supplied strings are stored and returned as-is (no server-side
      HTML rendering), so XSS via stored content is not possible at the API
      level
- [ ] The React frontend uses no `dangerouslySetInnerHTML` calls with
      user-supplied data
- [ ] SQL queries use the SQLAlchemy ORM exclusively — no raw string
      interpolation into SQL

### File Upload Security (Excel Import — spec 004)
- [ ] Uploaded files are validated by MIME type **and** file extension before
      processing; non-Excel files are rejected with `400`
- [ ] File size is capped at **10 MB**; larger uploads return `413`
- [ ] Uploaded files are processed in memory and **never written to disk**
- [ ] The filename provided by the client is never used in any server-side
      file system operation

### Password Management
- [ ] Only an `admin` can reset another user's password via
      `POST /api/admin/users/:id/reset-password`
- [ ] The endpoint generates a **temporary password** (min 12 chars, mixed
      case + digit + symbol) and returns it once in the response — it is never
      stored plain-text
- [ ] The user is forced to change the temporary password on next login
      (`must_change_password` flag on `users`)
- [ ] Users cannot change their own role or `supervisor_id` via any endpoint

### Logging & Monitoring
- [ ] Failed login attempts (wrong password, unknown email) are logged with
      timestamp and IP — without logging the attempted password
- [ ] All `403` and `401` responses are logged server-side for security review
- [ ] No sensitive data (passwords, full JWT payloads, case content) appears
      in application logs

## Out of Scope

- Multi-factor authentication (MFA) — future enhancement
- OAuth / SSO integration
- End-to-end encryption of case data at rest (consider if regulatory
  requirements demand it)
- Web Application Firewall (WAF) configuration — infrastructure concern
- Penetration testing — to be commissioned separately before go-live

## API Contract

### `POST /api/admin/users/:id/reset-password`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**200 OK**
```json
{ "temporary_password": "Xk9#mPqL2@rT" }
```

**403 Forbidden** — not admin  
**404 Not Found** — user does not exist

> The temporary password is returned **once**. It is not stored and cannot be
> retrieved again.

## Data Model Changes

Add to `users` table:
- `must_change_password` — `Boolean`, default `False`, not null
- `failed_login_attempts` — `Integer`, default `0`
- `last_failed_login_at` — `DateTime`, nullable

New table `login_audit_log`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `email_attempted` | String | Not null |
| `ip_address` | String(45) | Not null (supports IPv6) |
| `success` | Boolean | Not null |
| `attempted_at` | DateTime | Default UTC now |

## Open Questions

- [ ] Is HTTPS termination at a reverse proxy (nginx/caddy) or at the app?
      → Assumed reverse proxy; app does not handle TLS directly.
- [ ] What is the production hosting environment?
      → Must be confirmed to finalise HSTS and CORS config.
- [ ] Are there GDPR / RODO obligations for the case data?
      → ZUS data likely qualifies as sensitive personal data; legal review
      recommended before go-live.
- [ ] Should failed login lockout be implemented (e.g. lock after 5 failures)?
      → Rate limiting covers this for now; hard lockout TBD.
