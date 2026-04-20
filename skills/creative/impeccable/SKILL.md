# Impeccable — Design Language for AI

Design fluency for AI harnesses. 1 skill, 18 commands, and curated anti-patterns that teach AI to build distinctive, production-grade frontend interfaces — not generic "AI slop."

**Source:** [github.com/pbakaus/impeccable](https://github.com/pbakaus/impeccable) (18k+ stars)
**License:** Apache 2.0

## When to Load

Load this skill when:
- User asks to build, design, or create any web UI, page, component, or frontend
- User asks for design review, critique, or improvement of existing UI
- User asks about typography, color, layout, or visual design decisions
- Any task involves HTML/CSS/JS frontend output
- User invokes any of the 18 commands below

## 18 Commands

### Create
- **`/impeccable`** — Create distinctive, production-grade frontend interfaces. The core command. Call with `craft` for shape-then-build flow, `teach` for design context setup, `extract` to pull reusable components.
- **`/shape`** — Plan UX/UI before writing code. Structured discovery interview → design brief.

### Evaluate
- **`/audit`** — Technical quality checks: accessibility, performance, responsive, anti-patterns. Scored report with P0-P3 severity.
- **`/critique`** — UX design review: visual hierarchy, information architecture, emotional resonance, cognitive load. Quantitative scoring + persona-based testing.

### Refine
- **`/typeset`** — Fix font choices, hierarchy, sizing, type scale.
- **`/layout`** — Fix layout, spacing, visual rhythm, grid composition.
- **`/colorize`** — Introduce strategic color with OKLCH palettes.
- **`/animate`** — Add purposeful motion, micro-interactions, transitions.
- **`/delight`** — Add moments of joy and surprise.
- **`/bolder`** — Amplify boring, understated designs.
- **`/quieter`** — Tone down overly bold, noisy designs.
- **`/overdrive`** — Add technically extraordinary effects (beta).

### Simplify
- **`/distill`** — Strip to essence, remove what doesn't earn its place.
- **`/clarify`** — Improve unclear UX copy, labels, error messages.
- **`/adapt`** — Adapt for different devices, contexts, accessibility needs.

### Harden
- **`/polish`** — Final pass: design system alignment, shipping readiness.
- **`/optimize`** — Performance improvements, loading patterns.
- **`/harden`** — Error handling, edge cases, i18n, onboarding.

### System
- **`/impeccable teach`** — One-time setup: gather design context, save to `.impeccable.md`.
- **`/impeccable extract`** — Pull reusable components and tokens into the design system.

## Core Design Rules

### Typography
- Use a modular type scale with fluid sizing (clamp) for headings
- Use fewer sizes with more contrast — 5-step scale, ≥1.25 ratio between steps
- Line-height scales inversely with line length
- Cap body text at ~65-75ch width
- **BANNED fonts:** Inter, Roboto, Arial, Open Sans, system defaults, DM Sans, Plus Jakarta Sans, Outfit, Space Grotesk, IBM Plex *, Fraunces, Lora, Crimson*, Playfair Display, Cormorant*, Syne, Newsreader, DM Serif*
- Pair a distinctive display font with a refined body font
- DO NOT use monospace as lazy shorthand for "technical" vibes
- DO NOT put large rounded icons above every heading

### Color & Contrast
- **Use OKLCH, not HSL** — perceptually uniform, reduce chroma toward extremes
- Tint neutrals toward brand hue (even 0.005 chroma creates cohesion)
- 60-30-10 rule is about visual *weight*, not pixel count
- **BANNED:** Pure black (#000) or pure white (#fff) — always tint
- **BANNED:** Gray text on colored backgrounds
- **BANNED:** AI color palette (cyan-on-dark, purple-to-blue gradients, neon on dark)
- **BANNED:** Gradient text (`background-clip: text` with gradients)
- Theme choice (light/dark) must derive from audience context, not defaults

### Layout & Space
- Use 4pt spacing scale: 4, 8, 12, 16, 24, 32, 48, 64, 96
- Use `gap` instead of margins for siblings
- Vary spacing for hierarchy — don't apply same padding everywhere
- Self-adjusting grid: `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))`
- Container queries for components, viewport queries for page layout
- **BANNED:** Wrapping everything in cards
- **BANNED:** Nesting cards inside cards
- **BANNED:** Identical card grids repeated endlessly
- **BANNED:** Hero metric layout (big number + small label + gradient accent)
- **BANNED:** Centering everything — left-aligned asymmetric layouts feel more designed

### Absolute Bans (NEVER do these)
1. **Side-stripe borders** — `border-left:` or `border-right:` with width >1px colored accent. Use different element structure entirely.
2. **Gradient text** — `background-clip: text` with gradients. Solid colors only for text.

### Motion
- Use exponential easing (ease-out-quart/quint/expo) for natural deceleration
- For height animations, use grid-template-rows transitions
- **DO NOT** animate layout properties (width, height, padding, margin) — use transform + opacity
- **DO NOT** use bounce or elastic easing

### Interaction
- Use progressive disclosure — start simple, reveal sophistication
- Design empty states that teach the interface
- **DO NOT** make every button primary — use hierarchy

### UX Writing
- Make every word earn its place
- **DO NOT** repeat information users can already see

## The AI Slop Test

If someone sees the output and says "AI made this" immediately, it fails. A distinctive interface should make someone ask "how was this made?"

## Reference Files

Detailed references are in `references/`:
- `typography.md` — Type systems, font pairing, modular scales, OpenType
- `color-and-contrast.md` — OKLCH, tinted neutrals, dark mode, accessibility
- `spatial-design.md` — Spacing systems, grids, visual hierarchy
- `motion-design.md` — Easing curves, staggering, reduced motion
- `interaction-design.md` — Forms, focus states, loading patterns
- `responsive-design.md` — Mobile-first, fluid design, container queries
- `ux-writing.md` — Button labels, error messages, empty states
- `craft.md` — Shape-then-build flow
- `extract.md` — Component/token extraction flow

Individual command skills are in `commands/*.md`.

## Teach Mode

Before doing design work, gather context:
1. Check for existing `.impeccable.md` in project root
2. If missing, gather: target audience, use cases, brand personality/tone
3. Write to `.impeccable.md` with `## Design Context` section

## Usage in Hermes

When the user asks about frontend design, building UI, or improving existing interfaces:
1. Load this skill
2. Apply the design rules above
3. Reference specific command files for specialized tasks (audit, critique, polish, etc.)
4. Run the AI Slop Test before presenting output
