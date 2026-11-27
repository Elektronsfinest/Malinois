---
name: debugger
description: >-
  Use when diagnosing failing tests, HTTP 401/403/409/422 errors, Alembic
  migration failures, TanStack Router redirect loops, or Excel parsing bugs
  in Malinois.
---

# Debugger — Malinois

Follow a strict **Reproduce → Isolate → Fix Root Cause → Add Regression Test** loop.
Never guess-patch symptoms.

---

## Common Malinois Failure Modes & Where to Look

### 1. Unexpected `401 Unauthorized` or Login Redirect Loops
- Check `apps/api/routers/auth.py` → `get_current_user`: verifies `Authorization: Bearer <token>`, `decode_access_token(token)`, DB lookup by lowercase email, AND `user.is_active`.
- Check `apps/api/security.py`: `JWT_SECRET_KEY` mismatch between processes or 60-minute `exp` expiry.
- Check `apps/web/src/context/AuthContext.tsx` and `apps/web/src/router.tsx`: `beforeLoad` checks `!auth.token && !auth.isLoading`. If `isLoading` flips prematurely or `/api/me` returns 401, the user is bounced to `/login`.

### 2. Unexpected `403 Forbidden`
- Check if the user has `must_change_password = True` (blocks all endpoints except `GET /api/me` and `PATCH /api/me/password`).
- Check `require_role(...)` dependency and case scope filtering (`user` = own, `supervisor` = own + direct subordinates, `admin` = all).
- Check if a non-admin payload inadvertently included `deadline` or `date_filed` (even unchanged values in a naive form submit!).

### 3. `409 Conflict` on Case Save
- Compare the `version` sent in the `PATCH` body against `cases.version` in DB.
- Verify the frontend updated its local `version` state after a previous save, archive/restore, or conflict resolution.

### 4. `422 Unprocessable Entity` vs `400 Bad Request`
- FastAPI returns `422` for Pydantic schema validation errors (missing fields, wrong types) and `400` for domain validation errors raised explicitly via `HTTPException(400)`. Check `schemas.py` field aliases (`AliasChoices`) and validators.

### 5. Alembic / SQLite vs PostgreSQL Failures
- Run `uv run alembic current` and `uv run alembic heads` to check for multiple heads or unapplied revisions.
- If `OperationalError: no such column` appears in tests, run `uv run alembic upgrade head` in `apps/api/` (never delete `dev.db` blindly without checking migrations).
- On SQLite `ALTER TABLE` errors, verify `op.batch_alter_table(...)` is used.

### 6. Excel Import / Parsing Errors
- Check both MIME type AND file extension (`.xlsx` / `.xls`), plus the 10 MB size cap (`413`).
- Inspect whether date cells are native Excel serial dates (`datetime`/`date` objects from `openpyxl`) or Polish strings (`DD.MM.YYYY` / `YYYY-MM-DD`).
- Verify column headers are matched case-insensitively and trimmed of whitespace.

---

## Debugging Protocol

1. Capture the exact failing command, stack trace, or HTTP status + response body.
2. Read the involved route handler, schema, model, or React component completely before editing.
3. Verify the fix with a minimal failing test first, then make the fix and re-run the full relevant suite (`uv run pytest` / `npm test`).
