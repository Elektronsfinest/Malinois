# Plan: Excel Import, Export & Full Copy Editor (Spec 004)

## Backend changes

- **New dependencies (`apps/api/pyproject.toml`):**
  - `openpyxl` — in-memory `.xlsx` parsing and `.xlsx` export generation (`io.BytesIO`, zero disk writes).
  - `xlrd` — in-memory legacy `.xls` parsing.
- **Files affected (`apps/api/`):**
  - `models.py` — Add `WorkingCopy` model (`__tablename__ = "working_copies"`): `id`, `owner_id` (FK `users.id`, named `fk_working_copies_owner_id_users`, indexed), `source_type` (`String(20)`, `"upload" | "snapshot"`), `label` (`String(255)`), `rows_json` (`JSON`), `created_at` (`DateTime(timezone=True)`), `expires_at` (`DateTime(timezone=True)`, indexed).
  - `alembic/versions/<rev>_add_working_copies_table.py` — Migration creating `working_copies` table + indices (SQLite + PostgreSQL compatible).
  - `schemas.py` — Add Pydantic schemas: `WorkingCopyRow`, `WorkingCopySummaryResponse`, `WorkingCopyDetailResponse`, `WorkingCopyRowPatch`, `WorkingCopyPatchRequest`, `WorkingCopyCommitConflict`, `WorkingCopyCommitError`, `WorkingCopyCommitResponse`.
  - `services/audit.py` — Add clean hooks `trigger_pre_import_backup(actor_id, copy_id)` (Spec 017), `create_initial_case_note(case_id, actor_id, content)` (Spec 010), and `record_last_import_at(timestamp)` (Spec 012/014).
  - `services/excel_adapter.py` *(new)* — Pure in-memory adapter:
    - Validates extension (`.xlsx`/`.xls`), MIME type, and 10 MB size cap (`413`).
    - Parses `.xlsx` via `openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)` and `.xls` via `xlrd.open_workbook(file_contents=raw_bytes)`.
    - Supports both real ZUS headers (`Numer E2`, `DANE`, `DATA WPŁYWU EPWD`, `termin realizacji`, `Status`) and standard Malinois headers (`Nr sprawy`, `Tytuł`, `Klient`, `Przypisany`, `Termin`, `Data złożenia`, `Status`, `Uwagi`), preserving all extra/unmapped columns in `extra_columns` (safely handling duplicate headers like `INNE` / `inne`).
    - Parses native Excel dates and Polish/ISO date strings (`DD.MM.YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`); extracts leading date + suffix from `DATA WPŁYWU EPWD`; preserves free-text `termin realizacji` in `extra_columns` with a non-blocking warning while flagging malformed date-like strings (e.g. `32.13.2026`) as blocking errors.
    - Builds in-memory `.xlsx` bytes (`build_xlsx_bytes(rows)`) for `StreamingResponse` download.
  - `services/working_copies.py` *(new)* — Full lifecycle & commit engine:
    - Enforces 24h TTL (automatically excludes/prunes expired copies) and max 5 active copies per user (`409 Conflict` on 6th).
    - `create_copy_from_upload(db, actor, filename, content_type, raw_bytes, default_assigned_to)` — `admin` only (`403`), detects in-file duplicate `case_number` errors and DB-matched `case_number` conflicts (recording live `{ case_id, version }`).
    - `create_copy_from_cases(db, actor)` — all roles; snapshots caller's visible active cases into a `WorkingCopy`.
    - `list_copies`, `get_copy_owned` (`404` if missing/expired/not owned), `patch_copy` (blocks non-admin date cell edits with `403`; re-runs validation & conflict checks), `delete_copy`, `download_copy_bytes`.
    - `commit_copy(db, actor, copy_id)`:
      - Rejects with `400` if unresolved blocking errors or unresolved DB conflicts remain.
      - Triggers `trigger_pre_import_backup`.
      - Routes every row through `services/cases.py` (`create_case` / `update_case` with per-row `{ id, version }` and automatic audit reason `"Import / edycja kopii roboczej"` for admin date updates), catching per-row `409 Conflict` without silent overwrites.
      - Calls `create_initial_case_note` for non-empty `note` cells and `record_last_import_at`.
      - Refreshes `rows_json` with updated `case_id`/`version` and keeps the copy until its 24h TTL so the user can still download the committed `.xlsx`.
  - `routers/import_copies.py` *(new)* — Thin route handlers under `/api/import/copies`:
    - `GET /api/import/copies`
    - `POST /api/import/copies/upload` (`multipart/form-data`: `file` + optional `default_assigned_to`)
    - `POST /api/import/copies/from-cases`
    - `GET /api/import/copies/{copy_id}`
    - `PATCH /api/import/copies/{copy_id}`
    - `DELETE /api/import/copies/{copy_id}`
    - `GET /api/import/copies/{copy_id}/download`
    - `POST /api/import/copies/{copy_id}/commit`
  - `main.py` — Mount `import_copies_router`.

