---
name: rbac-cases
description: >-
  Use when implementing or modifying case CRUD, role scoping, date-field
  rules, optimistic locking (version), case notes, archive/restore, bulk
  actions, reassignment, or user deactivation in Malinois.
---

# RBAC & Case Domain Specialist — Malinois

Enforces the exact domain rules agreed for `specs/002`, `003`, `006`, `009`,
`010`, `011`, `015`, and `016`.

---

## Role Scoping Matrix

| Role | Active Cases Visible | Archived Cases Visible | Can Edit |
|---|---|---|---|
| `user` | Own (`assigned_to == me`) | Own + past assignee in `case_assignment_history` (**read-only** for past) | Non-date fields (`title`, `client_name`, `status`) on own active cases |
| `supervisor` | Own + direct subordinates (1-level only, no transitive nesting) | Own + direct subordinates (current or past) | Non-date fields on own + direct subordinates; reassign within team; restore own + subordinates |
| `admin` | All | All | All fields including `deadline` / `date_filed` (with mandatory `reason`) |

---

## Critical Domain Invariants

1. **Date Fields (`deadline`, `date_filed`):**
   - Only `admin` may write or modify dates — **including on `POST /api/cases`**.
   - Supervisors creating a case must pass `null`/omit dates (`403` if non-null).
   - Past deadlines are **allowed** on admin creation (with UI warning) and import.
   - Admin *updates* to `deadline` or `date_filed` require a non-empty `reason`
     string (`400` if missing), logged in `case_edit_log.reason`.
2. **Optimistic Locking (`version`) Everywhere:**
   - Single-case `PATCH`, `archive`, `restore` require `{ "version": <int> }`,
     verify inside a DB transaction, increment `version`, and return `409` with
     `current` on mismatch.
   - Bulk (`POST /api/cases/bulk`), reassignment (`POST /api/cases/reassign`),
     and Excel import commits (`POST /api/import/commit`) supply
     per-row `{ id, version }` and report per-row `409` conflicts without
     silent overwrites.
3. **Restore Restriction:**
   - Both single `POST /api/cases/:id/restore` and bulk `action: "restore"` are
     restricted strictly to `supervisor` (in-scope) and `admin`. Regular `user`
     receives `403 Forbidden`.
   - Restoring clears `notification_dismissals` for that case so deadlines
     reactivate cleanly.
4. **Immutable Notes (`case_notes`):**
   - There is **no** `cases.note` column. All notes live in `case_notes`.
   - Supports both case notes and person-only notes ("notatka do osoby") via
     nullable `case_id` + nullable `subject_user_id` with DB
     `CHECK (case_id IS NOT NULL OR subject_user_id IS NOT NULL)`.
   - Person-only notes are visible only to author, subject, subject's direct
     supervisor, and admin.
5. **Safe User / Supervisor Deactivation:**
   - Setting `is_active = false` on a user with active cases requires
     `reassign_cases_to` (active user).
   - Setting `is_active = false` on a supervisor with direct subordinates
     requires `reassign_subordinates_to` (active `supervisor` or `admin`).
   - Omitting either when blocking records exist returns **`409 Conflict`**
     listing `blocking_case_ids` and `blocking_subordinate_ids` (no silent
     fallback).
