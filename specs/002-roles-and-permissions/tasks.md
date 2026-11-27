# Tasks: Role-Based Access Control (Spec 002)

## Task 1 — Extend `User` model and create Alembic migration
**What:** Add `role`, `supervisor_id`, and `must_change_password` columns to `User` in `models.py` and generate + apply the Alembic batch migration.  
**Files:** `apps/api/models.py`, `apps/api/alembic/versions/<rev>_add_user_roles_and_supervisor.py`, `apps/api/tests/test_database.py`  
**Done when:** `uv run alembic upgrade head` succeeds cleanly on SQLite (`dev.db`) and `uv run pytest tests/test_database.py` passes.

## Task 2 — Security hardening & password policy helper
**What:** Pin `bcrypt` cost factor to 12, add `validate_jwt_secret()` for production startup, and add `validate_password_policy()` (min 12 chars, max 72 UTF-8 bytes, upper/lower/digit/special).  
**Files:** `apps/api/security.py`, `apps/api/main.py`, `apps/api/tests/test_security.py`  
**Depends on:** None (can run after Task 1).  
**Done when:** `uv run pytest tests/test_security.py` passes all boundary and error cases.

## Task 3 — Update `seed.py` with dev role hierarchy
**What:** Keep `trainee@example.com` / `Secret123!` (`role="user"`, `must_change_password=False`) and add idempotent dev seeds for `admin@example.com`, `supervisor@example.com`, and `user@example.com` (supervised by `supervisor@example.com`).  
**Files:** `apps/api/seed.py`  
**Depends on:** Task 1.  
**Done when:** Running `uv run python seed.py` twice is idempotent and creates all 4 users with the expected roles and supervisor link.

## Task 4 — Split auth dependencies & add `require_role` + updated `UserResponse`
**What:** Expand `UserResponse` with `role`, `supervisor_id`, `must_change_password`; split `get_authenticated_user` (for `GET /api/me`) and `get_current_user` (enforces `must_change_password` 403); implement reusable `require_role(*roles)` dependency.  
**Files:** `apps/api/schemas.py`, `apps/api/routers/auth.py`, `apps/api/tests/test_auth.py`  
**Depends on:** Task 1, Task 3.  
**Done when:** `uv run pytest tests/test_auth.py` passes and `GET /api/me` / `POST /api/login` return the extended user payload.

## Task 5 — Implement admin user management service, audit hook, and router
**What:** Build `services/audit.py` (logger hook), `services/users.py` (list with filters, create with policy + `must_change_password=True`, update/deactivate with self-lockout, last-admin guard, promotion/demotion rules, and atomic `reassign_subordinates_to` + `409 Conflict`), and `routers/admin_users.py` (`GET/POST /api/admin/users`, `PATCH /api/admin/users/:id`), mounted in `main.py`.  
**Files:** `apps/api/schemas.py`, `apps/api/services/audit.py`, `apps/api/services/users.py`, `apps/api/routers/admin_users.py`, `apps/api/main.py`  
**Depends on:** Task 2, Task 4.  
**Done when:** All three `/api/admin/users` endpoints are mounted and manually/unit verified.

## Task 6 — Backend RBAC & hierarchy test suite
**What:** Add comprehensive pytest suite covering the role matrix (`401`/`403`), `must_change_password` enforcement, user creation validation, hierarchy rules (`admin` + `supervisor` subordinates, auto-clear on promotion, self-supervision), self-lockout/last-admin protection, and atomic `409` deactivation/demotion reassignment.  
**Files:** `apps/api/tests/test_rbac.py`  
**Depends on:** Task 5.  
**Done when:** `uv run pytest` passes 100% of backend tests with zero failures.

## Task 7 — Frontend `User` type, `/admin` route guard, and Dashboard role UI
**What:** Extend `User` in `src/api/auth.ts`, add `/admin` route with `admin`-only `beforeLoad` redirect guard in `src/router.tsx`, add `AdminPlaceholderPage.tsx`, and display the Polish role badge + admin-only link in `DashboardPage.tsx`.  
**Files:** `apps/web/src/api/auth.ts`, `apps/web/src/router.tsx`, `apps/web/src/components/AdminPlaceholderPage.tsx`, `apps/web/src/components/DashboardPage.tsx`, `apps/web/src/App.css`, `apps/web/src/App.test.tsx`  
**Depends on:** Task 4.  
**Done when:** `npm test`, `npm run lint`, and `npm run build` all pass cleanly in `apps/web`.
