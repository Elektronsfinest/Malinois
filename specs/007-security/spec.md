# Security & Data Protection

## Goal

Ensure that the application is resistant to common web vulnerabilities,
enforces strict access controls, protects sensitive client case data at rest and
in transit, and provides safe password management. This spec applies to the
entire application and must be satisfied before any production deployment.

## User Stories

- As a user, I want my password to be stored securely so that it cannot be
  recovered even if the database is compromised.
- As an admin, I want to be the only person who can reset another user's
  password so that accounts cannot be hijacked by colleagues.
- As a user, I want my session token to have a bounded lifetime and deactivated
  accounts to lose access immediately so that compromised or former accounts
  cannot access sensitive case data.
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
- [ ] **Unified password policy (all flows — self-service, initial creation,
      admin reset):** minimum **12 characters**, containing at least one
      uppercase letter, one lowercase letter, one digit, and one special
      character
- [ ] JWTs are signed with HS256, carry **`sub` (email) only**, and expire
      after **60 minutes** of issue time (no refresh token, no inactivity timer)
- [ ] `get_current_user` loads `role`, `is_active`, and `must_change_password`
      from the database on **every request** — deactivated users immediately
      receive `401 Unauthorized`
- [ ] `JWT_SECRET_KEY` must be set via environment variable in production;
      the default dev key (`dev-secret-key-…`) must be rejected at startup if
      `ENV=production`
- [ ] Tokens are stored in `localStorage` under `"access_token"`; on any `401`
      response, the client preserves unsaved form drafts in `sessionStorage`
      and opens a re-login modal (clearing drafts on explicit logout or if a
      different user signs in — see spec 011)
- [ ] `GET /api/me` is called on page load to validate the token; a `401`
      triggers logout / re-login prompt
- [ ] `POST /api/login` is rate-limited to **10 requests per minute per IP**;
      excess requests return `429 Too Many Requests`

### Authorisation & Error Code Policy
- [ ] Every protected API endpoint checks the JWT and loads the user's DB
      state before processing the request
- [ ] A missing, malformed, expired token, or inactive user returns `401`
- [ ] If `must_change_password = true`, all endpoints except `GET /api/me` and
      `PATCH /api/me/password` return `403 Forbidden` with
      `{ "code": "password_change_required", "detail": "Musisz zmienić hasło przed kontynuowaniem." }`
- [ ] **Consistent 404 vs 403 policy (preventing ID enumeration):**
  - Accessing a case or resource that does **not exist** OR lies **outside the
    caller's visibility scope** always returns **`404 Not Found`**
  - **`403 Forbidden`** is reserved for role-gated endpoints (`/api/admin/*`)
    and unauthorized actions or fields on an **in-scope** resource (e.g.
    non-admin writing `deadline`/`date_filed`, regular `user` calling restore)
- [ ] Date fields (`deadline`, `date_filed`) on cases may only be written or
      modified by `admin` (including on `POST /api/cases`); non-admin attempts
      return `403 Forbidden`
- [ ] All `/api/admin/*` endpoints are inaccessible to `supervisor` and `user`
      roles (`403 Forbidden`)

### Transport Security
- [ ] In production, the application must be served exclusively over **HTTPS**
      (TLS 1.2 minimum, TLS 1.3 preferred) via reverse proxy
- [ ] HTTP → HTTPS redirect enforced at the reverse proxy level
- [ ] `Strict-Transport-Security` (HSTS) header set with `max-age ≥ 31536000`
      and `includeSubDomains`
- [ ] CORS is configured via `CORS_ORIGINS` env var; dev origins
      (`localhost:5173`) must not appear in production config

### Response & Input Security
- [ ] The API sets the following security headers on every response:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy` (minimum: `default-src 'self'`)
- [ ] All user-supplied strings are stored and returned as plain text; React
      never uses `dangerouslySetInnerHTML` with user-supplied data
- [ ] SQL queries use SQLAlchemy 2.0 ORM exclusively — no raw string
      interpolation into SQL

### File Upload & Backup Download Security
- [ ] Uploaded Excel files (data imports `.xlsx`/`.xlsm`/`.xls` and admin-only
      empty templates `.xlsx`/`.xlsm`, spec 004) are validated by MIME type
      **and** file extension before processing; non-Excel files return `400`
- [ ] Upload file size is capped at **10 MB**; larger uploads return `413`
- [ ] Uploaded data files are parsed strictly in memory and **never stored on
      server disk or persisted as files**; exports are filled from PostgreSQL
      into the empty template in memory and streamed directly to the client
- [ ] Empty Excel templates uploaded by admins (`PUT /api/admin/excel-template`)
      are stored as `LargeBinary` in the database (`excel_templates`), must pass
      a schema check and contain **zero case data rows / PII**, and are logged
      in `admin_audit_log` (spec 009); VBA macros are never executed on the
      server
- [ ] Client-supplied filenames are never used in any server-side filesystem
      operation
- [ ] Backup archive downloads (`POST /api/admin/backups/:filename/download`,
      spec 017) require **admin password re-verification** and are recorded in
      the audit log (spec 009)

### Password Management
- [ ] Only an `admin` can reset another user's password via
      `POST /api/admin/users/:id/reset-password`
- [ ] The endpoint generates a temporary password meeting the 12-char strong
      policy and returns it once in the response — never stored plain-text
- [ ] Both admin user creation (`POST /api/admin/users`) and admin password
      reset set `must_change_password = true`
- [ ] Users can change their own password via `PATCH /api/me/password` (spec
      008) by verifying their current password
- [ ] Users cannot change their own `role` or `supervisor_id` via any endpoint

### Logging & Monitoring
- [ ] Failed login attempts (wrong password, unknown email) are logged with
      timestamp, IP, and attempted email — never the attempted password
- [ ] All `403` and `401` responses are logged server-side for security review
- [ ] Admin permission changes (`role`, `supervisor_id`, `is_active`, password
      reset) and backup downloads are logged in the audit log (spec 009)
- [ ] No sensitive data (passwords, full JWT payloads, case content) appears
      in application logs

## Out of Scope

- Multi-factor authentication (MFA) — future enhancement
- OAuth / SSO integration
- End-to-end encryption of case data at rest (evaluate under RODO review)
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

> The temporary password is returned **once**. It is not stored plain-text and
> cannot be retrieved again.

## Data Model Changes

Add to `users` table:
- `must_change_password` — `Boolean`, `server_default="false"`, not null
- `failed_login_attempts` — `Integer`, `server_default="0"`, not null
- `last_failed_login_at` — `DateTime`, nullable

New table `login_audit_log`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `email_attempted` | String(255) | Not null |
| `ip_address` | String(45) | Not null (supports IPv6) |
| `success` | Boolean | Not null |
| `attempted_at` | DateTime | Default UTC now, not null |

## Resolved Decisions (Indaba Council)

- `404` for non-existent or out-of-scope cases; `403` for role-gated endpoints and forbidden actions/fields on in-scope resources (N-05).
- Unified 12-character strong password policy everywhere; `must_change_password = true` on both admin creation and reset (N-18).
- `sub`-only JWT; `role`, `is_active`, and `must_change_password` checked from DB on every request (N-17, N-20).
- Backup downloads require admin password re-verification + audit logging (N-23).
