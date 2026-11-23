# Malinois — Master Architecture & Spec Dependency Map

> **Authoritative Spec Index** — All 24 specification inconsistencies (**N-01 – N-24**)
> from `malinois-niespojnosci-specyfikacji.pdf` were resolved by consensus in the
> Indaba council ([resolve_n01_n24.transcript.md](../.indaba/artifacts/resolve_n01_n24.transcript.md)).
> Current architecture source of truth: `appbuild.drawio.xml` (non-local server,
> single DB, full Excel copy editor, preliminary editor + person/case notes,
> deadline notifications, archive, user accessibility settings).

---

## 1. Tech Stack & Visual Identity (Preserved)

| Layer | Technology |
|---|---|
| **Backend** | Python 3.14+, FastAPI, SQLAlchemy 2.0 (`Mapped[]`), Alembic, PostgreSQL (`psycopg`) / SQLite (`dev.db`), PyJWT (HS256, `sub`-only), bcrypt (`>= 12`), `uv`, `pytest` |
| **Frontend** | React 19, TypeScript (strict), Vite, TanStack Router, pure CSS custom properties, Vitest + Testing Library, Playwright |
| **Visual Palette** | Deep-navy glassmorphism (`#03071e`, `#0a1128`, `#001f54`, `#034078`, `#0077b6`, `#023e8a`, `#1282a2`, cyan focus `#48cae4`, glass cards `rgba(10, 25, 47, 0.7)`), `Plus Jakarta Sans`, semantic urgency (`#ef4444` overdue, `#f59e0b` due soon, `#22c55e` safe) |

---

## 2. Spec Inventory & Dependency Graph

| # | Slug | Status | Depends On | Key Routes / Endpoints |
|---|---|---|---|---|
| [001](001-auth/spec.md) | `auth` | ✅ Done | — | `/login`, `POST /api/login`, `GET /api/me`, `GET /health` |
| [002](002-roles-and-permissions/spec.md) | `roles-and-permissions` | 📋 Spec (Resolved) | 001 | `GET/POST /api/admin/users`, `PATCH /api/admin/users/:id` |
| [003](003-case-management/spec.md) | `case-management` | 📋 Spec (Resolved) | 002 | `/cases`, `GET/POST /api/cases`, `GET/PATCH /api/cases/:id` |
| [004](004-excel-import/spec.md) | `excel-import` | 📋 Spec (Resolved — pending business Excel sample) | 003, 007, 009, 010, 011, 017 | `/import`, `/api/import/copies/*` |
| [005](005-notifications/spec.md) | `notifications` | 📋 Spec (Resolved) | 003, 012 | `GET /api/notifications`, `POST /api/notifications/:case_id/dismiss` |
| [006](006-archive/spec.md) | `archive` | 📋 Spec (Resolved) | 003, 005, 009, 011, 016 | `/archive`, `POST /api/cases/:id/archive`, `POST /api/cases/:id/restore` |
| [007](007-security/spec.md) | `security` | 📋 Spec (Resolved) | 001, 002 | Cross-cutting; `POST /api/admin/users/:id/reset-password` |
| [008](008-user-settings/spec.md) | `user-settings` | 📋 Spec (Resolved) | 001, 007 | `/settings`, `PATCH /api/me/password`, `PATCH /api/me/settings` |
| [009](009-edit-history/spec.md) | `edit-history` | 📋 Spec (Resolved) | 002, 003 | `GET /api/cases/:id/history`, `GET /api/admin/audit-log` |
| [010](010-case-notes/spec.md) | `case-notes` | 📋 Spec (Resolved) | 002, 003 | `GET/POST /api/cases/:id/notes`, `GET/POST /api/users/:id/notes`, `DELETE /api/notes/:id` |
| [011](011-concurrent-editing/spec.md) | `concurrent-editing` | 📋 Spec (Resolved) | 003 | Cross-cutting (`version` on all case mutations + 401 draft recovery) |
| [012](012-admin-panel/spec.md) | `admin-panel` | 📋 Spec (Resolved) | 002, 007, 009, 017 | `/admin` (4 tabs: Users, Settings, Audit Log, Backups), `/api/admin/settings` |
| [013](013-search-and-filtering/spec.md) | `search-and-filtering` | 📋 Spec (Resolved) | 003, 006 | `GET /api/cases?q=&status=&assigned_to=&overdue=&due_soon=&page=&page_size=` |
| [014](014-dashboard/spec.md) | `dashboard` | 📋 Spec (Resolved) | 003, 012, 013 | `/`, `GET /api/dashboard/summary` |
| [015](015-bulk-operations/spec.md) | `bulk-operations` | 📋 Spec (Resolved) | 003, 006, 009, 011 | `POST /api/cases/bulk` |
| [016](016-case-reassignment/spec.md) | `case-reassignment` | 📋 Spec (Resolved) | 002, 003, 009, 010, 011 | `POST /api/cases/reassign` |
| [017](017-automated-backups/spec.md) | `automated-backups` | 📋 Spec (Resolved) | 007, 009, 012 | `GET/POST /api/admin/backups`, `POST /api/admin/backups/:filename/download` |

