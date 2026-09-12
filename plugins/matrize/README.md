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

That is the architecture. The **formatters that actually ship** are `css`, `vitepress`,
`html` and `pdf` (the sketchbook), and `provenance` (the graph viewer). Tailwind, SCSS,
JSON and TOML are the same shape of work and are *not built* — named here as absent
rather than listed as though `emit` could produce them, which is the same discipline the
plugin applies to a rule with no card behind it.

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
             emit --target ⟨ html | pdf | css | vitepress | provenance ⟩
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

## The sketchbook — the Specimen

![A landscape sketchbook spread titled Kontrast: a threshold chart plots six contrast
pairs against rules at 3.0, 4.5 and 7.0, with square red heads for pairs that fall short
and round dark heads for pairs that clear, beside an ANMERKUNGEN margin carrying two
rules with their anti-rules.](assets/sketchbook-screenshot.jpg)

Landscape A4 at **√2**, measured off a real reference rather than assumed — a generic
landscape scaffold uses 16:10, and the reference does not. One building block per spread,
a 66/34 split between specimen canvas and `ANMERKUNGEN` margin, numbered callouts in the
margin, a tinted box for the derived observation, and the approval block that makes the
whole thing a gate rather than a gallery.

The reference uses the callout number in **two** weights — filled pins the artwork,
outlined opens the margin entry. Only the outlined half ships: the filled `.pin` has a
style and no emitter, because a spread addresses its canvas by key rather than authoring
it as SVG here, so there is nowhere to carry the coordinates. Named as a gap rather than
described as if it worked.

```bash
python3 plugins/matrize/scripts/build_sketchbook_html.py \
  --data plugins/matrize/scripts/fixtures/sketchbook-demo.json --out /tmp/sketchbook.html
```

**Two modes.** `approval` (default) is the reference's shape — no code anywhere, because
it goes in front of a decision-maker. `handoff` adds a bottom-anchored snippet per spread
and an export control, which is what a developer needs and a client does not.

**Charts, where a measured value meets a fixed threshold.** One primitive, four call
sites — contrast, motion, type scale, spacing. Dot with a stem, never a bar, because a
bar implies a meaningful zero and contrast's floor is 1.0. Log axis for ratios, because
linearly a 15:1 pair eats the axis and squeezes the interesting 2.5–5 band into a sliver.
Colour is always redundant to position *and* shape *and* a printed value.

What the chart adds over a table is **margin**: 3.44 against a 4.5 threshold is a near
miss fixed by darkening a few percent, and 1.20 is a different colour. A table prints
"FAILS" for both.

**Text into illustration.** Prose past its slot budget stops being read, so an over-budget
`ANMERKUNG` is rendered as a do/don't figure instead — but only when the entry carries a
structured rule and anti-rule to draw. With nothing to draw it flags the overrun and
leaves the prose alone. Inventing a figure the lexicon never described is the same defect
as a rule with no card behind it.

The demo data is committed and deliberately shows a **failing** system: the action red
clears AA only at large sizes, one duration sits past the Doherty threshold, one spacing
step is off the grid, and one note runs past its budget with nothing to draw.

## Branding a surface, and what gets enforced

The question "may we have six or eight categorical hues?" turned out to be the wrong one.
Measured with `scripts/cvd.py` — CIEDE2000 under a Viénot-1999 dichromat simulation, the
metric this workshop's own token file already names — **every** categorical palette here
sits below the separation floor, the five-hue scale included:

| palette | n | worst deuteranopia | worst protanopia |
|---|---|---|---|
| the shipped five-hue scale | 5 | 5.70 | 5.30 |
| a six-fill canvas set | 6 | 3.40 | 3.41 |
| a seven-role set | 7 | 4.10 | 3.96 |
| an eight-entry hashed palette | 8 | 3.50 | **1.96** |

Widening the cap does not fix that; it makes the worst pair monotonically worse. What
carries the accessibility claim is the rule the token file already states — **colour is
never the only channel** — and unlike a hue count, that is decidable.

`scripts/redundancy.py` decides it, narrowly: a palette indexed by a computed key, or
three-plus sibling rules setting nothing but colour, with no second channel **where the
category is rendered**. A legend does not count — a legend maps name to hue, and reading
a chart requires the inverse. Anything it cannot decide returns `undecided`, which is
never reported as a violation.

The hook's third rule denies a write introducing colour-only encoding into a file the
project has **declared** a branded surface (`surfaces:` in `.claude/matrize.local.md`).
It never sweeps a repository it was not pointed at. A `Write` carries the whole file so
the full check runs; an `Edit` carries a fragment with no use sites, so only the
self-contained palette-index pattern is checked there — stated rather than implied.

