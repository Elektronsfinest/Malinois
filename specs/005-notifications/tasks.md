# Tasks: Deadline Notifications (Spec 005)

## Task 1 — Add `NotificationDismissal` model, `tzdata` check, and Alembic migration
**What:** Verify `ZoneInfo("Europe/Warsaw")` (installing `tzdata` if needed), add `NotificationDismissal` (`notification_dismissals` composite PK table) to `models.py`, and generate + verify the Alembic migration (`upgrade` → `downgrade -1` → `upgrade`).  
**Files:** `apps/api/pyproject.toml`, `apps/api/models.py`, `apps/api/alembic/versions/<rev>_add_notification_dismissals_table.py`  
**Done when:** `uv run alembic upgrade head`, `downgrade -1`, and `upgrade head` succeed cleanly and `ZoneInfo("Europe/Warsaw")` works.

## Task 2 — Build notification schemas, `services/notifications.py`, and `routers/notifications.py`
**What:** Add `NotificationItemResponse` in `schemas.py`, implement `services/notifications.py` (`Europe/Warsaw` date derivation, role scoping, composite-key dismissal, idempotency, `clear_case_dismissals` hook), and mount `GET /api/notifications` + `POST /api/notifications/{case_id}/dismiss` in `main.py`.  
**Files:** `apps/api/schemas.py`, `apps/api/services/notifications.py`, `apps/api/routers/notifications.py`, `apps/api/main.py`  
**Depends on:** Task 1.  
**Done when:** Notification endpoints are mounted in FastAPI.

## Task 3 — Backend notifications test suite (`tests/test_notifications.py`)
**What:** Write comprehensive pytest tests covering role scoping, `Europe/Warsaw` urgency classification, per-user dismissal isolation, idempotency, `404`/`400` errors, auto-reset on deadline change & `upcoming → overdue` transition, and non-reset on routine edits.  
**Files:** `apps/api/tests/test_notifications.py`  
**Depends on:** Task 2.  
**Done when:** `uv run pytest` passes 100% of backend tests.

## Task 4 — Frontend notifications API, Windows desktop Notification helper, and `NotificationCenter`
**What:** Create `src/api/notifications.ts`, `src/utils/desktopNotifications.ts` (Web Notifications API for native Windows toasts), `src/components/NotificationCenter.tsx` (navbar bell + count badge + dropdown + scrollable `alertdialog` popup + 60s smart polling + `"Zamknij"` / `"Zakończ sprawę"` / `"Ukryj na teraz"` / `"Włącz powiadomienia Windows"`), embed in `AppNav.tsx`, and add styles in `App.css`.  
**Files:** `apps/web/src/api/notifications.ts`, `apps/web/src/utils/desktopNotifications.ts`, `apps/web/src/components/NotificationCenter.tsx`, `apps/web/src/components/AppNav.tsx`, `apps/web/src/App.css`  
**Depends on:** Task 2.  
**Done when:** `npm run lint` and `npm run build` succeed cleanly.

## Task 5 — Frontend Vitest tests (`NotificationCenter.test.tsx`) & full verification gate
**What:** Write `src/NotificationCenter.test.tsx` testing bell badge, popup rendering, dismiss, close-case (`PATCH` with `version`), and Windows `Notification` API integration; verify full backend + frontend gate.  
**Files:** `apps/web/src/NotificationCenter.test.tsx`  
**Depends on:** Task 4.  
**Done when:** `uv run pytest`, `npm test`, `npm run lint`, and `npm run build` all pass cleanly.
