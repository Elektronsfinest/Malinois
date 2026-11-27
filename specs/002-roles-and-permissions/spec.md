# Role-Based Access Control

## Goal

Give every user in the system a clearly defined role that controls what cases
they can see, create, and edit. Three tiers exist: regular users own their own
cases, supervisors see and edit their own and direct subordinates' cases, and
administrators have full access including date creation/correction and user
management. This is the prerequisite for all case-management features.

## User Stories

- As a regular user (podrzędny), I want to see and edit only the cases assigned
  to me so that I cannot accidentally modify someone else's work.
- As a supervisor (nadrzędny), I want to see my own cases and all cases
  belonging to my direct subordinates so that I can monitor progress and
  intervene when needed.
- As a supervisor, I want to edit non-date fields on my own and my
  subordinates' cases so that I can help without changing critical deadlines.
- As an administrator, I want to see and edit every case in the system so that
  I can resolve errors and manage the entire dataset.
- As an administrator, I want to be the only role allowed to set or change a
  case's date (`deadline`, `date_filed`) so that date integrity is maintained.
- As an administrator, I want to manage user accounts (create, deactivate with
  explicit reassignment, assign roles and supervisors) so that the team
  structure is reflected in the app.

## Acceptance Criteria

### Backend
- [ ] The `users` table has a `role` column with values `admin`, `supervisor`,
      `user`; default is `user`
- [ ] The `users` table has a nullable `supervisor_id` FK to `users.id` for
      regular users assigned to a direct supervisor (one-level hierarchy only;
      no transitive nesting)
- [ ] The JWT payload remains `sub`-only (user email, as in `security.py`);
      `role`, `is_active`, and `must_change_password` are loaded from the
      database on every authenticated request via `get_current_user`
- [ ] Reusable `require_role(*roles)` dependency guards role-restricted routes
      and returns `403 Forbidden` for unauthorized roles
