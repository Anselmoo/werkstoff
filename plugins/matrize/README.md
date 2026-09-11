# matrize

**Derives a design system from reference exemplars, names every element, and emits it
to any target — so the decision that was skipped gets made once, in writing, instead of
re-guessed per project.**

A *Matrize* is the die: in stamping, the form that gives material its shape; in
typefounding, the matrix from which every piece of type is cast. One master, many
castings — which is exactly what this plugin is for. It takes the references someone
actually admires, measures what they do, names what recurs, and cuts a single neutral
master from which every target is struck: a DTCG token file, a stylesheet, a Tailwind
config, and a landscape sketchbook a non-technical decision-maker can approve.

The metaphor holds at both ends. A Matrize is itself struck by a *Patrize* — it is
derived from a reference before it becomes the thing others are made from, which is the
same two-step this pipeline runs.

One sentence is the whole scope, and it is also the refusal test:

> Derive a design system from exemplars, name every element, and emit it to any target.

Anything that is not *derive*, *name*, or *emit* does not belong here.

## Why this exists

The failure this plugin prevents is not bad taste. It is a **skipped decision phase**:
developers style before they decide, so every project ends up styled ad hoc with
nothing shared between them, and the reasons — why this red, why this spacing step, why
this radius — survive only as a comment nobody reads, or not at all.

This workshop has already lived that failure in its own tree.
`tools/design-tokens/tokens.css` carries a real derivation: one aerogel chemistry per
categorical slot, a five-hue cap the material itself imposes, measured WCAG ratios per
token, and a proof that the three-step ramp is contrast mathematics rather than style.
All of it lives in a 67-line CSS comment that the file's own text describes as linked
from nothing — and because CSS is the only representation, the docs-site copy is a
hand-maintained mirror that has already drifted and the SVGs hardcode the palette.

So the two invariants that shape everything below:

**The source of truth is not CSS.** Tokens live in a platform-neutral DTCG file. CSS,
Tailwind, SCSS, JSON for Sphinx, TOML for a Rust server — all of these are *formatter
output*, never input.

**Measurement and interpretation are separate phases.** `decode` measures and cites;
`name` interprets and justifies. Merging them makes a claim indistinguishable from a
measurement, and the whole point is being able to tell those apart later.

## What it is not

- **Not a drift auditor.** It never checks whether code still matches the system.
  matrize **creates** the system; `codebase-consistency` **guards** it.
- **Not `consistency-canonize`.** That derives a form from *the repository's own
  divergent sites* and feeds an in-place rewrite. matrize derives from *external
  reference exemplars* and feeds an emit. matrize never scans a repo for divergence —
  the moment it does, `/consistency-scan` owns the question instead.
- **Not `cupertino`.** `cupertino-council` designs one screen from taste principles
  before code; `cupertino-handbook-draft` describes one domain *as it already is* and
  explicitly disclaims researching external authority. Deriving from external exemplars
  is the thing that disclaimer leaves open.
- **Not `lehre`.** `lehre` enforces a doctrine at write time. matrize has no opinion
  about your code at all.
- **Not an icon library.** It delivers an icon *system* — grid, keyline shapes, stroke
  weight, optical sizing, naming scheme, 8–12 seed icons — plus the growth rule every
  further icon is built by. Adopting an existing open icon set until a brand-owned one
  exists is a first-class output here, not an admission of failure.

## Install

```
/plugin install matrize@werkstoff
```

Or, for a checkout: `claude --plugin-dir plugins/matrize`.

## The pipeline

```
preflight → survey → collect → decode → name → brief ⟨approval gate⟩
                                                  ↓
                                   ( echo | spread | retrofit )
                                                  ↓
                             tokens.json (DTCG) + asset manifest
                                                  ↓
             emit --target ⟨ html | pdf | css | tailwind | vitepress | sphinx | … ⟩
dolmetsch   cross-cutting, callable from any phase, reads LEXIKON.md
status      read-only, any time
```

Commands run in order, but each is standalone: stop, review, resume. Every one produces
an artefact that stands on its own.

## Two grades per reference, not one

`collect` records **both**, because they answer different questions:

| reliability | what the source supports |
|---|---|
| **A** | published guidelines, design-token files, documented specs — values usable as stated |
| **B** | declared CSS from a fetched page — usable as *ratios*, not as absolutes |
| **C** | screenshot measurement, visual estimate — direction only, never a token value alone |

