# Malinois

A full-stack web application for managing ZUS (Social Insurance) case deadlines.
Cases are imported from Excel, deadline alerts are shown to the right people at
the right time, and a strict role system ensures users only see and edit what
they are permitted to.

---

## Purpose

The system monitors deadlines for ZUS cases handled on behalf of clients.
It replaces manual Excel tracking with a centralised, multi-user web app that:

- Imports case data (dates, clients, assignments) from Excel files
- Compares deadlines against the current date and fires popup notifications
- Enforces three access tiers: regular users, supervisors, and administrators
- Archives closed cases without losing historical records

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.14+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| **Auth** | JWT (PyJWT, HS256, 60 min expiry), bcrypt password hashing |
| **Database** | PostgreSQL (production) · SQLite (local dev) |
| **Frontend** | React 19, TypeScript, Vite, TanStack Router |
| **Testing** | pytest, Vitest, Playwright (E2E) |
| **CI** | GitHub Actions |
| **Container** | Docker Compose (Postgres) |

---

## Role System

| Role | Polish | Sees | Can Edit |
|---|---|---|---|
| `user` | Podrzędny | Own cases only | Own cases (no dates) |
| `supervisor` | Nadrzędny | Own + direct subordinates' cases | Subordinates' cases (no dates) |
| `admin` | Administrator | All cases | All fields including dates |

> Only admins can change a case's `deadline` or `date_filed`. Only admins
> can create users, assign roles, and reset passwords.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                           Browser                              │
│                                                                │
│  React 19 + TanStack Router  (http://localhost:5173)           │
│                                                                │
│  /login  →  Main (case list)  →  Editor  →  Archive           │
│                        ↓                                       │
│          Notifications popup  │  User Settings                 │
│                        ↓                                       │
│          Admin Editor (Excel import/export, user mgmt)         │
│                                                                │
│          AuthContext  (token, user, role)                      │
│          src/api/  (all fetch calls centralised here)          │
└──────────────────────────┬─────────────────────────────────────┘
                           │  HTTPS · JSON · JWT Bearer
┌──────────────────────────┼─────────────────────────────────────┐
│  FastAPI  (http://localhost:8000)                               │
│                                                                │
│  routers/auth.py      POST /api/login   GET /api/me            │
│  routers/cases.py     GET/POST/PATCH /api/cases                │
│  routers/admin.py     /api/admin/*  (admin only)               │
│  routers/notify.py    GET /api/notifications                   │
│                                                                │
│  security.py  (JWT, bcrypt)   schemas.py  (Pydantic)           │
│  models.py    (SQLAlchemy ORM)                                 │
│  Alembic migrations                                            │
└──────────────────────────┬─────────────────────────────────────┘
                           │
             ┌─────────────▼────────────┐
             │  SQLite  dev.db          │  ← local dev (no Docker)
             │  PostgreSQL  :5432       │  ← Docker / production
             └──────────────────────────┘
```

---

## Getting Started

### Prerequisites

- Python 3.14+ with [uv](https://docs.astral.sh/uv/)
- Node 22+ with npm
- Docker (optional — only needed for PostgreSQL)

---

### Backend

```bash
cd apps/api

# Install dependencies
uv sync --dev

# Apply migrations
uv run alembic upgrade head

# Seed the dev user (trainee@example.com / Secret123!)
uv run python seed.py

# Start the API server
uv run fastapi dev main.py
```

API available at **http://localhost:8000**  
Swagger docs at **http://localhost:8000/docs**

---

### Frontend

```bash
cd apps/web

# Install dependencies
npm ci

# Start the dev server
npm run dev
```

App available at **http://localhost:5173**

> The frontend expects the backend running on `:8000`.

---

### PostgreSQL (optional)

```bash
# Start Postgres via Docker
docker compose up -d
```

Then prefix API commands with:
```bash
DATABASE_URL=postgresql+psycopg://malinois_user:malinois_password@localhost:5432/malinois_db
```

---

## API Endpoints

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/health` | — | Health check |
| `POST` | `/api/login` | — | Login, returns JWT + user |
| `GET` | `/api/me` | any | Current user info |
| `PATCH` | `/api/me/password` | any | Change own password |
| `GET` | `/api/cases` | any | Cases (filtered by role) |
| `POST` | `/api/cases` | admin/supervisor | Create a case |
| `PATCH` | `/api/cases/:id` | any* | Update case fields (*dates: admin only) |
| `POST` | `/api/cases/:id/archive` | any* | Archive a case |
| `POST` | `/api/cases/:id/restore` | supervisor/admin | Restore archived case |
| `GET` | `/api/notifications` | any | Active deadline notifications |
| `POST` | `/api/notifications/:id/dismiss` | any | Dismiss a notification |
| `POST` | `/api/admin/import` | admin | Import cases from Excel |
| `GET` | `/api/admin/export` | admin | Export all cases as Excel |
| `GET` | `/api/admin/users` | admin | List all users |
| `POST` | `/api/admin/users` | admin | Create a user |
| `PATCH` | `/api/admin/users/:id` | admin | Update role / supervisor |
| `POST` | `/api/admin/users/:id/reset-password` | admin | Reset user password |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///dev.db` | SQLAlchemy connection string |
| `JWT_SECRET_KEY` | `dev-secret-key-…` | JWT signing secret — **must change in production** |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `ENV` | `development` | `development`/`test` enables auto-seeding |
| `SEED_DEMO_USER` | _(unset)_ | Force `true` / `false` to override seeding |

> ⚠️ `JWT_SECRET_KEY` with the default value is **rejected** when `ENV=production`.

---

## Running Tests

### Backend (pytest)

```bash
cd apps/api
uv run alembic upgrade head
uv run python seed.py
uv run pytest
```

### Frontend (Vitest)

```bash
cd apps/web
npm test
```

### E2E (Playwright)

```bash
# Backend must be running on :8000
cd apps/web
npm run test:e2e
```

---

## CI

| Workflow | Triggers on | Steps |
|---|---|---|
| `ci-api.yml` | `apps/api/**` | install → migrate → seed → pytest |
| `ci-web.yml` | `apps/web/**`, `packages/**` | install → lint → vitest → build |
| `e2e.yml` | all branches | install → migrate → seed → playwright |

---

## Feature Specs

| # | Feature | Status |
|---|---|---|
| [001](specs/001-auth/spec.md) | User Authentication | ✅ Done |
| [002](specs/002-roles-and-permissions/spec.md) | Role-Based Access Control | 📋 Spec ready |
| [003](specs/003-case-management/spec.md) | Case Management | 📋 Spec ready |
| [004](specs/004-excel-import/spec.md) | Excel Import & Export | 📋 Spec ready |
| [005](specs/005-notifications/spec.md) | Deadline Notifications | 📋 Spec ready |
| [006](specs/006-archive/spec.md) | Case Archive | 📋 Spec ready |
| [007](specs/007-security/spec.md) | Security & Data Protection | 📋 Spec ready |
| [008](specs/008-user-settings/spec.md) | User Settings | 📋 Spec ready |

---

## Demo Credentials

| Field | Value |
|---|---|
| Email | `trainee@example.com` |
| Password | `Secret123!` |

> Seeded automatically in `development` and `test` environments.
