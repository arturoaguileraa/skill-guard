# Design system

Reference: awwwards-grade craft and the TypeSafe product aesthetic. High-contrast ink on paper, expressive grotesk, monospace technical accents, hairline structure, and smooth motion. **Color is reserved for meaning (risk), never decoration.** See [ADR-0007](adr/0007-awwwards-design-system.md).

## Type

- **Display + body:** `Host Grotesk` (300–800), tight tracking on headings (`.font-display`, `letter-spacing: -0.02em`).
- **Technical accents:** `JetBrains Mono` for labels, numbers, ids, filenames, status. The `.label-mono` utility (uppercase, tracked, 11px, muted) is the standard eyebrow/label.
- Loaded from Google Fonts in `apps/web/index.html`; `--font-sans` / `--font-mono` set in `apps/web/src/index.css`.

## Color

Tokens are shadcn/oklch neutrals, tuned in `apps/web/src/index.css`:

- Light: warm paper background, near-black ink, hairline borders.
- Dark: deep near-black, off-white ink.
- **Risk palette** (the only chromatic color): emerald = benign / low, amber = suspicious / mid, red = malicious / high. Thresholds: red ≥ 0.8, amber ≥ 0.55, else emerald. (The UI names are `benign` / `suspicious` / `malicious`; the oRPC contract and database keep `allow` / `escalate` / `block`.)

Both themes are first-class; `next-themes` with a toggle. Never hardcode hex — use the semantic tokens (`bg-background`, `text-muted-foreground`, `border-border`, …).

## Structure

- **Hairlines, not cards.** Sections are built from 1px borders and `gap-px` grids over a `bg-border` backdrop, not elevated rounded cards. Small radius (`--radius: 0.3rem`).
- Mono eyebrows label every block. Generous vertical rhythm in heroes.

## Motion

- Library: `motion` (framer-motion). Primitives in `apps/web/src/components/motion.tsx`:
  - `Reveal` — fade + rise on scroll into view.
  - `Stagger` / `StaggerItem` — staggered group entrance.
  - Easing: expo-out `cubic-bezier(0.16, 1, 0.3, 1)`.
- The risk dial number **counts up** (rAF tween, cubic ease-out) via `useCountUp` in `routes/index.tsx`.
- **Always** honor `prefers-reduced-motion` — the primitives disable animation, and `index.css` clamps durations globally.

## Components

- Built on `@skill-guard/ui` (shadcn "base-lyra" over base-ui). Note: base-ui `TooltipTrigger` takes `render={<el/>}`, not `asChild`.
- Prefer existing components; the custom bits (dial, thin meters, preset chips, hub rows) are hand-styled for control.

## Principles

1. Monochrome by default; color earns its place by meaning.
2. Mono for anything machine-ish (numbers, ids, code, status).
3. Hairlines and whitespace do the structural work.
4. Motion is calm and fast-settling, never bouncy or attention-seeking.
5. Every screen works at phone width and in both themes.