| rights | what may be reproduced |
|---|---|
| **R1** | values and prose both (public domain, permissive, or your own material) |
| **R2** | values and rules extracted and restated; brief quotation with attribution; text never bundled or adapted |
| **R3** | values measured and cited; nothing reproduced |

The two are orthogonal, and conflating them is a real trap: a CC BY-NC-ND design
reference is **grade A for reliability and forbidden for derivative text at the same
time**. A Design Card that would set a token from a grade-C source alone is rejected and
surfaced as an open question rather than quietly rounded into a number.

## Every rule carries its anti-rule

A rule without a stated failure case is decoration, so it is not emitted. The anti-rule
is the load-bearing half:

- "Red stays the only dominant action colour per view, never two at once."
- "Script face exclusively for the slogan, never as a headline substitute."
- "Alert green never in the same view as beginner green."

And a rule whose `purpose` can name neither a measured property of the target (contrast,
measure, touch-target size) nor a named design principle is a **copy**, not a rule —
`design-critic` rejects it on exactly that test. That is what keeps this from being a
copying machine with a lexicon.

## Required coverage

A system that omits any of these is incomplete, and `brief` says so: **states** (focus,
disabled, loading and empty — not just hover and press), **contrast** (computed, not
asserted), **motion** (duration, easing, distance, staggering, plus the anti-rule),
**inverse/dark as a named mode**, **content rules** (character budgets, tone,
orthography), and **provenance** (a spacing grid that is merely plausible is not the
same as one that is derived).

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Find out what can honestly be extracted here

````prompt
"before we start: what can matrize actually measure from these references, and what would only be a guess?"
````

> Triggers `matrize-preflight`: per-phase Ready / Ready-with-gaps / Not-ready, each
> reference graded for extraction reliability and for rights, and any existing
> CSS/token footprint already in the repo.

##### Lift an ad-hoc project into the taxonomy without changing how it looks

````prompt
"take this project's scattered CSS and name it as a system — same pixels, just organised and justified"
````

> Triggers `matrize-retrofit`: maps existing declarations onto the taxonomy and proves
> zero visual diff, rather than redesigning anything.

##### Measure the references before interpreting them

````prompt
"read these references and tell me what they actually do — ratios and relations, with a confidence rating per line"
````

> Triggers `matrize-decode`: Design Cards with source, selector-or-page reference, and
> a reliability grade; a second agent re-derives each one from the cited source.

##### Name what recurs, with the failure case

````prompt
"give every recurring element a name, a purpose, a rule and an anti-rule"
````

> Triggers `matrize-name`: writes `LEXIKON.md`, machine-addressable so `dolmetsch` can
> read it; `design-critic` rejects any rule that is really a copy.

##### See genuinely different directions side by side

````prompt
"show me four properly different directions for this, not four shades of the same one"
````

> Triggers `matrize-spread`: divergent idioms in one fixed shell so they stay
> comparable, each with a bounded specimen zone, plus a forced-choice block.

##### Turn vague direction into precise terms

````prompt
"make it airier — and tell me what that means in actual numbers"
````

> Triggers `matrize-dolmetsch`: translates both ways against `LEXIKON.md`, and says so
> plainly when a term is not in the lexicon rather than guessing.

##### Produce the approval artefact

````prompt
"emit the sketchbook as a landscape PDF I can put in front of the client"
````

> Triggers `matrize-emit`: headless Chrome print-to-pdf honouring `@page`, with the
> approval block that names the decision-maker and the gate criteria.

## The retrofit proof, on this repository's own tokens

`retrofit` is proven, not asserted, and on real material: `tools/design-tokens/tokens.css`
— 50 declarations, eight synced consumers.

```bash
python3 plugins/matrize/scripts/retrofit_css.py tools/design-tokens/tokens.css --out /tmp/tokens.json
python3 plugins/matrize/scripts/prove_retrofit.py tools/design-tokens/tokens.css /tmp/tokens.json
```

Three arms, because one is not enough:

| arm | asserts | catches |
|---|---|---|
| **1 textual** | every declaration reappears with an identical value | a dropped, added or altered token |
| **2 structural** | every `var(--x)` round-trips as a DTCG *reference* | a retrofit whose output is right and whose source of truth is wrong |
| **3 visual** | renders byte-identical at 1600×900 | cascade effects the first two cannot see |

