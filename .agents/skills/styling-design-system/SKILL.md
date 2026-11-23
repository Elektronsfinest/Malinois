---
name: styling-design-system
description: >-
  Use when touching CSS, layout, components, theme tokens, colours, typography,
  or animations in apps/web. Enforces Malinois's dark-blue glassmorphic palette,
  Plus Jakarta Sans typography, semantic urgency colours, and accessibility tokens.
---

# Malinois Design System & Styling

Malinois uses a **deep-navy glassmorphic** visual identity built on pure CSS custom
properties in `apps/web/src/index.css` and `apps/web/src/App.css`. Every new page,
modal, table, badge, and popup MUST preserve this palette and visual language.

---

## Core Colour Palette (Binding)

| Role | Token | Value | Current Usage |
|---|---|---|---|
| Canvas Base | `--color-bg-base` | `#03071e` | Page backdrop (`login-container`, `dashboard-container`) |
| Gradient Start | `--bg-gradient-start` | `#0a1128` | Deep navy gradient root |
| Gradient Mid | `--bg-gradient-mid` | `#001f54` | Mid-navy gradient / radial glow |
| Gradient End | `--bg-gradient-end` | `#034078` | Accent navy gradient |
| Body Gradient | `--bg-body-gradient` | `linear-gradient(135deg, #020b1f 0%, #001845 50%, #042562 100%)` | Global `body` backdrop |
| Glow Orb 1 | `--color-orb-primary` | `#0077b6` | Ambient floating orb (top-left) |
| Glow Orb 2 | `--color-orb-secondary` | `#023e8a` | Ambient floating orb (bottom-right) |
| Ambient Teal | `--color-accent-teal` | `#1282a2` | Subtle top-left radial glow |
| Interactive Focus / Accent | `--color-accent-cyan` | `#48cae4` | Input focus border, active links, focus rings |
| Glass Surface | `--color-surface-glass` | `rgba(10, 25, 47, 0.7)` | Cards, modals, tables, panels (`backdrop-filter: blur(40px)`) |
| Glass Border | `--color-border-subtle` | `rgba(255, 255, 255, 0.15)` | Card & table dividers |
| Text Primary | `--color-text-primary` | `#ffffff` | Headings, labels, primary cell content |
| Text Secondary | `--color-text-secondary` | `rgba(255, 255, 255, 0.75)` | Metadata, timestamps, subtitles |
| Text Muted | `--color-text-muted` | `rgba(255, 255, 255, 0.45)` | Placeholders, disabled labels |
| Primary Action Fill | `--color-btn-primary` | `#000000` (hover `#0d0d0d`) | Pill buttons (`border-radius: 26px–27px`, subtle white border) |

### Semantic & Deadline Urgency Colours

| State | Foreground / Border | Surface Fill | Meaning |
|---|---|---|---|
| **Overdue (`deadline < today`) / Error** | `#ef4444` / `#ff6b6b` | `rgba(127, 29, 29, 0.65)` (`#7f1d1d`) | Overdue case row/badge, destructive hover (`#dc2626`), error state |
| **Upcoming (within admin threshold)** | `#f59e0b` / `#fb923c` | `rgba(120, 53, 15, 0.55)` | Approaching deadline warning |
| **Safe (beyond threshold) / Success** | `#22c55e` | `rgba(6, 78, 59, 0.65)` (`#064e3b`) | Safe deadline, completed action, checkmark state |
| **Archived / Neutral** | `#94a3b8` | `rgba(30, 41, 59, 0.65)` | Archived badge, closed status |

---

## Typography & Spacing

- **Font family:** `--font-main: "Plus Jakarta Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Brand wordmark:** `MALINOIS` — uppercase, `font-weight: 800`, `letter-spacing: 3px`.
- **Polish locale strings:** All visible UI copy is in Polish (`zaloguj`, `wyloguj`, `Zakończono`, `Archiwizuj`, `Przywróć`, `Historia zmian`, `Notatki`, `Kopie zapasowe`). Never mix English and Polish in visible labels.
- **Date display:** Always format dates in Polish locale (`DD.MM.YYYY`, timestamps `DD.MM.YYYY, HH:mm`).

---

## Rules

1. **No raw colour drift:** Never introduce purple, beige, or off-brand light-gray SaaS palettes. Extend existing CSS custom properties in `:root`.
2. **Glassmorphism consistency:** New panels, modals, and popups use `--color-surface-glass` with `1px solid var(--color-border-subtle)`, `border-radius: 16px–24px`, and deep soft shadows (`0 20px 40px rgba(0, 0, 0, 0.5)`).
3. **Accessibility overrides:**
   - Support `[data-theme="high-contrast"]` (solid `#000000` surfaces, `#ffffff` text, `#48cae4` / `#facc15` high-contrast borders, `>= 7:1` contrast).
   - Support `[data-font-scale="normal" | "large" | "xlarge"]` via root `font-size` scaling (`100%` / `112.5%` / `125%`) and `rem`-based component sizing.
   - Respect `@media (prefers-reduced-motion: reduce)` and `[data-reduced-motion="true"]` by disabling `floatOrb`, `bounceIn`, `shake`, and transition animations.
4. **No `dangerouslySetInnerHTML`:** Render all case titles, client names, and notes as plain React text nodes.
5. **No decorative clutter:** Every badge, stat card, and colour highlight must map to real backend data (never placeholder numbers or fake charts).
