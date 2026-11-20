---
name: spec-first
description: >-
  Use this skill when the user wants to add a new feature, endpoint, page, or
  behaviour to the Malinois project following the spec-first workflow. It guides
  the agent through writing a human-readable spec before touching any code, then
  turning that spec into a plan, tasks, and finally implementation. Also use
  when the user asks to "spec out", "spec a feature", "write a spec", or "review
  a spec".
---

# Spec-First Skill — Malinois

The spec-first workflow keeps humans in the driver's seat. **You write the spec
by hand; the agent reviews, plans, and executes against it.** No code is
written or changed until a spec exists and has been reviewed.

---

## Workflow Overview

```
1. SPEC   → You (or the agent) write specs/<id>-<slug>/spec.md
2. REVIEW → Agent critiques the spec for gaps, contradictions, missing edge cases
3. PLAN   → Agent produces specs/<id>-<slug>/plan.md (technical decisions)
4. TASKS  → Agent produces specs/<id>-<slug>/tasks.md (ordered work units)
5. IMPL   → Agent implements task by task, running tests after each one
6. GATE   → All tests pass before the feature is considered done
```

> **Stop before IMPL if the spec is still in draft.** Ask the user to approve
> the spec and plan first.

---

## Step 1 — Write the Spec

Create a new numbered folder under `specs/`:

```
specs/
└── <NNN>-<feature-slug>/
    ├── spec.md        ← Write this first (see template below)
    ├── plan.md        ← Generated in Step 3
    └── tasks.md       ← Generated in Step 4
```

Numbering is sequential: `001`, `002`, `003`, ...  
Slug is lowercase, hyphenated: `user-login`, `password-reset`, `api-rate-limit`.

### spec.md template

```markdown
# <Feature Title>

## Goal
One or two sentences. What problem does this solve and for whom?

## User Stories
- As a <role>, I want to <action> so that <benefit>.

## Acceptance Criteria
- [ ] Criterion 1 — testable, specific, no ambiguity
- [ ] Criterion 2
- [ ] Edge case handled: <describe>

## Out of Scope
- Anything explicitly NOT part of this feature

## API Contract (if applicable)
### Request
`POST /api/<route>`
```json
{ "field": "type" }
```
### Response
```json
{ "field": "type" }
```

## Data Model Changes (if applicable)
Describe new columns, tables, or schema changes.

## Open Questions
- [ ] Question that needs an answer before implementation
```

---

## Step 2 — Agent Review

After the spec is drafted, the agent reads it and **must** check for:

- Acceptance criteria that are not testable
- Missing error/edge cases (401, 404, 422, network failure, empty states)
- Contradictions between user stories and acceptance criteria
- API contracts that conflict with existing endpoints (see `routers/auth.py`)
- Data model changes that would need an Alembic migration
- Frontend changes that touch `AuthContext` or the router guard

Report any issues before proceeding. If the spec is clean, say so explicitly.

---

## Step 3 — Plan (`plan.md`)

Write a `plan.md` next to the spec:

```markdown
# Plan: <Feature Title>

## Backend changes
- Files affected: list each file in `apps/api/`
- New dependencies: none / list with justification
- Migration needed: yes/no — reason

## Frontend changes
- Files affected: list each file in `apps/web/src/`
- New dependencies: none / list with justification

## Test plan
- New pytest tests: describe what each tests
- New Vitest tests: describe what each tests
- E2E coverage: yes/no — scenario

## Risks / Notes
- Anything the developer should know before approving
```

---

## Step 4 — Tasks (`tasks.md`)

Break the plan into small, ordered, independently verifiable tasks:

```markdown
# Tasks: <Feature Title>

## Task 1 — <short name>
**What:** One sentence description
**Files:** list of files to create or modify
**Done when:** specific test passes or observable output exists

## Task 2 — ...
```

Dependencies must be explicit: "Task 3 depends on Task 1 and Task 2."

---

## Step 5 — Implementation Rules

Work through tasks **one at a time**:

1. Implement the task
2. Run the relevant test suite — stop if tests fail
3. Report the result before moving to the next task

**Backend task checklist:**
- [ ] Run `uv run alembic upgrade head` if schema changed
- [ ] Run `uv run python seed.py` if new seed data needed
- [ ] Run `uv run pytest` — all tests must pass

**Frontend task checklist:**
- [ ] Run `npm test` — all Vitest tests must pass
- [ ] Run `npm run lint` — no lint errors

---

## Step 6 — Gate

The feature is **done** when:
- All acceptance criteria in `spec.md` are checked off
- `uv run pytest` passes with no failures
- `npm test` passes with no failures
- No new lint errors introduced

---

## Reference

- [Spec format details](./references/spec-format.md)
- [Existing specs](../../specs/)
- [Project conventions](../../AGENTS.md)
