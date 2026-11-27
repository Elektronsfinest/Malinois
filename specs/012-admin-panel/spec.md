# Admin Panel

## Goal

Give administrators a dedicated UI (`/admin`) for managing users, assigning
roles and supervisors, resetting passwords, configuring system settings and the
empty Excel export template, inspecting the admin audit log, and managing
database backups. All admin endpoints are secured with `require_role("admin")`
(spec 002, spec 007). Excel data import lives separately at `/import` (reached
from `/cases`, spec 004).

## User Stories

- As an admin, I want to see a list of all users with their roles, supervisors,
  and active status so that I have a full picture of the team structure.
- As an admin, I want to create a new user account with a temporary password
  that forces a password change on first login.
- As an admin, I want to change a user's role or supervisor assignment and
  safely deactivate accounts by explicitly reassigning their active cases and
  subordinates.
- As an admin, I want to reset a user's password and hand them a one-time
  temporary password so that locked-out users can regain access.
- As an admin, I want to configure `notification_threshold_days`, inspect the
  security/permission audit log, and manage backups in one place.

## Acceptance Criteria

### Backend
- [ ] All `/api/admin/*` endpoints return `403 Forbidden` for non-admin callers
- [ ] `GET /api/admin/users` supports optional query params:
      `?role=user|supervisor|admin` and `?supervisor_id=<id>` and
      `?is_active=true|false`
- [ ] `POST /api/admin/users` enforces the unified 12-character strong password
      policy (spec 007), sets `must_change_password = true`, and logs
      `user_created` in `admin_audit_log` (spec 009)
- [ ] `PATCH /api/admin/users/:id` accepts any subset of `role`,
      `supervisor_id`, `is_active`, plus optional `reassign_cases_to` and
      `reassign_subordinates_to`:
  - Returns `400` if `supervisor_id` points to a non-existent, inactive, or
    non-`supervisor`/non-`admin` user (or if `supervisor_id == id`)
  - When setting `is_active = false`: if the user owns active (non-archived)
    cases and `reassign_cases_to` (an active user) is omitted, OR if the user
    is a `supervisor` or `admin` with direct subordinates and
    `reassign_subordinates_to` (an active `supervisor` or `admin`) is omitted,
    returns **`409 Conflict`** with `blocking_case_ids` and
    `blocking_subordinate_ids` (no silent fallback)
  - Executes reassignment + deactivation atomically in one transaction and logs
    all permission changes in `admin_audit_log` (spec 009)
- [ ] `POST /api/admin/users/:id/reset-password` returns a one-time 12-char
      temporary password, sets `must_change_password = true`, and logs
      `password_reset` in `admin_audit_log` (spec 009)
- [ ] `GET /api/admin/settings` and `PATCH /api/admin/settings` manage
      `notification_threshold_days` (integer `1–365`, default `7`), logging
      `settings_updated` in `admin_audit_log`
- [ ] `GET /api/admin/excel-template` and `PUT /api/admin/excel-template`
      (spec 004) allow admins to inspect and upload/replace the empty `.xlsx` /
      `.xlsm` export template with mandatory schema validation and audit logging

### Frontend
- [ ] The Admin Panel lives at `/admin`, accessible only when `role = admin`;
      non-admins navigating to `/admin` are redirected to `/`
- [ ] The panel has **4 tabs**:
  1. **Użytkownicy** (Users)
  2. **Ustawienia systemowe** (System Settings)
  3. **Dziennik audytu** (Audit Log — spec 009)
  4. **Kopie zapasowe** (Backups — spec 017)
- [ ] **Użytkownicy tab:**
  - Displays table: email, role badge, supervisor email, active status
  - **"Dodaj użytkownika"** modal: email, temporary password (12+ chars), role,
    supervisor (if role = user)
  - Row click opens edit modal: change role, supervisor, active status, or
    trigger **"Reset hasła"** (one-time reveal dialog with copy button)
  - Deactivating a user with active cases or subordinates prompts the admin to
    select `reassign_cases_to` / `reassign_subordinates_to` in the confirmation
    dialog before submitting
- [ ] **Ustawienia systemowe tab:**
  - Editable `notification_threshold_days` (1–365); changes take effect
    immediately across notifications (005), case row urgency colours (003), and
    Dashboard `due_soon` (014)
  - **Szablon Excel (.xlsx / .xlsm)** section (spec 004): displays active
    template metadata and allows admins to upload/replace the empty export
    template with schema-check feedback
- [ ] **Dziennik audytu tab:**
  - Displays paginated `admin_audit_log` entries (spec 009) with action filter
- [ ] **Kopie zapasowe tab:**
  - Create manual backup, list backups, and download with password
    re-verification (spec 017)

## Out of Scope

- Bulk user import from CSV / Excel
- Excel case data import (lives at `/import`, reached from `/cases` per spec
  004)
- System configuration beyond `notification_threshold_days` and the Excel
  export template

## API Contract

User endpoints are defined in spec 002, password reset in spec 007, audit log
in spec 009, and backups in spec 017. This spec defines:

### `GET /api/admin/settings`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**200 OK**
```json
{ "notification_threshold_days": 7 }
```

---

### `PATCH /api/admin/settings`

**Request**
```json
{ "notification_threshold_days": 14 }
```

**200 OK** — updated settings object  
**400 Bad Request** — value out of range (must be 1–365)  
**403 Forbidden** — not admin

## Data Model Changes

New table `system_settings` (key-value store for global config):

| Column | Type | Constraints |
|---|---|---|
| `key` | String(100) | PK |
| `value` | String(500) | Not null |
| `updated_at` | DateTime | Auto-updated |

Seed row: `{ key: "notification_threshold_days", value: "7" }`.

## Resolved Decisions (Indaba Council)

- Admin Panel has 4 tabs: Users, Settings (including empty Excel template upload with schema check), Audit Log, Backups; Excel data import lives at `/import` reached from `/cases` (N-21, spec 004).
- Admin user creation enforces 12-char password policy and sets `must_change_password = true` (N-18).
- All admin permission changes are logged in `admin_audit_log` (N-22).
- User/supervisor deactivation requires explicit `reassign_cases_to` / `reassign_subordinates_to` with `409 Conflict` when omitted (N-24).
