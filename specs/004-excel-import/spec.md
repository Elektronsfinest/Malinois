# Excel Import & Template-Based Export

## Goal

Enable administrators to import client cases from Excel into PostgreSQL with
validation and duplicate conflict resolution, and allow authorised users to
download live, role-scoped case data from PostgreSQL populated into an
admin-managed **empty Excel template** (`.xlsx` or `.xlsm`) that preserves
business macros, pivot tables, formulas, and formatting.

All day-to-day case editing happens directly in PostgreSQL (`/cases`, spec 003)
with optimistic locking (`version`, spec 011). **No user-data Excel files are
ever stored on the server** (neither on disk nor in the database) — imports are
parsed strictly in memory and exports are filled and streamed in memory
(preserving spec 007).

## User Stories

- As an admin, I want to upload a populated Excel file, review parsed rows,
  validation errors, and duplicate `case_number` conflicts in a preview, and
  commit validated changes to PostgreSQL so that bad spreadsheets never corrupt
  live data or create unintended duplicates.
- As an admin, I want an automatic database backup snapshot created before every
  import commit so that I can always recover if an import goes wrong.
- As an admin, I want to upload and replace an **empty** Excel template
  (`.xlsx` or `.xlsm` with macros, pivot tables, and formulas) with an automatic
  schema check so that exported files match our official workbook layout.
- As a user, supervisor, or admin, I want to download an Excel file filled on
  the fly with my role-scoped live cases from PostgreSQL (preserving template
  macros and pivot tables) without storing any data files on the server.

> [!NOTE]
> **Real ZUS Workbook Schema Verified (import):**
> Column mapping and template schema validation MUST stay isolated in a
> dedicated adapter (`services/excel_adapter.py`). The adapter recognises
> **both** the real ZUS workbook layout (`Numer E2`, `DANE`,
> `DATA WPŁYWU EPWD`, `termin realizacji`, `Status`, plus all extra ZUS
> columns preserved verbatim) **and** the standard Malinois headers
> (`Nr sprawy`, `Tytuł`, `Klient`, `Przypisany`, `Termin`, `Data złożenia`,
> `Status`, `Uwagi`). Column names MUST NOT be hardcoded across routes,
> services, or frontend components.

> [!WARNING]
> **Implementation Gap:**
> The current code still implements the superseded `working_copies` design
> (`/api/import/copies/*`, including `supervisor` upload and snapshot copies).
> `excel_templates`, the template endpoints, `GET /api/cases/export`, and
> `POST /api/import/preview` / `commit` as specified below are still to be
> built. `plan.md` and `tasks.md` in this folder describe the superseded design.

## Acceptance Criteria

### Backend — Admin Excel Template Management (Empty Template Only)
- [ ] **Template storage (zero disk writes, zero PII):**
  - New table `excel_templates` stores the admin-uploaded **empty** `.xlsx` or
    `.xlsm` template binary (`LargeBinary`) in PostgreSQL/SQLite — never on the
    server filesystem (spec 007)
  - Only `admin` may view template metadata (`GET /api/admin/excel-template`) or
    upload/replace the template (`PUT /api/admin/excel-template`); non-admins
    receive `403 Forbidden`
- [ ] **Mandatory schema check on template upload (`PUT /api/admin/excel-template`):**
  - Validates MIME type **and** file extension (`.xlsx` or `.xlsm`) and caps
    upload size at **10 MB** (`413` if exceeded)
  - Parses strictly in memory (`io.BytesIO`, `keep_vba=True` for `.xlsm`) and
    verifies:
    1. Required data sheet name(s) exist
    2. Header row contains all required schema columns (via the configurable
       schema adapter)
    3. **No leftover case data rows / PII:** rejects with `400 Bad Request` if
       data rows below the header are non-empty
  - Marks the new template `is_active = true` (deactivating any previous
    template) and logs `excel_template_updated` in `admin_audit_log` (spec 009)
  - Client-supplied filename is stored only as display metadata and **never**
    used in any filesystem operation

### Backend — On-Demand Template-Filled Export (`GET /api/cases/export`)
- [ ] Available to all authenticated roles; queries live cases from PostgreSQL
      strictly filtered by caller's role scope (spec 002) and optional active
      list filters (`q`, `status`, `assigned_to`, `overdue`, `due_soon`,
      `archived`)
- [ ] Loads the active empty template from `excel_templates` into memory
      (`io.BytesIO`, `keep_vba=True` when `.xlsm`), writes live case rows into
      the template's data sheet, sets `refreshOnLoad = True` on any pivot table
      caches so Excel refreshes pivots and formulas on open, and streams the
      result via `StreamingResponse` — **never writes to disk**
- [ ] If no custom template has been uploaded yet, generates a clean `.xlsx` in
      memory with the standard headers so export works out of the box
- [ ] Sets appropriate `Content-Type` (`.xlsx` or macro-enabled `.xlsm`) and
      `Content-Disposition: attachment; filename="malinois-cases-<YYYY-MM-DD>.<ext>"`

