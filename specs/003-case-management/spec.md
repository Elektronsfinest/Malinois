# Case Management

## Goal

Provide the core data model and CRUD operations for client cases (sprawy). Users
can view their assigned cases, see deadlines, and update case metadata through
the inline preliminary editor (`Edytor wstępny`). The case list (`/cases`) is
the primary working table of the application and reflects each user's role
(see spec 002).

## User Stories

- As a regular user, I want to see a list of my assigned cases with their
  deadlines so that I know what requires attention.
- As a regular user, I want to edit non-date fields (title, client name, status)
  on my cases and add notes (spec 010) so that I can keep information current.
- As a supervisor, I want to view and manage my own cases and my direct
  subordinates' cases so that I can monitor my team's workload.
- As an admin, I want to see all cases and edit any field (including dates, with
  a mandatory audit reason) so that I can fix errors.
- As any authenticated user, I want case rows to be colour-coded by deadline
  urgency (driven by the admin notification threshold) so that overdue and
  near-due items stand out immediately.

## Acceptance Criteria

### Backend
- [ ] All case mutations route through a single service layer enforcing role
      scoping, date immutability, optimistic locking (`version`, spec 011), and
      audit logging (spec 009)
- [ ] `GET /api/cases` returns `{ items, total, page, page_size }` filtered by
      role as described in spec 002 (excludes archived cases by default)
- [ ] Each case object includes: `id`, `case_number`, `title`, `client_name`,
      `assigned_to`, `deadline`, `date_filed`, `status`, `archived`, `version`,
      `created_at`, `updated_at` (no `cases.note` column — notes live in
      `case_notes`, spec 010)
- [ ] `GET /api/cases/:id` returns a single case; `404 Not Found` if non-existent
      or outside the caller's visibility scope
- [ ] `POST /api/cases` creates a new case:
  - `admin` may set `deadline` and `date_filed` (including past deadlines for
    overdue records)
  - `supervisor` may create a case for themselves or a direct subordinate, but
    MUST omit or pass `null` for `deadline` and `date_filed` (`403 Forbidden`
    if non-null dates are supplied); an admin populates dates afterward
  - `user` receives `403 Forbidden`
- [ ] `PATCH /api/cases/:id` requires `version` (spec 011), updates editable
      fields, increments `version`, and logs field-level changes (spec 009):
  - `user` and `supervisor` may edit `title`, `client_name`, `status` on
    in-scope cases
  - `admin` may edit all fields including `deadline` and `date_filed`; any
    change to `deadline` or `date_filed` requires a non-empty `reason` string
    (max 500 chars), recorded in `case_edit_log` (spec 009); returns `400` if
    `reason` is missing or blank
- [ ] `DELETE /api/cases/:id` is not exposed — cases are archived, not deleted
      (see spec 006-archive)
- [ ] All timestamps are stored and returned as ISO 8601 UTC; date comparisons
      for "today" / overdue use the `Europe/Warsaw` timezone

### Frontend
- [ ] Main case list lives at `/cases` (Dashboard lives at `/`, spec 014)
- [ ] The `/cases` header includes an **"Import / Edytor pliku"** button routing
      to `/import` (Full Excel Copy Editor, spec 004)
- [ ] The table renders columns: checkbox (spec 015), case number, title,
      client, assigned to (supervisor/admin view), deadline (Polish format
      `DD.MM.YYYY`), status
- [ ] Deadline column uses colour coding + accessible text badge driven by the
      admin-configured `notification_threshold_days` (default `7`, spec 012):
  - Red (`#ef4444`) — strictly past deadline (`deadline < today` in `Europe/Warsaw`)
  - Orange (`#f59e0b`) — due today or within `notification_threshold_days`
  - Green (`#22c55e`) — due beyond `notification_threshold_days`
  - Neutral — `deadline` is `null` (awaiting admin date entry)
- [ ] Clicking a row opens the inline **Edytor wstępny** (Case Editor panel)
      with editable fields, Notes section (spec 010), and collapsible Edit
      History (spec 009)
