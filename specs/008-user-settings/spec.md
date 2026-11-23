# User Settings & Accessibility

## Goal

Allow each user to personalise their experience (theme and accessibility
preferences from `appbuild.drawio.xml`) and manage their own password. Password
changes are self-service (requiring current password), while admin password
resets set `must_change_password = true` (spec 012); role and supervisor
assignments remain admin-only (spec 002).

## User Stories

- As a user, I want to change my own password so that I can maintain account
  security without depending on an admin.
- As a user, I want to configure accessibility preferences (font size, high
  contrast, reduced motion) and theme so that the app is comfortable and
  accessible to use.
- As a user forced to change their password (after account creation or admin
  reset), I want to be redirected to `/settings` immediately after login so
  that I cannot use the app with a temporary password.

## Acceptance Criteria

### Backend
- [ ] `PATCH /api/me/password` accepts `{ current_password, new_password }`;
      verifies `current_password` against bcrypt hash before updating and clears
      `must_change_password = false`
- [ ] Unified password policy (spec 007): `new_password` must be at least **12
      characters**, containing at least one uppercase letter, one lowercase
      letter, one digit, and one special character, and must differ from
      `current_password`; returns `400 Bad Request` otherwise
- [ ] After a successful password change, the existing JWT remains valid until
      its natural 60-minute expiry
- [ ] `PATCH /api/me/settings` validates and persists UI & accessibility
      preferences in `users.ui_settings`:
  - `theme`: `"dark"` (default Malinois navy glass) | `"light"`
  - `font_size`: `"small"` | `"normal"` (default) | `"large"` | `"xl"`
  - `high_contrast`: `boolean | null` (default `null` — inherit OS `prefers-contrast`)
  - `reduced_motion`: `boolean | null` (default `null` — inherit OS `prefers-reduced-motion`)
- [ ] `GET /api/me` response includes `role`, `must_change_password`, and
      `ui_settings`
- [ ] If `must_change_password = true`, all API endpoints except `GET /api/me`
      and `PATCH /api/me/password` return `403 Forbidden` with:
      `{ "code": "password_change_required", "detail": "Musisz zmienić hasło przed kontynuowaniem." }`

### Frontend
- [ ] User Settings page lives at `/settings`, accessible from the navigation
      bar user menu
- [ ] **"Zmień hasło"** section has: current password, new password, confirm
      new password inputs with inline validation (12+ chars, complexity,
      matches confirm, differs from current)
- [ ] **"Dostępność i wygląd"** (Accessibility & Appearance) section provides:
  - Theme selector (`Ciemny — Malinois` / `Jasny`)
  - Font size selector (`Mała` / `Normalna` / `Duża` / `Bardzo duża`)
  - High contrast selector (`Systemowe` / `Włączony` / `Wyłączony`)
  - Reduced motion selector (`Systemowe` / `Włączone` / `Wyłączone`)
- [ ] Changes apply immediately to `document.documentElement.dataset`
      (`data-theme`, `data-font-size`, `data-high-contrast`,
      `data-reduced-motion`) and persist via `PATCH /api/me/settings`
- [ ] On `must_change_password = true`, TanStack Router `beforeLoad` redirects
      to `/settings` and blocks navigation to all other routes until the
      password is changed, showing an explanatory banner at the top

## Out of Scope

- Changing email address (admin-only operation)
- Account deletion
- Notification sound or threshold toggles (notification threshold is a global
  admin setting — see spec 005 & spec 012)

## API Contract

### `PATCH /api/me/password`

**Headers:** `Authorization: Bearer <jwt>`

**Request**
```json
{
  "current_password": "OldTempPass1!",
  "new_password": "NewStrongPass2@#"
}
```

**204 No Content** — password updated and `must_change_password` cleared  
**400 Bad Request** — weak password (<12 chars or missing complexity), matches current password, or `current_password` incorrect  
**401 Unauthorized** — invalid/expired token or inactive user

---

### `PATCH /api/me/settings`

**Headers:** `Authorization: Bearer <jwt>`

**Request** (all fields optional)
```json
{
  "theme": "dark",
  "font_size": "large",
  "high_contrast": true,
  "reduced_motion": null
}
```

**200 OK** — full updated `ui_settings` object  
**400 Bad Request** — unknown key or invalid enum value

## Data Model Changes

Add to `users` table:
- `ui_settings` — `JSON`, nullable (stores `theme`, `font_size`, `high_contrast`, `reduced_motion`)

`must_change_password` is defined in spec 007.

## Resolved Decisions (Indaba Council)

- Self-service password change (with current password) + admin reset (`must_change_password = true`) replaces the "tylko admin?" note in `appbuild` (N-02).
- Accessibility settings (`font_size`, `high_contrast`, `reduced_motion`) with `null` OS media-query inheritance added (N-02).
- Unified 12-character minimum password policy enforced everywhere (N-18).
- `notifications_sound` removed from story, schema, and examples (N-19).