### Backend — Data Import Preview & Commit (Admin Only)
- [ ] **Preview (`POST /api/import/preview`, `admin` only; `403` for others):**
  - Validates uploaded `.xlsx` / `.xlsm` / `.xls` by MIME type **and**
    extension, capped at **10 MB** (`413` if exceeded), parsed strictly in
    memory and **never stored on disk or persisted as a file**
  - Column mapping lives in `services/excel_adapter.py`, recognising both real
    ZUS headers (`Numer E2`, `DANE`, `DATA WPŁYWU EPWD`, `termin realizacji`,
    `Status`) and standard Malinois headers (`Nr sprawy`, `Tytuł`, `Klient`,
    `Przypisany` (email), `Termin`, `Data złożenia`, `Status`, `Uwagi`); all
    unmapped columns (e.g. `DATA OPRACOWANIA`, `APROBANT`, `OFE`, `Składki`,
    `uprawnienie od`, `Pesel`, `INNE`, `data`, `inne`) are preserved verbatim
    in `cases.extra_fields` (spec 003), deduplicating repeated headers safely;
    `Pesel` values are never logged
  - The admin may supply an optional `default_assigned_to` user ID (active or
    inactive); rows without a `Przypisany` email inherit it and can be changed
    per row in the preview before committing
  - `DATA WPŁYWU EPWD` preserves its exact raw string in `extra_fields`,
    extracts a leading Polish/ISO date into `date_filed` when present (e.g.
    `14.05.2026-ERN` → `2026-05-14`), and allows pure-text entries (e.g.
    `z urzędu - EDUK`) with `date_filed = null`; when no `Tytuł` column exists,
    `title` is built from the suffix (or case number) + client
  - Dates accept **both** native Excel date serials (`datetime`/`date`) **and**
    Polish text formats (`DD.MM.YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`); unparseable
    values produce a per-row validation error, never a silent `null`. The one
    exception is non-date free text in `termin realizacji` / `Termin`, which is
    preserved in `extra_fields` with `deadline = null` and a visible
    non-blocking warning badge (malformed date-like strings such as
    `32.13.2026` still block the row)
  - Past deadlines are allowed (overdue cases are valid domain records)
  - Duplicate `case_number` rows **within the same uploaded file** are blocked
    as preview validation errors
  - Rows whose `case_number` matches an existing PostgreSQL case are flagged as
    `conflict` with the live case's `{ id, version }`, requiring explicit
    per-row resolution: `skip` (avoid duplicates) or `update_existing` (no
    auto-merge)
- [ ] **Commit (`POST /api/import/commit`, `admin` only; `403` for others):**
  - Accepts validated rows and explicit per-row conflict resolutions (`skip` |
    `update_existing` with `{ id, version }`)
  - Rejects with `400` if unresolved validation errors or unresolved duplicate
    conflicts remain
  - Triggers an **automatic `pre_import` backup snapshot** (spec 017)
    immediately before applying live mutations
  - Routes every row mutation through the unified case service layer (spec 003),
    supplying per-row `{ id, version }` for updates, incrementing `version`, and
    reporting per-row `409 Conflict` if a live case changed since preview (no
    silent overwrites)
  - Migrates any non-empty `Uwagi / Note` cell into an initial immutable
    `case_notes` entry (spec 010)
  - Logs all field-level updates to `case_edit_log` (spec 009)
  - Updates `system_settings["last_import_at"]` (spec 014)
  - Returns `{ created, updated, skipped, conflicts: [{ row, case_id, reason }], errors: [{ row, reason }] }`

### Frontend
- [ ] `/cases` header includes:
  - **"Pobierz Excel"** button (all roles) — calls `GET /api/cases/export` with
    active filters and downloads the template-filled `.xlsx`/`.xlsm`
  - **"Import Excel"** button (`admin` only) — routes to `/import`
- [ ] `/import` (`admin` only; non-admins redirected to `/`) displays:
  - Drag-and-drop / file picker for `.xlsx` / `.xlsm` / `.xls` data import
  - Preview table of parsed rows with inline error badges and `skip` /
    `update_existing` selectors for DB-matched `case_number` rows
  - **"Zatwierdź import"** (Commit) button with confirmation modal and
    post-commit summary (created / updated / skipped / conflicts)
- [ ] `/admin` → **Ustawienia systemowe** tab (spec 012) displays a **Szablon
      Excel** card showing active template metadata (filename, macro support,
      upload date, uploader) and an **"Wgraj / Zastąp szablon"** upload control
      that surfaces schema-check errors clearly

## Out of Scope

- Storing populated user-data Excel files on server disk or in the database
- Server-side scratchpad / working-copy spreadsheet editing (all live edits
  happen directly in PostgreSQL on `/cases` with optimistic locking)
