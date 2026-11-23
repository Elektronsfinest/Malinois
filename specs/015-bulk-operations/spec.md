# Bulk Case Actions

## Goal

Allow users, supervisors, and administrators to select multiple cases on `/cases`
or `/archive` and execute batch actions (`set_status`, `archive`, `restore`)
in a single atomic operation while strictly enforcing role permissions,
optimistic locking (`version`), and audit logging.

## User Stories

- As a regular user, I want to select multiple cases assigned to me and mark
  them as closed or archive them simultaneously.
- As a supervisor, I want to select multiple cases across my own and my direct
  subordinates' cases and change status, archive, or restore them at once.
- As an admin, I want to perform batch operations across any selection of cases
  in the system.
- As any user, I want per-row version conflicts reported clearly without
  silently overwriting another colleague's concurrent edit.

## Acceptance Criteria

### Backend
- [ ] `POST /api/cases/bulk` routes every row through the unified case service
      layer (spec 003, spec 011):
  - Actions supported: `set_status`, `archive`, `restore`
  - Body schema:
    `{ "items": [{ "id": 12, "version": 2 }, ...], "action": "set_status", "params": { "status": "closed" } }`
- [ ] **Role & scope validation for every case in `items`:**
  - `user`: all cases must be assigned to the caller (`assigned_to == caller.id`);
    **`restore` is forbidden for regular `user` (`403 Forbidden`)** — matching
    spec 006 and `appbuild.drawio.xml`
  - `supervisor`: all cases must be assigned to the caller or direct
    subordinates; may call `set_status`, `archive`, and `restore`
  - `admin`: may target any case with any supported action
- [ ] **Error & conflict semantics (atomic transaction):**
  - Maximum of **200 items** per request; larger arrays or invalid action/params
    return `400 Bad Request`
  - If any case ID does not exist OR lies outside the caller's visibility scope,
    the entire transaction rolls back and returns **`404 Not Found`** (spec 007)
  - If the caller lacks action permission on an in-scope case (e.g. `user`
    calling `restore`), the entire transaction rolls back and returns
    **`403 Forbidden`**
  - Every row verifies `cases.version == item.version` and increments `version`;
    if one or more rows have stale versions, the transaction rolls back and
    returns **`409 Conflict`** with `conflicts: [{ case_id, expected_version, current_version }]`
    so no concurrent edits are silently overwritten
- [ ] Each changed case appends corresponding entries to `case_edit_log` (spec
      009); bulk `restore` also clears `notification_dismissals` for restored
      cases (spec 005)
- [ ] Date fields (`deadline`, `date_filed`) can never be modified via bulk
      actions

### Frontend
- [ ] `/cases` and `/archive` tables include a checkbox column with descriptive
      `aria-label` and a master "select all on current page" checkbox
- [ ] When ≥ 1 case is selected, a sticky glassmorphic floating action bar
      appears at the bottom showing `"Zaznaczono: X spraw"` and role-appropriate
      buttons:
  - On `/cases`: **"Zmień status"**, **"Archiwizuj"**, **"Przepisz zaznaczone"**
    (supervisor/admin, spec 016), **"Odznacz wszystkie"**
  - On `/archive`: **"Przywróć zaznaczone"** (visible to `supervisor` and
    `admin` only — hidden for regular `user`)
- [ ] Clicking an action opens an accessible confirmation dialog stating the
      affected count; while in flight, buttons show spinners and checkboxes are
      disabled
- [ ] On `409 Conflict`, displays the list of conflicting cases and offers to
      refresh the table; on `200 OK`, refreshes the table and announces
      `"Zaktualizowano X spraw"` in an `aria-live="polite"` toast

## Out of Scope

- Bulk editing of text fields (`title`, `client_name`)
- Bulk modification of `deadline` or `date_filed`
- Selecting cases across multiple pages (applies to current page, max 200 items)

## API Contract

### `POST /api/cases/bulk`

**Headers:** `Authorization: Bearer <jwt>`

**Request Body — set status**
```json
{
  "items": [
    { "id": 12, "version": 2 },
    { "id": 15, "version": 1 },
    { "id": 18, "version": 4 }
  ],
  "action": "set_status",
  "params": { "status": "closed" }
}
```

**Request Body — restore (supervisor / admin only)**
```json
{
  "items": [
    { "id": 12, "version": 3 }
  ],
  "action": "restore"
}
```

**200 OK**
```json
{
  "success": true,
  "affected_count": 3,
  "action": "set_status"
}
```

**400 Bad Request** — unknown action, invalid params, empty list, or > 200 items  
**403 Forbidden** — regular `user` attempted `restore`  
**404 Not Found** — one or more case IDs do not exist or are outside caller's scope  
**409 Conflict** — one or more rows failed optimistic `version` check (`{ "detail": "...", "conflicts": [{ "case_id": 12, "expected_version": 2, "current_version": 3 }] }`)

## Data Model Changes

No new tables. Operates on `cases` (incrementing `version`), appends to
`case_edit_log` (spec 009), and clears `notification_dismissals` on `restore`.

## Resolved Decisions (Indaba Council)

- Bulk `restore` is restricted exclusively to `supervisor` and `admin` (N-04).
- Per-row `{ id, version }` required and verified atomically with `409 Conflict` reporting (N-06).
- Out-of-scope or missing IDs return `404`; forbidden actions on in-scope cases return `403` (N-05).
- Explicitly in scope and cross-referenced from specs 003 and 006 (N-12).
