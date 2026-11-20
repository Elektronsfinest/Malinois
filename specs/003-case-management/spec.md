# Case Management

## Goal

Provide the core data model and CRUD operations for ZUS cases (sprawy). Users
can view their assigned cases, see deadlines, and update case metadata. The
case list is the primary workspace of the application and must reflect each
user's role (see spec 002).

## User Stories

- As a regular user, I want to see a list of my assigned cases with their
  deadlines so that I know what requires attention.
- As a regular user, I want to edit editable fields (status, notes) on my
  cases so that I can keep the information current.
- As a supervisor, I want to see cases grouped by team member so that I can
  monitor my team's workload.
- As an admin, I want to see all cases and edit any field (including dates) so
  that I can fix errors.
- As any authenticated user, I want case rows to be colour-coded by deadline
  urgency so that overdue and near-due items stand out immediately.

## Acceptance Criteria

### Backend
- [ ] `GET /api/cases` returns cases filtered by role as described in spec 002
- [ ] Each case object includes: `id`, `title`, `client_name`, `assigned_to`,
      `deadline`, `date_filed`, `status`, `note`, `archived`, `created_at`,
      `updated_at`
- [ ] `GET /api/cases/:id` returns a single case; `404` if not visible to user
- [ ] `POST /api/cases` (admin/supervisor) creates a new case; body must include
      `title`, `assigned_to`, `deadline`
- [ ] `PATCH /api/cases/:id` updates editable fields; date fields restricted to
      admin only (spec 002)
- [ ] `DELETE /api/cases/:id` is not exposed — cases are archived, not deleted
      (see spec 005-archive)
- [ ] All timestamps are stored and returned as ISO 8601 UTC
- [ ] The API rejects a `deadline` value in the past on creation (`400`)

### Frontend
- [ ] The Main page renders a table of cases with columns: title, client,
      assigned to (supervisor/admin view), deadline, status
- [ ] Deadline column uses colour coding:
      - Red — past deadline (overdue)
      - Orange — due within 7 days
      - Green — due in 8+ days
- [ ] Clicking a row opens the inline Editor (spec 004)
- [ ] A "Zakończono" toggle on each row marks status as `closed` and suppresses
      future deadline notifications for that case
- [ ] Supervisors see cases grouped by team member with per-member totals
- [ ] Admins see all cases with a user-filter dropdown

## Out of Scope

- Full-text search across cases (future enhancement)
- Bulk edit / bulk assign
- Case templates
- Attachments (covered separately if needed)

## API Contract

### `GET /api/cases`

**200 OK**
```json
[
  {
    "id": 1,
    "title": "Sprawa emerytalna – Kowalski",
    "client_name": "Jan Kowalski",
    "assigned_to": 3,
    "deadline": "2027-02-10",
    "date_filed": "2026-11-01",
    "status": "open",
    "note": null,
    "archived": false,
    "created_at": "2026-11-01T08:00:00Z",
    "updated_at": "2026-11-15T14:30:00Z"
  }
]
```

---

### `POST /api/cases`

**Request**
```json
{
  "title": "Sprawa rentowa – Nowak",
  "client_name": "Anna Nowak",
  "assigned_to": 5,
  "deadline": "2027-03-01",
  "date_filed": "2026-11-20"
}
```

**201 Created** — full case object  
**400 Bad Request** — missing required fields or deadline in the past  
**403 Forbidden** — regular user tried to create a case

---

### `PATCH /api/cases/:id`

**Request** (all fields optional)
```json
{ "status": "closed", "note": "Sprawa zakończona pomyślnie." }
```

**200 OK** — updated case object  
**403 Forbidden** — permission error (see spec 002)  
**404 Not Found**

## Data Model Changes

New table `cases`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `title` | String(255) | Not null |
| `client_name` | String(255) | Not null |
| `assigned_to` | Integer | FK → `users.id`, not null |
| `deadline` | Date | Not null |
| `date_filed` | Date | Nullable |
| `status` | String | Default `"open"`, values: `open \| closed` |
| `note` | Text | Nullable |
| `archived` | Boolean | Default `False` |
| `created_at` | DateTime | Default UTC now, not null |
| `updated_at` | DateTime | Auto-updated on change |

Indices: `assigned_to`, `deadline`, `archived`.

## Open Questions

- [ ] Should `client_name` be a separate `clients` table for deduplication?
      → Start with inline string; extract later if needed.
- [ ] What is the exact set of editable fields for a supervisor vs. user?
      → To be confirmed before implementation.
