# AGENTS.md — Malinois Project Guide

This file describes the project structure, tech stack, conventions, and rules for AI agents working on this codebase. Read it fully before making any changes.

---

## Project Overview

**Malinois** is a full-stack web application with:
- A **FastAPI** backend (`apps/api`) backed by **PostgreSQL** (via Docker) or **SQLite** (local dev)
- A **React + Vite** frontend (`apps/web`) using **TanStack Router** for routing and auth
- **GitHub Actions** CI for both apps
- A shared `packages/` directory for cross-app types

The app is a **case-management and deadline-tracking system** (built as a trainee project) for tracking deadlines and client cases imported from Excel. It implements:
- JWT-based authentication with three user roles (admin / supervisor / user)
- Role-scoped case visibility and editing (users see own cases, supervisors see team, admins see all)
- Excel import/export of case data with date parsing
- Deadline notifications with popup alerts
- Case archiving (soft-delete with restore)
- Strict security controls over sensitive personal data

---

## Backend — `apps/api`

### Language & Runtime
- **Python 3.14+**
- Package manager: **uv** (`uv sync`, `uv run`)

### Dependencies (`pyproject.toml`)

| Package | Purpose |
|---|---|
| `fastapi[standard]` | Web framework — routes, dependency injection, OpenAPI docs |
| `sqlalchemy` | ORM — `DeclarativeBase`, `mapped_column`, `Session`, `select()` |
| `alembic` | Database migrations — always use instead of `create_all` |
| `psycopg[binary]` | PostgreSQL driver (used in production via `DATABASE_URL`) |
| `pyjwt` | JWT encoding/decoding (`jwt.encode`, `jwt.decode`, `jwt.PyJWTError`) |
| `bcrypt` | Password hashing (`bcrypt.hashpw`, `bcrypt.checkpw`, `bcrypt.gensalt`) |
| `httpx` *(dev)* | Async HTTP client used by FastAPI's `TestClient` internally |
| `pytest` *(dev)* | Test runner — config in `pyproject.toml` under `[tool.pytest.ini_options]` |

### Key Files

**`database.py`**
- Reads `DATABASE_URL` env var; defaults to `sqlite:///dev.db` for local dev
- Exports: `engine`, `SessionLocal`, `Base`, `get_db`
- `get_db()` is a generator dependency — always use `yield` and close in `finally`
- `Base` is `DeclarativeBase` — all models must inherit from it

**`models.py`**
- `User` table (`__tablename__ = "users"`): `id` (PK), `email` (unique + indexed), `hashed_password`, `is_active` (default `True`)
- Uses SQLAlchemy 2.0 `Mapped[]` + `mapped_column()` style
- Extend here for new models; always import `Base` from `database`

**`schemas.py`**
- `LoginRequest` — accepts `email` or `username` alias (via `AliasChoices`); normalizes email to lowercase
- `LoginResponse` — returns `access_token`, `token_type`, `user: UserResponse`
- `UserResponse` — `id`, `email`, `is_active` (Pydantic v2 with `ConfigDict(from_attributes=True)`)

**`security.py`**
- `hash_password(password)` → bcrypt hash string
- `verify_password(plain, hashed)` → bool (guards against >72-byte passwords)
- `create_access_token(subject)` → signed JWT (HS256, 60 min expiry, `sub` = email)
- `decode_access_token(token)` → `str | None` (the `sub` claim); returns `None` on any `PyJWTError`
- `JWT_SECRET_KEY` read from env var — dev default is `"dev-secret-key-change-in-production"` (**always override in prod**)

**`main.py`**
- CORS origins read from `CORS_ORIGINS` env var (default: `http://localhost:5173,http://127.0.0.1:5173`)
- Calls `ensure_seeded()` on startup via `@asynccontextmanager lifespan`
- Mounts `auth_router` (prefix `/api`) from `routers/auth.py`
- `GET /health` returns `{"status": "ok"}`

