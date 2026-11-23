# Case Search & Filtering

## Goal

Let users quickly narrow down their case list on `/cases` (and `/archive`)
using filters and a search box. Filtering by deadline range, overdue/due-soon
status, case status, assigned user, and client name/title gives every role a
fast, bookmarkable workspace.

## User Stories

- As a regular user, I want to filter my cases by status (open / closed) or
  overdue flag so that I can focus on what still needs attention.
- As a regular user, I want to search by client name, case number, or case
  title so that I can jump to a specific case without scrolling.
- As a supervisor, I want to filter by myself or any direct subordinate so that
  I can review one person's workload at a time.
- As a supervisor, I want to filter by deadline range or `due_soon` so that I
  can see what's approaching across my team.
- As an admin, I want to combine filters freely so that I can produce any
  ad-hoc view I need.

## Acceptance Criteria

### Backend
- [ ] `GET /api/cases` accepts the following optional query parameters:
  - `q` — case-insensitive partial match across `case_number`, `title`, and
    `client_name`
  - `status` — `open | closed`
  - `assigned_to` — user ID:
    - `user`: may only filter by their own ID (`403` otherwise)
    - `supervisor`: may filter by their own ID OR any direct subordinate ID
      (`403` otherwise)
    - `admin`: may filter by any user ID
  - `deadline_from` — ISO 8601 date (`YYYY-MM-DD`); returns cases with
    `deadline >= deadline_from`
  - `deadline_to` — ISO 8601 date (`YYYY-MM-DD`); returns cases with
    `deadline <= deadline_to`
  - `overdue` — `true | false`; when `true`, returns open cases where
    `deadline < today_warsaw` (strictly past in `Europe/Warsaw` timezone;
    today's deadline is NOT overdue)
  - `due_soon` — `true | false`; when `true`, returns open cases where
    `today_warsaw <= deadline <= today_warsaw + notification_threshold_days`
  - `archived` — `true | false` (default `false`); mirrors spec 006 (including
    past-assignee visibility when `archived=true`)
- [ ] All filters are combinable (AND logic) and applied **after** role-based
      visibility scoping
- [ ] Default sort is `deadline ASC NULLS LAST`; `sort` param accepts
      `deadline_asc | deadline_desc | updated_at_desc`
- [ ] Pagination: `page` (default `1`) and `page_size` (default `50`, max `200`);
      response ALWAYS uses the unified shape `{ items, total, page, page_size }`
      (consistent across specs 002, 003, 006, 013)

### Frontend
- [ ] The `/cases` header has a search input filtering by `q` (debounced 300 ms)
- [ ] Filter bar below header provides dropdowns/pickers for: status, assigned
      user (supervisor: self + direct subordinates; admin: all), `deadline_from`,
      `deadline_to`, and quick toggles for "Zaległe" (`overdue=true`) and
      "Zbliżający się termin" (`due_soon=true`)
- [ ] Active filters appear as dismissable chips with a **"Wyczyść filtry"**
      button
- [ ] Filter state is synced with URL search params via TanStack Router so
      filtered views (including Dashboard card links) are bookmarkable
- [ ] Pagination controls appear below the table when `total > page_size`

## Out of Scope

- Saved / named filter presets
- Full-text search across `case_notes` (spec 010) or `case_edit_log` (spec 009)
- Dedicated search engines (Elasticsearch) — SQLAlchemy `ILIKE` / `LIKE` with
  B-tree indices is sufficient for expected data volume

## API Contract

### `GET /api/cases` — extended with filters

**Example request**
```
GET /api/cases?status=open&overdue=true&sort=deadline_asc&page=1&page_size=20
Authorization: Bearer <jwt>
```

**200 OK**
```json
{
  "items": [
    {
      "id": 1,
      "case_number": "CASE-2027-0001",
      "title": "Sprawa emerytalna – Kowalski",
      "client_name": "Jan Kowalski",
      "assigned_to": 3,
      "deadline": "2027-01-10",
      "date_filed": "2026-11-01",
      "status": "open",
      "archived": false,
      "version": 2
    }
  ],
  "total": 47,
  "page": 1,
  "page_size": 20
}
```

**400 Bad Request** — invalid ISO date format, invalid `page`/`page_size`, or unknown `sort` value  
**403 Forbidden** — `assigned_to` filter targets a user outside the caller's scope

## Data Model Changes

Indices on `cases` (created in spec 003 migration): `case_number`, `title`,
`client_name`, `assigned_to`, `deadline`, `archived`.

## Resolved Decisions (Indaba Council)

- Unified response key `items` (`{ items, total, page, page_size }`) across 002, 003, 006, 013 (N-14).
- Supervisors can filter by their own ID as well as direct subordinates (N-03).
- Dedicated `overdue=true` (`deadline < today` in `Europe/Warsaw`) and `due_soon=true` (using `notification_threshold_days`) query parameters added (N-15, N-16).