- [ ] A "Zakończono" toggle on each row marks status as `closed` (sending
      `version`) and suppresses future deadline notifications for that case
- [ ] When an admin creates a case with a past deadline, a non-blocking warning
      banner informs them the case will immediately be marked overdue
- [ ] When an admin modifies `deadline` or `date_filed`, the UI requires a
      non-empty "Powód zmiany daty" input before submitting
- [ ] Supervisor per-member totals are displayed via `GET /api/dashboard/summary`
      (spec 014); `/cases` supports filtering by self or any direct subordinate
      (spec 013)

## Out of Scope

- Case templates
- Binary file attachments on individual cases (covered separately if needed)
- Bulk actions and reassignment are specified in **spec 015-bulk-operations**
  and **spec 016-case-reassignment**

## API Contract

### `GET /api/cases`

**200 OK**
```json
{
  "items": [
    {
      "id": 1,
      "case_number": "CASE-2027-0001",
      "title": "Sprawa emerytalna – Kowalski",
      "client_name": "Jan Kowalski",
      "assigned_to": 3,
      "deadline": "2027-02-10",
      "date_filed": "2026-11-01",
      "status": "open",
      "archived": false,
      "version": 2,
      "created_at": "2026-11-01T08:00:00Z",
      "updated_at": "2026-11-15T14:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

---

### `POST /api/cases`

**Request (admin)**
```json
{
  "case_number": "CASE-2027-0002",
  "title": "Sprawa rentowa – Nowak",
  "client_name": "Anna Nowak",
  "assigned_to": 5,
  "deadline": "2027-03-01",
  "date_filed": "2026-11-20"
}
```

**Request (supervisor — dates must be null or omitted)**
```json
{
  "title": "Sprawa rentowa – Nowak",
  "client_name": "Anna Nowak",
  "assigned_to": 5,
  "deadline": null,
  "date_filed": null
}
```

**201 Created** — full case object (`version: 1`)  
**400 Bad Request** — missing required fields or duplicate `case_number`  
**403 Forbidden** — regular user tried to create a case, supervisor assigned outside team, or non-admin supplied non-null `deadline`/`date_filed`

---

### `PATCH /api/cases/:id`

**Request (user / supervisor)**
```json
{
  "version": 2,
  "status": "closed"
}
```

**Request (admin changing a date)**
```json
{
  "version": 2,
  "deadline": "2027-03-15",
  "reason": "Korekta pomyłki pisarskiej z importu Excel"
}
```

**200 OK** — updated case object (`version: 3`)  
**400 Bad Request** — admin changed a date without non-empty `reason`  
**403 Forbidden** — non-admin attempted to modify `deadline`/`date_filed`  
**404 Not Found** — case does not exist or is outside caller's scope  
**409 Conflict** — `version` mismatch (see spec 011)

## Data Model Changes

New table `cases`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `case_number` | String(100) | Nullable, unique, indexed |
| `title` | String(255) | Not null, indexed |
| `client_name` | String(255) | Not null, indexed |
| `assigned_to` | Integer | FK → `users.id`, not null, indexed |
| `deadline` | Date | Nullable (admin-only write), indexed |
| `date_filed` | Date | Nullable (admin-only write) |
| `status` | String(20) | Default `"open"`, values: `open \| closed` |
| `archived` | Boolean | Default `False`, indexed |
| `version` | Integer | Not null, `server_default="1"` |
| `created_at` | DateTime | Default UTC now, not null |
| `updated_at` | DateTime | Auto-updated on change |

## Resolved Decisions (Indaba Council)

- `cases.note` removed; immutable `case_notes` (spec 010) is the sole note store (N-10).
- Only `admin` writes `deadline`/`date_filed`, including on creation; date edits require `reason` (N-07).
- Past deadlines allowed on admin creation (with UI warning) and import (N-08).
- Main table route is `/cases`; urgency threshold uses `notification_threshold_days` (N-15).
- `GET /api/cases` returns `{ items, total, page, page_size }` (N-14).