`scripts/emit_vitepress.py` is the applying half: it turns a theme's hand-copied literals
into references to the token set. It proposes the mapping by value-matching, which the
provenance graph refuses to do — the difference is what the result is used for. There a
match became an asserted edge; here it is a proposal a human reviews, and every ambiguity
is reported rather than resolved.

## The vocabulary

`references/vocabulary/` carries the domain layer: one file per dimension — colour, grid
and spacing, typography, motion, icons — plus `visual-asset-taxonomy.md`, the parent the
five hang off.

Each file names the terms a design system actually uses, the **pairs people confuse**,
and ends with **Decoding notes**: what that dimension yields from a reference and at what
grade. So `matrize-decode` knows the base unit is inferable at grade B by taking the GCD
of observed spacing — and that *a GCD of 1 means there is no grid, which is itself the
finding* — without rediscovering it per run.

Every term carries a **kind**, and the kind is a routing rule rather than a note:

| kind | where it goes | what refuses it |
|---|---|---|
| `token` | a stored value — `tokens.json` | — |
| `derived` | computed from tokens; never stored separately | `V-VOCAB-NOT-A-TOKEN` |
| `rule` | a constraint — a lexicon entry, **and it needs an anti-rule** | `V-VOCAB-RULE-NO-ANTIRULE` |
| `property` | observed or measured; not stored at all | `V-VOCAB-NOT-A-TOKEN` |

A `rule`-kind term with no anti-rule is mis-classified, not merely incomplete. A `derived`
or `property` term sitting in `tokens.json` is a value that will drift from whatever it
was derived from.

The taxonomy's **Origin** column bounds what can be promised at all: `derivable` classes
are delivered whole, `drawn` classes only as a system plus seeds and a growth rule,
`captured` and `shot` classes as rules and never as assets. That is the honest reason
this plugin ships an icon *system* rather than an icon library.

### The vocabulary is compiled, and it refuses

Until it was compiled, all of the above reached the pipeline as prose inside four
`SKILL.md` files — which the werkstoff workshop has measured as the weakest enforcement
layer there is, beneath a fenced command. So the most load-bearing content in the plugin
was the least enforced content in it.

`scripts/vocabulary.py` parses the six files into a registry — **223 dimension terms**
(`token` 78 · `rule` 65 · `property` 62 · `derived` 18) and **31 asset classes** — and
`scripts/validate_tokens.py` checks every token against it. The `PreToolUse` guard then
refuses a write to `<root>/system/tokens.json` that contradicts it, because a rule that
must hold regardless of model cooperation belongs in a hook.

```bash
python3 plugins/matrize/scripts/vocabulary.py --selftest          # 35 checks
python3 plugins/matrize/scripts/vocabulary.py --audit <tokens.json>
python3 plugins/matrize/scripts/validate_tokens.py <tokens.json>  # 36 cases
```

Three properties are worth stating because each is a trap this plugin walked into first.

**It is parsed at runtime, never compiled to a committed JSON.** One source, so there is
no second copy to drift.

**A parser that extracts nothing makes every rule pass vacuously.** The selftest asserts
per-file counts measured by hand (46 / 38 / 36 / 46 / 57), and a file yielding zero terms
is a parser failure rather than an empty file. The same discipline covers the validator:
if the registry cannot be built, `V-VOCAB-REGISTRY` fails closed instead of letting the
other twelve rules quietly disappear. *No findings* and *no checks* look identical from the outside.

**Headers are found by the separator row, never by the first cell.** `motion.md`'s
Principles table carries an ordinary data row beginning `| Origin | Motion emanates…`, and
a parser that whitelists first cells re-latches there, invents a table boundary, and drops
two thirds of that table — raising nothing. The selftest keeps the wrong parser executable
and fails if it does not misbehave.

### What the vocabulary does NOT do

It does not propose a term for a token. Matching custom-property names against the
registry binds **1** of this repository's own 50 declarations, because names are *roles*
(`--space-1`, `--bg`) and the vocabulary names *concepts* (`Spacing step`, `Surface /
background`). The binding is interpretation, and invariant I3 keeps interpretation in a
separate artefact written by a separate agent. `--audit` reports what is named and what is
not, and proposes nothing.

Homonyms are real and are reported rather than resolved: `Opacity` is `derived` in
`color-system.md` and `property` in `motion.md`, so every concept is addressed as
`term` + `dimension`. A project that genuinely needs a concept the vocabulary lacks
declares the extension with its reason and the card that decided it; `matrize-status`
reports those as the vocabulary's backlog.

## Three presentation classes, chosen by the shape of the question

