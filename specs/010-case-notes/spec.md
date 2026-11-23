# Case & Person Notes

## Goal

Provide the **sole** note-taking system for Malinois (`case_notes`), allowing
users to attach immutable free-text notes to a case, to a specific employee
("notatka do osoby" from `appbuild.drawio.xml`), or to both. Replaces the
removed `cases.note` column from spec 003.

## User Stories

- As a regular user, I want to add a note to one of my cases so that I can
  record context that isn't captured in structured fields.
- As a supervisor, I want to read notes left by my subordinates on their cases
  and leave instructions on a subordinate's case or directly on a person's
  profile.
- As any user, I want to see who wrote each note and when so that I know whose
  instruction or comment it reflects.
- As an admin, I want to delete any note so that inappropriate content can be
  removed.

## Acceptance Criteria

### Backend
- [ ] `case_notes` is the exclusive note store (`cases.note` is removed from
      spec 003). Any imported `Uwagi / Note` column (spec 004) creates an
      initial `case_notes` row
- [ ] Schema supports both case notes and person notes via nullable `case_id`
      and nullable `subject_user_id` with a DB check constraint:
      `CHECK (case_id IS NOT NULL OR subject_user_id IS NOT NULL)`
- [ ] **Case notes endpoints:**
  - `GET /api/cases/:id/notes` returns all notes attached to `case_id`, newest
    first; returns `404 Not Found` if case does not exist or is out of scope
  - `POST /api/cases/:id/notes` creates a note with `{ "content": "...", "subject_user_id": <optional int> }`;
    `content` must be non-empty and ≤ 2000 characters (`400` otherwise);
    returns `404` if case is out of scope
- [ ] **Person-only notes ("notatka do osoby") endpoints:**
  - `GET /api/users/:user_id/notes` returns person notes where
    `subject_user_id == user_id` (newest first); visible only to the note
    **author**, the **subject user**, the **subject's direct supervisor**, and
    **admin** (`404 Not Found` otherwise)
  - `POST /api/users/:user_id/notes` creates a person-only note (`case_id = null`,
    `subject_user_id = user_id`); allowed for the user themselves, their direct
    supervisor, or admin (`404` if target user is out of scope)
- [ ] `DELETE /api/notes/:note_id` — author may delete their own note; `admin`
      may delete any note; non-author non-admin on a visible note receives
      `403 Forbidden`; out-of-scope or non-existent note returns `404 Not Found`
- [ ] Notes are immutable after creation (delete and re-create instead)
- [ ] Author (`author_id`) is always derived from the authenticated user
      (`get_current_user`), never from the request body

### Frontend
- [ ] The inline Case Editor (`Edytor wstępny`, spec 003) shows a **"Notatki"**
      section with existing notes, an optional "Dotyczy osoby" dropdown
      (in-scope users), a text area with character counter (max 2000), and a
      **"Dodaj notatkę"** button
- [ ] Supervisors and admins can also view/add person-only notes on a team
      member's card/panel
- [ ] Each note displays: author email, optional subject email badge, timestamp
      (Polish locale `DD.MM.YYYY, HH:mm`), and plain-text content (never
      `dangerouslySetInnerHTML`)
- [ ] A **"Usuń"** button appears on notes authored by the current user, and on
      all notes for `admin`
- [ ] New notes appear at the top of the list immediately without a page reload

## Out of Scope

- Editing a note after creation
- `@mention` autocomplete or push notifications for notes
- File attachments on notes
- Note-level visibility overrides on case notes (everyone with access to a case
  sees all notes attached to that case)

## API Contract

### `GET /api/cases/:id/notes`
**Headers:** `Authorization: Bearer <jwt>`  
**200 OK**
```json
[
  {
    "id": 5,
    "case_id": 12,
    "subject_user_id": 3,
    "subject_email": "jan@example.com",
    "content": "Klient potwierdził odbiór dokumentów telefonicznie.",
    "author_email": "anna@example.com",
    "created_at": "2027-01-14T09:00:00Z"
  }
]
```
**404 Not Found** — case does not exist or is outside caller's scope

---

### `POST /api/cases/:id/notes`
**Request**
```json
{ "content": "Złożono odwołanie w sprawie klienta.", "subject_user_id": null }
```
**201 Created** — created note object  
**400 Bad Request** — empty content, over 2000 chars, or invalid `subject_user_id`  
**404 Not Found** — case does not exist or is outside caller's scope

---

### `GET /api/users/:user_id/notes` & `POST /api/users/:user_id/notes`
**Headers:** `Authorization: Bearer <jwt>`  
**Request (POST)**
```json
{ "content": "Proszę o priorytetowe przejęcie spraw podczas urlopu Anny." }
```
**200 OK / 201 Created** — note list / created note object (`case_id: null`)  
**404 Not Found** — target user does not exist or is outside caller's scope

---

### `DELETE /api/notes/:note_id`
**204 No Content** — deleted  
**403 Forbidden** — not the author and not admin (on a visible note)  
**404 Not Found** — note does not exist or is outside caller's scope

## Data Model Changes

New table `case_notes`:

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, auto-increment |
| `case_id` | Integer | FK → `cases.id`, nullable, indexed |
| `subject_user_id` | Integer | FK → `users.id`, nullable, indexed |
| `author_id` | Integer | FK → `users.id`, not null |
| `content` | Text | Not null, max 2000 chars |
| `created_at` | DateTime | Default UTC now, not null |

Constraints & indices:
- `CHECK (case_id IS NOT NULL OR subject_user_id IS NOT NULL)`
- Index `(case_id, created_at DESC)`
- Index `(subject_user_id, created_at DESC)`

## Resolved Decisions (Indaba Council)

- `cases.note` removed from spec 003; `case_notes` is the sole note store and imported `Uwagi` becomes an initial `case_notes` entry (N-10).
- "Notatka do osoby" supported via nullable `case_id` + nullable `subject_user_id` with DB `CHECK` constraint and visibility scoped to author, subject, subject's supervisor, and admin (N-10).
- Out-of-scope resources return `404` (N-05).
