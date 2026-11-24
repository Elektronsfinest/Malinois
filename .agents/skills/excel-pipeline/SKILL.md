---
name: excel-pipeline
description: >-
  Use when implementing or modifying Excel data import (/import), admin empty
  .xlsx/.xlsm template upload and schema validation (excel_templates),
  Polish/native date conversion, duplicate conflict resolution, or in-memory
  template-filled Excel export streaming in Malinois.
---

# Excel Import & Template-Based Export Pipeline — Malinois

Implements `specs/004-excel-import/spec.md` and `specs/007-security/spec.md`.
All live case editing happens directly in PostgreSQL (`/cases`, `spec 003`)
with optimistic locking (`version`, `spec 011`). **No user-data Excel files are
ever stored on the server** — imports are parsed strictly in memory and exports
populate an admin-managed **empty** template in memory and stream it directly.

---

## Architecture: Direct DB Editing + Empty Template Export (Zero Disk I/O)

1. **No Disk Writes & Zero Stored Data Files:**
   - Validate all Excel uploads by MIME type **and** extension (`.xlsx`/`.xlsm`
     for templates; `.xlsx`/`.xlsm`/`.xls` for data imports), max **10 MB**
     (`413` if larger).
   - Never write uploaded or generated files to server disk, and never use
     client-supplied filenames in any filesystem operation.
   - Never execute VBA macros on the server — `.xlsm` macros are preserved
     passively in the template binary and run only on the user's machine.
2. **Admin Empty Template Management (`excel_templates`):**
   - `GET /api/admin/excel-template` / `PUT /api/admin/excel-template` (`admin`
     only; `403` for others).
   - Stores the empty `.xlsx` or `.xlsm` template bytes in PostgreSQL/SQLite
     (`excel_templates.content` `LargeBinary`) with `is_active = True`
     (deactivating previous versions) and logs `excel_template_updated` in
     `admin_audit_log`.
   - **Mandatory Schema Check on Upload (`400` on failure):**
     1. Required data sheet name(s) exist.
     2. Header row matches expected schema columns (via the swappable mapping
        adapter).
     3. **Zero PII / data rows:** reject if any data rows below the header are
        populated.
3. **On-Demand Template-Filled Export (`GET /api/cases/export`):**
   - Available to all authenticated roles; queries live cases from PostgreSQL
     strictly filtered by caller's role scope (`spec 002`) and active filters.
   - Loads the active empty template from `excel_templates` into `io.BytesIO`
     using `openpyxl.load_workbook(..., keep_vba=True)` when `has_macros=True`.
   - Writes live case rows into the data sheet, sets `refreshOnLoad = True` on
     any pivot table caches so Excel refreshes pivots and formulas on open, and
     streams via `StreamingResponse`.
   - Falls back to generating a clean in-memory `.xlsx` if no custom template
     has been uploaded yet.
4. **Pending Business Schema — Swappable Adapter:**
   - **Important:** The real Excel workbook / template has **not yet been
     delivered by the business**. Keep all sheet names, header matching, and
     schema validation inside a single configurable adapter module — never
     hardcode provisional column names across routes, services, or frontend
     components.
   - Provisional placeholder columns: `Nr sprawy / Case Number`,
     `Tytuł / Title`, `Klient / Client`, `Przypisany / Assigned To`,
     `Termin / Deadline`, `Data złożenia / Date Filed` (optional),
     `Uwagi / Note` (optional).

---

## Import Preview, Date Parsing & Commit Rules (`admin` only)

1. **Dual Date Support (`POST /api/import/preview`):**
   - Accept native Excel date cells (`datetime`/`date` objects from `openpyxl`)
     AND Polish text formats: `DD.MM.YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`.
   - Unparseable dates produce a per-row validation error — never silently
     coerced to `null`.
   - Past deadlines are valid (overdue cases are allowed on import).
2. **Duplicate & Conflict Handling:**
   - Duplicate `case_number` rows **within the same uploaded file** are blocked
     as preview validation errors.
   - Rows matching an existing DB `case_number` are flagged as conflicts with
     live `{ id, version }` and require explicit per-row `skip` (avoid
     duplicates) or `update_existing` (no auto-merge).
3. **Commit Guarantees (`POST /api/import/commit`):**
   - Reject with `400` if unresolved validation errors or conflicts remain.
   - Automatically trigger a **`pre_import` backup snapshot** (`spec 017`)
     immediately before mutating live `cases`.
   - Route every row through the unified case service layer with per-row
     `{ id, version }`, reporting per-row `409` conflicts without silent
     overwrites.
   - Migrate non-empty `Uwagi / Note` cells into initial immutable `case_notes`
     entries (`spec 010`) and update `system_settings["last_import_at"]`.