---

## 3. Frontend Route Map

| Path | Screen | Guard / Access |
|---|---|---|
| `/login` | Login | Public (redirects authenticated users to `/`) |
| `/` | **Dashboard** (`spec 014`) | Authenticated (landing page after login) |
| `/cases` | **Main Case Table & Edytor wstępny** (`spec 003`, `013`, `015`) | Authenticated (includes `"Import / Edytor pliku"` button → `/import`) |
| `/import` | **Full Excel Copy Editor** (`spec 004`) | Authenticated (upload is `admin`-only; live snapshot & `.xlsx` download for all roles) |
| `/archive` | **Case Archive** (`spec 006`) | Authenticated (`Przywróć` restricted to `supervisor` & `admin`) |
| `/settings` | **User Settings & Accessibility** (`spec 008`) | Authenticated (forced redirect target when `must_change_password = true`) |
| `/admin` | **Admin Panel** (`spec 012`) — 4 tabs: Users, Settings, Audit Log, Backups | `admin` only (non-admins redirected to `/`) |

---

## 4. Unified Role & Permission Matrix

| Capability | `user` (Podrzędny) | `supervisor` (Nadrzędny) | `admin` (Administrator) |
|---|---|---|---|
| **Active Case Visibility** | Own cases only | Own + direct subordinates' cases (no transitive nesting) | All cases |
| **Archive Visibility** | Own + past-assignee cases (read-only for past) | Own + direct subordinates' (current or past) | All archived cases |
| **Create Case (`POST /api/cases`)** | ❌ `403` | ✅ Own/subordinates, **dates must be `null`** | ✅ Any user, any dates (past allowed with UI warning) |
| **Edit Non-Date Fields** (`title`, `client_name`, `status`) | ✅ Own cases | ✅ Own + direct subordinates | ✅ All cases |
| **Edit Dates** (`deadline`, `date_filed`) | ❌ `403` | ❌ `403` | ✅ All cases (**requires non-empty `reason`**) |
| **Archive Case** (single & bulk) | ✅ Own cases | ✅ Own + direct subordinates | ✅ All cases |
| **Restore Case** (single & bulk) | ❌ `403` | ✅ Own + direct subordinates | ✅ All cases |
| **Reassign Case** (`POST /api/cases/reassign`) | ❌ `403` | ✅ Within own + direct subordinates | ✅ Any active user |
| **Excel Copy Editor (`/import`)** | Live snapshot copy + non-date edits + `.xlsx` download | Live snapshot copy + non-date edits + `.xlsx` download | Upload `.xlsx`/`.xls` + full edit + commit (with auto pre-import backup) |
| **Admin Panel (`/admin`)** | ❌ Redirect / `403` | ❌ Redirect / `403` | ✅ Full access (4 tabs) |

---

## 5. Cross-Cutting Invariants

1. **Error Codes (N-05):** Non-existent or out-of-scope resources ALWAYS return `404 Not Found`. `403 Forbidden` is reserved for role-gated endpoints and unauthorized actions/fields on an in-scope resource (plus `must_change_password` returning `403` with `code: "password_change_required"`).
2. **Optimistic Locking (N-06):** Single unified case service layer; every mutation (`PATCH`, `archive`, `restore`, `bulk`, `reassign`, `import commit`) checks and increments `cases.version`, returning `409 Conflict` on mismatch with zero silent overwrites.
3. **Pagination Contract (N-14):** `GET /api/cases` ALWAYS returns `{ items, total, page, page_size }`.
4. **Timezone & Deadlines (N-15, N-16):** `Europe/Warsaw` timezone; `overdue` is strictly `deadline < today`; `due_soon` uses admin-configured `notification_threshold_days` (default `7`).
5. **Single Database (N-23):** One PostgreSQL/SQLite DB holds all 11 tables: `users`, `cases`, `case_notes`, `case_edit_log`, `case_assignment_history`, `notification_dismissals`, `working_copies`, `system_settings`, `login_audit_log`, `admin_audit_log`, `backup_logs`.
6. **Zero Disk Uploads (N-01):** Uploaded Excel files are parsed in memory into `working_copies.rows_json` (24h TTL, max 5/user) and downloaded `.xlsx` files are streamed from memory.
