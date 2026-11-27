# Plan: Deadline Notifications (Spec 005)

## Backend changes

- **Files affected (`apps/api/`):**
  - `models.py` — Add `NotificationDismissal` model (`__tablename__ = "notification_dismissals"`):
    - `user_id` (`Integer`, FK `users.id` named `fk_notif_dismissals_user_id`, PK)
    - `case_id` (`Integer`, FK `cases.id` named `fk_notif_dismissals_case_id`, PK)
    - `deadline_snapshot` (`Date`, PK)
    - `state` (`String(20)`, PK — `"upcoming" | "overdue"`)
    - `dismissed_at` (`DateTime(timezone=True)`, default UTC now, not null)
  - `alembic/versions/<rev>_add_notification_dismissals_table.py` — Migration creating `notification_dismissals` with composite primary key `(user_id, case_id, deadline_snapshot, state)` (SQLite + PostgreSQL compatible).
  - `schemas.py` — Add `NotificationUrgency = Literal["upcoming", "overdue"]` and `NotificationItemResponse` (`case_id`, `case_title`, `client_name`, `assigned_to_email`, `deadline`, `days_remaining`, `urgency`, `version`).
  - `services/notifications.py` *(new)* —
    - `get_today_warsaw() -> date` using `ZoneInfo("Europe/Warsaw")` (with `tzdata` or safe fallback if Windows tz db is missing — note: we should check if `ZoneInfo("Europe/Warsaw")` works on Python 3.14 Windows or needs `tzdata`!).
    - `get_notification_threshold_days(db) -> int` returning `7` (hook for Spec 012 `system_settings`).
    - `list_active_notifications(db, actor) -> list[NotificationItemResponse]` — derives notifications for in-scope open, non-archived cases with `deadline IS NOT NULL` and `(deadline - today_warsaw).days <= threshold`, excludes rows matching `(actor.id, case.id, case.deadline, urgency)` in `notification_dismissals`, sorted `deadline ASC, case_id ASC`.
    - `dismiss_notification(db, actor, case_id) -> None` — loads case via `case_service.get_case_in_scope` (`404` if missing/out-of-scope); verifies case currently qualifies for an active notification (`400` if not); inserts dismissal idempotently (`204`).
    - `clear_case_dismissals(db, case_id) -> None` — helper hook for Spec 006 archive restore.
  - `routers/notifications.py` *(new)* — Thin route handlers:
    - `GET /api/notifications` (`200 OK`)
    - `POST /api/notifications/{case_id}/dismiss` (`204 No Content`)
  - `main.py` — Include `notifications_router`.
- **New dependencies:** Check `tzdata` on Windows for `ZoneInfo("Europe/Warsaw")` (add `tzdata` if needed).
- **Migration needed:** Yes — creates `notification_dismissals`.

## Frontend changes

- **Files affected (`apps/web/src/`):**
  - `api/notifications.ts` *(new)* — Typed API client (`NotificationItem`, `fetchNotificationsRequest`, `dismissNotificationRequest`).
  - `utils/desktopNotifications.ts` *(new)* — Wrapper around `window.Notification`: checks support/permission, requests permission on user click, fires a grouped native Windows toast notification (`new Notification(...)`) and focuses the window on click, degrades cleanly when unsupported/denied.
  - `components/NotificationCenter.tsx` *(new)* — Mounted inside `AppNav` for all authenticated pages:
    - Polls `GET /api/notifications` on mount and every 60 seconds.
    - Renders the navbar **notification bell button + red count badge** (hidden when count is `0`) and dropdown panel listing all active notifications + **"Włącz powiadomienia Windows"** button when `Notification.permission === "default"`.
    - Renders a single scrollable accessible in-app popup modal (`role="alertdialog"`, `aria-modal="true"`) on initial load (and on 60s poll only when a brand-new or newly-escalated-to-`overdue` notification appears), with **"Zamknij"** (dismiss), **"Zakończ sprawę"** (`PATCH /api/cases/:id` with `version` & `status: "closed"`), and **"Ukryj na teraz"** buttons.
    - Fires a native Windows desktop notification when `Notification.permission === "granted"` and new/initial active notifications arrive.
  - `components/AppNav.tsx` — Embed `<NotificationCenter />` in the right navbar section.
  - `App.css` — Styles for the notification bell, count badge, dropdown panel, and scrollable alertdialog popup.

## Test plan

- **New pytest tests (`apps/api/tests/test_notifications.py`):**
  - Role scoping (`user` sees own, `supervisor` sees own + direct subordinates, `admin` sees all).
  - Deadline math in `Europe/Warsaw`: `deadline < today` → `overdue` (`days_remaining < 0`); `deadline == today` → `upcoming` (`days_remaining == 0`); `0 < diff <= 7` → `upcoming`; `diff > 7`, `deadline is None`, `status == "closed"`, `archived == True` → excluded.
  - Sorting `deadline ASC, case_id ASC` and `assigned_to_email` presence.
  - `POST /api/notifications/:case_id/dismiss`:
    - Per-user isolation (dismissing for `user` does not dismiss for `supervisor`).
    - Idempotent repeat dismiss (`204`).
    - Out-of-scope / nonexistent case → `404`.
    - Case without active notification (closed / null deadline / far future) → `400`.
    - Auto-reset when deadline changes (admin edits deadline) OR when state transitions `upcoming` → `overdue`!
    - Non-deadline edit (e.g. changing title) does **not** reset dismissal.
    - `clear_case_dismissals` resets dismissal cleanly (ready for Spec 006).
- **New Vitest tests (`apps/web/src/NotificationCenter.test.tsx`):**
  - Shows bell badge count + opens scrollable `alertdialog` popup on load with Polish dates and `"ZALEGŁE"` / `"Termin dzisiaj"` / `"Za X dni"` labels.
  - Clicking `"Zamknij"` calls `POST /api/notifications/:id/dismiss` and removes the item.
  - Clicking `"Zakończ sprawę"` calls `PATCH /api/cases/:id` with `{ version, status: "closed" }` and removes the item.
  - Native Windows `Notification` API is invoked when `Notification.permission === "granted"` and permission button is shown when `"default"`.

## Risks / Notes

- **Windows timezone data:** Python on Windows requires `tzdata` for `zoneinfo.ZoneInfo("Europe/Warsaw")`. We'll verify in Task 1 and add `tzdata` via `uv add tzdata` if not already installed.
- **Browser Windows notification permission:** Browsers only allow `Notification.requestPermission()` inside a click handler, so we expose a clear **"Włącz powiadomienia Windows"** button inside the popup and bell panel.
