# Tasks: Excel Import, Export & Full Copy Editor (Spec 004)

## Task 1 — Add `openpyxl` & `xlrd`, `WorkingCopy` model, and Alembic migration
**What:** Install `openpyxl` and `xlrd` via `uv add`, add `WorkingCopy` (`working_copies` table) to `models.py`, and generate + verify the Alembic migration (`upgrade` → `downgrade -1` → `upgrade`).  
**Files:** `apps/api/pyproject.toml`, `apps/api/models.py`, `apps/api/alembic/versions/<rev>_add_working_copies_table.py`  
**Done when:** `uv run alembic upgrade head`, `downgrade -1`, and `upgrade head` succeed cleanly.

## Task 2 — Build `services/excel_adapter.py` (dual ZUS + Malinois parser & `.xlsx` builder)
**What:** Implement in-memory `.xlsx`/`.xls` parsing (MIME + extension + 10 MB cap), dual ZUS/Malinois column adapter (`DATA WPŁYWU EPWD` suffix/date extraction, `termin realizacji` warning vs error, `extra_columns` preservation), and in-memory `.xlsx` export builder.  
**Files:** `apps/api/services/excel_adapter.py`  
**Depends on:** Task 1.  
**Done when:** Adapter parses both ZUS and Malinois workbooks and builds downloadable `.xlsx` bytes in memory.

## Task 3 — Build working-copy schemas, hooks, `services/working_copies.py`, and `routers/import_copies.py`
**What:** Add working-copy Pydantic schemas, cross-spec hooks in `services/audit.py`, full working-copy lifecycle & commit service (24h TTL, max 5/user `409`, role-scoped snapshots, non-admin date `403`, per-row `{ id, version }` commit via `services/cases.py`), and mount `/api/import/copies/*` in `main.py`.  
**Files:** `apps/api/schemas.py`, `apps/api/services/audit.py`, `apps/api/services/working_copies.py`, `apps/api/routers/import_copies.py`, `apps/api/main.py`  
**Depends on:** Task 2.  
**Done when:** All `/api/import/copies/*` endpoints are mounted in FastAPI.

## Task 4 — Backend Excel Copy Editor test suite
**What:** Write `tests/test_import_copies.py` covering upload security (`403`/`400`/`413`/`409`), real ZUS parsing edge cases, Malinois `.xlsx` round-trip, duplicate/conflict resolution, non-admin date protection, and per-row version conflict detection on commit.  
**Files:** `apps/api/tests/test_import_copies.py`  
**Depends on:** Task 3.  
**Done when:** `uv run pytest` passes 100% of backend tests.

## Task 5 — Frontend API client, `/import` route, and `CasesPage` / `AppNav` links
**What:** Create `src/api/importCopies.ts`, add `/import` route in `src/router.tsx`, enable `"Import / Edytor pliku"` link in `CasesPage.tsx`, and add `Import / Edytor` to `AppNav.tsx`.  
**Files:** `apps/web/src/api/importCopies.ts`, `apps/web/src/router.tsx`, `apps/web/src/components/CasesPage.tsx`, `apps/web/src/components/AppNav.tsx`  
**Depends on:** Task 3.  
**Done when:** Route and links wire cleanly.

## Task 6 — Build `ImportPage.tsx` (Full Excel Copy Editor UI) and styles
**What:** Implement `src/components/ImportPage.tsx` (admin upload dropzone + default assignee selector with `(nieaktywny)`, `"Otwórz kopię bieżących spraw"`, active copies list with TTL & delete, editable spreadsheet grid with `extra_columns`, error/warning badges, `skip`/`update_existing` conflict dropdowns, read-only dates for non-admins, `.xlsx` download, and commit modal + summary) and add styles in `src/App.css`.  
**Files:** `apps/web/src/components/ImportPage.tsx`, `apps/web/src/App.css`  
**Depends on:** Task 5.  
**Done when:** `npm run lint` and `npm run build` pass with zero errors.

## Task 7 — Frontend Vitest tests (`ImportPage.test.tsx`) & full gate verification
**What:** Write `src/ImportPage.test.tsx` covering admin upload vs non-admin snapshot UI, conflict resolution, and commit summary; run full backend + frontend verification gate.  
**Files:** `apps/web/src/ImportPage.test.tsx`  
**Depends on:** Task 6.  
**Done when:** `uv run pytest`, `npm test`, `npm run lint`, and `npm run build` all pass cleanly.
