# Case Archive

## Goal

Allow cases to be archived (soft-deleted) instead of permanently removed.
Regular users can archive their own cases; supervisors and admins can restore
archived cases. Archived cases are hidden from `/cases` by default and remain
accessible in a dedicated Archive page (`/archive`), including read-only
visibility for users who were previously assigned to the case.

## User Stories

- As a regular user, I want to archive a case that is no longer active so that
  my main view stays clean without losing the record.
- As a user, I want to browse archived cases that are currently assigned to me
  or were previously assigned to me so that I can reference historical work.
- As a supervisor, I want to restore an archived case belonging to me or my
  direct subordinates so that it re-appears in the active case list.
- As an admin, I want to see all archived cases and restore any of them so that
  no data is permanently lost.

## Acceptance Criteria

### Backend
- [ ] `POST /api/cases/:id/archive` requires `{ "version": <int> }` (spec 011),
      sets `archived = true`, increments `version`, and logs `field_name = "archived"`
      in `case_edit_log` (spec 009):
  - Allowed for the current assignee, their direct supervisor, or an admin
  - Returns `404 Not Found` if case does not exist or is out of scope
  - Returns `409 Conflict` on `version` mismatch
- [ ] `POST /api/cases/:id/restore` requires `{ "version": <int> }` (spec 011),
      sets `archived = false`, increments `version`, clears prior
      `notification_dismissals` for the case (spec 005) so active deadlines
      re-notify, and logs `field_name = "archived"` in `case_edit_log` (spec 009):
  - Restricted exclusively to `supervisor` (own + direct subordinates' cases)
    and `admin`
  - Returns `403 Forbidden` if a regular `user` attempts to restore an in-scope
    case
  - Returns `404 Not Found` if case does not exist or is out of scope
  - Returns `409 Conflict` on `version` mismatch
- [ ] `GET /api/cases` excludes archived cases by default (`archived=false`)
- [ ] `GET /api/cases?archived=true` returns `{ items, total, page, page_size }`
      (consistent with spec 013) filtered by archive visibility rules:
  - `user`: cases where `assigned_to == current_user.id` OR `current_user.id`
    appears as a past assignee in `case_assignment_history` (spec 016); past
    assignees have **read-only** access
  - `supervisor`: own archived cases + direct subordinates' archived cases
    (current or past assignees)
  - `admin`: all archived cases
- [ ] Archiving hides notifications at query time (spec 005); no stale
      dismissal rows block reactivation upon restore

### Frontend
- [ ] The Archive page (`/archive`) is accessible from main navigation for all
      roles
- [ ] Archive page renders a paginated table matching `/cases` filtered to
      `archived=true`
- [ ] An **"Archiwizuj"** button appears on each active case row (sending
      `version`)
- [ ] The Archive page shows a **"Przywróć"** (Restore) button visible to
      `supervisor` and `admin` roles only (never shown to regular `user`)
- [ ] Past-assignee archived cases display a read-only indicator
- [ ] Archived cases show no deadline notification badge

## Out of Scope

- Permanent deletion (cases are never hard-deleted)
- Scheduled auto-archiving based on closure date
- Bulk archive / bulk restore are covered in **spec 015-bulk-operations**
  (where bulk `restore` is likewise restricted to `supervisor` and `admin`)

## API Contract

### `POST /api/cases/:id/archive`

**Headers:** `Authorization: Bearer <jwt>`

**Request**
```json
{ "version": 3 }
```

**200 OK** — updated case object (`archived: true`, `version: 4`)  
**404 Not Found** — case does not exist or is outside caller's scope  
**409 Conflict** — `version` mismatch (returns latest `current` case object)

---

### `POST /api/cases/:id/restore`

**Headers:** `Authorization: Bearer <jwt>` (supervisor or admin only)

**Request**
```json
{ "version": 4 }
```

**200 OK** — updated case object (`archived: false`, `version: 5`)  
**403 Forbidden** — regular `user` tried to restore  
**404 Not Found** — case does not exist or is outside caller's scope  
**409 Conflict** — `version` mismatch (returns latest `current` case object)

---

### `GET /api/cases?archived=true`

Returns `{ items, total, page, page_size }` filtered by archive visibility rules.

## Data Model Changes

No new tables. Uses `cases.archived` (spec 003), `cases.version` (spec 011),
and `case_assignment_history` (spec 016).

## Resolved Decisions (Indaba Council)

- Both single and bulk restore are restricted to `supervisor` and `admin` (N-04).
- Archive and restore require `version` and increment it (N-06).
- Archive visibility includes past assignees from `case_assignment_history` with read-only access (N-13).
- Restore clears `notification_dismissals` for that case so notifications reactivate cleanly (N-11).
- Bulk archive/restore cross-referenced to spec 015 (N-12).
