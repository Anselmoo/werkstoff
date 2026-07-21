---
domain: <design|code|testing|documentation>
generated: <ISO date>
sourceMode: <analyzed|scaffolded|mixed>
dimensions: [<dimension id>, <dimension id>, ...]
version: 1
---

# <Domain> Handbook

## Purpose & scope

<One paragraph: what this handbook governs for this project, and what it
explicitly does not — e.g. "This handbook governs this project's visual
design conventions: color, typography, tokens, components, layout,
accessibility, and voice. It does not govern backend architecture or API
design — see the code handbook for that.">

## Dimensions

<Repeat this block once per dimension, in the order listed in the
frontmatter's `dimensions` field. Dimension IDs and titles come from the
matching `references/handbook-<domain>.md` catalog.>

### Dimension: <id> — <title>

**Rule**: <the enforceable rule itself, stated as a plain declarative
sentence a reader can check code/copy/tests against, not a vague value
statement>

**Rationale**: <why this rule exists for this project — cite the
governing principle (Apple-craft framing: clarity, restraint, consistency)
or, for the design domain, the specific council reference it derives from>

**Source**: <where this rule came from — a specific file:line the draft
step read if `sourceMode` is `analyzed`, or "scaffolded default — no
existing convention found" if `scaffolded`>

**Enforcement**: <must | should | consider>

**Detection signal**: <the concrete, mechanically-checkable pattern
`cupertino-handbook-check` looks for to flag a violation of this rule —
e.g. "a color pair failing 4.5:1 contrast", "a public function with no
docstring", "a test file with no assertions">

---

### Worked example (Design domain, Accessibility dimension)

### Dimension: accessibility-baseline — Accessibility baseline

**Rule**: Body text must hit WCAG AA (4.5:1) against its background; every
interactive element has a visible `:focus-visible` ring;
`prefers-reduced-motion` is honored.

**Rationale**: Usability's veto (see `council-palettes.md` "Rules that
survive any register" #5; `tokens-starter.css`'s reduced-motion media
query).

**Source**: `council-palettes.md`, `tokens-starter.css:129-135`
(scaffolded default if this project has no CSS yet; analyzed-and-confirmed
if it does).

**Enforcement**: must

**Detection signal**: new CSS/component code introducing a color pair
failing 4.5:1, or a `:focus` override with no `:focus-visible` fallback, or
an animation with no `prefers-reduced-motion` guard.

## Exceptions & waivers

| Rule | Scope of exception | Reason | Date | Approved by |
|---|---|---|---|---|
| _(none yet)_ | | | | |

An empty table is expected for a freshly-drafted handbook — never omit
this section even when there is nothing to list yet.

## Change log

- <ISO date> — Initial draft (`sourceMode: <analyzed|scaffolded|mixed>`).
