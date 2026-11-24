# Self-review: Malinois Specification Harmonization (N-01..N-24) & Agent Skills Architecture

See [`AGENTS.md`](../../AGENTS.md) and [`.indaba/artifacts/resolve_n01_n24.transcript.md`](../../.indaba/artifacts/resolve_n01_n24.transcript.md).

---

## 1. Boundary and layering

- **Single-DB & Unified Case Service Layer:**
  - All case mutations (`PATCH`, archive, restore, bulk operations, reassignments, and Excel working copy commits) are routed through a single service layer (`apps/api/services/cases.py`). No business logic or database queries leak into FastAPI route handlers or React view components.
  - The service layer strictly enforces optimistic locking (`version`), rejecting stale concurrent modifications with `409 Conflict`.
- **Anti-Enumeration Boundary (N-05):**
  - Any request attempting to fetch, modify, or archive a case that either does not exist or lies outside the caller's authorized visibility scope returns `404 Not Found`. `403 Forbidden` is reserved exclusively for role-gated administrative endpoints or unauthorized field modifications (e.g. non-admin attempting to set `deadline`). Resource existence is never leaked.
- **Supervisor Hierarchy Boundary (N-03):**
  - Supervisor scoping is non-transitive: supervisors can view and edit their own cases and direct subordinates' cases only (`assigned_to IN (self, direct_subordinates)`). No multi-level hierarchy or transitive team inheritance exists.
- **In-Memory Excel Processing Seam (spec 004):**
  - The Excel import and export pipelines operate strictly in memory. Uploaded data workbooks are parsed in memory and never stored; admin-managed empty `.xlsx`/`.xlsm` templates live in `excel_templates` (schema-checked, zero PII) and are filled from PostgreSQL and streamed via memory buffers on export. The server filesystem is completely bypassed.
- **Skill Encapsulation:**
  - 9 domain-specific skills in `.agents/skills/` (`architect`, `security-guard`, `rbac-cases`, `excel-pipeline`, `migrations`, `styling-design-system`, `accessibility`, `qa-testing`, `debugger`) cleanly isolate system invariants, rules, and verification checklists.

---

## 2. The local/remote seam

- **Dual-Database Engine Parity:**
  - The application maintains 100% parity between local development (`sqlite:///dev.db`) and production container environments (`postgresql+psycopg`).
  - SQLAlchemy 2.0 `Mapped[]` declarative models and Alembic migrations avoid SQLite-incompatible features (e.g., enum types, JSON operators, or non-standard constraints), ensuring migrations execute identically across both targets.
- **Stateless Storage vs. Ephemeral Containers:**
  - By persisting Excel working copies in the database rather than on local disk (N-01), multi-instance deployments behind load balancers can preview, edit, and commit Excel uploads without shared NFS volumes or sticky sessions.
- **Client/Server Auth Boundary (N-17):**
  - While JWT tokens expire deterministically after 60 minutes with no refresh token, form drafts are safeguarded on the client via `sessionStorage` (keyed by email). When a `401 Unauthorized` occurs mid-edit, the user re-authenticates in place without losing their work.

---

## 3. Public surface and semver

**major** — Full harmonization of the Malinois platform contract across all 17 feature specifications, resolving 24 legacy inconsistencies and establishing the authoritative API surface:

- **Standardized Collection Shape (N-14):**
  - `GET /api/cases` and all filtered views across specs 002, 003, 006, 013, and 015 consistently return `{ items, total, page, page_size }`.
- **Route Topology (N-15, N-21):**
  - `/` is the primary authenticated Dashboard; `/cases` hosts the main case management table.
  - The Admin Panel (`/admin`) is standardized to 4 dedicated tabs: Users, Settings, Audit Log, and Backups. Excel Import is accessed from the `/cases` toolbar.
- **Schema Modifications & Removals:**
  - Added `version: int` (default `1`) to `cases` table for optimistic locking.
  - Removed `cases.note` column (N-10); notes are now managed exclusively via the immutable `case_notes` table (spec 010).
  - Removed `notifications_sound` from user settings and specifications (N-19).
  - Added `excel_templates` table (spec 004) and `automated_backups` table (spec 017).
- **JWT Surface Minimization (N-20):**
  - The JWT payload is restricted to `sub` (email) and standard expiration claims (`exp`). Role, active status, and password change flags are queried on every request.

---

## 4. Accessibility and i18n

- **WCAG 2.1 AA Compliance (Spec 008, `accessibility` skill):**
  - Every interactive element supports full keyboard navigation (`Tab` / `Shift+Tab`) with visible focus outlines (`2px solid #48cae4`, `outline-offset: 2px`).
  - Native HTML dialogs and accessible alert dialogs (`role="alertdialog"`) trap focus and handle `Escape` dismissal for overdue alerts and conflict modals.
  - Live regions (`aria-live="polite"` / `assertive`) announce toast updates and critical validation errors.
