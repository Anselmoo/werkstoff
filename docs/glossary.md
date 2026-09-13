---
title: Glossary
---

# Glossary

Terms this repository uses in a specific sense, not the generic one a reader might
assume. Each entry names the canonical term, defines it as this repo actually uses it
with a link to the page that uses it that way, and lists the synonyms that get used
loosely elsewhere but should not be reached for here.

## Terms

### beat

An ordered moment in a workflow where a skill or agent earns its place, named
identically whether it is only documented or actually enforced. The [prompt
catalog](catalog/index.md) uses it for a recipe's ordered list of skill dispatches (a
`beats:` frontmatter field, each with a `skill`, a `why`, and an optional `prompt`) —
purely documentary, nothing runs it. [`takt`](plugins/takt.md) uses the identical word
for the same concept once it is compiled into `.claude/takt.local.md` and enforced as a
`PreToolUse` denial. [`arbeitsplan`](plugins/arbeitsplan.md) is the compiler that turns
a stated problem into the beat declaration takt then enforces. A beat is therefore not
tied to one plugin's internal pipeline — it is the cross-plugin ordering unit, whether
that ordering is only written down or actually gated.

Not: *step, stage, phase* (see below for why each of those names something narrower).

### stage

A structural unit of a codebase's own graph, not a moment in a workflow.
[`andon`](plugins/andon.md) walks a repository's *value stream* stage-by-stage — each
stage is a node such as ingest, normalize, enrich, score, publish — and proves the
[wire](#wire) between consecutive stages before advancing.
[`self-assess-stage-map`](plugins/self-assess.md) derives the same kind of object
independently: it clusters files into stages by shallowest package boundary (never by
manifest directory) and writes the stage graph other self-assess skills depend on. In
both cases a "stage" is a piece of the *codebase*, not a piece of a *process* — the
opposite of what [beat](#beat) names. `code-modernization`'s "eight-stage pipeline"
(cited in [the catalog](catalog/index.md)) is the one place "stage" is used for a
pipeline step instead, borrowed from that plugin's own vocabulary rather than
werkstoff's; do not read it back into andon's sense.

Not: *step* as a synonym for this structural sense (step is generic prose, not a term
of art here); *phase* (a [phase](#phase) subdivides one orchestrator's own pipeline,
not a codebase graph).

### wire

The handoff between two consecutive [stages](#stage) in andon's value stream — what
andon proves or refutes with one of seven evidence-grounded strategies before allowing
the cursor to advance past it. See [`plugins/andon`](plugins/andon.md): "proving each
wire before advancing," and `andon-verify`, which "routes a wire to one of seven
evidence-grounded strategies."

Not: *handoff, connection, edge* — used informally in prose describing the concept, but
"wire" is the word the plugin's own commands and ledger schema use.

### phase

A named subdivision inside *one orchestrator's own* fixed pipeline, scoped to that
orchestrator rather than shared across plugins the way a [beat](#beat) is.
`self-assess-autopilot` names its own CHECK, PLAN, and FIX+VALIDATE phases (see
[`plugins/self-assess`](plugins/self-assess.md)); `andon-loop` internally runs "Phases
0-6" (detect topology, init/resume the ledger, scan, dispatch, enforce, advance,
detect convergence — [`plugins/andon`](plugins/andon.md)). Nothing outside that one
orchestrator schedules against a phase the way takt schedules against a beat; a phase
is private to its pipeline.

Not: *step* (used loosely for the same idea in prose, e.g. "first step of
self-assess-autopilot's CHECK phase" — informal, not a distinct term); *beat* (crosses
plugin boundaries and can be takt-enforced; a phase cannot).

### step

Not a defined term in this repository. It appears throughout the docs as plain English
for "a moment in a sequence" — sometimes meaning a [beat](#beat) ("wedged in as a step
inside another workflow," [orchestration README](orchestration/README.md)), sometimes a
[stage](#stage) transition, sometimes a sub-part of a [phase](#phase). Treat any
occurrence as informal narration, and use the precise term (beat, stage, or phase) when
writing new docs instead of reaching for "step."

### leaf and orchestrator

The distinction the whole [orchestration catalog](orchestration/README.md) is built on.
An **orchestrator** is a fixed sequence whose middle steps read artifacts an earlier
step wrote — it cannot be dropped into another workflow, because a step invoked without
its predecessor's artifact either refuses or fabricates (`andon-loop`,
`self-assess-autopilot`, `compass-solve`, the `/consistency-*` command chain,
`arbeitsplan-compile` → `arbeitsplan-run`, and eight more are named by that page). A
**leaf** is dispatchable at any moment from a scoped prompt, carries no pipeline state,
and returns a result rather than advancing a ledger — everything else in werkstoff,
including every named agent. The [prompt catalog](catalog/index.md) states the
resulting convention directly: "Leaves only" — recipe beats name leaves and
dispatchable agents, never orchestrators, because an orchestrator owns a whole task and
must never be wedged in as a step inside another.

Not: *sub-skill, helper, component* for leaf; *pipeline, workflow* alone for
orchestrator (both are used, but "orchestrator" specifically marks the
cannot-be-dropped-in-partway property, which those looser words don't carry).

### report viewer

A self-contained `.html` file under `plugins/*/assets/*-viewer.html` that renders one
plugin's findings as a static, dependency-free page: no build step, no external network
fetch, colour never the sole channel, and a verdict stated in words rather than left for
the reader to infer from a number. Twelve plugins ship one (13 files — matrize ships
two), and every one is paired with a `scripts/build_<name>_html.py` generator, a
committed demo fixture, and a committed screenshot, per
[`report-viewer-standard.md`](plugin-authoring/references/report-viewer-standard.md)
and enforced by `nacharbeit_lint.py`'s `A-VIEWER-REQUIRED` rule (see the root
[`CLAUDE.md`](https://github.com/Anselmoo/werkstoff/blob/main/CLAUDE.md)).

Not: *HTML report* (says nothing about self-containment or the required generator/
fixture/screenshot triad); *dashboard* (implies live data or multiple linked views,
which none of these are — each is one static page from one run); *self-contained HTML*
(accurate but generic — "report viewer" is the name the standard, the lint rule, and
every plugin's own file path actually use).

### SKILL.md

The one required file inside a skill directory: YAML frontmatter plus a markdown body,
the only file Claude Code's discovery mechanism actually reads to learn a skill exists
and what triggers it. See
[`craft-standards.md`](plugin-authoring/references/craft-standards.md)'s file-tree
listing: "`SKILL.md` — required: YAML frontmatter + markdown body." Anything else the
skill needs — worked examples, schemas, longer reference material — lives in
`references/`, loaded progressively rather than inlined.

Not: *skill definition, skill file* — both are used informally elsewhere to mean the
same file, but neither says which file, and this repo has a documented failure mode
specifically about that one file: frontmatter that fails to parse still loads, silently,
with no description and no tools, so a SKILL.md with broken YAML never triggers and
nothing reports an error (`test/plugins/lint-frontmatter.py` exists for exactly this).
Naming the file precisely matters here more than usual.

### design token

A named design value (colour, radius, spacing, type scale) defined once in
[`tools/design-tokens/tokens.css`](https://github.com/Anselmoo/werkstoff/blob/main/tools/design-tokens/tokens.css)
and vendored byte-identically into every plugin's `assets/tokens.css` by `.rrt.toml`'s
`artifact_targets` — never hand-edited at the vendored copy, only at the source, then
regenerated with `rrt artifacts --regenerate`. The rationale for *which* values are
tokens (one aerogel chemistry per categorical slot, contrast measured against the dark
background) is documented in the token file's own header; the docs-facing account of
the token set lives at [Design tokens](/plugin-authoring/references/design-tokens).

Not: *theme variable, CSS variable, style constant* — accurate as CSS mechanics but
silent on the single-source-of-truth-plus-vendoring discipline that is the actual point
of calling it a token here.

### design root

The configurable directory `matrize-collect` establishes before anything else,
defaulting to `.design/` (overridable via `.claude/matrize.local.md`'s `root:` key),
holding three fixed subdirectories — `references/` (read-only after collection),
`system/` (`DECODE.md`, `LEXIKON.md`, `BRIEF.md`, `tokens.json`, `assets/`), and `out/`
(emitted targets). See
[`matrize-collect`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/matrize/skills/matrize-collect/SKILL.md)'s
"Step 1 — establish the design root." The plugin's own `hooks.json` write-scope guard
denies edits to `<root>/references/**` while allowing `<root>/system/**` and
`<root>/out/**`, so the design root's own subdirectories carry different permissions,
not just different contents.

Not: *design directory, output folder* — both undercount the structure: a design root
is specifically the three-subdirectory layout matrize's guard enforces, not an
arbitrary place to put design files.

### marker

A file [`takt`](plugins/takt.md) checks for as evidence a beat completed; takt itself
never writes one — whatever performs the beat creates it (`mkdir -p .takt && touch
.takt/council-done`, for example). A marker written as `.takt/<name>` is **repo-level**
and is never namespaced by an `arbeitsplan` `runId`; a bare name is **per-run** and
always is namespaced under `.takt/<runId>/` — one beat declaration can carry both kinds
(see the root [`CLAUDE.md`](https://github.com/Anselmoo/werkstoff/blob/main/CLAUDE.md)).

Not: *flag, lock file, sentinel* — generic terms for the same filesystem pattern that
don't carry the repo-level-vs-per-run distinction a marker's own naming convention
encodes.

### escape hatch

The explicitly named, environment-variable-gated way to bypass a fail-closed
`PreToolUse` guard when its rule genuinely does not apply — never a silent default,
always named in the denial message itself. Examples: `takt`'s `TAKT_DISABLE_GUARD=1` or
removing the declaration file ([`plugins/takt`](plugins/takt.md)), `cupertino`'s
`CUPERTINO_DISABLE_GUARD=1` ([`plugins/cupertino`](plugins/cupertino.md)). The root
[`CLAUDE.md`](https://github.com/Anselmoo/werkstoff/blob/main/CLAUDE.md) states the
requirement directly: a hook must "fail **closed** with a named escape hatch." A guard
with no escape hatch that still fails closed is a bug (it denies forever with no way
out); a guard whose escape hatch is undocumented is unsafe (nobody knows the bypass
exists to audit its use).

Not: *bypass, override, kill switch* — all describe the mechanism but drop the "named in
the denial message" requirement that makes it an escape hatch rather than an
undocumented backdoor.

### shrink-only baseline

A recorded count of pre-existing findings (lint violations, missing releases, whatever
the check counts) that a new convention is not required to fix retroactively, on the
condition that the recorded number may only go down, never up. The root
[`CLAUDE.md`](https://github.com/Anselmoo/werkstoff/blob/main/CLAUDE.md) states it for
the Python `ruff.toml` conventions ("The baseline may only shrink. … Adding a path
there, or raising a number, means new code was written against the old convention — fix
the code instead") and the same discipline is named again for
`test/plugins/tag-releases-baseline.txt`. The point of the pattern is that a baseline
which can grow is not a baseline at all — it is silent permission to keep doing the old
thing as long as you also add your name to a list.

Not: *grandfathered, legacy exception, allowlist* — all imply a permanent carve-out;
shrink-only specifically forbids that carve-out from ever getting bigger.

## Plugin names

Every German-named plugin is named for a manufacturing or shop-floor concept its README
states explicitly; the gloss below is quoted or closely paraphrased from that plugin's
own README, not invented here.

### werkstoff

German for "material". The [design rationale in
`tools/design-tokens/tokens.css`](https://github.com/Anselmoo/werkstoff/blob/main/tools/design-tokens/tokens.css)
states the fit directly: the repo's whole visual identity is one material, silica
aerogel, chosen because the name itself means "material" and the brand commits to being
one substance rather than a palette of unrelated colours.

### andon

Not a German word; borrowed from the Toyota Production System. "andon borrows the
Toyota andon cord — stop the line the moment a defect is found rather than letting it
flow downstream" ([`plugins/andon/README.md`](plugins/andon.md)). The plugin halts a
hardening loop at the first stage whose wire cannot be proven, exactly as an andon cord
stops a physical assembly line.

### arbeitsplan

German for "work plan" / routing sheet. "An *Arbeitsplan* is the routing sheet that
turns a part drawing into a concrete sequence of operations — which machine, which
tooling, how long. That is this plugin's job: problem drawing in, operation sequence
out." ([`plugins/arbeitsplan/README.md`](plugins/arbeitsplan.md)). It compiles a stated
problem into an executable, budgeted workflow the same way a shop routing sheet turns a
drawing into an operation sequence.

### lehre

German for both a go/no-go gauge and doctrine. "A *Lehre* is a go/no-go gauge: a
fixture a part either passes through or is rejected by. It also means doctrine. This
plugin is both halves." ([`plugins/lehre/README.md`](plugins/lehre.md)). It researches a
code doctrine and then denies the write that would violate it — gauge and doctrine in
one plugin, as the German word already is.

### matrize

German for a stamping die or type-founding matrix. "A *Matrize* is the die: in
stamping, the form that gives material its shape; in typefounding, the matrix from
which every piece of type is cast. One master, many castings — which is exactly what
this plugin is for." ([`plugins/matrize/README.md`](plugins/matrize.md)). It derives one
master design system from reference exemplars and strikes every output target (tokens,
stylesheet, Tailwind config, sketchbook) from that single master.

### nacharbeit

German for rework — specifically, reworking a manufactured part that failed inspection.
"*Nacharbeit* is the manufacturing word for exactly that: rework of a part that did not
pass, back to the drawing." ([`plugins/nacharbeit/README.md`](plugins/nacharbeit.md)).
It reviews another plugin against the official Anthropic standard and reworks what
fails, the same way a manufacturing rework pass returns a failed part to spec before it
ships.

### takt

No German-meaning gloss appears in the plugin's own README today, unlike the other six;
this entry is grounded in what the README says the plugin *does* rather than in a name
etymology it does not state. "Enforces declared beat order at the tool-call layer, so
sequencing is a gate rather than a sentence." ([`plugins/takt/README.md`](plugins/takt.md)).
It ships no skills or agents of its own — only the `PreToolUse` hook and declaration
format that turns another plugin's stated ordering into a runtime denial.
