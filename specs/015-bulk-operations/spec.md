# Bulk Case Actions

## Goal

Allow users, supervisors, and administrators to select multiple cases from the
case list and execute batch actions (status change, archive, restore) in a
single operation. With hundreds of cases imported from Excel, performing updates
one case at a time is slow and error-prone.

## User Stories

- As a regular user, I want to select multiple cases assigned to me and mark
  them as closed simultaneously when a batch of tasks is finished.
- As a supervisor, I want to select multiple cases across my team and archive
  them at once after reviewing.
- As an admin, I want to perform batch operations across any selection of cases
  in the system without opening each case individually.
- As any user, I want clear feedback on how many cases were successfully
  updated and whether any failed.

## Acceptance Criteria

### Backend
- [ ] `POST /api/cases/bulk` performs the specified action on an array of case IDs:
  - Actions supported: `set_status`, `archive`, `restore`
  - Body schema: `{ "case_ids": [1, 2, ...], "action": "set_status", "params": { "status": "closed" } }`
- [ ] Validates caller permissions for *every* case in the `case_ids` array:
  - `user`: all cases must be assigned to the caller
  - `supervisor`: all cases must be assigned to the caller or direct subordinates
  - `admin`: may target any case
- [ ] Entire batch executes within a single database transaction:
  - If the caller lacks permission for any case in the list, the entire request
    is rejected with `403 Forbidden` and no changes are committed
  - If any case ID does not exist, rejected with `404 Not Found` and no changes
    are committed
- [ ] Maximum of 200 cases per bulk request; larger arrays receive `400 Bad Request`
- [ ] Each changed case creates corresponding audit entries in `case_edit_log`
      (spec 009) recording the field changes and the acting user
- [ ] Date fields (`deadline`, `date_filed`) cannot be modified via bulk actions

### Frontend
- [ ] The Main case table includes a checkbox column as the first column
- [ ] The table header contains a "select all on current page" master checkbox
- [ ] When 1 or more cases are selected, a sticky floating action bar appears
      at the bottom of the screen showing:
  - "Zaznaczono: X spraw"
  - Action buttons: "Zmień status", "Archiwizuj", "Odznacz wszystkie"
- [ ] Clicking an action button opens a confirmation dialog stating the number
      of affected cases before submitting
- [ ] While the bulk request is in flight, the action buttons show loading spinners
      and checkboxes are disabled
- [ ] On success, the table refreshes and a notification toast displays
      "Zaktualizowano X spraw"

## Out of Scope

- Bulk editing of text fields (`title`, `client_name`)
- Bulk modification of deadlines or filing dates
- Selecting all cases across multiple pages (bulk action applies only to the
  current selected page, max 200 items)

## API Contract

### `POST /api/cases/bulk`

**Headers:** `Authorization: Bearer <jwt>`

**Request Body — set status**
```json
{
  "case_ids": [12, 15, 18],
  "action": "set_status",
  "params": {
    "status": "closed"
  }
}
```

**Request Body — archive**
```json
{
  "case_ids": [12, 15, 18],
  "action": "archive"
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

**400 Bad Request** — unknown action, invalid params, or more than 200 IDs  
**403 Forbidden** — caller lacks permissions on one or more requested cases  
**404 Not Found** — one or more case IDs do not exist  

## Data Model Changes

No new database tables required. Operates on the existing `cases` table and appends
rows to `case_edit_log` (spec 009).
