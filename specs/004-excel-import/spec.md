# Excel Import

## Goal

Allow authorised users to upload a ZUS Excel file containing case data. The
app reads dates and case metadata from the file, validates the content, and
either creates new cases or updates existing ones in the database. The site
always works on a copy of the original document — the source file is never
modified.

## User Stories

- As an admin, I want to upload an Excel file so that all case deadlines are
  imported into the system without manual entry.
- As an admin, I want to download the current case data back as an Excel file
  so that I have a snapshot for auditing or offline use.
- As an admin, I want the import to report validation errors (missing columns,
  bad dates) so that I can fix the file before retrying.
- As a user, I want the imported data to automatically appear in my case list
  so that I can start working immediately after upload.

## Acceptance Criteria

### Backend
- [ ] `POST /api/admin/import` accepts `multipart/form-data` with an `.xlsx`
      or `.xls` file; returns `400` for other file types
- [ ] The endpoint is restricted to `admin` role; returns `403` for others
- [ ] The importer reads the following columns (by header name, case-insensitive):
      `Tytuł / Title`, `Klient / Client`, `Przypisany / Assigned To` (email),
      `Termin / Deadline` (date), `Data złożenia / Date Filed` (date, optional)
- [ ] Dates are parsed as Polish locale (`DD.MM.YYYY` or `YYYY-MM-DD`)
- [ ] Rows with missing required columns or unparseable dates are collected into
      a validation error report and skipped — they do not abort the entire import
- [ ] On successful import, the response includes a summary:
      `{ created, updated, skipped, errors: [{ row, reason }] }`
- [ ] `GET /api/admin/export` generates and returns an `.xlsx` file of all
      cases visible to admin; `Content-Disposition: attachment` header set
- [ ] Uploaded files are processed in memory and not persisted to disk
      (optional file storage is a future enhancement)

### Frontend
- [ ] The Admin Editor page has a drag-and-drop zone and a "Browse" button for
      file upload
- [ ] Upload progress is shown while the server processes the file
- [ ] On completion, a summary modal shows counts of created/updated/skipped
      rows and lists any errors with row numbers
- [ ] A "Download Excel" button on the Admin Editor page triggers
      `GET /api/admin/export`
- [ ] Non-admin users do not see the import/export controls

## Out of Scope

- Importing users from Excel
- Real-time collaborative import (concurrent uploads)
- Persistent storage of uploaded files (optional storage node noted in diagram)
- Support for `.csv`, `.ods`, or Google Sheets

## API Contract

### `POST /api/admin/import`

**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**Body:** `multipart/form-data`, field `file` containing `.xlsx`/`.xls`

**200 OK**
```json
{
  "created": 12,
  "updated": 3,
  "skipped": 1,
  "errors": [
    { "row": 7, "reason": "Nieprawidłowa data w kolumnie 'Termin': '99.13.2027'" }
  ]
}
```

**400 Bad Request** — wrong file type or completely unparseable file  
**403 Forbidden** — not admin

---

### `GET /api/admin/export`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**200 OK** — `.xlsx` binary  
**Headers:**
```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="malinois-export-2027-01-15.xlsx"
```

**403 Forbidden** — not admin

## Data Model Changes

No new tables. Import writes to the `cases` table (spec 003).

Optional future addition: `import_logs` table to track upload history (not in
scope for this spec).

## Open Questions

- [ ] What is the exact column layout of the real ZUS Excel file?
      → A sample file is needed before implementation can begin.
- [ ] Should duplicate rows (same title + client + deadline) overwrite or be
      skipped?
      → Default: update if assigned user matches; skip with error otherwise.
- [ ] Is the "Assigned To" column an email or a display name?
      → Assumed email for now; must match an existing user account.
