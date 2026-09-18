# 0007 — awwwards-grade design system

**Status:** Accepted

## Context

An early "make it professional" UI pass read as generic AI-generated slop. The product's credibility depends on the UI feeling crafted. The reference direction: the logged-in TypeSafe console and awwwards-grade sites — expressive grotesk type, monospace technical accents, high-contrast ink on paper, hairline structure, and smooth scroll-driven motion.

## Decision

A monochrome, editorial design system (full spec in [../design-system.md](../design-system.md)):
- **Host Grotesk** (display/body) + **JetBrains Mono** (labels, numbers, ids) via Google Fonts.
- High-contrast ink/paper, both themes first-class; **color reserved for risk meaning** (emerald/amber/red), never decoration.
- Hairline structure (1px borders, `gap-px` grids) over cards; small radius.
- `motion` (framer-motion) for reveals/stagger with expo-out easing; a rAF count-up on the risk dial; `prefers-reduced-motion` honored everywhere.
- Built the foundation directly (tokens, motion primitives, page) rather than delegating the vibe, after the delegated pass missed.

## Consequences

- **Positive:** Distinct, credible product feel the user approved. Reusable primitives (`components/motion.tsx`, `.label-mono`, tokens in `index.css`) keep the three routes consistent.
- **Negative:** One added dependency (`motion`). Custom-styled bits (dial, meters, hub rows) carry their own styling instead of leaning on shadcn defaults — intentional, for control.
