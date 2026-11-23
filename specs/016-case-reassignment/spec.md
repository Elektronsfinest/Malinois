# Case Reassignment & Substitutions

## Goal

Allow supervisors and administrators to reassign cases between team members
(e.g. during sick leave, vacation, or workload balancing) while maintaining a
permanent `case_assignment_history` table so past assignees retain read-only
access in the Archive (spec 006) and every transfer is audited.

## User Stories

- As a supervisor, I want to transfer cases from an absent subordinate (or
  myself) to another active direct subordinate so that deadlines are not missed.
- As a supervisor, I want the assignee picker restricted to myself and my
  direct subordinates so that I cannot reassign cases outside my team.
- As an admin, I want to reassign any case to any active user across the
  organisation.
- As any user viewing a case or archive, I want to see who previously handled
  the case and why it was reassigned.

## Acceptance Criteria

### Backend
- [ ] `POST /api/cases/reassign` accepts per-row `{ "items": [{ "id": 4, "version": 2 }, ...] }`,
      `new_assigned_to` (user ID), and optional `reason` (max 500 chars)
- [ ] **Permission enforcement:**
  - `user`: cannot reassign cases (`403 Forbidden`)
  - `supervisor`: all targeted cases must be assigned to the supervisor or a
    direct subordinate (`404 Not Found` if any case does not exist or is outside
    scope), and `new_assigned_to` must be the supervisor or an active direct
    subordinate (`403 Forbidden` if target is outside their team)
  - `admin`: can reassign any existing case (`404` if missing) to any active user
- [ ] Target user must exist and have `is_active = true`; returns `400 Bad Request`
      otherwise
- [ ] **Optimistic locking & atomicity (spec 011):**
  - Executes inside a single DB transaction through the unified case service
    layer
  - Verifies `cases.version == item.version` for every row and increments
    `version`; any mismatch rolls back and returns **`409 Conflict`** with
    `conflicts: [{ case_id, expected_version, current_version }]`
- [ ] For each reassigned case:
  - Appends a row to `case_assignment_history` (`case_id`, `from_user_id`,
    `to_user_id`, `changed_by_id`, `reason`, `reassigned_at`) — used by spec
    006 Archive for past-assignee read-only visibility
  - Appends an entry to `case_edit_log` (spec 009) with `field_name = "assigned_to"`,
    `old_value = <previous_user_id>`, `new_value = <new_user_id>`,
    `reason = <reason>`
  - If `reason` is provided, appends an automated `case_notes` row (spec 010):
    `"Przepisano sprawę na <nowy_użytkownik>. Powód: <powód>"`
- [ ] Maximum of 200 items per request (`400` if exceeded)

### Frontend
- [ ] In the inline Case Editor (spec 003), `supervisor` and `admin` see a
      **"Przepisz sprawę"** button
- [ ] In the `/cases` floating bulk bar (spec 015), `supervisor` and `admin`
      see a **"Przepisz zaznaczone"** button
- [ ] Reassignment modal shows:
  - Dropdown of eligible active users (supervisor: self + direct subordinates;
    admin: all active users)
  - Optional text input: `"Powód przepisania (np. zastępstwo, urlop)"`
  - **"Zatwierdź przepisanie"** button
- [ ] Upon `200 OK`, table refreshes with updated assignee; on `409 Conflict`,
      shows conflicting cases and prompts refresh
- [ ] Regular `user` role never sees reassignment controls

## Out of Scope

- Automatic round-robin assignment
- Time-limited temporary delegation with automatic revert

## API Contract

### `POST /api/cases/reassign`

**Headers:** `Authorization: Bearer <jwt>` (supervisor or admin only)

**Request Body**
```json
{
  "items": [
    { "id": 4, "version": 2 },
    { "id": 7, "version": 5 }
  ],
  "new_assigned_to": 3,
  "reason": "Zastępstwo – urlop wypoczynkowy do 28.02"
}
```

**200 OK**
```json
{
  "success": true,
  "reassigned_count": 2,
  "new_assigned_to": 3,
  "new_assigned_to_email": "anna@example.com"
}
```

**400 Bad Request** — target user inactive/missing or > 200 items  
**403 Forbidden** — caller is `user`, or supervisor chose a target outside their team  
**404 Not Found** — one or more case IDs do not exist or are outside caller's scope  
**409 Conflict** — one or more rows failed optimistic `version` check

## Data Model Changes

New table `case_assignment_history`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `case_id` | Integer | FK → `cases.id`, not null, indexed |
| `from_user_id` | Integer | FK → `users.id`, not null, indexed |
| `to_user_id` | Integer | FK → `users.id`, not null, indexed |
| `changed_by_id` | Integer | FK → `users.id`, not null |
| `reason` | String(500) | Nullable |
| `reassigned_at` | DateTime | Default UTC now, not null |

Also modifies `cases.assigned_to` + `cases.version`, appends to `case_edit_log`
(spec 009), and optionally creates `case_notes` (spec 010).

## Resolved Decisions (Indaba Council)

- `case_assignment_history` table added to back past-assignee archive visibility (N-13).
- Per-row `{ id, version }` checked and incremented atomically with `409` conflict reporting (N-06).
- Out-of-scope cases return `404`; out-of-team target or `user` role returns `403` (N-05).
