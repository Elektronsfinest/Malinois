# User Authentication

## Goal
Allow a user to log in with an email and password, receive a session token, and
access protected pages. Unauthenticated users are redirected to the login page.
This is the foundation all other features build on.

## User Stories
- As a trainee, I want to log in with my email and password so that I can access
  the protected dashboard.
- As a logged-in user, I want my session to be remembered across page refreshes
  so that I don't have to log in every time I open the app.
- As a logged-in user, I want to log out so that my session is cleared from the
  browser.
- As an unauthenticated visitor, I want to be redirected to the login page when
  I try to visit a protected route so that I can't access content I shouldn't.

## Acceptance Criteria

### Backend
- [x] `POST /api/login` returns `200` with `access_token` (JWT), `token_type`,
      and `user` object (`id`, `email`, `is_active`) for valid credentials
- [x] `POST /api/login` returns `401` for a valid email with the wrong password
- [x] `POST /api/login` returns `401` for an email that does not exist
- [x] `GET /api/me` returns `200` with the current user when a valid Bearer
      token is provided
- [x] `GET /api/me` returns `401` when no Authorization header is sent
- [x] `GET /api/me` returns `401` when an invalid or expired token is sent
- [x] `GET /health` returns `200` with `{"status": "ok"}`
- [x] Passwords are stored as bcrypt hashes — never plain text
- [x] CORS allows requests from `http://localhost:5173`

### Frontend
- [x] Unauthenticated users visiting `/` are redirected to `/login`
- [x] Authenticated users visiting `/login` are redirected to `/`
- [x] The login form has an `email` input and a `hasło` (password) input
- [x] The form does not call `fetch()` if either field is empty
- [x] The form does not call `fetch()` if the email format is invalid
- [x] A `401` response from the backend shows "Niepoprawny login lub hasło"
- [x] On successful login the token is stored in `localStorage` under
      `"access_token"`
- [x] On page refresh, if a token exists in `localStorage`, the app calls
      `GET /api/me` to restore the session
- [x] A `401` from `/api/me` on refresh clears the token and redirects to login
- [x] The dashboard shows `"Witaj, <email>!"` for the logged-in user
- [x] The logout button clears the token from `localStorage` and redirects to
      `/login`

## Out of Scope
- Password reset / forgot-password flow
- Email verification
- OAuth / social login
- Role-based access control
- Remember-me / extended sessions
- Rate limiting on login attempts

## API Contract

### `POST /api/login`

**Request**
```json
{ "email": "trainee@example.com", "password": "Secret123!" }
```

**200 OK**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "trainee@example.com",
    "is_active": true
  }
}
```

**401 Unauthorized**
```json
{ "detail": "Niepoprawny login lub hasło" }
```

---

### `GET /api/me`

**Headers:** `Authorization: Bearer <jwt>`

**200 OK**
```json
{
  "id": 1,
  "email": "trainee@example.com",
  "is_active": true
}
```

**401 Unauthorized** — missing, malformed, or expired token

---

### `GET /health`

**200 OK**
```json
{ "status": "ok" }
```

## Data Model

**Table: `users`**

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | Primary key, auto-increment |
| `email` | String | Unique, indexed, not null |
| `hashed_password` | String | Not null |
| `is_active` | Boolean | Default `True`, not null |

Migration: `alembic/versions/` (already applied).

## Open Questions
- [x] Should the token expire? → Yes, 60 minutes (implemented in `security.py`)
- [x] SQLite for local dev or Postgres required? → SQLite for local dev, Postgres
      via Docker for production-like environments
