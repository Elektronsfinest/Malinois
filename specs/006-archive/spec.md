# Case Archive

## Goal

Allow cases to be archived (soft-deleted) instead of permanently removed.
Regular users can archive their own cases; supervisors can restore archived
cases belonging to their team. Archived cases are hidden from the main view
but remain accessible in a dedicated Archive page.

## User Stories

- As a regular user, I want to archive a case that is no longer active so that
  my main view stays clean without losing the record.
- As a user, I want to browse my own archived cases so that I can reference
  historical work.
- As a supervisor, I want to restore an archived case belonging to my team so
  that it re-appears in the active case list.
- As an admin, I want to see all archived cases and restore any of them so that
  no data is permanently lost.

## Acceptance Criteria

### Backend
- [ ] `POST /api/cases/:id/archive` sets `archived = true` on the case; only
      the assigned user, their supervisor, or an admin may archive a case
- [ ] `GET /api/cases` excludes archived cases by default
- [ ] `GET /api/cases?archived=true` returns only archived cases visible to
      the user (by role rules from spec 002)
- [ ] `POST /api/cases/:id/restore` sets `archived = false`; only supervisors
      and admins may call this endpoint (`403` for regular users)
- [ ] Archiving a case automatically dismisses all pending notifications for
      that case across all users

### Frontend
- [ ] The Archive page is accessible from the main navigation for all roles
- [ ] Archive page renders a table identical to the Main page but filtered to
      archived cases only
- [ ] Regular users see only their own archived cases; supervisors see their
      team's; admins see all
- [ ] An "Archiwizuj" button appears on each active case row (for users with
      permission)
- [ ] The Archive page shows a "Przywróć" (Restore) button — visible to
      supervisors and admins only
- [ ] Archived cases show no deadline notification badge

## Out of Scope

- Permanent deletion (cases are never hard-deleted)
- Bulk archive / bulk restore
- Scheduled auto-archiving based on closure date

## API Contract

### `POST /api/cases/:id/archive`

**Headers:** `Authorization: Bearer <jwt>`

**204 No Content** — archived  
**403 Forbidden** — user lacks permission  
**404 Not Found**

---

### `POST /api/cases/:id/restore`

**Headers:** `Authorization: Bearer <jwt>` (supervisor or admin)

**204 No Content** — restored  
**403 Forbidden** — regular user tried to restore  
**404 Not Found**

---

### `GET /api/cases?archived=true`

Returns archived cases filtered by role. Same schema as `GET /api/cases`.

## Data Model Changes

No new tables. The `archived` boolean column is already defined in spec 003.

## Open Questions

- [ ] Should archiving require a reason/comment? → No for now.
- [ ] Should restored cases re-activate notifications? → Yes, if deadline is
      still within threshold.
