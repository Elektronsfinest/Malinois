# Concurrent Editing & Draft Protection

## Goal

Allow multiple users to work on the same case safely without silently
overwriting each other's changes, and prevent silent loss of unsaved edits when
a 60-minute JWT expires mid-edit. Every case mutation in the system routes
through one service layer enforcing optimistic locking (`version`), and
session-expiry drafts are preserved in `sessionStorage`.

## User Stories

- As a user editing a case, I want to be warned if someone else saves a change
  to the same case while I am still editing so that I don't unknowingly
  overwrite their work.
- As a user, I want to see what the other person changed so that I can decide
  whether to keep my version, their version, or merge manually.
- As a supervisor or admin running bulk actions, archive/restore, reassignment,
  or an Excel import commit, I want stale versions to be detected per row so that
  concurrent edits are never silently clobbered.
- As a user whose 60-minute session expires while editing a form, I want my
  unsaved changes preserved across re-login so that I never lose work silently.

## Acceptance Criteria

### Backend
- [ ] The `cases` table has a `version` column (`Integer`, not null,
      `server_default="1"`)
- [ ] **Unified service-layer enforcement (zero bypasses):**
  - Every single-case mutation (`PATCH /api/cases/:id`,
    `POST /api/cases/:id/archive`, `POST /api/cases/:id/restore`) MUST require
    `version` in the request body, verify `cases.version == submitted_version`
    inside a DB transaction, atomically increment `version = version + 1`, and
    return `409 Conflict` with the latest `current` case object on mismatch
  - Bulk operations (`POST /api/cases/bulk`, spec 015), reassignment
    (`POST /api/cases/reassign`, spec 016), and Excel import commits
    (`POST /api/import/commit`, spec 004) MUST supply per-row
    `{ id, version }` from the UI selection or import preview, verify and
    increment `version` on each row, and report per-row `409` conflicts without
    silent overwrites
- [ ] `GET /api/cases` and `GET /api/cases/:id` always return `version` on
      every case object

### Frontend
- [ ] When opening the inline Case Editor (spec 003), the client records the
      loaded `version` and sends it on every save, archive, or restore request
- [ ] On a `409 Conflict` response, an accessible conflict modal
      (`role="alertdialog"`) shows two columns: **"Twoja wersja"** (unsaved
      values) and **"Zapisana wersja"** (latest server values from `current`)
- [ ] The user chooses:
  - **"Nadpisz"** — re-submits their changes using `current.version` (all field
    changes are still recorded normally in `case_edit_log`, spec 009)
  - **"Odrzuć moje zmiany"** — reloads the editor from `current`
- [ ] **Session-expiry draft protection (N-17):**
  - On any `401 Unauthorized` while a form has unsaved edits, the frontend
    persists the draft in `sessionStorage` keyed by the current user's email
    and opens an inline **re-login modal**
  - Upon successful re-authentication as the **same user**, the modal closes
    and the unsaved draft is restored automatically
  - Drafts are cleared immediately on explicit logout or if a **different
    user** signs in
- [ ] No silent data loss — the editor never discards unsaved changes without
      explicit user confirmation

## Out of Scope

- Real-time collaborative cursor sync (Google Docs style)
- WebSocket-based live presence indicators (future enhancement)
- Automatic three-way text merging (resolved explicitly by the user)

## API Contract

### `PATCH /api/cases/:id` — with version check

**Request**
```json
{
  "version": 3,
  "status": "closed"
}
```

**200 OK** — save successful
```json
{
  "id": 1,
  "version": 4,
  "status": "closed"
}
```

**409 Conflict** — version mismatch
```json
{
  "detail": "Konflikt wersji: sprawa została zmodyfikowana przez innego użytkownika.",
  "current": {
    "id": 1,
    "case_number": "CASE-2027-0001",
    "title": "Sprawa emerytalna – Kowalski",
    "client_name": "Jan Kowalski",
    "assigned_to": 3,
    "deadline": "2027-02-10",
    "date_filed": "2026-11-01",
    "status": "open",
    "archived": false,
    "version": 4,
    "updated_at": "2027-01-15T12:00:00Z"
  }
}
```

## Data Model Changes

Add to `cases` table:
- `version` — `Integer`, not null, `server_default="1"` (also listed in spec 003)

## Resolved Decisions (Indaba Council)

- All case mutations (PATCH, archive, restore, bulk, reassign, Excel import commit) enforce and increment `version` through one service layer with no silent overwrites (N-06).
- On `401` during editing, unsaved drafts are saved to `sessionStorage` and restored via a re-login modal, clearing on explicit logout or user switch (N-17).
