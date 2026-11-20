# User Settings

## Goal

Allow each user to personalise their experience (UI preferences) and manage
their own account credentials. Password changes are self-service; role and
supervisor assignments are admin-only (spec 002).

## User Stories

- As a user, I want to change my own password so that I can maintain account
  security without depending on an admin.
- As a user, I want to choose UI preferences (e.g. theme, notification sounds)
  so that the app suits my working style.
- As a user forced to change their password (after an admin reset), I want to
  be redirected to the settings page immediately after login so that I cannot
  use the app with a temporary password.

## Acceptance Criteria

### Backend
- [ ] `PATCH /api/me/password` accepts `{ current_password, new_password }`;
      verifies `current_password` against bcrypt hash before updating
- [ ] New password must be at least 8 characters, contain at least one
      uppercase letter, one digit, and one special character; `400` otherwise
- [ ] After a successful password change, the existing JWT remains valid until
      its natural expiry (no forced logout of other sessions)
- [ ] `PATCH /api/me/settings` persists UI preferences as a JSON blob on the
      user record
- [ ] `GET /api/me` response includes `must_change_password` flag
- [ ] If `must_change_password = true`, all API endpoints except
      `PATCH /api/me/password` and `GET /api/me` return `403` with message
      `"Musisz zmienić hasło przed kontynuowaniem."`

### Frontend
- [ ] The User Settings page is accessible from a dropdown on the navigation bar
- [ ] The page has a "Zmień hasło" section with: current password, new
      password, confirm new password fields
- [ ] Validation: new password ≠ current, confirm matches new; errors shown
      inline
- [ ] On `must_change_password = true`, the app redirects to User Settings
      immediately after login and blocks navigation to other pages
- [ ] A banner at the top of User Settings explains why the change is required
      when in forced-change mode

## Out of Scope

- Changing email address (admin-only operation)
- Account deletion
- Notification preference toggles (notification threshold is global admin
  setting — see spec 005)

## API Contract

### `PATCH /api/me/password`

**Headers:** `Authorization: Bearer <jwt>`

**Request**
```json
{
  "current_password": "OldPass1!",
  "new_password": "NewPass2@"
}
```

**204 No Content** — password updated  
**400 Bad Request** — weak password or current_password incorrect  
**401 Unauthorized** — invalid token

---

### `PATCH /api/me/settings`

**Headers:** `Authorization: Bearer <jwt>`

**Request**
```json
{ "theme": "dark", "notifications_sound": false }
```

**200 OK** — updated settings object

## Data Model Changes

Add to `users` table:
- `ui_settings` — `JSON`, nullable (stores theme and other preferences)

`must_change_password` is defined in spec 007.

## Open Questions

- [ ] What UI preferences are required? → At minimum: theme (light/dark).
      Full list TBD.