**`routers/auth.py`**
- `POST /api/login` — verifies credentials via `verify_password`, returns `LoginResponse` with JWT + user info
- `GET /api/me` — requires `Authorization: Bearer <token>` header; returns `UserResponse` for the current user
- `get_current_user` dependency — parses Bearer token, calls `decode_access_token`, queries DB, raises HTTP 401 on any failure

**`seed.py`**
- Seeds `trainee@example.com` / `Secret123!` (bcrypt hashed) on startup in `development` / `test` envs
- Controlled by `ENV` env var and `SEED_DEMO_USER` override
- Safe to call repeatedly — checks for existing user before inserting
- Run manually: `uv run python seed.py`

### Running the API

```bash
cd apps/api

# Install dependencies (including dev)
uv sync --dev

# Run database migrations
uv run alembic upgrade head

# Seed the database (dev only)
uv run python seed.py

# Start the dev server with auto-reload
uv run fastapi dev main.py
# or
uv run uvicorn main:app --reload
```

API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Running Tests

```bash
cd apps/api
uv run alembic upgrade head   # ensure schema is up to date
uv run python seed.py         # seed test user
uv run pytest                 # runs all tests verbosely
```

> **Important:** Tests run against SQLite (`dev.db`) locally. CI uses the same path. Never hardcode credentials or connection strings in test files.

### Adding Migrations

```bash
cd apps/api
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

Always commit migration files in `alembic/versions/`. The `env.py` is already configured to use `Base.metadata` and `DATABASE_URL`. Never call `Base.metadata.create_all()` directly in production code.

---

## Frontend — `apps/web`

### Language & Runtime
- **TypeScript** (strict mode, `tsconfig.app.json`)
- **Node 22**, package manager: **npm**

### Dependencies (`package.json`)

| Package | Purpose |
|---|---|
| `react` + `react-dom` | UI framework (React 19) |
| `@tanstack/react-router` | Typed, file-system-free router with context-based auth guards |
| `vite` + `@vitejs/plugin-react` | Dev server and bundler |
| `typescript` | Static type checking |
| `vitest` | Unit/component test runner (Vite-native) |
| `@testing-library/react` | Component rendering + query utilities |
| `@testing-library/user-event` | Simulates realistic user interactions (typing, clicking) |
| `@testing-library/jest-dom` | Extended DOM matchers (`.toBeInTheDocument()`, etc.) |
| `jsdom` | DOM environment for Vitest (configured in `vite.config.ts`) |
| `@playwright/test` | E2E browser testing |
| `eslint` + `typescript-eslint` + plugins | Linting |

### Key Files

**`src/router.tsx`**
- Target routes (current auth MVP implements `/` and `/login`; full app routes per `specs/DEPENDENCY_MAP.md`):
  - `/login` (public — redirects authenticated users to `/`)
  - `/` (Dashboard — landing page after login, `spec 014`)
  - `/cases` (Main case table & inline Edytor wstępny, `spec 003`, `013`, `015`)
  - `/import` (Full Excel Copy Editor, `spec 004`, reached from `/cases`)
  - `/archive` (Case Archive, `spec 006`)
  - `/settings` (User Settings & Accessibility, `spec 008`; forced target when `must_change_password = true`)
  - `/admin` (Admin Panel — 4 tabs: Users, Settings, Audit Log, Backups; `admin` only, `spec 012`)
- `beforeLoad` guards redirect unauthenticated users to `/login`, force `must_change_password` users to `/settings`, and redirect non-admins away from `/admin`
- Router context carries `auth: AuthContextValue` — injected in `App.tsx`

**`src/context/AuthContext.tsx`**
- `AuthProvider` manages `token`, `user`, `isLoading`, `authError`
- Token persisted in `localStorage` under key `"access_token"`
- On mount: if token exists but no `user`, calls `GET /api/me` to restore session
- On 401 from `/api/me`: clears token and resets state (session expired)
- Exposes: `login()`, `logout()`, `authenticate()`, `commitLogin()`

**`src/context/useAuth.ts`**
- Exports `useAuth()` hook and `AuthContextValue` type
- Always use `useAuth()` in components — do not read `localStorage` directly

**`src/api/auth.ts`**
- `loginRequest(email, password)` → `POST /api/login` → returns `LoginResponse`
- `fetchMeRequest(token)` → `GET /api/me` → returns `User`
- Throws `ApiError` (with `.status` property) on non-2xx responses
- All backend fetches go here — do not `fetch()` directly in components

**`src/components/LoginPage.tsx`**
- Controlled form with `email` and `hasło` (password) inputs
- Client-side validation: required fields + valid email format — no `fetch` on invalid input
- Shows `"Niepoprawny login lub hasło"` on HTTP 401
- Submit button has states: default → `loading` → `success` → `error`

**`src/components/DashboardPage.tsx`**
- Shown only when authenticated (`/` route)
- Displays `"Witaj, <email>!"` and a logout button that calls `logout()` from `useAuth()`

### Running the Frontend

```bash
cd apps/web