| class | form | answers |
|---|---|---|
| **Ledger** | static document, print-first, no script at all | a finite list of measured claims against fixed thresholds |
| **Specimen** | static document, landscape, set in the system's own tokens | what the design looks like |
| **Viewer** | interactive, screen only | where a value came from and what depends on it |

The test that sorts them is falsifiable: **print it**. If nothing is lost, it should not
have been interactive. The derivation-health report loses nothing, so it is a Ledger —
and a finite ledger has a property a screen destroys, in that it is complete and it ends.
A reader who can click no longer knows whether they have seen everything.

Being a Ledger has a pleasant consequence. The two independent XSS barriers a
client-rendered viewer needs collapse into something stronger than either: there is no
script, so there is no injection surface. The contrast chart is server-rendered SVG and
prints with the rest.

## The provenance graph — the one interactive artefact

![A dark three-column graph: one reference node on the left, a column of Design Cards,
and a column of tokens, with curved edges between them and a sidebar for the selected
node. The verdict reads: 50 tokens trace to 1 reference, and 3 roles share --silica, so
changing it changes 3 things, not one.](assets/provenance-viewer-screenshot.jpg)

Everything else matrize emits is print-first, because an approval artefact ends as a PDF
in front of someone who does not get a `localhost` URL. A graph earns the exception: it
has no readable static layout, and the reader arrives with a target question rather than
reading it end to end — *why is this token this value, and what breaks if I change it?*
Click any node and both answers light up at once.

```bash
python3 plugins/matrize/scripts/retrofit_css.py tools/design-tokens/tokens.css --out /tmp/tokens.json
python3 plugins/matrize/scripts/build_provenance_html.py --tokens /tmp/tokens.json --out /tmp/prov.html
```

**Edges are read, never inferred.** They come from each token's written `edge` field and
from DTCG `{ref}` aliases. Nothing here matches values across files — and `--paranoid`
makes that refusal testable by re-deriving the graph the wrong way and reporting the
disagreement. On this repository's own tokens it finds four:

```
value-matching would MERGE 2 distinct roles that share one value: radius.sm, space.1
value-matching would MERGE 2 distinct roles that share one value: radius.panel, space.2
value-matching would COLLAPSE 2 roles aliasing color.ferria into one node …
value-matching would COLLAPSE 3 roles aliasing color.silica into one node: color.accent,
  color.cat-1, color.diverging-cool — so "what breaks if I change color.silica?" would
  answer 1 instead of 3
```

That is the whole argument for writing edges rather than reconstructing them, measured on
real material instead of asserted. The selftest asserts both cases against the actual
file: `4px` must stay two nodes, and `--silica` must show three dependents.

Grade travels with the edge, so a grade-C origin is drawn dashed — reusing the `4,3` dash
that already means *unproven* elsewhere in this workshop.

## The icon system, and gradients

![A sketchbook spread titled Icon-System showing twelve stroke icons on a 24 grid with
their keyline named under each, a row demonstrating optical stroke at 24, 16 and 12px,
and margin notes stating the grid is derived from the spacing base and that the wordmark
is not part of the set.](assets/icon-system-screenshot.jpg)

**The grid is derived, not decreed.** Grid = 6× the system's spacing base, live area 5×,
padding 0.5×, stroke = base/2. A 4px base lands on the 24/20/2/2 convention Feather,
Lucide and Tabler already share — so the derivation agrees with the ecosystem instead of
fighting it, and an 8px base yields a 48 grid without anyone re-deciding.

**A brand mark is not an icon.** A logo is drawn once at one size and may keep its own
geometry; an icon set is rendered at many sizes, so it needs uniform stroke and shared
keylines or it stops reading as one family. This repo's own mark is 32-grid at 2.75
stroke and deliberately sits outside the system.

**Geometry is checked, not asserted.** Every seed is defined as primitives rather than a
path string, so the same data renders *and* validates: inside the live area, on the
subdivision, filling one of four keylines. `icons.py --selftest` plants an off-grid point,
an off-subdivision point and a bad keyline, and requires each to be caught.

**Twelve seeds, never a library.** The growth rule is the deliverable. Until a
brand-owned set exists, adopt one open family wholesale — mixing two is visible
immediately at the terminals — and record it as a reference with its rights grade.

**Gradients are tokens, and they carry the exception.** Stops are *references* to roles,
so changing a role changes the gradient. Nothing is invented: a role set with no deeper
step yields no gradient and a **finding** saying why. A gradient whose endpoints are
indistinguishable is caught as a flat fill, and a third stop is challenged in its own
purpose text. Every one ships the anti-rule that matters here — **never in an
illustration zone**, where tone comes from flat colour and overlap rather than a blend.

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
