# Case Reassignment & Substitutions

## Goal

Allow supervisors and administrators to reassign cases between team members,
such as when an employee is on sick leave, vacation, or when workload balancing
is required. The system tracks reassignment history and ensures cases never fall
outside supervisor oversight.

## User Stories

- As a supervisor, I want to transfer cases from an absent subordinate to an
  active team member so that statutory deadlines are not missed.
- As a supervisor, I want to see a filtered list of only my direct subordinates
  when choosing a new assignee so that I cannot assign cases outside my team.
- As an admin, I want to reassign any case across any department or team.
- As a regular user, I want to see which cases were newly reassigned to me so
  that I can prioritize them immediately.
- As any user viewing a case, I want to see who previously handled the case and
  why it was reassigned.

## Acceptance Criteria

### Backend
- [ ] `POST /api/cases/reassign` accepts an array of `case_ids`, a `new_assigned_to`
      user ID, and an optional `reason` string (max 500 chars)
- [ ] Permission enforcement:
  - `user`: cannot reassign cases (`403 Forbidden`)
  - `supervisor`: can only reassign cases currently assigned to themselves or
    direct subordinates, and target user must be another direct subordinate or
    the supervisor themselves
  - `admin`: can reassign any case to any active user
- [ ] Target user must exist and have `is_active = true`; otherwise returns `400`
- [ ] Entire reassignment executes in a single database transaction
- [ ] Each reassigned case logs a change in `case_edit_log` (spec 009) with:
  - `field_name = "assigned_to"`
  - `old_value = <previous_user_id>`
  - `new_value = <new_user_id>`
- [ ] If a `reason` was provided, an automated note (spec 010) is added to each
      case: `"Przepisano sprawę na <nowy_użytkownik>. Powód: <powód>"`

### Frontend
- [ ] In the case Editor, supervisors and admins see a "Przepisz sprawę" action
- [ ] In the Main table floating bulk bar (spec 015), supervisors and admins see
      a "Przepisz zaznaczone" button
- [ ] Clicking "Przepisz" opens a modal:
  - Dropdown to select the target employee (supervisors see their team; admins see all)
  - Optional text input: "Powód przepisania (np. zastępstwo, urlop)"
  - "Zatwierdź przepisanie" button
- [ ] Upon successful reassignment, the table updates and reflects the new assignee
- [ ] Regular users do not see reassignment buttons or controls

## Out of Scope

- Automatic rule-based round-robin assignment (cases are assigned manually or via Excel)
- Time-limited temporary delegation with auto-revert (reversion is performed manually)

## API Contract

### `POST /api/cases/reassign`

**Headers:** `Authorization: Bearer <jwt>` (supervisor or admin only)

**Request Body**
```json
{
  "case_ids": [4, 7],
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

**400 Bad Request** — target user inactive or missing  
**403 Forbidden** — caller is not supervisor/admin or target is outside team  
**404 Not Found** — case IDs not found  

## Data Model Changes

No new database tables required. Modifies `cases.assigned_to`, creates
`case_edit_log` entries (spec 009), and optionally creates `case_notes` (spec 010).
