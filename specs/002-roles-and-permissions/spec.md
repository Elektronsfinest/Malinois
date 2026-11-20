# Role-Based Access Control

## Goal

Give every user in the system a clearly defined role that controls what cases
they can see, create, and edit. Three tiers exist: regular users own their own
cases, supervisors see and partially edit their subordinates' cases, and
administrators have full access including date correction. This is the
prerequisite for all case-management features.

## User Stories

- As a regular user (podrzędny), I want to see and edit only the cases assigned
  to me so that I cannot accidentally modify someone else's work.
- As a supervisor (nadrzędny), I want to see all cases belonging to users in my
  team so that I can monitor progress and intervene when needed.
- As a supervisor, I want to edit selected fields on my subordinates' cases
  (but not dates) so that I can help without changing critical deadlines.
- As an administrator, I want to see and edit every case in the system so that
  I can resolve errors and manage the entire dataset.
- As an administrator, I want to be the only role allowed to change a case's
  date so that date integrity is maintained.
- As an administrator, I want to manage user accounts (create, deactivate,
  assign roles and supervisors) so that the team structure is reflected in the
  app.

## Acceptance Criteria

### Backend
- [ ] The `users` table has a `role` column with values `admin`, `supervisor`,
      `user`; default is `user`
- [ ] The `users` table has a nullable `supervisor_id` FK to `users.id` for
      regular users assigned to a supervisor
- [ ] `GET /api/cases` returns only the requesting user's own cases when role
      is `user`
- [ ] `GET /api/cases` returns all cases belonging to direct subordinates when
      role is `supervisor`
- [ ] `GET /api/cases` returns all cases when role is `admin`
- [ ] `PATCH /api/cases/:id` for a `user` rejects changes to fields they don't
      own with `403`
- [ ] `PATCH /api/cases/:id` date fields (`deadline`, `date_filed`) return `403`
      unless the requesting user has role `admin`
- [ ] `GET /api/admin/users` is accessible only to `admin`; returns `403`
      otherwise
- [ ] `POST /api/admin/users` creates a new user (admin only); returns `403`
      for non-admins
- [ ] `PATCH /api/admin/users/:id` updates role / supervisor / is_active (admin
      only)

### Frontend
- [ ] The Main page (case list) only shows rows the current user is authorised
      to see (enforced server-side; frontend reflects the returned data)
- [ ] Edit controls for date fields are hidden from non-admin users
- [ ] The Admin panel link in navigation is visible only when role is `admin`
- [ ] Supervisor users see a "Team" section grouping cases by subordinate

## Out of Scope

- Multi-level supervisor hierarchies (more than one level of nesting)
- Fine-grained field-level permissions beyond the date restriction
- Self-registration — user creation is admin-only
- Audit log of permission changes (covered in spec 006-audit-log)

## API Contract

### `GET /api/cases`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK** — array filtered by role (see criteria above)
```json
[
  {
    "id": 1,
    "title": "Sprawa XYZ",
    "assigned_to": 3,
    "deadline": "2027-01-15",
    "status": "open"
  }
]
```

**403 Forbidden** — token missing role claim

---

### `PATCH /api/cases/:id`

**Headers:** `Authorization: Bearer <jwt>`

**Request**
```json
{ "status": "closed", "note": "Zakończono" }
```

**200 OK** — updated case object  
**403 Forbidden** — user does not own the case, or tried to edit a date field without admin role  
**404 Not Found** — case does not exist or is not visible to the user

---

### `GET /api/admin/users`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**200 OK**
```json
[
  { "id": 1, "email": "jan@example.com", "role": "supervisor", "supervisor_id": null },
  { "id": 2, "email": "anna@example.com", "role": "user", "supervisor_id": 1 }
]
```

**403 Forbidden** — requesting user is not admin

---

### `POST /api/admin/users`

**Request**
```json
{
  "email": "nowy@example.com",
  "password": "TempPass1!",
  "role": "user",
  "supervisor_id": 1
}
```

**201 Created** — new user object  
**400 Bad Request** — email already taken or validation error  
**403 Forbidden** — not admin

---

### `PATCH /api/admin/users/:id`

**Request** (all fields optional)
```json
{ "role": "supervisor", "supervisor_id": null, "is_active": false }
```

**200 OK** — updated user object  
**403 Forbidden** — not admin  
**404 Not Found**

## Data Model Changes

Add to `users` table:
- `role` — `String`, not null, default `"user"`, values: `admin | supervisor | user`
- `supervisor_id` — `Integer`, nullable, FK → `users.id` (self-referential)

New table `cases` (created in spec 003-case-management, referenced here for
FK constraints):
- `assigned_to` — FK → `users.id`

## Open Questions

- [ ] Can a supervisor be assigned to another supervisor (nested teams)?
      → Assumed no for now; one level only.
- [ ] Who can reset a user's password? → Admin only (see spec 007-security).
