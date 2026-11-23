# Excel Import, Export & Full Copy Editor

## Goal

Provide an in-app **Full Excel Copy Editor** (`/import`) that lets authorised
users upload an Excel file or open an editable snapshot of live cases as a
server-side **working copy**, inspect/edit rows and resolve conflicts in a grid,
download a copy as `.xlsx` to their computer, and explicitly commit validated
changes to the live `cases` table. The application ALWAYS operates on copies —
original files are never modified and uploaded files are **never written to
disk** (preserving spec 007).

## User Stories

- As an admin, I want to upload an Excel file into a server-side working copy,
  review parsed rows and validation errors, edit cells if needed, and commit
  changes explicitly so that bad spreadsheets never corrupt live data.
- As a user, supervisor, or admin, I want to open an editable copy of the cases
  visible to me, make scratch edits or download an `.xlsx` copy to my computer,
  without mutating the live database until explicitly committed (respecting my
  role permissions).
- As an admin, I want duplicate rows and version conflicts to be highlighted in
  the copy preview so that I choose `skip` or `update_existing` explicitly with
  no silent overwrites.
- As an admin, I want an automatic database backup snapshot created before every
  import commit so that I can always recover if an import goes wrong.

> [!IMPORTANT]
> **Pending Business Input — Excel Schema Not Yet Delivered:**
> The real Excel workbook has **not yet been delivered by the business**.
> All column names below are **provisional placeholders** only. Implementation
> MUST isolate Excel column mapping behind a dedicated, easily swappable
> mapping/adapter layer (with `extra_columns` JSON passthrough) and MUST NOT
> hardcode final column names into the core `working_copies` engine until
> the sample workbook is provided and signed off.

## Acceptance Criteria

### Backend
- [ ] **Working copies storage (no disk writes):**
  - New table `working_copies` stores parsed/snapshot rows as JSON in the
    single database (24-hour TTL, max **5 active copies per user**; creating a
    6th returns `409 Conflict` until an old copy is deleted or expires)
  - Uploaded `.xlsx` / `.xls` files are validated by MIME type **and** extension,
    capped at **10 MB** (`413` if exceeded), parsed strictly in memory, and
    **never written to disk** (spec 007)
  - Downloading any copy (`GET /api/import/copies/:copy_id/download`) generates
    the `.xlsx` binary in memory and streams it with
    `Content-Disposition: attachment`
- [ ] **Creating a working copy:**
  - `POST /api/import/copies/upload` (`admin` only; `403` for others) parses an
    uploaded `.xlsx`/`.xls` into a `working_copies` row
  - `POST /api/import/copies/from-cases` (all authenticated roles) snapshots
    the caller's visible live cases (filtered by spec 002 role rules) into a
    working copy for inspection, editing, or `.xlsx` download
- [ ] **Parsing & validation rules (schema-agnostic adapter until business sample arrives):**
  - Column mapping lives in a single configurable adapter module (not scattered
    across routes or DB models). **Provisional placeholder columns** (to be
    replaced once the business delivers the sample workbook):
    `Nr sprawy / Case Number`, `Tytuł / Title`, `Klient / Client`,
    `Przypisany / Assigned To` (email), `Termin / Deadline`,
    `Data złożenia / Date Filed` (optional), `Uwagi / Note` (optional); all
    other/unmapped columns in the spreadsheet are preserved verbatim in
    `extra_columns` JSON on each copy row so the full sheet can be edited and
    re-downloaded intact regardless of final column layout
  - Dates accept **both** native Excel date serials (`datetime`/`date`) **and**
    Polish text formats (`DD.MM.YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`); unparseable
    values produce a per-row validation error, never a silent `null`
  - Past deadlines are allowed (overdue cases are valid domain records)
  - Duplicate `case_number` rows **within the same uploaded file** are blocked
    as preview validation errors
  - Rows whose `case_number` matches an existing DB case are flagged as
    `conflict` with the live case's `id` and `version`, requiring explicit
    per-row resolution: `skip` or `update_existing` (no auto-merge)
- [ ] **Editing & committing a working copy:**
  - `GET /api/import/copies` lists the caller's active (non-expired) copies
  - `GET /api/import/copies/:copy_id` returns the copy rows, validation errors,
    and conflict markers (`404` if not owned by caller)
  - `PATCH /api/import/copies/:copy_id` updates cells or conflict resolutions
    (`skip` / `update_existing`) on the working copy only (does not touch live
    `cases`). Non-admins cannot modify `deadline`/`date_filed` cells (`403`)
  - `DELETE /api/import/copies/:copy_id` discards a working copy
  - `POST /api/import/copies/:copy_id/commit` (`admin` only for uploads; role-
    scoped non-date updates for live snapshots):
    - Rejects with `400` if unresolved validation errors or unresolved duplicate
      conflicts remain
    - Triggers an **automatic backup snapshot** (spec 017) immediately before
      applying live mutations
    - Routes every row mutation through the unified case service layer (spec
      003), supplying per-row `{ id, version }` for updates, incrementing
      `version`, and reporting per-row `409 Conflict` if a live case changed
      since the copy was created (no silent overwrites)
    - Migrates any non-empty `Uwagi / Note` cell into an initial immutable
      `case_notes` entry (spec 010)
    - Logs all field-level updates to `case_edit_log` (spec 009)
    - Updates `system_settings["last_import_at"]` (spec 014)
    - Returns `{ created, updated, skipped, conflicts: [{ row, case_id, reason }], errors: [{ row, reason }] }`

