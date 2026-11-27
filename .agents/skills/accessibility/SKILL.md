---
name: accessibility
description: >-
  Use when building or reviewing UI components, forms, tables, modals, deadline
  popups, or User Settings accessibility controls in apps/web. Enforces WCAG 2.1 AA,
  keyboard navigation, ARIA semantics, and user accessibility preferences.
---

# Accessibility Specialist — Malinois

`appbuild.drawio.xml` explicitly requires **accessibility** inside User Settings,
and case-management tooling must be usable by keyboard-only and low-vision
employees without friction.

---

## Mandatory User Accessibility Controls (`spec 008`)

Every user can configure and persist the following preferences in `users.ui_settings`:

1. **Theme / Contrast (`theme`):** `"dark"` (default Malinois navy glass) | `"light"` | `"high-contrast"` (pure `#000000` canvas, `#ffffff` text, `#48cae4` / `#facc15` borders, `>= 7:1` contrast ratio).
2. **Font Scale (`font_scale`):** `"normal"` (`100%`) | `"large"` (`112.5%`) | `"xlarge"` (`125%`) — applied via `document.documentElement.dataset.fontScale` so all `rem`-based typography and spacing scales cleanly without clipping or horizontal scroll.
3. **Reduced Motion (`reduced_motion`):** `boolean` (defaults to OS `prefers-reduced-motion: reduce`) — disables ambient glow-orb animations, button morph transitions, bounce/shake keyframes, and modal fade slides.

---

## Component Accessibility Checklist

### Forms & Inputs
- Every `<input>`, `<select>`, and `<textarea>` MUST have a programmatically associated `<label htmlFor="...">`.
- Inline validation errors use `role="alert"` and `aria-describedby` linked to the failing field.
- Never rely on placeholder text as a label.

### Tables (Main Cases, Archive, Admin Users, Backups)
- Use semantic `<table>`, `<thead>`, `<tbody>`, `<th scope="col">`.
- Sortable headers expose `aria-sort="ascending" | "descending" | "none"` and are operable with `Enter` / `Space`.
- Bulk selection checkboxes have descriptive `aria-label` (e.g. `"Zaznacz sprawę: Sprawa emerytalna – Kowalski"`).
- Never convey deadline urgency by colour alone — pair colour with explicit text/badge (`ZALEGŁE`, `Za X dni`, `W terminie`).

### Modals, Conflict Dialogs & Deadline Popups
- Use `role="dialog"` (or `role="alertdialog"` for overdue popups and destructive confirmations) with `aria-modal="true"` and `aria-labelledby`.
- Trap focus inside open modals, support `Escape` to close (except forced password-change gate), and restore focus to the triggering element on close.
- Toast feedback (e.g. `"Zaktualizowano 3 sprawy"`) uses an `aria-live="polite"` status region; critical errors use `aria-live="assertive"`.

### Keyboard & Focus
- Every interactive control must be reachable via `Tab` / `Shift+Tab` in logical DOM order.
- Visible `:focus-visible` outline (`2px solid #48cae4`, `outline-offset: 2px`) on every button, link, row action, and tab — never `outline: none` without a replacement focus indicator.
- Skip-to-main-content link (`"Przejdź do treści"`) at the top of authenticated pages.
