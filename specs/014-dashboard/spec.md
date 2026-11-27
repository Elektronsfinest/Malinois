# Dashboard & Summary Stats

## Goal

Replace the bare `"Witaj, email!"` placeholder at `/` with an actionable
landing dashboard that gives each user an at-a-glance overview of their
workload. Supervisors and admins see per-member team summaries via the single
`GET /api/dashboard/summary` endpoint. Clicking any card or team row navigates
to `/cases` with the corresponding filter pre-applied.

## User Stories

- As a regular user, I want to see a summary of my open, overdue, and due-soon
  cases the moment I log in so that I can prioritise without navigating.
- As a supervisor, I want to see case counts per direct subordinate (and my own
  cases) so that I can spot who is overloaded or falling behind on deadlines.
- As an admin, I want to see a system-wide summary (total cases, overdue,
  due-soon, last import timestamp) so that I can monitor the whole operation.
- As any user, I want to click a summary card to jump to `/cases` with the
  matching filter pre-applied so that the dashboard is actionable.

## Acceptance Criteria

### Backend
- [ ] `GET /api/dashboard/summary` is the single summary endpoint for Dashboard
      and supervisor per-member totals (no duplicate `/api/cases/summary`)
- [ ] All date boundaries use the `Europe/Warsaw` timezone and the admin-
      configured `notification_threshold_days` (default `7`, spec 012)
- [ ] Response for `user` role includes:
  - `notification_threshold_days` — current global threshold
  - `open_cases` — count of their open, non-archived cases
  - `overdue_cases` — count where `deadline < today_warsaw` (strictly past;
    today's deadline is NOT overdue) and `status = open` and `archived = false`
  - `due_soon` — count where `today_warsaw <= deadline <= today_warsaw +
    notification_threshold_days` and `status = open` and `archived = false`
  - `closed_this_month` — count closed in the current calendar month
    (`Europe/Warsaw`)
- [ ] Response for `supervisor` role includes the above (scoped to own +
      direct subordinates' cases) plus:
  - `team_summary` — array of `{ user_id, email, open_cases, overdue_cases,
    due_soon }` for the supervisor and each direct subordinate
- [ ] Response for `admin` role includes the above (`team_summary` = all active
      users) plus:
  - `total_cases` — total non-archived cases in the system
  - `import_last_at` — ISO 8601 UTC timestamp of the last committed Excel copy
    (nullable, read from `system_settings["last_import_at"]`)
- [ ] Uses a small fixed number of SQL aggregate queries — no N+1 per user

### Frontend
- [ ] Dashboard lives at `/` (login redirects to `/`); Main case table lives
      at `/cases`
- [ ] Renders stat cards styled with Malinois dark-blue glassmorphism:
  - **"Otwarte sprawy"** → clicks through to `/cases?status=open`
  - **"Zaległe"** (red accent `#ef4444` when > 0) → clicks through to
    `/cases?overdue=true&status=open`
  - **"Zbliżający się termin (≤ X dni)"** (orange accent `#f59e0b` when > 0,
    where `X = notification_threshold_days`) → clicks through to
    `/cases?due_soon=true&status=open`
  - **"Zamknięte w tym miesiącu"** → clicks through to `/cases?status=closed`
- [ ] Supervisors see a **"Mój zespół"** table below the cards (one row per
      member with open, overdue, and due-soon counts); clicking a row navigates
      to `/cases?assigned_to=<user_id>`
- [ ] Admins see the team table plus **"Ostatni import"** timestamp (Polish
      locale `DD.MM.YYYY, HH:mm`)
- [ ] Stats auto-refresh every 5 minutes while the page is open
- [ ] Loading state renders glassmorphic skeleton placeholders (no blank flash)

## Out of Scope

- Historical charts or trend graphs (future enhancement)
- Real-time WebSocket push updates (5-minute polling is sufficient)
- Per-case type breakdowns

## API Contract

### `GET /api/dashboard/summary`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK — user role**
```json
{
  "notification_threshold_days": 7,
  "open_cases": 12,
  "overdue_cases": 2,
  "due_soon": 4,
  "closed_this_month": 5
}
```

**200 OK — supervisor role**
```json
{
  "notification_threshold_days": 7,
  "open_cases": 12,
  "overdue_cases": 2,
  "due_soon": 3,
  "closed_this_month": 6,
  "team_summary": [
    { "user_id": 2, "email": "supervisor@example.com", "open_cases": 3, "overdue_cases": 0, "due_soon": 1 },
    { "user_id": 4, "email": "anna@example.com", "open_cases": 7, "overdue_cases": 2, "due_soon": 2 },
    { "user_id": 5, "email": "piotr@example.com", "open_cases": 2, "overdue_cases": 0, "due_soon": 0 }
  ]
}
```

**200 OK — admin role**
```json
{
  "notification_threshold_days": 7,
  "open_cases": 80,
  "overdue_cases": 5,
  "due_soon": 14,
  "closed_this_month": 21,
  "total_cases": 134,
  "import_last_at": "2027-01-14T08:00:00Z",
  "team_summary": []
}
```

## Data Model Changes

No new tables. Reads `cases`, `users`, and `system_settings` (`notification_threshold_days`, `last_import_at`).

## Resolved Decisions (Indaba Council)

- Dashboard at `/`, Main case table at `/cases`, login redirects to `/` (N-15).
- Single summary endpoint `GET /api/dashboard/summary` replaces any duplicate cases summary endpoint (N-14).
- `due_this_week` replaced by `due_soon` driven by `notification_threshold_days` (N-15).
- "Zaległe" is strictly `deadline < today` (`Europe/Warsaw`) and links to `/cases?overdue=true&status=open` (N-16).
