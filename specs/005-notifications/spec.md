# Deadline Notifications

## Goal

Alert users — in a hard-to-miss way — when a case deadline is approaching or
overdue. Notifications appear as popup windows (preferred) with optional
in-app badge counts. All users with access to a case receive the alert;
notifications can be dismissed per case.

## User Stories

- As a regular user, I want a popup notification when a case I'm assigned to
  has a deadline within 7 days so that I don't miss it.
- As a regular user, I want to mark a case as "zakończono" (closed) from the
  notification so that future reminders stop.
- As a supervisor, I want to receive notifications for cases belonging to any
  of my subordinates so that I can monitor the team.
- As a user, I want to dismiss a notification for a specific case so that I
  stop seeing it without closing the case.
- As an admin, I want to configure the global reminder threshold (number of
  days before deadline) so that the team gets timely alerts.

## Acceptance Criteria

### Backend
- [ ] `GET /api/notifications` returns all active (non-dismissed) notifications
      for the requesting user, filtered by their role
- [ ] A notification is generated server-side for every case where
      `deadline - today <= threshold_days` AND `status != "closed"` AND
      `archived = false`
- [ ] Default threshold is 7 days; configurable via admin settings
- [ ] `POST /api/notifications/:case_id/dismiss` marks the notification
      dismissed for the requesting user; does not affect other users' notifications
- [ ] The dismiss is per-user, per-case — stored in a `notification_dismissals`
      junction table
- [ ] Overdue cases (`deadline < today`) generate a separate `overdue`
      notification type
- [ ] `GET /api/notifications` response includes urgency: `upcoming | overdue`

### Frontend
- [ ] On login and on each page load, the client polls `GET /api/notifications`
      (or uses a WebSocket if implemented)
- [ ] Active notifications appear as popup windows on top of the page content
- [ ] Each popup shows: case title, client name, deadline, days remaining
      (or "ZALEGŁE" for overdue)
- [ ] Each popup has a "Zamknij" button (dismiss for this user) and a
      "Zakończ sprawę" button (closes the case)
- [ ] A notification badge in the navigation bar shows the count of active
      notifications
- [ ] After dismissing all notifications, the badge disappears
- [ ] Closed cases generate no further notifications even if deadline has passed

## Out of Scope

- Push notifications (browser/OS level) — future enhancement
- Email or SMS notifications
- Per-user notification thresholds (global threshold only for now)
- Notification history / archive

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
    "urgency": "upcoming"
  },
  {
    "case_id": 7,
    "case_title": "Sprawa ABC",
    "client_name": "Maria Wiśniewska",
    "deadline": "2026-11-10",
    "days_remaining": -10,
    "urgency": "overdue"
  }
]
```

---

### `POST /api/notifications/:case_id/dismiss`

**Headers:** `Authorization: Bearer <jwt>`

**204 No Content** — dismissal recorded  
**404 Not Found** — case not visible to user

## Data Model Changes

New table `notification_dismissals`:

| Column | Type | Constraints |
|---|---|---|
| `user_id` | Integer | FK → `users.id`, not null |
| `case_id` | Integer | FK → `cases.id`, not null |
| `dismissed_at` | DateTime | Default UTC now |

Composite PK: `(user_id, case_id)`.

No new column on `cases` — notification state is derived at query time.

## Open Questions

- [ ] Should notifications persist across browser sessions (server-side) or be
      reset on each login? → Server-side dismiss (implemented via DB table).
- [ ] What is the exact default threshold in days? → 7 days assumed; must be
      confirmed by client.
- [ ] WebSocket vs. polling? → Start with polling every 60 s; upgrade later.
