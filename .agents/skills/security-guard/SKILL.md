---
name: security-guard
description: >-
  Use when any change touches authentication, JWT handling, password policy,
  role checks, 403/404 responses, file uploads, backup downloads, security
  headers, or audit logging in Malinois. Assumes the caller is hostile.
---

# Security & Data Protection Guard — Malinois

Malinois handles sensitive client personal data. Every endpoint, upload handler,
and frontend view must satisfy `specs/007-security/spec.md` without exception.

---

## Non-Negotiable Security Invariants

1. **Passwords & Hashing:**
   - Hash with `bcrypt` (cost factor `>= 12`) via `security.hash_password()`.
   - Never store, return (except one-time admin reset), or log plain-text passwords.
   - **Unified 12-character strong password policy** everywhere (self-service
     change, admin user creation, admin reset): min 12 chars, uppercase +
     lowercase + digit + special character.
   - Both admin user creation and admin password reset set
     `must_change_password = true`; while true, all endpoints except
     `GET /api/me` and `PATCH /api/me/password` return `403` with
     `{ "code": "password_change_required", "detail": "Musisz zmienić hasło przed kontynuowaniem." }`.
2. **JWT & Immediate Deactivation:**
   - HS256 JWT carries **`sub` (email) only** and expires after **60 minutes**
     (no refresh token, no role claim in token).
   - Reject default dev `JWT_SECRET_KEY` at startup when `ENV=production`.
   - `get_current_user` loads `role`, `is_active`, and `must_change_password`
     from the DB on **every request** — deactivated users immediately get `401`.
3. **Anti-Enumeration (`404` vs `403`):**
   - Accessing a case, note, or copy that does **not exist** OR lies **outside
     the caller's visibility scope** MUST return **`404 Not Found`**.
   - Reserve **`403 Forbidden`** for role-gated endpoints (`/api/admin/*`) and
     unauthorized actions/fields on an **in-scope** resource (non-admin writing
     dates, regular `user` calling restore, `must_change_password`).
4. **In-Memory Uploads & Safe Downloads:**
   - Validate Excel uploads by **both** MIME type and extension (`.xlsx`/`.xls`).
   - Enforce **10 MB** upload cap (`413 Payload Too Large`).
   - Parse strictly in memory and store rows in `working_copies.rows_json` —
     **never write uploaded files to disk** and never use client filenames in
     filesystem paths.
   - Backup downloads (`POST /api/admin/backups/:filename/download`) require
     **admin password re-verification**, strict filename allowlist (no `..`,
     `/`, `\`), and logging to `admin_audit_log`.
5. **Input, SQL & Transport Hardening:**
   - SQLAlchemy 2.0 ORM exclusively — zero raw SQL string interpolation.
   - Zero `dangerouslySetInnerHTML` with user-supplied data in React.
   - Rate-limit `POST /api/login` to **10 requests/minute/IP** (`429`).
   - Set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
     `Referrer-Policy: strict-origin-when-cross-origin`, and
     `Content-Security-Policy` on every API response.
   - Log all failed logins (`login_audit_log`, never the password), all
     `401`/`403` responses, and all admin permission/backup actions
     (`admin_audit_log`).
