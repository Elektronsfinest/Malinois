# Spec Format Reference

This reference describes every section of a `spec.md` file, what belongs in
it, and common mistakes to avoid.

---

## File Location

```
specs/<NNN>-<slug>/spec.md
```

- `NNN` — zero-padded three-digit number, sequential (`001`, `002`, ...)
- `slug` — lowercase, hyphenated, describes the feature (`user-login`,
  `password-reset`)

---

## Sections

### `# Title`
The feature name. Concise. No "Implement" or "Add" prefix — just the noun:
✅ `# Password Reset`  
❌ `# Implement password reset feature`

---

### `## Goal`
One to three sentences. Answers:
- **Who** benefits?
- **What** can they do that they couldn't before?
- **Why** does it matter?

---

### `## User Stories`
Standard format: `As a <role>, I want to <action> so that <benefit>.`

Each story should map to at least one acceptance criterion. If a story has no
criterion, it is not implementable.

---

### `## Acceptance Criteria`
Checkboxes. Each criterion must be:
- **Testable** — a test can be written to verify it
- **Specific** — no "it should work correctly"
- **Atomic** — one thing per bullet

Good examples:
```
- [ ] POST /api/login returns 200 with access_token and user.email for valid credentials
- [ ] POST /api/login returns 401 for a non-existent email
- [ ] POST /api/login returns 401 for a correct email with wrong password
- [ ] The login form does not call fetch() if the email field is empty
- [ ] The login form shows "Niepoprawny login lub hasło" on 401
```

Bad examples:
```
- [ ] The login works correctly          ← not testable
- [ ] Handle errors                      ← not specific
- [ ] Login and show dashboard           ← not atomic
```

---

### `## Out of Scope`
Explicitly list what this spec does NOT cover. This prevents scope creep and
signals to reviewers that those things were considered and intentionally
deferred.

---

### `## API Contract`
Required for any spec that adds or changes a backend endpoint.

Include:
- HTTP method + path
- Request body (JSON example)
- Success response (JSON example with status code)
- Error responses (each HTTP status and what triggers it)

---

### `## Data Model Changes`
Required if the spec needs new tables, columns, or index changes.

Describe the change in plain English. The agent will generate the Alembic
migration; the spec just needs to document intent.

Example:
```
Add a `reset_token` column (String, nullable, indexed) and a
`reset_token_expires_at` column (DateTime, nullable) to the `users` table.
```

---

### `## Open Questions`
Blockers that need a human decision before implementation can start.
Unresolved open questions mean the spec is a draft — not ready for planning.

Format: `- [ ] Question text` (check off when resolved with a note).

---

## Dos and Don'ts

| Do | Don't |
|---|---|
| Write acceptance criteria before thinking about code | Describe implementation details in the spec |
| Keep each spec focused on one feature | Bundle multiple unrelated features |
| Number specs sequentially | Skip numbers or reuse them |
| Check off criteria as tests are written | Mark criteria done without a test |
| Keep open questions tracked until resolved | Leave the spec in draft and start coding |