- **User Accessibility Settings:**
  - Persisted user preferences: `theme` (including high-contrast mode with pure `#000000` canvas and `>= 7:1` contrast ratio), `font_scale` (`normal`, `large`, `xlarge` mapped to document root `rem` scaling), and `reduced_motion`.
- **Semantic Urgency Indicators (N-16):**
  - Urgency is never communicated by color alone: overdue items are flagged with explicit text badges (`ZALEGŁE`, `Za X dni`, `W terminie`) alongside semantic color tokens (`#ef4444`, `#f59e0b`, `#22c55e`).
- **Localization & Polish Date Support (N-08):**
  - All UI copy, case statuses, and audit messages are authored in Polish.
  - Date parsing in the Excel pipeline natively supports Polish date patterns (`DD.MM.YYYY`, `DD-MM-YYYY`) as well as ISO dates (`YYYY-MM-DD`).

---

## 5. Supply chain and packaging

- **Runtime Dependencies:**
  - Python: `fastapi[standard]`, `sqlalchemy`, `alembic`, `psycopg[binary]`, `pyjwt`, `bcrypt`. Package management enforced via `uv`.
  - Frontend: `react` (v19), `typescript`, `vite`, `@tanstack/react-router`.
- **Zero Disk Exposure:**
  - No temporary file directories or staging folders required. Memory-only parsing and streaming ensure no sensitive case data or PII remains on physical disk after request termination.
- **Security Hardening:**
  - Bcrypt password hashing configured with cost factor `>= 12`.
  - Rate limiting enforced on `POST /api/login` (10 requests/minute/IP).
  - Mandatory HTTP security headers: `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.

---

## 6. Honest output

- **Accurate Aggregations & Counts:**
  - Dashboard metrics (`GET /api/dashboard/summary`) and case lists compute real SQL aggregate counts from database records; no synthetic or estimated counters.
- **Transparent Conflict Resolution (N-06):**
  - On version collisions (`409 Conflict`), the server returns the complete `current` case state. The client presents an honest, transparent side-by-side comparison ("Twoja wersja" vs. "Zapisana wersja") so users can make informed overwrite or discard decisions without silent data loss.
- **Timezone Precision (N-16):**
  - Overdue calculations strictly evaluate `deadline < today` in the `Europe/Warsaw` timezone; cases with a deadline matching today's calendar date are treated accurately as due today ("W terminie"), never prematurely marked overdue.

---

## 7. Verification

Verification performed via tracked Indaba council sessions and cross-spec contract audits:

```text
======================================================================
INDABA COUNCIL VERIFICATION AUDIT — ZERO CONTRADICTIONS CONFIRMED
======================================================================
Artifact: .indaba/artifacts/verify_updated_specs.transcript.md
Debate: verify_updated_specs (Claude & AGY Consensus)

- N-14 GET /api/cases shape:
  { items, total, page, page_size } verified across 002, 003, 006, 013, DEPENDENCY_MAP, AGENTS.md.
- N-05 404 vs 403 anti-enumeration:
  Verified across 002, 003, 005, 006, 007, 009, 010, 015, 016.
- N-06 Optimistic locking (version):
  Unified service layer enforcement verified across 002, 003, 004, 006, 011, 015, 016.
- N-15, N-21 Routes and Admin tabs:
  Mounted at /, /cases, /import, /archive, /settings, /admin (4 tabs: Users, Settings, Audit Log, Backups).
- N-18, N-20 Passwords and JWT:
  12-character minimum and sub-only claim verified across 002, 007, 008, 011, 012.
- N-10, N-19 Removed fields:
  cases.note eliminated in favor of case_notes; notifications_sound removed.
- N-22, N-23 Internal links and Single-DB architecture:
  All cross-spec references verified; DB2 confirmed rejected.

OUTCOME: AGREEMENT REACHED (0 contradictions found across all 17 specs).
======================================================================
```

---

## Known gaps

- **Production Excel Sample Needed (Spec 004):**
  - The business Excel template columns and sample spreadsheets from the client/trainee stakeholders are still pending. Column mappings in `specs/004-excel-import/spec.md` remain marked as draft until the physical file is reviewed.
- **Backend / Frontend Implementation:**
  - PR #5 delivers the complete specification resolution, architectural contracts, transcripts, and agent skill guides. Actual application code implementation of specs 002–017 will be rolled out across subsequent feature branches following the milestone schedule in `plan.md`.
- **Seed User Password Alignment:**
  - Existing dev seed script (`apps/api/seed.py`) uses `Secret123!` (10 characters), which must be updated in Milestone 2 to conform to the newly harmonized 12-character password minimum (e.g. `Secret123456!`).
