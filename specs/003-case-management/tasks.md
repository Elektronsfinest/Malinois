# Tasks: Case Management (Spec 003)

## Task 1 — Add `Case` model and Alembic migration
**What:** Add `Case` model (`cases` table with `extra_fields` JSON and named FK `fk_cases_assigned_to_users`) in `models.py` and generate + verify the Alembic migration (`upgrade` → `downgrade -1` → `upgrade`).  
**Files:** `apps/api/models.py`, `apps/api/alembic/versions/<rev>_add_cases_table.py`  
**Done when:** `uv run alembic upgrade head`, `downgrade -1`, and `upgrade head` all succeed cleanly on SQLite.

## Task 2 — Add case schemas, audit hook, and unified `services/cases.py`
**What:** Add case Pydantic schemas in `schemas.py`, add PII-safe `log_case_changes` hook in `services/audit.py`, and implement `services/cases.py` (role scoping, `404` anti-enumeration, inactive-assignee support, date/reason rules, optimistic locking `409`, archived read-only guard).  
**Files:** `apps/api/schemas.py`, `apps/api/services/audit.py`, `apps/api/services/cases.py`  
**Depends on:** Task 1.  
**Done when:** Service functions import cleanly and enforce all role, date, and version invariants.

## Task 3 — Wire `routers/cases.py`, Spec 002 deactivation hook, and sample seeds
**What:** Create `routers/cases.py` (`GET/POST /api/cases`, `GET/PATCH /api/cases/{case_id}`, `GET /api/users/assignable`), mount in `main.py`, wire `get_blocking_case_ids` + atomic case reassignment in `services/users.py`, and add 4 idempotent Polish ZUS sample cases in `seed.py`.  
**Files:** `apps/api/routers/cases.py`, `apps/api/main.py`, `apps/api/services/users.py`, `apps/api/seed.py`  
**Depends on:** Task 2.  
**Done when:** `uv run python seed.py` runs idempotently and endpoints are mounted in FastAPI.

## Task 4 — Backend Case Management & deactivation integration test suite
**What:** Write comprehensive `tests/test_cases.py` covering role visibility (`404`), pagination/sorting, assignable users (including inactive), creation/date/reason rules, archived guard, `409` optimistic locking, and Spec 002 user deactivation with active cases.  
**Files:** `apps/api/tests/test_cases.py`  
**Depends on:** Task 3.  
**Done when:** `uv run pytest` passes 100% of backend tests.

## Task 5 — Frontend API client, `Europe/Warsaw` date utilities, and shared `AppNav`
**What:** Create `src/api/cases.ts`, `src/utils/dates.ts` (Polish `DD.MM.YYYY` + 4 urgency levels), and `src/components/AppNav.tsx`, and wire `/cases` route into `src/router.tsx`.  
**Files:** `apps/web/src/api/cases.ts`, `apps/web/src/utils/dates.ts`, `apps/web/src/components/AppNav.tsx`, `apps/web/src/router.tsx`, `apps/web/src/components/DashboardPage.tsx`, `apps/web/src/components/AdminPlaceholderPage.tsx`  
**Depends on:** Task 3.  
**Done when:** TypeScript compiles cleanly with `npm run build` and existing tests pass.

## Task 6 — Build `/cases` table, `"Nowa sprawa"` modal, inline Editor, and `409` conflict modal
**What:** Implement `src/components/CasesPage.tsx` and styles in `src/App.css`: case table with urgency badges & `"Zakończono"` toggle, `"Nowa sprawa"` modal (with `(nieaktywny)` badges, supervisor date hiding, admin past-deadline warning), inline **Edytor wstępny** (including `extra_fields` and admin `"Powód zmiany daty"`), and accessible `409` conflict resolution modal.  
**Files:** `apps/web/src/components/CasesPage.tsx`, `apps/web/src/App.css`  
**Depends on:** Task 5.  
**Done when:** `npm run lint` and `npm run build` succeed with zero errors.

## Task 7 — Frontend Vitest tests for `/cases` & Gate verification
**What:** Write `src/CasesPage.test.tsx` testing urgency rendering, role-based UI controls, inactive assignee labeling, `"Zakończono"` toggle, admin date reason enforcement, and `409 Conflict` modal resolution; verify full backend + frontend gate.  
**Files:** `apps/web/src/CasesPage.test.tsx`  
**Depends on:** Task 6.  
**Done when:** `uv run pytest`, `npm test`, `npm run lint`, and `npm run build` all pass cleanly.