- [ ] Visibility scope for `GET /api/cases` and single-case endpoints:
  - `user`: own cases only (`assigned_to == current_user.id`)
  - `supervisor`: own cases + direct subordinates' cases (`assigned_to ==
    current_user.id` OR `assigned_to IN direct_subordinate_ids`)
  - `admin`: all cases
- [ ] Out-of-scope or non-existent case IDs always return `404 Not Found` (never
      leaking existence); `403 Forbidden` is reserved for role-gated endpoints
      and unauthorized actions/fields on an in-scope resource
- [ ] Editable fields for `user` and `supervisor` are identical on their
      in-scope cases: non-date metadata (`title`, `client_name`, `status`);
      notes are added via immutable `case_notes` (spec 010)
- [ ] Date fields (`deadline`, `date_filed`) may only be written or modified by
      `admin` (including on `POST /api/cases`); non-admin attempts to supply
      non-null dates return `403 Forbidden`
- [ ] `assigned_to` changes only via `admin` or team-scoped reassignment
      (`POST /api/cases/reassign`, spec 016)
- [ ] `GET /api/admin/users` is accessible only to `admin`; returns `403`
      otherwise
- [ ] `POST /api/admin/users` creates a new user (admin only), enforces the
      12-character strong password policy (spec 007), and sets
      `must_change_password = true`; returns `403` for non-admins
- [ ] `PATCH /api/admin/users/:id` updates `role`, `supervisor_id`, `is_active`
      (admin only) and logs permission changes to the audit log (spec 009).
      Deactivating a user with active cases requires `reassign_cases_to`, and
      deactivating a supervisor with direct subordinates requires
      `reassign_subordinates_to` (pointing to an active `supervisor` or
      `admin`); omitting either returns `409 Conflict` listing blocking IDs

### Frontend
- [ ] The Main page (`/cases`) only shows rows the current user is authorised
      to see (enforced server-side; frontend reflects the returned data)
- [ ] Edit controls for date fields (`deadline`, `date_filed`) are hidden from
      non-admin users
- [ ] The Admin panel link (`/admin`) in navigation is visible only when role
      is `admin`
- [ ] Supervisor users see per-member team summaries on Dashboard (`/`, spec
      014) and can filter `/cases` by themselves or any direct subordinate

## Out of Scope

- Multi-level / transitive supervisor hierarchies (more than one level of nesting)
- Fine-grained field-level permissions beyond the date and reassignment restrictions
- Self-registration — user creation is admin-only

## API Contract

### `GET /api/cases`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK** — paginated object filtered by role (consistent across specs 002, 003, 006, 013)
```json
{
  "items": [
    {
      "id": 1,
      "case_number": "CASE-2027-0001",
      "title": "Sprawa XYZ",
      "client_name": "Jan Kowalski",
      "assigned_to": 3,
      "deadline": "2027-01-15",
      "date_filed": "2026-11-01",
      "status": "open",
      "archived": false,
      "version": 1
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

**401 Unauthorized** — missing, invalid, expired token, or inactive user  
**403 Forbidden** — `must_change_password` is true (`code: "password_change_required"`)

---

### `PATCH /api/cases/:id`

**Headers:** `Authorization: Bearer <jwt>`

**Request** (`version` required per spec 011)
```json
{ "version": 1, "status": "closed" }
```

**200 OK** — updated case object (with incremented `version`)  
**403 Forbidden** — attempted to edit a restricted field (e.g. `deadline` or `date_filed` without `admin` role) on an in-scope case  
**404 Not Found** — case does not exist or is outside the caller's visibility scope  
**409 Conflict** — `version` mismatch (returns latest `current` case object; see spec 011)

---

### `GET /api/admin/users`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**200 OK**
```json
[
  { "id": 1, "email": "jan@example.com", "role": "supervisor", "supervisor_id": null, "is_active": true },
  { "id": 2, "email": "anna@example.com", "role": "user", "supervisor_id": 1, "is_active": true }
]
```

**403 Forbidden** — requesting user is not admin

---

### `POST /api/admin/users`

**Request**
```json
{
  "email": "nowy@example.com",
  "password": "TempPass123!@",
  "role": "user",
  "supervisor_id": 1
}
```

**201 Created** — new user object (`must_change_password: true`)  
**400 Bad Request** — email already taken, weak password (<12 chars / missing complexity), or invalid `supervisor_id`  
**403 Forbidden** — not admin

---

### `PATCH /api/admin/users/:id`

**Request** (all fields optional; `reassign_cases_to` / `reassign_subordinates_to` required when deactivating a user with active cases or subordinates)
```json
{
  "role": "supervisor",
  "supervisor_id": null,
  "is_active": false,
  "reassign_cases_to": 4,
  "reassign_subordinates_to": 5
}
```

**200 OK** — updated user object  
**400 Bad Request** — invalid `supervisor_id` or reassignment target inactive/invalid  
**403 Forbidden** — not admin  
**404 Not Found** — user not found  
**409 Conflict** — deactivation blocked because user has active cases or direct subordinates and reassignment targets were omitted (returns `{ "detail": "...", "blocking_case_ids": [...], "blocking_subordinate_ids": [...] }`)

## Data Model Changes

Add to `users` table:
- `role` — `String(20)`, not null, `server_default="user"`, values: `admin | supervisor | user`
- `supervisor_id` — `Integer`, nullable, FK → `users.id` (self-referential), indexed

## Resolved Decisions (Indaba Council)

- Supervisor visibility includes **own + direct subordinates' cases** only (N-03).
- JWT carries `sub` only; `role`, `is_active`, and `must_change_password` are loaded from DB on every request (N-20).
- Out-of-scope cases return `404`; role/field denials on in-scope resources return `403` (N-05).
- Permission changes are logged in `spec 009-edit-history` (N-22).
- Deactivation requires explicit reassignment with `409 Conflict` when omitted (N-24).
