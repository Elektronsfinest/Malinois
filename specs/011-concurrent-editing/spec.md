# Concurrent Editing

## Goal

Allow multiple users to edit the same case simultaneously without silently
overwriting each other's changes. The system must detect conflicts, present
them clearly, and let the user decide how to resolve them. This is a hard
requirement from the client: several people may work on the same case at the
same time.

## User Stories

- As a user editing a case, I want to be warned if someone else saves a change
  to the same case while I am still editing so that I don't unknowingly
  overwrite their work.
- As a user, I want to see what the other person changed so that I can decide
  whether to keep my version, their version, or merge manually.
- As a supervisor, I want case edits to be safe regardless of concurrency so
  that I can trust the data integrity of the system.

## Acceptance Criteria

### Backend
- [ ] The `cases` table has a `version` column (integer, default `1`)
- [ ] Every successful `PATCH /api/cases/:id` request must include
      `{ "version": <current_version> }` in the body
- [ ] If the submitted `version` does not match the current `version` in the
      database, the server returns `409 Conflict` with the latest case data
      so the client can show the diff
- [ ] On a successful save, `version` is incremented by 1 atomically
- [ ] `GET /api/cases/:id` and `GET /api/cases` always return the current
      `version` field on each case object
- [ ] The version check is performed inside a database transaction to prevent
      race conditions between two concurrent saves

### Frontend
- [ ] When opening the case Editor, the client records the `version` it loaded
- [ ] Every save request sends the recorded `version` alongside the changed
      fields
- [ ] On a `409` response, the editor shows a conflict modal with two columns:
      "Twoja wersja" (your unsaved values) and "Zapisana wersja" (the values
      that were saved by the other user)
- [ ] The user can choose: "Nadpisz" (force-save your version, loading the new
      `version` number first) or "Odrzuć moje zmiany" (reload from server)
- [ ] After resolving, the editor updates to reflect the chosen outcome
- [ ] No silent data loss — the editor never discards unsaved changes without
      explicit user confirmation

## Out of Scope

- Real-time collaborative editing (Google Docs style — live cursor sync)
- WebSocket-based "someone is editing" presence indicators (future enhancement)
- Three-way merge of overlapping text fields — the user resolves manually

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
  "detail": "Conflict: case was modified by another user.",
  "current": {
    "id": 1,
    "version": 4,
    "status": "open",
    "note": "Zmiana przez Anna.",
    "updated_at": "2027-01-15T12:00:00Z"
  }
}
```

The `current` object contains the full latest case so the client can render
the diff without an extra request.

## Data Model Changes

Add to `cases` table:
- `version` — `Integer`, not null, default `1`

No new tables. The version column is updated atomically within the existing
`PATCH` transaction.

## Open Questions

- [ ] Should `version` be exposed to end users in the UI or kept internal?
      → Internal — only shown in the conflict modal for debugging if helpful.
- [ ] What happens if the same user has the case open in two browser tabs?
      → Same conflict flow — the second save from tab 2 will get a `409`.
- [ ] Is optimistic locking sufficient, or is a pessimistic lock (edit lock)
      needed? → Optimistic locking (version field) is sufficient for the
      expected concurrency level; pessimistic locks add UX complexity.