# Install dependencies
npm ci

# Start dev server (http://localhost:5173)
npm run dev

# Run unit tests (Vitest, single run)
npm test

# Run tests in watch mode
npm run test:watch

# Lint
npm run lint

# Build for production
npm run build

# Run E2E tests (Playwright — requires backend running on :8000)
npm run test:e2e
```

---

## Docker / Database

### Local Development with PostgreSQL

```bash
# Start Postgres on port 5432
docker compose up -d

# Stop
docker compose down
```

Then set the connection string before running the API:
```bash
DATABASE_URL=postgresql+psycopg://malinois_user:malinois_password@localhost:5432/malinois_db uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://malinois_user:malinois_password@localhost:5432/malinois_db uv run fastapi dev main.py
```

The API defaults to **SQLite** (`dev.db`) when `DATABASE_URL` is not set — no Docker needed for basic local dev.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<api_dir>/dev.db` | SQLAlchemy connection string |
| `JWT_SECRET_KEY` | `"dev-secret-key-change-in-production"` | JWT signing secret — **must be changed in production** |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed origins |
| `ENV` | `development` | Controls seeding: `development`/`test`/`local` = seed on startup |
| `SEED_DEMO_USER` | *(unset)* | Force-enable (`true`/`1`/`yes`) or disable (`false`/`0`/`no`) seeding |

---

## CI / GitHub Actions

| Workflow | Trigger | Steps |
|---|---|---|
| `ci-api.yml` | Push/PR touching `apps/api/**` | `uv sync` → `alembic upgrade head` → `python seed.py` → `pytest` |
| `ci-web.yml` | Push/PR touching `apps/web/**` or `packages/**` | `npm ci` → `eslint` → `vitest run` → `vite build` |

---

## Coding Conventions

### Python (Backend)
- Use **SQLAlchemy 2.0 style**: `select()`, `session.scalar()`, `Mapped[]`, `mapped_column()`
- Use **Pydantic v2**: `model_validate()`, `ConfigDict`, `field_validator`, `AliasChoices`
- Never store plain-text passwords — always use `hash_password()` from `security.py`
- Always decode JWTs with `decode_access_token()` — never inspect token payloads manually
- Keep route handlers thin — put reusable logic in helper functions or service modules
- New routes go in `routers/` as separate files, included in `main.py` via `app.include_router()`
- Use `Depends(get_db)` for all DB access; never create sessions manually in route handlers

### TypeScript (Frontend)
- Strict TypeScript — no `any` without a comment explaining why
- Auth state lives exclusively in `AuthContext` — do not read/write `localStorage` outside of it
- Always use `useAuth()` to access token and user in components
- API calls go in `src/api/` — do not call `fetch()` directly in components or hooks
- Route guards belong in `router.tsx` via `beforeLoad` — not inside page components

