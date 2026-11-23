# Case Notes

## Goal

Allow users to attach free-text notes to a case or to a specific person
involved in the case. Notes provide context that does not fit into structured
fields — internal comments, reminders, or instructions left for colleagues.

## User Stories

- As a regular user, I want to add a note to one of my cases so that I can
  record context that isn't captured in any structured field.
- As a supervisor, I want to read notes left by my subordinates on their cases
  so that I understand the case status without asking them directly.
- As a user, I want to see who wrote each note and when so that I know whose
  opinion or instruction it reflects.
- As a supervisor, I want to leave a note on a subordinate's case so that I
  can give instructions without editing the structured fields.
- As an admin, I want to delete any note so that inappropriate content can be
  removed.

## Acceptance Criteria

### Backend
- [ ] `GET /api/cases/:id/notes` returns all notes for a case, newest first;
      visibility follows the same role rules as `GET /api/cases/:id`
- [ ] `POST /api/cases/:id/notes` creates a new note; body: `{ "content": "…" }`;
      `content` must be non-empty and ≤ 2000 characters
- [ ] `DELETE /api/cases/:id/notes/:note_id` — a user may delete their own
      notes; an admin may delete any note; others receive `403`
- [ ] Notes are not editable after creation — delete and re-create instead
- [ ] The note author is derived from the JWT, not from the request body

### Frontend
- [ ] The case Editor panel shows a "Notatki" section with a list of existing
      notes and a text area + "Dodaj notatkę" button
- [ ] Each note displays: author email, timestamp (Polish locale), note content
- [ ] A note created by the current user shows a "Usuń" (delete) button;
      admin users see it on all notes
- [ ] The text area has a visible character counter (max 2000)
- [ ] After submitting, the new note appears at the top of the list without a
      full page reload

## Out of Scope

- Editing a note after creation
- Mentioning / tagging other users in notes
- Attaching files to notes
- Note visibility restrictions below the case level (all users with case access
  see all notes on that case)

## API Contract

### `GET /api/cases/:id/notes`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK**
```json
[
  {
    "id": 5,
    "content": "Klient potwierdził odbiór dokumentów telefonicznie.",
    "author_email": "anna@example.com",
    "created_at": "2027-01-14T09:00:00Z"
  }
]
```

**403 Forbidden** — case not visible to user  
**404 Not Found**

---

### `POST /api/cases/:id/notes`

**Request**
```json
{ "content": "Złożono odwołanie do ZUS." }
```

**201 Created**
```json
{
  "id": 6,
  "content": "Złożono odwołanie do ZUS.",
  "author_email": "jan@example.com",
  "created_at": "2027-01-15T11:22:00Z"
}
```

**400 Bad Request** — empty content or over 2000 characters  
**403 Forbidden** — no access to case

---

### `DELETE /api/cases/:id/notes/:note_id`

**204 No Content** — deleted  
**403 Forbidden** — not the author and not admin  
**404 Not Found**

## Data Model Changes

New table `case_notes`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `case_id` | Integer | FK → `cases.id`, not null |
| `author_id` | Integer | FK → `users.id`, not null |
| `content` | Text | Not null, max 2000 chars |
| `created_at` | DateTime | Default UTC now, not null |

Index: `(case_id, created_at DESC)`.

## Open Questions

- [ ] Should notes be included in the edit history (spec 009)?
      → No — notes are their own entity, not a field on `cases`.
- [ ] Should supervisors be able to delete subordinates' notes?
      → No for now; admin-only deletion keeps it simple.