- Importing user accounts from Excel
- Executing VBA macros on the server (macros are preserved passively in the
  template and run only in the user's local Excel)
- Support for `.csv`, `.ods`, or Google Sheets

## API Contract

### `GET /api/admin/excel-template`
**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**200 OK**
```json
{
  "id": 3,
  "filename": "szablon_spraw_v2.xlsm",
  "content_type": "application/vnd.ms-excel.sheet.macroEnabled.12",
  "has_macros": true,
  "size_bytes": 48120,
  "uploaded_by_email": "admin@example.com",
  "uploaded_at": "2027-01-15T09:00:00Z"
}
```
**403 Forbidden** — not admin  
**404 Not Found** — no custom template uploaded yet

### `PUT /api/admin/excel-template`
**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**Body:** `multipart/form-data`, field `file` (empty `.xlsx` or `.xlsm`, max 10 MB)  
**200 OK** — active template metadata (same shape as `GET`)  
**400 Bad Request** — invalid MIME/extension, failed schema check (missing sheet
or required headers), or template contains non-empty data rows  
**403 Forbidden** — not admin  
**413 Payload Too Large** — file exceeds 10 MB

### `GET /api/cases/export`
**Headers:** `Authorization: Bearer <jwt>` (all roles)  
**Query Params:** same optional filter params as `GET /api/cases` (`q`,
`status`, `assigned_to`, `overdue`, `due_soon`, `archived`)  
**200 OK** — populated `.xlsx` or `.xlsm` binary streamed from memory  
`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
(or `application/vnd.ms-excel.sheet.macroEnabled.12` for `.xlsm` templates)  
`Content-Disposition: attachment; filename="malinois-cases-<YYYY-MM-DD>.<ext>"`

### `POST /api/import/preview`
**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**Body:** `multipart/form-data`, field `file` (`.xlsx` / `.xlsm` / `.xls`, max 10 MB),
optional field `default_assigned_to` (user ID)  
**200 OK** — `{ rows, errors, conflicts }` parsed strictly in memory  
**400 Bad Request** — invalid MIME/extension or unparseable workbook  
**403 Forbidden** — not admin  
**413 Payload Too Large** — file exceeds 10 MB

### `POST /api/import/commit`
**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**Request Body**
```json
{
  "rows": [
    {
      "row": 2,
      "case_number": "CASE-2027-0010",
      "title": "Sprawa emerytalna – Nowak",
      "client_name": "Anna Nowak",
      "assigned_to_email": "jan@example.com",
      "deadline": "2027-03-15",
      "date_filed": "2027-01-10",
      "note": "Pilne dokumenty",
      "extra_fields": { "APROBANT": "JK" },
      "resolution": "create"
    },
    {
      "row": 5,
      "case_number": "CASE-2027-0001",
      "existing_case_id": 42,
      "version": 2,
      "title": "Zaktualizowany tytuł",
      "client_name": "Jan Kowalski",
      "assigned_to_email": "jan@example.com",
      "deadline": "2027-02-20",
      "date_filed": "2026-11-01",
      "resolution": "update_existing"
    }
  ]
}
```
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
**400 Bad Request** — unresolved validation errors or conflicts  
**403 Forbidden** — not admin

## Data Model Changes

New table `excel_templates`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `filename` | String(255) | Not null (display label only, never used as FS path) |
| `content_type` | String(120) | Not null (`.xlsx` or `.xlsm` MIME type) |
| `has_macros` | Boolean | Not null, default `False` |
| `size_bytes` | Integer | Not null |
| `content` | LargeBinary | Not null (empty template bytes, zero PII) |
| `is_active` | Boolean | Not null, default `True`, indexed |
| `uploaded_by_id` | Integer | FK → `users.id`, not null |
| `uploaded_at` | DateTime | Default UTC now, not null |

## Open Blockers (Business Input Required)

- [x] **Sample Excel workbook delivered & analyzed** (stored locally in
      gitignored `impwork/`): 14-column ZUS layout mapped in
      `services/excel_adapter.py` with full preservation of unmapped columns.
- [ ] **Export template not yet verified:** Finalize the template's required
      sheet name(s) and required vs. optional columns, and verify macro
      (`.xlsm`) + pivot table (`refreshOnLoad`) behaviour with `openpyxl`.

## Architecture Decisions

- **Direct PostgreSQL editing + Template-Based Export (superseding N-01 `working_copies`):**
  All live case editing happens directly in PostgreSQL (`/cases`, spec 003)
  with optimistic locking (`version`, spec 011). No user-data Excel files are
  ever stored on the server. To preserve business macros (`.xlsm`), pivot
  tables, formulas, and styling on download, admins manage an empty template in
  `excel_templates` (validated by a mandatory schema check on upload), which is
  filled from PostgreSQL and streamed strictly in memory on `GET /api/cases/export`.
- Per-row `{ id, version }` checked on import commit; conflicts reported per row
  without silent overwrites (N-06).
- Native Excel dates + Polish text dates supported; past deadlines allowed (N-08).
- Duplicate `case_number` in-file blocked; DB matches require `skip`/`update_existing` (N-09).
- Imported `Uwagi` becomes an initial `case_notes` row (N-10).
- Automatic `pre_import` backup snapshot before every import commit (N-23).