### Frontend
- [ ] Accessed via **"Import / Edytor pliku"** button on Main (`/cases`)
      routing to `/import` (outside the Admin Panel, spec 012)
- [ ] `/import` displays:
  - Drag-and-drop / file picker for `.xlsx`/`.xls` upload (admin only)
  - "Otwórz kopię bieżących spraw" button (all roles) to open a live snapshot
  - List of caller's active working copies (with TTL expiry indicator and delete)
  - Full editable spreadsheet grid for the selected copy (including extra
    columns), with inline error badges and `skip` / `update_existing` selectors
    for DB-matched `case_number` rows
  - Date columns are read-only in the grid for non-admin users
  - **"Pobierz Excel (.xlsx)"** button to download the working copy to disk
  - **"Zatwierdź zmiany"** (Commit) button with confirmation modal and post-
    commit summary (created / updated / skipped / conflicts)

## Out of Scope

- Importing user accounts from Excel
- Real-time multi-user editing of the same working copy
- Writing raw uploaded files to server disk (forbidden by spec 007)
- Support for `.csv`, `.ods`, or Google Sheets

## API Contract

### `POST /api/import/copies/upload`
**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**Body:** `multipart/form-data`, field `file` (`.xlsx`/`.xls`, max 10 MB)  
**201 Created** — working copy metadata + parsed preview rows + errors/conflicts  
**400 Bad Request** — invalid MIME/extension or unparseable workbook  
**403 Forbidden** — not admin  
**409 Conflict** — user already has 5 active working copies  
**413 Payload Too Large** — file exceeds 10 MB

### `POST /api/import/copies/from-cases`
**Headers:** `Authorization: Bearer <jwt>`  
**201 Created** — working copy populated from caller's visible cases

### `GET /api/import/copies/:copy_id` / `PATCH /api/import/copies/:copy_id` / `DELETE /api/import/copies/:copy_id`
**Headers:** `Authorization: Bearer <jwt>`  
**200 OK** (GET/PATCH) / **204 No Content** (DELETE)  
**403 Forbidden** — non-admin attempted to edit date cells  
**404 Not Found** — copy does not exist, expired, or belongs to another user

### `GET /api/import/copies/:copy_id/download`
**Headers:** `Authorization: Bearer <jwt>`  
**200 OK** — `.xlsx` binary streamed from memory  
`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`  
`Content-Disposition: attachment; filename="malinois-copy-<id>-<YYYY-MM-DD>.xlsx"`

### `POST /api/import/copies/:copy_id/commit`
**Headers:** `Authorization: Bearer <jwt>`  
**200 OK**
```json
{
  "created": 12,
  "updated": 3,
  "skipped": 1,
  "conflicts": [
    { "row": 5, "case_id": 42, "reason": "Sprawa została zmodyfikowana przez innego użytkownika (konflikt wersji)." }
  ],
  "errors": []
}
```
**400 Bad Request** — unresolved validation errors or conflicts in copy  
**403 Forbidden** — insufficient role permissions

## Data Model Changes

New table `working_copies`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `owner_id` | Integer | FK → `users.id`, not null, indexed |
| `source_type` | String(20) | Not null (`upload` \| `snapshot`) |
| `label` | String(255) | Not null (display label, never used as FS path) |
| `rows_json` | JSON | Not null (parsed rows, extra columns, `case_id`, `version`, resolution) |
| `created_at` | DateTime | Default UTC now, not null |
| `expires_at` | DateTime | `created_at + 24h`, not null, indexed |

## Open Blockers (Business Input Required)

- [ ] **Sample Excel workbook not yet delivered:** Finalize exact sheet
      name(s), column headers, required vs. optional columns, unique case
      identifier column, assignee identifier format (email vs. full name), and
      actual date cell formatting once the business provides a sample file.

## Resolved Decisions (Indaba Council)

- Full Excel Copy Editor from `appbuild.drawio.xml` backed by `working_copies` DB table (24h TTL, max 5/user), strictly in-memory parsing/streaming (N-01).
- Per-row `{ id, version }` checked on commit; conflicts reported per row without silent overwrites (N-06).
- Native Excel dates + Polish text dates supported; past deadlines allowed (N-08).
- Duplicate `case_number` in-file blocked; DB matches require `skip`/`update_existing` (N-09).
- Imported `Uwagi` becomes an initial `case_notes` row (N-10).
- Reached at `/import` from Main (`/cases`), with automatic pre-commit backup snapshot (N-21, N-23).
