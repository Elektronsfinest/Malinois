# Edit History

## Goal

Record every change made to a case and make that history visible to users who
have access to the case. This gives supervisors and admins full traceability
over who changed what and when, and allows users to understand the state of a
case without asking colleagues.

## User Stories

- As a regular user, I want to see the edit history of my cases so that I know
  what changed and when.
- As a supervisor, I want to see the edit history of all cases in my team so
  that I can audit changes my subordinates made.
- As an admin, I want to see the full edit history of any case so that I can
  investigate errors or disputes.
- As any user, I want each history entry to show the field that changed, the
  old value, the new value, and who made the change so that the log is
  actionable.

## Acceptance Criteria

### Backend
- [ ] Every `PATCH /api/cases/:id` request appends one or more rows to a
      `case_edit_log` table — one row per changed field
- [ ] Each log entry stores: `case_id`, `user_id`, `field_name`, `old_value`
      (string), `new_value` (string), `changed_at` (UTC datetime)
- [ ] `GET /api/cases/:id/history` returns the edit log for a case in reverse
      chronological order (newest first)
- [ ] The endpoint respects role visibility — a regular user can only see
      history for cases assigned to them; a supervisor sees their team's;
      an admin sees all
- [ ] Log entries are immutable — they cannot be updated or deleted via any API
- [ ] Archiving and restoring a case (`POST /api/cases/:id/archive` and
      `/restore`) also create a log entry with `field_name = "archived"` and
      values `"false" → "true"` / `"true" → "false"`
- [ ] Import via Excel (`POST /api/admin/import`) logs changes at the field
      level for every updated case row

### Frontend
- [ ] The case Editor (inline panel) has a collapsible "Historia zmian" section
      at the bottom
- [ ] Each history entry shows: timestamp (Polish locale), user display name or
      email, field name (human-readable label), old → new value
- [ ] The section is paginated or limited to the 50 most recent entries, with a
      "Pokaż więcej" link
- [ ] Date field changes (`deadline`, `date_filed`) are labelled with an admin
      badge to signal they require elevated privileges

## Out of Scope

- Reverting to a previous value from the history UI (undo is not supported)
- Exporting the audit log to Excel (covered if needed in spec 004 extension)
- Logging read access (`GET` requests)

## API Contract

### `GET /api/cases/:id/history`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK**
```json
[
  {
    "id": 42,
    "field_name": "status",
    "old_value": "open",
    "new_value": "closed",
    "changed_by_email": "jan@example.com",
    "changed_at": "2027-01-15T10:34:00Z"
  },
  {
    "id": 41,
    "field_name": "note",
    "old_value": null,
    "new_value": "Złożono odwołanie.",
    "changed_by_email": "jan@example.com",
    "changed_at": "2027-01-14T08:12:00Z"
  }
]
```

**403 Forbidden** — case not visible to user  
**404 Not Found**

## Data Model Changes

New table `case_edit_log`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `case_id` | Integer | FK → `cases.id`, not null |
| `user_id` | Integer | FK → `users.id`, not null |
| `field_name` | String(100) | Not null |
| `old_value` | Text | Nullable |
| `new_value` | Text | Nullable |
| `changed_at` | DateTime | Default UTC now, not null |

Index: `(case_id, changed_at DESC)`.

## Open Questions

- [ ] Should login audit events (spec 007) be merged into this table or kept
      separate? → Keep separate — `login_audit_log` is a security table;
      `case_edit_log` is a business table.
- [ ] Should field names be stored as internal column names (`date_filed`) or
      translated labels (`Data złożenia`)? → Internal names; translation done
      on the frontend.
