# Plan: Malinois Specification Harmonization (N-01..N-24) & Agent Skills Architecture

Implementation plan derived from [Elektronsfinest/Malinois#5](https://github.com/Elektronsfinest/Malinois/pull/5), establishing a unified single-DB case management platform, 24 reconciled core specification rules (**N-01 – N-24**), and a 9-specialist agent skill matrix.

---

## 1. Modules touched

| File / Module | Change |
| :--- | :--- |
| `specs/DEPENDENCY_MAP.md` | Master architecture map, route topology, 3-tier role permissions matrix, spec dependency DAG, and N-01..N-24 audit log |
| `AGENTS.md` | Updated system instructions: route hierarchy (`/` Dashboard, `/cases` Main), single-DB guarantee, unified case service layer, 12-char password policy, `version` locking |
| `.agents/skills/*` | 9 new project agent skills: `architect`, `security-guard`, `rbac-cases`, `excel-pipeline`, `migrations`, `styling-design-system`, `accessibility`, `qa-testing`, `debugger` |
| `.indaba/artifacts/*` | Council transcripts: `resolve_n01_n24.transcript.md`, `spec_debate.transcript.md`, `verify_updated_specs.transcript.md` (0 contradictions verified) |
| `.indaba/workflows/*` | Automated debate workflows: `resolve-inconsistencies.workflow.ai.yml` and `verify-specs.workflow.ai.yml` |
| `specs/002-roles-and-permissions/spec.md` | Non-transitive supervisor scope (own + direct subordinates); `404` for out-of-scope; `sub`-only JWT; admin-only dates |
| `specs/003-case-management/spec.md` | Removed legacy `cases.note`; added `version` integer locking; standardized `GET /api/cases` response `{items, total, page, page_size}` |
| `specs/004-excel-import/spec.md` | Server-side `working_copies` DB table (no disk storage); Polish date formats (`DD.MM.YYYY`); mandatory pre-import snapshot; streaming export |
| `specs/005-notifications/spec.md` | Notification dismissal lifecycle keyed on `(user_id, case_id, deadline_snapshot, state)`; removed `notifications_sound`; multi-user supervisor alerts |
| `specs/006-archive/spec.md` | Restore restricted to supervisor/admin; archive visibility includes historical assignees (`case_assignment_history`); `404` for out-of-scope |
| `specs/007-security/spec.md` | Unified 12-char password policy; bcrypt cost `>= 12`; `sub`-only 60-min JWT; strict `404` vs `403` anti-enumeration; zero temporary files on disk |
| `specs/008-user-settings/spec.md` | User accessibility controls (`theme`, `font_scale`, `reduced_motion`); self-service password change; removed `notifications_sound` |
| `specs/009-edit-history/spec.md` | Mandatory audit logging for admin date modifications (with required `reason`), password resets, and deactivation reassignments |
| `specs/010-case-notes/spec.md` | Dedicated immutable `case_notes` table; added nullable `subject_user_id` for person-specific notes; replaced inline case notes |
| `specs/011-concurrent-editing/spec.md` | Optimistic locking via `version`; `409 Conflict` schema returning `current` object; `401` session-expiry draft preservation in `sessionStorage` |
| `specs/012-admin-panel/spec.md` | 4-tab panel structure (Users, Settings, Audit Log, Backups); import moved to `/cases`; user deactivation case reassignment guard (`409`) |
| `specs/013-search-and-filtering/spec.md` | Case query standardization; unified search parameters matching `GET /api/cases` pagination; `Europe/Warsaw` date boundaries |
| `specs/014-dashboard/spec.md` | Mounted at `/`; login landing page; single `GET /api/dashboard/summary` endpoint; strict overdue definition (`deadline < today`) |
| `specs/015-bulk-operations/spec.md` | Moved into scope; per-row `version` verification and reporting; bulk restore restricted to supervisor and admin |
| `specs/016-case-reassignment/spec.md` | Moved into scope; supervisor reassignment limited to subordinates; mandatory reassignment on user/supervisor deactivation |
| `specs/017-automated-backups/spec.md` | Single-DB backup orchestrator; pre-import snapshots; password-reverified, audit-logged download endpoints |

---

## 2. Architecture & Data Flow

```mermaid
flowchart TD
    Client["React 19 Frontend (TanStack Router)"] -->|HTTPS + JWT (sub-only)| APIGateway["FastAPI Gateway (/api)"]
    
    subgraph AuthSecurity ["Authentication & Guardrails"]
        APIGateway --> CurrentUser["get_current_user Dependency"]
        CurrentUser --> DBUser["Load Role & is_active from DB"]
        DBUser -->|is_active=False| Auth401["401 Unauthorized / Re-login Modal"]
        DBUser -->|must_change_password=True| PwdGate["403 password_change_required"]
    end

    subgraph ServiceLayer ["Unified Case Service Layer"]
        DBUser --> CaseService["Case Service Layer"]
        CaseService --> Scoping["RBAC Scoping Filter<br/>User: Own | Supervisor: Own+Direct | Admin: All"]
        Scoping -->|Out of Scope / Missing| Res404["404 Not Found (Anti-enumeration)"]
        Scoping -->|Role Violation| Res403["403 Forbidden"]
        
        CaseService --> Concurrency["Version Validator (Optimistic Locking)"]
        Concurrency -->|version != current.version| Res409["409 Conflict (Returns current)"]
        Concurrency -->|version == current.version| Mutation["Execute Mutation & Increment version"]
    end

    subgraph Storage ["Single-DB Persistence (PostgreSQL / SQLite)"]
        Mutation --> CasesTable[("cases")]
        Mutation --> NotesTable[("case_notes (Immutable)")]
        Mutation --> HistoryTable[("case_assignment_history & edit_log")]
        Mutation --> CopiesTable[("working_copies (Excel JSON, 24h TTL)")]
        Mutation --> BackupsTable[("automated_backups & snapshots")]
    end

    subgraph ExcelFlow ["Excel Pipeline (Zero Disk I/O)"]
        Client -->|Upload .xlsx in-memory| ParseStream["In-Memory Parser (Polish + ISO dates)"]
        ParseStream --> CopiesTable
        CopiesTable -->|Explicit Commit| CaseService
        CaseService -->|Pre-import Snapshot| BackupsTable
        CaseService -->|Export Request| MemoryStream["In-Memory Streaming XLSX"]
        MemoryStream --> Client
    end
```

---

## 3. Where the behaviour lives

- **Authentication & Claims Seam (`apps/api/security.py`, `routers/auth.py`):**
  - JWT carries **only `sub`** (user email).
  - Role (`admin`, `supervisor`, `user`), `is_active`, and `must_change_password` are loaded dynamically from the database on every authenticated request via `get_current_user`.
  - Passwords enforce a 12-character minimum, hashed with bcrypt (cost `>= 12`).

- **Unified Case Service Layer (`apps/api/services/cases.py`):**
  - All single-case mutations (`PATCH`, archive, restore), bulk operations, reassignments, and Excel working copy commits go through a single service layer.
  - Enforces atomic `version` increments; rejects stale versions with `409 Conflict`.
  - Enforces date immutability: non-admins attempting to modify `deadline` or `date_filed` receive `403 Forbidden`; admin date changes require a non-empty `reason` logged to `case_edit_log`.

- **Access Control & Anti-Enumeration (`apps/api/dependencies.py`):**
  - Any request targeting an existing case outside the caller's authorized visibility scope returns `404 Not Found`, identical to a non-existent ID, preventing resource enumeration.
  - Supervisors see their own cases and direct subordinates' cases (`assigned_to IN (self, subordinates)`) with zero transitive inheritance.

- **Excel In-Memory Pipeline (`apps/api/services/excel.py`):**
  - Uploaded workbooks are parsed entirely in memory and persisted as structured JSON rows in the `working_copies` table (max 5 copies per user, 24h TTL). No temporary or permanent files touch the server disk.
  - Handles Polish date formats (`DD.MM.YYYY`, `DD-MM-YYYY`) and ISO dates.
  - Commits trigger an automatic `pre_import` snapshot in `automated_backups`.

- **Frontend Resilience & Accessibility (`apps/web/src/*`):**
  - Draft recovery: Any `401 Unauthorized` encountered during active form editing captures form state into `sessionStorage` (keyed by user email) and displays an inline re-login dialog.
  - WCAG 2.1 AA compliant design system: High-contrast theme (`#000000` canvas, `>= 7:1` contrast), font scaling (`100%`, `112.5%`, `125%`), and reduced-motion toggle.
  - Semantic urgency: Overdue status (`deadline < today` in `Europe/Warsaw`) paired with text badges (`ZALEGŁE`, `Za X dni`), never color alone.

---

## 4. Trade-offs taken

- **Server-side `working_copies` in DB vs. Filesystem Storage (N-01):**
  - Storing parsed Excel data as JSON in `working_copies` keeps the server stateless, eliminates disk file lifecycle/permissions bugs, and honors the strict zero-disk security mandate. Cost: Slightly higher database storage during active preview sessions (mitigated by 24h TTL and 5-copy limit).
- **Optimistic Locking via `version` vs. Pessimistic / WebSocket Locks (N-06, N-11):**
  - Optimistic locking avoids lock-abandonment issues when users close tabs without saving. Stale saves yield an accessible `409` diff modal with "Twoja wersja" vs. "Zapisana wersja". Cost: Users who concurrently edit the same case must manually resolve collisions.
- **`sub`-Only JWT vs. Self-Contained JWT (N-20):**
  - Carrying only email in the token requires a database lookup on every request. This ensures immediate deactivation, instant role updates, and forced password changes without token revocation blacklists or distributed cache invalidation.
- **`404 Not Found` vs. `403 Forbidden` on Case Access (N-05):**
  - Returning `404` for out-of-scope IDs conceals case existence from unauthorized users, eliminating ID enumeration attacks. `403` is reserved strictly for authenticated users attempting unauthorized actions on in-scope resources or accessing admin endpoints.
- **Dedicated Immutable `case_notes` vs. Inline `cases.note` (N-10):**
  - Eliminating `cases.note` in favor of an append-only `case_notes` table prevents note clobbering during concurrent case updates and supports both case-level and person-level (`subject_user_id`) notes with full author audit trails.

---

## 5. Milestones

1. **Architecture & Foundation Contracts (Completed in PR #5):**
   - Resolve 24 specification contradictions via Indaba council debates.
   - Authoritative `DEPENDENCY_MAP.md` and updated `AGENTS.md`.
   - Install 9 specialized project agent skills in `.agents/skills/`.
   - Verify 0 contradictions across all 17 feature specifications.

2. **Core Auth, User Settings & Security Hardening (Specs 001, 002, 007, 008):**
   - 12-character password validation, `sub`-only JWT verification, `must_change_password` gate.
   - User settings table with accessibility preferences (`theme`, `font_scale`, `reduced_motion`).
   - Admin user management routes, role scoping, and safe deactivation check (`409` if active cases exist).

3. **Case Engine, Notes & Concurrency (Specs 003, 009, 010, 011):**
   - SQLAlchemy 2.0 models with `version: Mapped[int]` and `case_notes`.
   - Unified case service layer enforcing version check, admin date restriction, and `404` scoping.
   - `sessionStorage` draft recovery on `401` in the frontend Case Editor.

4. **Navigation, Dashboard & Filtering (Specs 013, 014):**
   - Mount Dashboard at `/` and Case Table at `/cases`.
   - Implement `GET /api/dashboard/summary` and standardized `GET /api/cases` `{items, total, page, page_size}`.
   - Strict `Europe/Warsaw` date evaluation for `overdue=true`.

5. **Excel Pipeline & Backups (Specs 004, 017):**
   - In-memory Excel parsing with Polish date format resilience.
   - `working_copies` table, preview API, and commit flow with automatic pre-import backup.
   - Streaming in-memory `.xlsx` export.

6. **Bulk Operations, Reassignment & Archive (Specs 005, 006, 015, 016):**
   - Bulk status updates, bulk archive, and supervisor/admin bulk restore.
   - Reassignment workflows with mandatory deactivation reassignment (`reassign_cases_to`).
   - Notification dismissal lifecycle keyed on deadline snapshots.

7. **System Verification & E2E Acceptance:**
   - Execute test suites across all 9 skills (role-matrix tests, 409 concurrency tests, accessibility audits).
   - Playwright end-to-end flows for case editing, conflict resolution, and Excel import.

---

## 6. Risks and mitigation

| Risk | Mitigation |
| :--- | :--- |
| **Silent data loss during concurrent saves** | Mandatory `version` column checked in single service layer; `409 Conflict` returns latest `current` case for side-by-side diff modal. |
| **Information leakage via case ID guessing** | Strict `404 Not Found` returned whenever a case is missing OR outside caller's RBAC scope. |
| **Malformed Excel dates corrupting deadlines** | Multi-format parser handles native Excel floats and Polish text strings (`DD.MM.YYYY`); non-admin import rejects date modifications; preview flags invalid rows. |
| **Disk fill / temporary file leakage** | Entire Excel pipeline operates in memory (streaming parser and generator) and database (`working_copies` table with 24h TTL). Zero files on disk. |
| **Orphaned cases on user deactivation** | `PATCH /api/admin/users/:id` requires `reassign_cases_to` if the user owns active cases, returning `409` if omitted. |
| **Form loss on 60-minute token expiration** | TanStack Router / Axios interceptor catches `401`, preserves form state to `sessionStorage`, and presents inline re-login modal. |
| **Accessibility regression on high-contrast/scale** | `accessibility` skill enforces WCAG 2.1 AA rules, pure `rem` typography, and CSS variables; verified in automated component tests. |
