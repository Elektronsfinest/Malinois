---
name: excel-pipeline
description: >-
  Use when implementing or modifying the Full Excel Copy Editor (/import),
  .xlsx/.xls parsing, Polish/native date conversion, working_copies storage,
  conflict resolution, or in-memory Excel export streaming in Malinois.
---

# Excel Copy Editor & Import/Export Pipeline — Malinois

Implements `specs/004-excel-import/spec.md` in alignment with `appbuild.drawio.xml`
("strona działa tylko na kopiach prawdziwych dokumentów") and `specs/007-security/spec.md`
(strict zero-disk upload rule).

---

## Architecture: Working Copies, Never Disk Files

1. **No Disk Writes Ever:**
   - Validate uploads by MIME type **and** `.xlsx`/`.xls` extension, max **10 MB**
     (`413` if larger).
   - Parse bytes in memory (`io.BytesIO`) and store structured rows in
     `working_copies.rows_json` (single DB).
   - Never use the client-supplied filename in any filesystem operation.
   - Generate downloads (`GET /api/import/copies/:id/download`) in memory and
     stream via `StreamingResponse`.
2. **Lifecycle Limits:**
   - Every working copy has a **24-hour TTL** (`expires_at = created_at + 24h`).
   - Maximum **5 active copies per user** (`409 Conflict` on 6th).
   - Two entry points:
     - `POST /api/import/copies/upload` (`admin` only) — parse uploaded file.
     - `POST /api/import/copies/from-cases` (all roles) — snapshot caller's
       visible live cases into an editable copy.
3. **Full-Sheet Preservation & Pending Business Schema:**
   - **Important:** The real Excel workbook has **not yet been delivered by
     the business**. Keep all column header matching inside a single
     configurable mapping adapter — never hardcode provisional column names
     across routes, services, or frontend grid components.
   - Provisional placeholder columns (subject to update once business delivers
     the sample file): `Nr sprawy / Case Number`, `Tytuł / Title`,
     `Klient / Client`, `Przypisany / Assigned To`, `Termin / Deadline`,
     `Data złożenia / Date Filed` (optional), `Uwagi / Note` (optional).
   - Any additional/unmapped columns are preserved verbatim in `extra_columns`
     JSON per row so the full workbook can be edited and re-downloaded cleanly
     without schema lock-in.

---

## Date Parsing & Conflict Rules

1. **Dual Date Support:**
   - Accept native Excel date cells (`datetime`/`date` objects from `openpyxl`)
     AND Polish text formats: `DD.MM.YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`.
   - Unparseable dates produce a per-row validation error — never silently
     coerced to `null`.
   - Past deadlines are valid (overdue cases are allowed on import).
2. **Duplicate & Conflict Handling:**
   - Duplicate `case_number` rows **within the same uploaded file** are blocked
     as preview validation errors.
   - Rows matching an existing DB `case_number` are flagged as conflicts with
     live `{ id, version }` and require explicit per-row `skip` or
     `update_existing` (no auto-merge).
3. **Commit Guarantees (`POST /api/import/copies/:id/commit`):**
   - Reject with `400` if unresolved validation errors or conflicts remain.
   - Non-admins editing live snapshot copies cannot modify `deadline` or
     `date_filed` (`403`).
   - Automatically trigger a **`pre_import` backup snapshot** (`spec 017`)
     immediately before mutating live `cases`.
   - Route every row through the unified case service layer with per-row
     `{ id, version }`, reporting per-row `409` conflicts without silent
     overwrites.
   - Migrate non-empty `Uwagi / Note` cells into initial immutable `case_notes`
     entries (`spec 010`) and update `system_settings["last_import_at"]`.
