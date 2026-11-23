---
name: qa-testing
description: >-
  Use when writing, reviewing, or running backend pytest tests, frontend Vitest
  component tests, or Playwright E2E tests in Malinois. Covers role-matrix testing,
  concurrency 409 tests, and CI parity.
---

# QA & Testing Specialist — Malinois

No task in `specs/<NNN>/tasks.md` is complete until its tests exist and pass.

---

## Test Stack

| Layer | Runner | Location | Command |
|---|---|---|---|
| Backend API | `pytest` + `fastapi.testclient.TestClient` | `apps/api/tests/` | `cd apps/api && uv run pytest` |
| Frontend Unit/UI | `vitest` + `@testing-library/react` + `user-event` | `apps/web/src/**/*.test.tsx` | `cd apps/web && npm test` |
| Frontend Lint & Build | `eslint` + `tsc` + `vite build` | `apps/web/` | `cd apps/web && npm run lint && npm run build` |
| Full-Stack E2E | `@playwright/test` | `apps/web/e2e/` | `cd apps/web && npm run test:e2e` |

---

## Backend Testing Rules

1. **Use `TestClient` synchronously** — do not introduce unnecessary `pytest-asyncio` boilerplate for FastAPI route tests.
2. **Test the full Role Matrix on every protected endpoint:**
   - Unauthenticated → `401`
   - Deactivated user (`is_active=False`) → `401`
   - `must_change_password=True` → `403` (except `GET /api/me` and `PATCH /api/me/password`)
   - `user` (own resource vs someone else's resource)
   - `supervisor` (own + direct subordinate vs other team's resource)
   - `admin` (all resources)
3. **Test Date Immutability:** Verify `user` and `supervisor` receive `403` when attempting to modify `deadline` or `date_filed` via `PATCH`, bulk, or Excel copy editor.
4. **Test Concurrency (`version`):** Verify stale `version` returns `409 Conflict` with the latest `current` case payload and does not overwrite DB state.
5. **Test Atomicity:** For bulk operations and reassignments, verify that a single unauthorized or missing ID rolls back the entire transaction.
6. **Never hardcode production secrets or external DB URLs** in tests; use the seeded/fixture SQLite DB. Default seeded test account: `trainee@example.com` / `Secret123!`.

---

## Frontend Testing Rules

1. **Mock network calls with `vi.spyOn(globalThis, "fetch")`** and restore mocks in `afterEach`.
2. **Query by accessible role/label** (`getByRole`, `getByLabelText`, `findByText`) — avoid fragile CSS class selectors.
3. **Use `userEvent.setup()`** for realistic typing, clicking, and keyboard navigation.
4. **Always test all UI states:** loading (skeleton/spinner), empty state, error state (`role="alert"`), and role-conditional controls (e.g. date inputs hidden for non-admins, Restore hidden for regular users, Admin link hidden for non-admins).
5. **Respect `AuthContext`:** Never manipulate `localStorage` directly in components; test through `AuthProvider`.

---

## CI Gate Before Finishing

```bash
# Backend
cd apps/api && uv run alembic upgrade head && uv run python seed.py && uv run pytest

# Frontend
cd apps/web && npm run lint && npm test && npm run build
```
