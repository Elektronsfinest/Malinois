# Edit History & Audit Log

## Goal

Record every change made to a case (`case_edit_log`) and every administrative
security/permission action (`admin_audit_log`). Case history is visible to
users who have access to the case; admin audit logs are visible to admins in
the Admin Panel's Audit Log tab (spec 012). This ensures full traceability over
who changed what, when, and why.

## User Stories

- As a regular user, I want to see the edit history of my cases so that I know
  what changed and when.
- As a supervisor, I want to see the edit history of my own and my direct
  subordinates' cases so that I can audit changes in my team.
- As an admin, I want to see the full edit history of any case — including the
  mandatory reason for every date change — so that I can investigate errors.
- As an admin, I want an immutable audit log of permission changes (role,
  supervisor, activation, password reset) and backup downloads so that security
  actions are traceable.

## Acceptance Criteria

### Backend — Case Edit Log
- [ ] Every case mutation (`PATCH /api/cases/:id`, archive/restore, bulk
      actions, reassignment, Excel import commit) appends one row per changed
      field to `case_edit_log`
- [ ] Each row stores: `case_id`, `user_id`, `field_name`, `old_value`
      (string), `new_value` (string), `reason` (nullable string; **required**
      when `field_name` is `deadline` or `date_filed` per spec 003),
      `changed_at` (UTC datetime)
- [ ] `GET /api/cases/:id/history` returns the edit log for a case in reverse
      chronological order (newest first), supporting `?limit=50&offset=0`
- [ ] Visibility matches spec 002 / spec 006 (including past assignees on
      archived cases); returns `404 Not Found` if the case does not exist or is
      outside the caller's scope (spec 007)
- [ ] Log entries are strictly immutable — no update or delete endpoint exists
- [ ] Archiving and restoring create a log entry with `field_name = "archived"`
      and values `"false" → "true"` / `"true" → "false"`
- [ ] Reassignment creates a log entry with `field_name = "assigned_to"`
- [ ] Excel import commits (spec 004) log field-level changes for every updated
      case row

### Backend — Admin Audit Log
- [ ] New immutable table `admin_audit_log` records all administrative security
      and permission actions:
  - `user_created`, `role_changed`, `supervisor_changed`, `user_activated`,
    `user_deactivated`, `password_reset`, `settings_updated`,
    `excel_template_updated`, `backup_downloaded`
- [ ] `GET /api/admin/audit-log` (`admin` only; `403` for others) returns
      paginated `{ items, total, page, page_size }` ordered newest first, with
      optional `?action=` and `?target_user_id=` filters

### Frontend
- [ ] The inline Case Editor (spec 003) has a collapsible **"Historia zmian"**
      section at the bottom
- [ ] Each entry shows: timestamp (Polish locale `DD.MM.YYYY, HH:mm`), user
      email, translated field label, `old → new` value, and `reason` (if
      present)
- [ ] Paginated in batches of 50 with a **"Pokaż więcej"** button
- [ ] Date field changes (`deadline`, `date_filed`) display an admin badge plus
      the recorded reason
- [ ] Admin Panel's **Dziennik audytu** tab (spec 012) displays
      `admin_audit_log` entries with action filter and pagination

## Out of Scope

- Reverting to a previous value from the history UI (undo is not supported)
- Logging read-only `GET` requests
- Logging `case_notes` inside `case_edit_log` (notes are their own immutable
  entity in spec 010)

## API Contract

### `GET /api/cases/:id/history`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK**
```json
[
  {
    "id": 42,
    "field_name": "deadline",
    "old_value": "2027-02-10",
    "new_value": "2027-02-20",
    "reason": "Korekta pomyłki z importu",
    "changed_by_email": "admin@example.com",
    "changed_at": "2027-01-15T10:34:00Z"
  },
  {
    "id": 41,
    "field_name": "status",
    "old_value": "open",
    "new_value": "closed",
    "reason": null,
    "changed_by_email": "jan@example.com",
    "changed_at": "2027-01-14T08:12:00Z"
  }
]
```

**404 Not Found** — case does not exist or is outside caller's scope

---

### `GET /api/admin/audit-log`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**200 OK**
```json
{
  "items": [
    {
      "id": 10,
      "actor_email": "admin@example.com",
      "action": "role_changed",
      "target_user_id": 4,
      "details": { "old_role": "user", "new_role": "supervisor" },
      "created_at": "2027-01-15T11:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

**403 Forbidden** — not admin

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
| `reason` | String(500) | Nullable (required for date edits) |
| `changed_at` | DateTime | Default UTC now, not null |

Index: `(case_id, changed_at DESC)`.

New table `admin_audit_log`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `actor_id` | Integer | FK → `users.id`, not null |
| `action` | String(50) | Not null, indexed |
| `target_user_id` | Integer | FK → `users.id`, nullable |
| `details` | JSON | Nullable |
| `created_at` | DateTime | Default UTC now, not null, indexed |

## Resolved Decisions (Indaba Council)

- Admin date changes record mandatory `reason` in `case_edit_log` (N-07).
- `cases.note` removed; notes live exclusively in `case_notes` (N-10).
- Admin permission mutations (`role`, `supervisor_id`, `is_active`, password reset) and backup downloads are logged in `admin_audit_log` (N-22, N-23).
- Out-of-scope cases return `404` (N-05).