### Tests
- Backend tests use `fastapi.testclient.TestClient` (synchronous, no async needed)
- Frontend unit tests use **Vitest** + **Testing Library** — mock `fetch` with `vi.spyOn(globalThis, 'fetch')`
- E2E tests use **Playwright** against the full running stack
- The seeded test credentials are always: `trainee@example.com` / `Secret123!`
- Run backend tests from `apps/api/` — pytest `pythonpath` is set to `.` in `pyproject.toml`

---

## Role System

Three roles control data visibility and edit permissions (see `specs/DEPENDENCY_MAP.md` for full matrix):

| Role | Polish | Sees (Active / Archive) | Can Edit |
|---|---|---|---|
| `user` | Podrzędny | Own cases / own + past-assignee (read-only) | Own non-date fields (no dates, no restore) |
| `supervisor` | Nadrzędny | Own + direct subordinates (1-level) | Own + subordinates' non-date fields, team reassign, restore (no dates) |
| `admin` | Administrator | All cases | All fields including dates (date edits require audit `reason`) |

**Critical rules for agents:**
- Date fields (`deadline`, `date_filed`) may only be written by `admin` (including on `POST /api/cases`) — always enforce this in the unified case service layer
- Role and `supervisor_id` can only be changed via `/api/admin/users/:id` — never via self-service endpoints; deactivation requires explicit `reassign_cases_to` / `reassign_subordinates_to` (`409` if omitted while blocking records exist)
- Always filter case queries by role; return `404 Not Found` for non-existent or out-of-scope cases, and reserve `403 Forbidden` for role-gated endpoints and unauthorized actions/fields on in-scope resources
- JWT carries `sub` (email) only; `get_current_user` loads `role`, `is_active`, and `must_change_password` from the DB on every request
- Implement role checks as a reusable `require_role(*roles)` dependency — do not duplicate inline
- Every case mutation (`PATCH`, `archive`, `restore`, `bulk`, `reassign`, `import commit`) must check and increment `cases.version` (`409 Conflict` on mismatch)
- `GET /api/cases` always returns `{ items, total, page, page_size }`

---

## Security Rules (enforced in all code)

- **Never** store or log plain-text passwords; enforce unified **12-character** strong password policy everywhere
- **Never** interpolate user input into raw SQL strings — use SQLAlchemy ORM only
- **Never** use `dangerouslySetInnerHTML` with user-supplied data in React
- **Never** write uploaded files to disk — parse in memory into `working_copies.rows_json` (24h TTL, max 5/user) and stream `.xlsx` downloads from memory
- **Never** use the client-supplied filename in any server-side path operation
- Uploaded files must be validated by MIME type **and** extension before processing
- Cap file upload size at 10 MB (`413` for oversized requests)
- Backup downloads require admin password re-verification and are logged in `admin_audit_log`
- All endpoints must set security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`
- `JWT_SECRET_KEY` must be an env var — reject the dev default if `ENV=production`
- Rate-limit `POST /api/login` to 10 requests/minute/IP (`429` on excess)
- Log all failed logins (timestamp, IP, email attempted — never the password)
- See [spec 007](specs/007-security/spec.md) for the full security specification

---

## Project Skills (`.agents/skills/`)

| Skill | Purpose |
|---|---|
| `spec-first` | Spec-first workflow (spec → review → plan → tasks → impl → gate) |
| `architect` | Single-DB architecture, unified case service layer, route & pagination contracts |
| `security-guard` | Auth, 12-char password policy, `sub`-only JWT, `404`/`403` anti-enumeration, in-memory uploads |
| `rbac-cases` | Role matrix, date immutability, `version` optimistic locking, `case_notes`, safe deactivation |
| `excel-pipeline` | Full Excel Copy Editor (`working_copies`), Polish + native dates, pre-import backup, streaming export |
| `migrations` | Alembic + SQLAlchemy 2.0 `Mapped[]` with SQLite + PostgreSQL parity |
| `styling-design-system` | Dark-blue glassmorphic palette (`#03071e`–`#48cae4`), `Plus Jakarta Sans`, urgency & a11y tokens |
| `accessibility` | WCAG 2.1 AA, keyboard navigation, ARIA dialogs/live regions, font-size/high-contrast/reduced-motion |
| `qa-testing` | `pytest` role-matrix & `409` tests, Vitest + Testing Library, Playwright E2E |
| `debugger` | Diagnosing 401/403/409/422 errors, Alembic heads, TanStack Router guards, Excel parsing |

