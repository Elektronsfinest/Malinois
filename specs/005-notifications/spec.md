# Deadline Notifications

## Goal

Alert users — in a hard-to-miss way — when a case deadline is approaching or
overdue. Notifications appear as in-app popup windows on login/refresh and in a
navigation-bar notification bell panel. All users with direct responsibility
for a case (the assignee and their direct supervisor) receive the alert;
notifications can be dismissed per user and automatically reactivate if the
deadline changes, transitions from upcoming to overdue, or if the case is
restored from archive.

## User Stories

- As a regular user, I want a popup notification when a case I'm assigned to
  has a deadline within the configured threshold so that I don't miss it.
- As a regular user, I want to mark a case as "zakończono" (closed) from the
  notification so that future reminders stop.
- As a supervisor, I want to receive notifications for my own cases and all
  cases belonging to my direct subordinates so that I can monitor the team.
- As a user, I want to dismiss a notification for a specific case so that I
  stop seeing it until its deadline changes or it becomes overdue.
- As an admin, I want to configure the global reminder threshold
  (`notification_threshold_days`, default 7) so that the team gets timely alerts.

## Acceptance Criteria

### Backend
- [ ] `GET /api/notifications` returns all active (non-dismissed) notifications
      for the requesting user, filtered by their role (spec 002: `user` = own;
      `supervisor` = own + direct subordinates; `admin` = all)
- [ ] A notification is derived at query time for every case where:
  - `deadline IS NOT NULL`
  - `deadline - today_warsaw <= notification_threshold_days` (where
    `today_warsaw` is the current date in `Europe/Warsaw` timezone)
  - `status != "closed"` AND `archived = false`
- [ ] Urgency classification (`state`):
  - `overdue`: strictly `deadline < today_warsaw`
  - `upcoming`: `today_warsaw <= deadline <= today_warsaw + threshold_days`
    (a deadline equal to today is `upcoming` / "Termin dzisiaj", not overdue)
- [ ] Default threshold is `7` days; configurable via `PATCH /api/admin/settings`
      (`notification_threshold_days`, spec 012)
- [ ] `POST /api/notifications/:case_id/dismiss` records a dismissal for the
      requesting user keyed on `(user_id, case_id, deadline_snapshot, state)`:
  - Does not affect other users' notifications
  - Automatically resets (stops matching) if the case's `deadline` changes or
    if its `state` transitions from `upcoming` to `overdue`
  - Routine non-deadline edits (e.g. title, client name, notes) do **not**
    reset an active dismissal (resolving "oprócz edycji?" in `appbuild`)
  - Restoring a case from archive (spec 006) deletes prior dismissals for that
    case so notifications reactivate if the deadline is still within threshold
- [ ] `POST /api/notifications/:case_id/dismiss` returns `404 Not Found` if the
      case does not exist or is outside the caller's visibility scope (spec 007)

### Frontend
- [ ] On login and on each page load (plus 60-second polling), the client
      fetches `GET /api/notifications`
- [ ] Active notifications appear as accessible in-app popup windows (`role="alertdialog"`)
      and are also listed in the navigation bar notification bell panel
- [ ] Each popup shows: case title, client name, deadline (Polish format
      `DD.MM.YYYY`), days remaining (or `"Termin dzisiaj"` / `"ZALEGŁE"`)
- [ ] Each popup has a **"Zamknij"** button (dismiss for this user) and a
      **"Zakończ sprawę"** button (marks `status = "closed"` with `version`)
- [ ] A notification bell badge in the navigation bar shows the count of active
      notifications; disappears when count is `0`
- [ ] Closed or archived cases generate no notifications

## Out of Scope

- Browser/OS push notifications
- Email or SMS notifications
- Notification sound toggles (excluded per spec 008)
- Notifications for routine case edits (only deadline upcoming/overdue)
- Per-user notification thresholds (global admin setting only)

## API Contract

### `GET /api/notifications`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK**
```json
[
  {
    "case_id": 4,
    "case_title": "Sprawa XYZ",
    "client_name": "Jan Kowalski",
    "deadline": "2027-01-20",
    "days_remaining": 3,
    "urgency": "upcoming",
    "version": 2
  },
  {
    "case_id": 7,
    "case_title": "Sprawa ABC",
    "client_name": "Maria Wiśniewska",
    "deadline": "2026-11-10",
    "days_remaining": -10,
    "urgency": "overdue",
    "version": 5
  }
]
```

---

### `POST /api/notifications/:case_id/dismiss`

**Headers:** `Authorization: Bearer <jwt>`

**204 No Content** — dismissal recorded for current `(deadline, urgency)`  
**404 Not Found** — case does not exist or is outside the caller's scope

## Data Model Changes

New table `notification_dismissals`:

| Column | Type | Constraints |
|---|---|---|
| `user_id` | Integer | FK → `users.id`, not null |
| `case_id` | Integer | FK → `cases.id`, not null |
| `deadline_snapshot` | Date | Not null |
| `state` | String(20) | Not null (`upcoming` \| `overdue`) |
| `dismissed_at` | DateTime | Default UTC now, not null |

Composite PK: `(user_id, case_id, deadline_snapshot, state)`.

No new column on `cases` — notification state is derived at query time.

## Resolved Decisions (Indaba Council)

- "Wielu użytkowników" notifies both the assignee and their direct supervisor (N-09).
- Dismissal key `(user_id, case_id, deadline_snapshot, state)` resets on deadline change, `upcoming -> overdue`, or archive-then-restore, but not on routine edits (N-11).
- Strictly `Europe/Warsaw` timezone; `deadline < today` is overdue (N-16).
- Channels limited to in-app popup + bell panel (N-11).
