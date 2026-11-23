# Automated Backups & Data Snapshots

## Goal

Protect ZUS case data, user records, notes, and edit logs against data corruption,
accidental deletion, or infrastructure failure. The system provides automated
scheduled backups and on-demand manual snapshots triggered before risky operations
(such as large Excel imports).

## User Stories

- As an admin, I want automated daily database backups so that the system can be
  restored quickly without data loss in the event of an outage.
- As an admin, I want to create a manual backup snapshot before importing a large
  Excel file so that I have a clean restore point.
- As an admin, I want to see a list of existing backups with creation date, type,
  and file size so that I can monitor storage health.
- As an admin, I want to securely download a backup archive to an external drive.

## Acceptance Criteria

### Backend
- [ ] Automated daily backup job runs at 02:00 UTC and creates a compressed database
      snapshot in the designated backup directory (`/backups`)
- [ ] `POST /api/admin/backups` triggers an immediate manual snapshot:
  - Generates a timestamped file: `malinois_backup_YYYYMMDD_HHMMSS_manual.sql.gz`
    (or `.sqlite.gz` in local dev)
  - Records a row in `backup_logs`
- [ ] `GET /api/admin/backups` returns a list of existing backups ordered newest first
- [ ] `GET /api/admin/backups/:filename/download` streams the backup file:
  - Only accessible to callers with `role = admin`
  - Validates that filename does not contain path traversal characters (`..`, `/`, `\`)
  - Sets `Content-Disposition: attachment; filename="<filename>"`
- [ ] Backup retention policy:
  - Keeps daily backups for 14 days
  - Prunes backups older than 14 days automatically during the nightly job to
    prevent disk saturation
- [ ] All backup endpoints return `403 Forbidden` for non-admin users

### Frontend
- [ ] Admin Panel includes a dedicated **Kopie zapasowe** (Backups) tab
- [ ] Tab displays:
  - "Utwórz kopię zapasową" (Create backup now) button with loading state
  - Table of backups: Date & Time (Polish locale), Type (Automatyczna / Ręczna),
    File size (formatted in KB / MB), and "Pobierz" (Download) action link
- [ ] Clicking "Utwórz kopię zapasową" disables the button, displays a progress
      spinner, and adds the new backup to the list upon completion
- [ ] Download link uses authenticated streaming fetch with Bearer token

## Out of Scope

- One-click in-app database restoration (database restore is an infrastructure-level
  operation executed via CLI to prevent accidental production overwrite)
- Cloud storage integration (S3 / Azure Blob) in MVP — local mounted volume storage
  is used initially

## API Contract

### `GET /api/admin/backups`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**200 OK**
```json
[
  {
    "id": 1,
    "filename": "malinois_backup_20270115_020000_auto.sql.gz",
    "size_bytes": 1458290,
    "backup_type": "automated",
    "created_at": "2027-01-15T02:00:00Z"
  },
  {
    "id": 2,
    "filename": "malinois_backup_20270115_114500_manual.sql.gz",
    "size_bytes": 1459102,
    "backup_type": "manual",
    "created_at": "2027-01-15T11:45:00Z"
  }
]
```

---

### `POST /api/admin/backups`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**201 Created**
```json
{
  "id": 3,
  "filename": "malinois_backup_20270115_142000_manual.sql.gz",
  "size_bytes": 1460300,
  "backup_type": "manual",
  "created_at": "2027-01-15T14:20:00Z"
}
```

---

### `GET /api/admin/backups/:filename/download`

**Headers:** `Authorization: Bearer <jwt>` (admin only)

**200 OK** — binary stream (`application/gzip`)  
**400 Bad Request** — invalid filename or path traversal attempt  
**403 Forbidden** — not admin  
**404 Not Found** — file not found on disk  

## Data Model Changes

New table `backup_logs`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `filename` | String(255) | Not null, unique |
| `size_bytes` | BigInteger | Not null |
| `backup_type` | String(20) | Not null (`automated` or `manual`) |
| `created_at` | DateTime | Default UTC now, not null |
| `created_by_id` | Integer | FK → `users.id`, nullable (null for automated cron) |
