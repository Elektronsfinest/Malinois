# Admin Panel

## Goal

Give administrators a dedicated UI for managing users, assigning roles and
supervisors, resetting passwords, and monitoring the overall health of the
system. All admin operations are already secured at the API level (spec 002,
spec 007); this spec covers the frontend panel and ties the admin API endpoints
together into a coherent workflow.

## User Stories

- As an admin, I want to see a list of all users with their roles and
  supervisors so that I have a full picture of the team structure.
- As an admin, I want to create a new user account so that a new colleague can
  start using the system without registering themselves.
- As an admin, I want to change a user's role or supervisor assignment so that
  the team hierarchy stays accurate.
- As an admin, I want to deactivate a user account so that a former employee
  loses access immediately.
- As an admin, I want to reset a user's password and hand them a temporary one
  so that locked-out users can regain access.
- As an admin, I want to trigger an Excel import and monitor its progress so
  that case data is kept up to date.

## Acceptance Criteria

### Backend
- [ ] All `/api/admin/*` endpoints return `403` for non-admin callers (already
      required by spec 002; verified here with dedicated tests)
- [ ] `GET /api/admin/users` supports optional query params:
      `?role=user|supervisor|admin` and `?supervisor_id=<id>` for filtering
- [ ] `POST /api/admin/users` enforces strong password policy on the initial
      password (spec 007)
- [ ] `PATCH /api/admin/users/:id` accepts any subset of:
      `role`, `supervisor_id`, `is_active`; returns `400` if `supervisor_id`
      points to a non-existent or non-supervisor user
- [ ] `POST /api/admin/users/:id/reset-password` returns a one-time temporary
      password and sets `must_change_password = true` (spec 007, spec 008)

### Frontend
- [ ] The Admin Panel is a top-level page accessible only when `role = admin`;
      non-admins navigating to `/admin` are redirected to `/`
- [ ] The panel has three tabs: **Użytkownicy**, **Import / Export**,
      **Ustawienia systemowe**
- [ ] **Użytkownicy tab:**
  - [ ] Displays a table: email, role badge, supervisor email, active status
  - [ ] "Dodaj użytkownika" button opens a modal form with fields:
        email, temporary password, role, supervisor (if role = user)
  - [ ] Clicking a row opens an edit modal: change role, supervisor,
        active status, or trigger password reset
  - [ ] "Reset hasła" button in the edit modal shows the generated temporary
        password in a one-time reveal dialog with a copy button
  - [ ] Deactivating a user shows a confirmation dialog before saving
- [ ] **Import / Export tab:**
  - [ ] Drag-and-drop / file picker for Excel upload (spec 004)
  - [ ] Import summary modal after upload
  - [ ] "Pobierz Excel" button for export
- [ ] **Ustawienia systemowe tab:**
  - [ ] Notification threshold (days before deadline) — editable number input
  - [ ] Save button; changes take effect immediately for all users

## Out of Scope

- Bulk user import from CSV / Excel
- Audit log of admin actions in the UI (the `login_audit_log` table in spec 007
  covers security events; a full admin audit trail is a future enhancement)
- System configuration beyond the notification threshold

## API Contract

All endpoints are defined in specs 002, 004, and 007. This spec adds:

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

## Open Questions

- [ ] Should there be a system-wide "maintenance mode" toggle in settings?
      → Out of scope for now.
- [ ] Is the notification threshold per-team or global?
      → Global for now; per-team thresholds are a future enhancement.