---

## Spec-First Workflow

New features follow a spec-first process. **Write the spec before touching any
code.** The agent reviews the spec, generates a plan and tasks, then
implements and tests one task at a time.

See [specs/DEPENDENCY_MAP.md](specs/DEPENDENCY_MAP.md) for the master dependency
graph, route map, role matrix, and Indaba resolution audit trail.

```
specs/
├── DEPENDENCY_MAP.md ← master architecture, route map, role matrix, invariants
└── <NNN>-<slug>/
    ├── spec.md    ← human-written feature spec (required before coding)
    ├── plan.md    ← technical decisions (agent-generated, human-approved)
    └── tasks.md   ← ordered work units (agent-generated)
```

The step-by-step procedure is in the **`spec-first` skill**:
`.agents/skills/spec-first/SKILL.md`

The spec format reference (what every section means and common mistakes) is in:
`.agents/skills/spec-first/references/spec-format.md`

**Existing specs:**
| # | Slug | Feature | Status |
|---|---|---|---|
| [001](specs/001-auth/spec.md) | auth | User Authentication | ✅ Done |
| [002](specs/002-roles-and-permissions/spec.md) | roles-and-permissions | Role-Based Access Control | 📋 Spec (Resolved) |
| [003](specs/003-case-management/spec.md) | case-management | Case Management | 📋 Spec (Resolved) |
| [004](specs/004-excel-import/spec.md) | excel-import | Excel Import, Export & Full Copy Editor | 📋 Spec (Resolved) |
| [005](specs/005-notifications/spec.md) | notifications | Deadline Notifications | 📋 Spec (Resolved) |
| [006](specs/006-archive/spec.md) | archive | Case Archive | 📋 Spec (Resolved) |
| [007](specs/007-security/spec.md) | security | Security & Data Protection | 📋 Spec (Resolved) |
| [008](specs/008-user-settings/spec.md) | user-settings | User Settings & Accessibility | 📋 Spec (Resolved) |
| [009](specs/009-edit-history/spec.md) | edit-history | Edit History & Audit Log | 📋 Spec (Resolved) |
| [010](specs/010-case-notes/spec.md) | case-notes | Case & Person Notes | 📋 Spec (Resolved) |
| [011](specs/011-concurrent-editing/spec.md) | concurrent-editing | Concurrent Editing & Draft Protection | 📋 Spec (Resolved) |
| [012](specs/012-admin-panel/spec.md) | admin-panel | Admin Panel | 📋 Spec (Resolved) |
| [013](specs/013-search-and-filtering/spec.md) | search-and-filtering | Case Search & Filtering | 📋 Spec (Resolved) |
| [014](specs/014-dashboard/spec.md) | dashboard | Dashboard & Summary Stats | 📋 Spec (Resolved) |
| [015](specs/015-bulk-operations/spec.md) | bulk-operations | Bulk Case Actions | 📋 Spec (Resolved) |
| [016](specs/016-case-reassignment/spec.md) | case-reassignment | Case Reassignment & Substitutions | 📋 Spec (Resolved) |
| [017](specs/017-automated-backups/spec.md) | automated-backups | Automated Backups & Data Snapshots | 📋 Spec (Resolved) |

---

## .gitignore — Do Not Commit

- `apps/api/__pycache__/` and `*.pyc` files
- `apps/api/dev.db` — local SQLite database
- `apps/api/.venv/` — Python virtual environment
- `apps/web/node_modules/` — JS dependencies
- `apps/web/playwright-report/` and `apps/web/test-results/` — generated test output
- `apps/web/dist/` — production build output
