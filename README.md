# Malinois — Trainee TDD Starter & Testing Guide

Welcome to the **Malinois** project! This repository is pre-configured with **GitHub Actions CI**, **Backend Tests (`pytest`)**, **Frontend Unit/Component Tests (`Vitest` + `React Testing Library`)**, and **End-to-End Tests (`Playwright`)**.

All assignment requirements are already encoded as automated tests (the **Red** phase of Test-Driven Development). Your goal is to write the implementation code to make every test turn **Green**.

---

## 1. What is TDD (Test-Driven Development)?

**Test-Driven Development (TDD)** is a software development practice where tests are written **before** the production code. Instead of writing features first and testing later, you let the tests drive your design and implementation through a short, repeatable loop known as **Red → Green → Refactor**:

1. 🔴 **Red** — Run the test suite and watch the tests fail. Read the failure output carefully to understand what behavior or contract is missing.
2. 🟢 **Green** — Write the minimal amount of production code required to make the failing test pass.
3. 🔵 **Refactor** — Clean up your code (split components, improve naming, remove duplication, organize endpoints/modules) while keeping all tests green.

### How to Follow TDD in This Project
1. Run a single test file (or watch mode) to see what is currently failing.
2. Implement one requirement at a time (start with **Task 1 Backend**, then **Task 1 Frontend**, then **E2E**, and finally **Task 2 Database & Migrations**).
3. Re-run the tests after every small change.
4. Once all tests pass, refactor your code and open/update your Pull Request so GitHub Actions verifies everything in CI.

### Useful TDD & Tooling Links
- [Martin Fowler — Test-Driven Development](https://martinfowler.com/bliki/TestDrivenDevelopment.html)
- [Agile Alliance — What is TDD?](https://www.agilealliance.org/glossary/tdd/)
- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy 2.0 ORM Quickstart](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Vitest Guide](https://vitest.dev/guide/)
- [React Testing Library Introduction](https://testing-library.com/docs/react-testing-library/intro/)
- [Playwright Documentation](https://playwright.dev/docs/intro)

---

## 2. How to Run the Project & Tests Locally

### Backend (`apps/api`)
Requires Python 3.14+ and [`uv`](https://docs.astral.sh/uv/).

```bash
cd apps/api

# Install dependencies
uv sync --dev

# Run the FastAPI development server (http://localhost:8000)
uv run fastapi dev main.py --port 8000

# Run all backend tests
uv run pytest

# Run only Task 1 authentication tests
uv run pytest tests/test_auth.py

# Run only Task 2 database & Alembic tests
uv run pytest tests/test_database.py
```

### Frontend (`apps/web`)
Requires Node.js 22+ and `npm`.

```bash
cd apps/web

# Install dependencies
npm install

# Start the Vite dev server (http://localhost:5173)
npm run dev

# Run frontend tests once
npm test

# Run frontend tests in interactive watch mode (recommended for TDD!)
npm run test:watch
```

### End-to-End Tests (`Playwright`)
Playwright automatically boots both the FastAPI server (`:8000`) and Vite server (`:5173`) if they are not already running.

```bash
cd apps/web

# Install the Chromium browser (first time only)
npx playwright install chromium

# Run E2E tests
npm run test:e2e
```

---

## 3. How to Make the Tests Pass with Your Code

To integrate smoothly with the existing test suites, make sure your implementation follows these contracts:

### A. Backend — Task 1 (`apps/api/main.py`)
Tests in `apps/api/tests/test_auth.py` import `app` from `main.py` and verify:
- **Test User Credentials**:
  - Email/Username: `trainee@example.com`
  - Password: `Secret123!`
- **`POST /api/login`**:
  - Accepts JSON `{ "email": "...", "password": "..." }`.
  - On valid credentials: returns `200 OK` with a JSON object containing a non-empty token (`"access_token"` or `"token"`) and user details (`"email": "trainee@example.com"`, either at top level or nested under `"user"`).
  - On invalid password or unknown user: returns `401 Unauthorized` with a JSON error message (`"detail"` or `"message"`).
- **`GET /api/me`**:
  - Protected endpoint requiring `Authorization: Bearer <token>`.
  - Returns `200 OK` with `{ "email": "trainee@example.com", ... }` when the token is valid.
  - Returns `401` (or `403` when missing header) if the token is missing or invalid.
- **CORS**:
  - Configure FastAPI's `CORSMiddleware` to allow requests from `http://localhost:5173` (with `allow_methods=["*"]`, `allow_headers=["*"]`).

### B. Frontend — Task 1 (`apps/web/src/`)
Tests in `apps/web/src/App.test.tsx` and `apps/web/e2e/app.spec.ts` render `<App />` and verify:
- **Protected Route (`/`)**:
  - Unauthenticated users visiting `/` are redirected to `/login`.
- **Login Page (`/login`)**:
  - Contains inputs associated with labels matching `/email/i` and `/hasło|password/i` (use `<label htmlFor="...">` or `aria-label`).
  - Contains a submit button matching `/zaloguj/i`.
  - Validates empty fields and invalid email formats on the client side before calling `fetch`.
  - Displays `"Niepoprawny login lub hasło"` when `/api/login` responds with `401`.
  - Stores the received token in `localStorage` or `sessionStorage` under key `token` or `access_token`.
- **Dashboard (`/`)**:
  - Displays `"Witaj, trainee@example.com!"`.
  - Contains a logout button matching `/wyloguj/i` that clears the stored token and redirects back to `/login`.

### C. Database & Migrations — Task 2 (`apps/api/`)
Tests in `apps/api/tests/test_database.py` inspect your SQLAlchemy and Alembic setup:
- **`apps/api/models.py`**:
  - Define `User` mapped to `__tablename__ = "users"` with columns:
    - `id` (Primary Key)
    - `email` (`String`, `unique=True`, `index=True`)
    - `hashed_password` (`String`)
    - `is_active` (`Boolean`, `default=True`)
- **`apps/api/database.py`**:
  - Expose `SessionLocal` and a generator dependency `get_db()` that uses `yield` and closes the session in a `finally:` block.
- **Password Hashing & Seeding**:
  - Hash `Secret123!` using `bcrypt` or `argon2` (never store plain text in `hashed_password`).
  - Seed `trainee@example.com` automatically if the `users` table is empty.
- **Alembic (`apps/api/alembic/`)**:
  - Initialize Alembic in `apps/api/` (`alembic init alembic`), point `target_metadata = Base.metadata` in `alembic/env.py`, generate the initial migration in `alembic/versions/`, and apply it (`alembic upgrade head`).
