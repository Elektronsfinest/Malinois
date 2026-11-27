---
name: architect
description: >-
  Use when designing new endpoints, deciding module/service boundaries, adding
  routes, or checking how features interact across apps/api and apps/web in
  Malinois. Enforces single-DB, unified case service layer, and route contracts.
---

# Full-Stack Architect — Malinois

Malinois is a **single-database**, non-local web application (FastAPI + React 19)
for client case & deadline management. Every architectural decision must keep the
backend thin at the router layer and enforce invariants in one place.

---

## Backend Boundaries (`apps/api`)

1. **Thin Routers → Service Layer → ORM Models:**
   - Routers (`routers/*.py`) handle HTTP parsing, auth dependencies
     (`get_current_user`, `require_role`), and status codes only.
   - **All case mutations** (`PATCH`, `archive`, `restore`, `bulk`, `reassign`,
     `import commit`) MUST pass through a **single unified case service layer**
     (`services/cases.py`) that enforces:
     1. Role-based visibility scoping (returns `404` on out-of-scope)
     2. Date-field immutability (`admin` only, including on creation; `reason`
        required on date edits)
     3. Optimistic locking (`cases.version` check + atomic increment; `409` on
        mismatch)
     4. Field-level audit logging (`case_edit_log`)
     5. Notification dismissal cleanup on `restore`
2. **Single Database (`DB2? = No`):**
   - One PostgreSQL (production) / SQLite (`dev.db`) database holds all 11
     tables: `users`, `cases`, `case_notes`, `case_edit_log`,
     `case_assignment_history`, `notification_dismissals`, `excel_templates`,
     `system_settings`, `login_audit_log`, `admin_audit_log`, `backup_logs`.
3. **Pagination & Summary Contracts:**
   - `GET /api/cases` ALWAYS returns `{ items, total, page, page_size }`
     (never a bare array).
   - Supervisor & admin per-member totals come exclusively from
     `GET /api/dashboard/summary` (never add a duplicate summary endpoint).
4. **Timezone Invariant:**
   - Store and return timestamps in ISO 8601 UTC.
   - Compute "today", `overdue` (`deadline < today`), and `due_soon`
     (`today <= deadline <= today + notification_threshold_days`) in
     `Europe/Warsaw`.

---

## Frontend Boundaries (`apps/web`)

1. **Canonical Route Map (`src/router.tsx`):**
   - `/login` — public (redirects authenticated users to `/`)
   - `/` — **Dashboard** (`spec 014`)
   - `/cases` — **Main Case Table & Edytor wstępny** (`spec 003`, `013`, `015`)
   - `/import` — **Excel Data Import** (`spec 004`, `admin` only, reached from `/cases`)
   - `/archive` — **Case Archive** (`spec 006`)
   - `/settings` — **User Settings & Accessibility** (`spec 008`)
   - `/admin` — **Admin Panel** (`spec 012`, 4 tabs: Users, Settings, Audit Log,
     Backups; `admin` only)
2. **Auth & API Seams:**
   - Auth state lives exclusively in `AuthContext` (`useAuth()`). Never read or
     write `localStorage` directly in components.
   - All HTTP requests go through `src/api/*.ts`. Never call `fetch()` directly
     in components or hooks.
   - Route guards (`beforeLoad`) enforce authentication, `must_change_password`
     redirect to `/settings`, and `admin` role for `/admin`.
   - On `401` mid-edit, save unsaved drafts to `sessionStorage` keyed by user
     email and open the inline re-login modal (spec 011).

---

## Reference

- Master spec index: `specs/DEPENDENCY_MAP.md`
- Indaba council decisions: `.indaba/artifacts/resolve_n01_n24.transcript.md`