Arm 2 is the one worth explaining. Arm 1 does catch crude flattening — rewriting
`--accent: var(--silica)` as a hex is a textual change. What it cannot see is a token
file storing the *literal string* `"var(--silica)"` instead of the reference
`{color.silica}`: the CSS is byte-identical, the render is byte-identical, and the token
file now holds an opaque string with no edge in it. The system has forgotten that accent
**is** silica — which is the answer to "what breaks if I change silica?" — and every
non-CSS formatter emits that string into a target where `var()` means nothing.

Arm 3 carries its own instrument check, because **two blank pages are also
byte-identical**. The fixture must render differently with and without the tokens, or the
pass is vacuous.

Current result on this repo: **zero visual diff, structure preserved**, all 10 aliases
intact.

## Hooks

One `PreToolUse` hook, `hooks/matrize_guard.py`, `type: "command"`. It is **inert unless
the configured design root exists** — it never polices an unrelated project that merely
has the plugin installed — and it denies exactly two things:

1. any write or edit under `<root>/references/**` — references are read-only, which is
   how the copyright boundary is carried mechanically rather than by good intentions;
2. any write to `<root>/system/tokens.json` or `<root>/out/**` while a `spread` choice
   record is unanswered — an n-proposal portfolio with no forced choice is a
   procrastination machine.

It denies nothing else. A guard that policed every write outside the design root would
police your whole repository the moment it was installed.

## The derivation-health report

![matrize derivation-health report: a dark table-based report listing six references with
their reliability and rights grades, four tokens blocked because their only evidence is a
screenshot, and a computed-contrast table in which two roles fail WCAG AA.](assets/derivation-viewer-screenshot.jpg)

It charts what the pipeline knows about its own evidence: which references were decoded,
their grades, which tokens rest on grade-C evidence alone, and which contrast pairs fail.
Ratios are computed by `scripts/contrast.py` and cannot be supplied — the builder rejects
input that states one, because a number a human typed is a claim and a number the script
derived is a measurement.

The demo data is committed, so the screenshot above is reproducible:

```bash
python3 plugins/matrize/scripts/build_derivation_html.py \
  --data plugins/matrize/scripts/fixtures/derivation-demo.json --out /tmp/derivation.html
```

It deliberately shows a failing run rather than a clean one — four tokens blocked and a
primary action colour that clears AA only at large sizes. A demo in which nothing is wrong
demonstrates nothing.

## Fan-out safety

`decode` fans out one `reference-decoder` per reference: first batch 4, escalating
×1 → ×2 → ×4, hard cap 16. The **circuit breaker** trips when accepted cards fall
strictly below two-thirds of *measurable* cards, judged per batch rather than
cumulatively — a reference that could not be fetched or read at all is excluded from the
denominator instead of being counted as a rejection. The correct response to a tripped
breaker is a revised rubric, never more agents.

Every agent is read-only. Agents return structured results and the orchestrating skill
writes the artefacts, so reference content — which is untrusted input, and can contain
instruction-shaped text — has no path to disk through an agent.

## Running it outside werkstoff

Nothing here depends on this repository. Install the plugin, and optionally drop this in
the target project's `.claude/settings.json` to declare the same boundary the hook
enforces:

```json
{
  "permissions": {
    "allow": ["Read(**)", "Write(.design/system/**)", "Write(.design/out/**)",
              "Edit(.design/system/**)", "Edit(.design/out/**)"],
    "deny": ["Edit(.design/references/**)", "Write(.design/references/**)"]
  }
}
```

That guards the file tools only; a shell command that writes a file goes through Bash
permissions instead. The hook is what actually refuses.

## Verifying a change to this plugin

```bash
python3 plugins/nacharbeit/scripts/nacharbeit_lint.py plugins/matrize --docs-root docs
python3 test/plugins/lint-frontmatter.py plugins/matrize
python3 test/plugins/lint-release-wiring.py
python3 plugins/matrize/hooks/test_matrize_guard.py
python3 test/plugins/verify-hooks-deny.py plugins/matrize
claude plugin validate plugins/matrize --strict
```

## Escape hatch

`MATRIZE_DISABLE_GUARD=1` disables the hook entirely. It is named in every deny message
the guard emits. The guard fails **closed**: if it cannot decide, it denies and tells you
which variable turns it off.
