# Case Search & Filtering

## Goal

Let users quickly narrow down their case list using filters and a search box.
As the number of imported cases grows, scrolling through a flat list becomes
impractical. Filtering by deadline range, status, assigned user, and client
name gives everyone — from a regular user with a few cases to an admin with
hundreds — a usable interface.

## User Stories

- As a regular user, I want to filter my cases by status (open / closed) so
  that I can focus on what still needs attention.
- As a regular user, I want to search by client name or case title so that I
  can jump to a specific case without scrolling.
- As a supervisor, I want to filter by team member so that I can review one
  person's workload at a time.
- As a supervisor, I want to filter by deadline range so that I can see what's
  due this week across the whole team.
- As an admin, I want to combine filters freely so that I can produce any
  ad-hoc view I need.

## Acceptance Criteria

### Backend
- [ ] `GET /api/cases` accepts the following optional query parameters:
  - `q` — full-text search across `title` and `client_name` (case-insensitive,
    partial match)
  - `status` — `open | closed`
  - `assigned_to` — user ID; supervisors may filter by any subordinate ID;
    regular users may only filter by their own ID; admin can filter by any
  - `deadline_from` — ISO 8601 date; returns cases with `deadline ≥` this date
  - `deadline_to` — ISO 8601 date; returns cases with `deadline ≤` this date
  - `archived` — `true | false` (default `false`); mirrors the archive filter
    from spec 006
- [ ] All filters are combinable (AND logic)
- [ ] The endpoint still enforces role-based row visibility before applying
      filters — a user cannot access cases outside their permission scope by
      crafting a filter
- [ ] `assigned_to` filter for a regular user returns `403` if the target ID
      is not their own
- [ ] Results are sorted by `deadline ASC` by default; a `sort` param accepts
      `deadline_asc | deadline_desc | updated_at_desc`
- [ ] Pagination: `page` (default 1) and `page_size` (default 50, max 200)
      query params; response includes `total`, `page`, `page_size`

### Frontend
- [ ] The Main page header has a search input that filters by `q` as the user
      types (debounced 300 ms)
- [ ] A filter bar below the header has dropdowns / date pickers for:
      status, assigned user (supervisor/admin only), deadline from, deadline to
- [ ] Active filters are shown as dismissable chips above the case table
- [ ] "Wyczyść filtry" button resets all filters at once
- [ ] Filter state is preserved in the URL query string so that a filtered view
      can be bookmarked or shared
- [ ] Pagination controls appear at the bottom of the table when `total >
      page_size`

## Out of Scope

- Saved / named filter presets
- Full-text search across notes (spec 010) or edit history (spec 009)
- Elasticsearch or other dedicated search engine — SQLite/Postgres LIKE queries
  are sufficient for the expected data volume

## API Contract

### `GET /api/cases` — extended with filters

**Example request**
```
GET /api/cases?status=open&deadline_to=2027-01-31&sort=deadline_asc&page=1&page_size=20
Authorization: Bearer <jwt>
```

**200 OK**
```json
{
  "total": 47,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "id": 1,
      "title": "Sprawa emerytalna – Kowalski",
      "client_name": "Jan Kowalski",
      "assigned_to": 3,
      "deadline": "2027-01-10",
      "status": "open",
      "archived": false,
      "version": 2
    }
  ]
}
```

**400 Bad Request** — invalid date format or unknown `sort` value  
**403 Forbidden** — `assigned_to` filter targets a user outside the caller's
scope

## Data Model Changes

No new tables. Requires a database index on `cases.title` and
`cases.client_name` for `LIKE` queries to be fast enough:

```sql
CREATE INDEX idx_cases_title ON cases (title);
CREATE INDEX idx_cases_client_name ON cases (client_name);
```

Add to the Alembic migration for spec 003 (or as a follow-up migration).

## Open Questions

- [ ] Should `q` search case notes (spec 010) as well?
      → Out of scope for this spec; can be added later.
- [ ] Is the Polish locale accent-insensitive search needed
      (e.g. "Kowalski" matches "Kowalski" with or without diacritics)?
      → Nice to have; depends on the database collation. Flag as a future
      enhancement.