## Frontend changes

- **Files affected (`apps/web/src/`):**
  - `api/importCopies.ts` *(new)* — Typed API client for all `/api/import/copies/*` endpoints including multipart upload and authenticated blob download (`downloadWorkingCopy`).
  - `components/ImportPage.tsx` *(new)* — `/import` Full Excel Copy Editor:
    - Admin-only drag-and-drop / file picker (`.xlsx`/`.xls`) with `"Domyślny pracownik"` dropdown (including `(nieaktywny)` badge).
    - `"Otwórz kopię bieżących spraw"` button (all roles).
    - Sidebar/list of caller's active working copies (TTL countdown + `"Usuń"` button).
    - Full editable spreadsheet grid (core columns + dynamic `extra_columns`), inline error/warning badges, `skip` / `update_existing` conflict selectors, read-only date cells for non-admins.
    - `"Zapisz kopię"`, `"Pobierz Excel (.xlsx)"`, and `"Zatwierdź zmiany"` (with confirmation modal + post-commit summary banner).
  - `components/CasesPage.tsx` — Enable the `"Import / Edytor pliku"` button as a `<Link to="/import">`!
  - `components/AppNav.tsx` — Add `Import / Edytor` (`/import`) nav link.
  - `router.tsx` — Add authenticated `/import` route.
  - `App.css` — Styles for `/import` dropzone, copy list, editable spreadsheet grid, conflict/warning pills, and commit summary.

## Test plan

- **New pytest tests (`apps/api/tests/test_import_copies.py`):**
  - Upload validation: non-admin `403`, invalid extension/MIME `400`, >10 MB `413`, 6th active copy `409`.
  - Dual parser tests:
    - Real ZUS format (Column A `14.05.2026-ERN` & `z urzędu - EDUK`, Column N free-text warning vs broken date `32.13.2026` error, `Numer E2`, `DANE`, `extra_columns`, duplicate `INNE`/`inne` headers, `default_assigned_to` including inactive user).
    - Standard Malinois format + in-memory `.xlsx` download → re-upload round-trip.
    - Legacy `.xls` parsing check.
  - Duplicate in-file `case_number` blocked as error; DB-matched `case_number` flagged as `conflict` requiring `skip` or `update_existing`.
  - Snapshot (`from-cases`) role scoping (`user` sees own, `supervisor` sees team, `admin` sees all), non-admin date edit `403`, cross-user copy access `404`.
  - Commit: blocks on unresolved errors/conflicts (`400`), creates + updates via unified case service, detects stale live `version` as per-row conflict without silent overwrite, refreshes copy row versions so copy remains downloadable.
- **New Vitest tests (`apps/web/src/ImportPage.test.tsx`):**
  - Admin sees upload dropzone + default assignee dropdown with `(nieaktywny)`; non-admin sees snapshot button without upload dropzone and read-only date cells.
  - Editing cells, resolving conflict (`skip` / `update_existing`), committing with confirmation modal and displaying post-commit summary (`created`, `updated`, `skipped`).

## Risks / Notes

- **Zero disk writes:** All uploads are read into `bytes`/`io.BytesIO` in memory and parsed directly; `.xlsx` downloads are built in `io.BytesIO` and streamed via `StreamingResponse`.
- **PII (`Pesel`):** Redacted in audit logs; never written to temporary disk files.
- **Hooks:** `trigger_pre_import_backup`, `create_initial_case_note`, and `record_last_import_at` are clean service hooks ready for Specs 010, 012, and 017.
