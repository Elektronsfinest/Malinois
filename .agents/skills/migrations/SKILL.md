---
name: migrations
description: >-
  Use whenever modifying apps/api/models.py, adding/removing columns or tables,
  creating indices, or running Alembic migrations. Enforces SQLAlchemy 2.0 style
  and SQLite + PostgreSQL parity.
---

# Database & Alembic Migrations — Malinois

Malinois runs **SQLite** (`dev.db`) in local dev/CI and **PostgreSQL** (`psycopg`)
in Docker/production. Every schema change must work identically on both engines.

---

## Mandatory Rules

1. **Alembic only — never `Base.metadata.create_all()`** in application or production code.
2. **SQLAlchemy 2.0 style:** Always use `Mapped[...]` and `mapped_column(...)` in `apps/api/models.py`. Inherit from `Base` in `database.py`.
3. **SQLite batch mode:** SQLite does not support `ALTER TABLE ... DROP COLUMN` or `ALTER COLUMN` natively without batch operations. When altering existing columns or constraints, use `with op.batch_alter_table("table_name") as batch_op:` so migrations succeed on both SQLite and PostgreSQL.
4. **Explicit `server_default` on non-null additions:** Adding a `NOT NULL` column to an existing table (e.g. `users.role`, `users.must_change_password`, `cases.version`) MUST include a `server_default` so existing rows migrate cleanly.
5. **Explicit indices:** Add indices for every foreign key and filter column (`cases.assigned_to`, `cases.deadline`, `cases.archived`, `cases.title`, `cases.client_name`, `(case_edit_log.case_id, changed_at DESC)`, `(case_notes.case_id, created_at DESC)`).
6. **Reversible `downgrade()`:** Every migration must implement a working `downgrade()` that cleanly reverses `upgrade()`.
7. **Never edit a committed migration:** Once a revision is merged, create a new follow-up revision instead of mutating history.

---

## Workflow

```bash
cd apps/api

# 1. Update models.py (and import new models in alembic/env.py if in separate files)
# 2. Autogenerate migration
uv run alembic revision --autogenerate -m "add_cases_table"

# 3. Inspect the generated file in alembic/versions/ — verify types, defaults, indices, batch mode
# 4. Test upgrade -> downgrade -> upgrade cycle on SQLite
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head

# 5. Re-seed if needed and run full backend test suite
uv run python seed.py
uv run pytest
```

---

## Verification Checklist

- [ ] Migration file committed under `apps/api/alembic/versions/`
- [ ] `upgrade head`, `downgrade -1`, and `upgrade head` all succeed cleanly
- [ ] No PostgreSQL-only types (e.g. `JSONB` without generic `JSON` fallback, or native `ENUM` without `create_type`/portable `String`) break SQLite
- [ ] `seed.py` remains idempotent after migration
- [ ] `uv run pytest` passes with zero errors
