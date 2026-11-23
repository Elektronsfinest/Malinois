# Dashboard & Summary Stats

## Goal

Replace the bare "Witaj, email!" placeholder with a meaningful landing page
that gives each user an at-a-glance overview of their workload. Supervisors
and admins see team-level summaries. Everyone lands here after login and
immediately knows if something needs urgent attention.

## User Stories

- As a regular user, I want to see a summary of my open and overdue cases the
  moment I log in so that I can prioritise without navigating anywhere.
- As a supervisor, I want to see case counts per team member so that I can spot
  who is overloaded or falling behind on deadlines.
- As an admin, I want to see a system-wide summary (total cases, overdue,
  recently closed) so that I can monitor the health of the whole operation.
- As any user, I want to click a summary card to jump to the filtered case list
  so that the dashboard is actionable, not just informational.

## Acceptance Criteria

### Backend
- [ ] `GET /api/dashboard` returns summary stats scoped by the caller's role
- [ ] Response for `user` role includes:
  - `open_cases` — count of their open, non-archived cases
  - `overdue_cases` — count where `deadline < today` and `status = open`
  - `due_this_week` — count where `deadline` is within the next 7 days and
    `status = open`
  - `closed_this_month` — count closed in the current calendar month
- [ ] Response for `supervisor` role includes the above plus:
  - `team_summary` — array of `{ user_id, email, open_cases, overdue_cases }`
    for each direct subordinate
- [ ] Response for `admin` role includes the above (team_summary = all users)
  plus:
  - `total_cases` — total non-archived cases in the system
  - `import_last_at` — timestamp of the last successful Excel import
    (nullable)
- [ ] The endpoint uses a single efficient query (or a small fixed number of
      queries) — no N+1 per user

### Frontend
- [ ] The Dashboard (`/`) shows stat cards:
  - "Otwarte sprawy" with the count
  - "Zaległe" (overdue) with the count — card is red if count > 0
  - "Termin w tym tygodniu" with the count — card is orange if count > 0
  - "Zamknięte w tym miesiącu" with the count
- [ ] Clicking any card navigates to `/` (Main) with the corresponding filter
      pre-applied (e.g. clicking "Zaległe" sets `deadline_to=today&status=open`)
- [ ] Supervisors see an additional "Mój zespół" table below the cards showing
      one row per team member with their open and overdue counts; clicking a
      row jumps to the case list filtered by that user
- [ ] Admins see the supervisor view plus "Ostatni import" timestamp
- [ ] Stats refresh automatically every 5 minutes while the user is on the page
- [ ] Loading state: skeleton placeholders are shown while the API call is in
      flight; no blank flash

## Out of Scope

- Historical charts or trend graphs (future enhancement)
- Real-time push updates (polling every 5 min is sufficient)
- Per-case type breakdowns (cases are not categorised in this version)

## API Contract

### `GET /api/dashboard`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK — user role**
```json
{
  "open_cases": 12,
  "overdue_cases": 2,
  "due_this_week": 4,
  "closed_this_month": 5
}
```

**200 OK — supervisor role**
```json
{
  "open_cases": 3,
  "overdue_cases": 0,
  "due_this_week": 1,
  "closed_this_month": 2,
  "team_summary": [
    { "user_id": 4, "email": "anna@example.com", "open_cases": 7, "overdue_cases": 2 },
    { "user_id": 5, "email": "piotr@example.com", "open_cases": 2, "overdue_cases": 0 }
  ]
}
```

**200 OK — admin role**
```json
{
  "open_cases": 0,
  "overdue_cases": 0,
  "due_this_week": 0,
  "closed_this_month": 1,
  "total_cases": 134,
  "import_last_at": "2027-01-14T08:00:00Z",
  "team_summary": [ ]
}
```

## Data Model Changes

No new tables. `import_last_at` can be derived from the `system_settings` table
(spec 012) with a key `last_import_at` updated after each successful import.

## Open Questions

- [ ] Should "Zaległe" include cases where `deadline = today` or only
      `deadline < today`? → Strictly past (`deadline < today`).
- [ ] Should the dashboard show a list of the top 5 most urgent cases below the
      cards? → Nice to have; defer to a follow-up iteration.
