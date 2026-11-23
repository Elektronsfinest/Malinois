# Automated Backups & Data Snapshots

## Goal

Protect the **single** Malinois database (users, active & archived cases,
working copies, notes, edit history, and audit logs — confirming `DB2? = No`)
against data corruption, bad imports, or infrastructure failure. Provides
scheduled nightly backups, **mandatory automatic pre-import snapshots** (spec
004), on-demand manual snapshots, and password-reverified, audit-logged admin
downloads.

## User Stories

- As an admin, I want automated daily database backups so that the system can
  be restored quickly without data loss in the event of an outage.
- As an admin, I want an automatic snapshot taken before every Excel copy
  commit so that any bad bulk import has an immediate clean restore point.
- As an admin, I want to trigger a manual backup snapshot and inspect backup
  history (date, type, file size).
- As an admin, I want backup downloads to require password re-verification and
  be recorded in the audit log so that sensitive personal data is protected.

## Acceptance Criteria

### Backend
- [ ] Single-database architecture: all application tables live in one
      PostgreSQL (prod) or SQLite (local dev) database; backups snapshot this
      entire database
- [ ] Automated daily backup job runs at `02:00 UTC` and creates a compressed
      snapshot in the configured backup directory (`BACKUP_DIR`, default `/backups`)
- [ ] **Automatic pre-import snapshot (N-23):** every
      `POST /api/import/copies/:copy_id/commit` (spec 004) automatically creates
      a snapshot with `backup_type = "pre_import"` before mutating live `cases`
- [ ] `POST /api/admin/backups` triggers an immediate manual snapshot:
  - Generates `malinois_backup_YYYYMMDD_HHMMSS_<type>.sql.gz` (or `.sqlite.gz`
    in local dev)
  - Records a row in `backup_logs` (`backup_type`: `automated` | `manual` |
    `pre_import`)
- [ ] `GET /api/admin/backups` returns existing backups ordered newest first
- [ ] `POST /api/admin/backups/:filename/download` streams the backup file:
  - Restricted to `admin` (`403` for others)
  - **Requires admin password re-verification:** request body
    `{ "password": "<current_admin_password>" }` verified via bcrypt
    (`401 Unauthorized` if password is invalid)
  - Validates `filename` matches strict allowlist pattern and rejects path
    traversal (`..`, `/`, `\`) with `400 Bad Request`
  - Records `backup_downloaded` (with `filename`) in `admin_audit_log` (spec 009)
  - Sets `Content-Disposition: attachment; filename="<filename>"`
- [ ] Retention policy: keeps backup files for **14 days** and prunes expired
      backup archive files during the nightly job (never deletes live or
      archived `cases` rows)
- [ ] All `/api/admin/backups*` endpoints return `403 Forbidden` for non-admin
      users

### Frontend
- [ ] Mounted as the 4th tab (**Kopie zapasowe**) in Admin Panel (`/admin`,
      spec 012)
- [ ] Displays:
  - **"Utwórz kopię zapasową"** button with loading state
  - Table of backups: Date & Time (Polish locale `DD.MM.YYYY, HH:mm`), Type
    (`Automatyczna` / `Ręczna` / `Przed importem`), File size (KB / MB), and
    **"Pobierz"** action button
- [ ] Clicking **"Pobierz"** opens a password re-verification modal before
      calling `POST /api/admin/backups/:filename/download` with Bearer token
      and streaming the download

## Out of Scope

- One-click in-app database restoration (restoration is a CLI/infrastructure
  operation to prevent accidental production overwrite)
- Cloud object storage (S3 / Azure Blob) in MVP — mounted volume storage first

## API Contract

### `GET /api/admin/backups`
**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**200 OK**
```json
[
  {
    "id": 2,
    "filename": "malinois_backup_20270115_114500_pre_import.sql.gz",
    "size_bytes": 1459102,
    "backup_type": "pre_import",
    "created_at": "2027-01-15T11:45:00Z"
  },
  {
    "id": 1,
    "filename": "malinois_backup_20270115_020000_automated.sql.gz",
    "size_bytes": 1458290,
    "backup_type": "automated",
    "created_at": "2027-01-15T02:00:00Z"
  }
]
```

---

### `POST /api/admin/backups`
**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**201 Created** — created `backup_logs` entry

---

### `POST /api/admin/backups/:filename/download`
**Headers:** `Authorization: Bearer <jwt>` (admin only)  
**Request Body**
```json
{ "password": "AdminCurrentPassword1!" }
```
**200 OK** — binary stream (`application/gzip`)  
**400 Bad Request** — invalid filename or path traversal attempt  
**401 Unauthorized** — invalid admin password  
**403 Forbidden** — not admin  
**404 Not Found** — backup file not found

## Data Model Changes

New table `backup_logs`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `filename` | String(255) | Not null, unique |
| `size_bytes` | BigInteger | Not null |
| `backup_type` | String(20) | Not null (`automated` \| `manual` \| `pre_import`) |
| `created_at` | DateTime | Default UTC now, not null |
| `created_by_id` | Integer | FK → `users.id`, nullable (null for automated cron) |

## Resolved Decisions (Indaba Council)

- Single database confirmed (`DB2? = No`) (N-23).
- Mandatory automatic `pre_import` backup snapshot before every Excel copy commit (N-23).
- Backup downloads require admin password re-verification and are logged in `admin_audit_log` (N-23).
- Mounted as the 4th tab inside Admin Panel `/admin` (N-21).
