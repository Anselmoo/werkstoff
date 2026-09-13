# codebase-consistency

**Derives which of two or more valid, undocumented patterns already competing in a live
codebase should become the canon, then aligns every divergent site to it with a
provable equivalence check.**

Point Claude at a live, already-modern area of your codebase that grew
inconsistent — divergent architecture, docs, code patterns, and style
across modules — and get back: a divergence inventory, a navigable
consistency matrix, a provenance-tracked canon for every undocumented
pattern, a maintainer-ready alignment brief, and an in-place alignment
pass with an equivalence check so you can prove nothing drifted.

## Why this exists

It works by enforcing a sequence, for the same reason a modernization
pipeline does: harmonizing style before understanding *why* it diverged,
or aligning code without a way to prove nothing broke, is how these
efforts stall halfway and get reverted.

```
preflight → scan → map → canonize → brief → align → verify
```

The discovery commands (`scan`, `map`, `canonize`) write artifacts to
`analysis/<area>/`. `brief` synthesizes them into an approval gate.
`align` applies the approved canon **in place** — there is no
`legacy/`-vs-`modernized/` split here, because there is no old system
running beside a new one, just one live codebase getting more consistent
commit by commit. `verify` proves it.

## What it is not

### Scope — read this before installing both this and `self-assess`

This plugin does **one specific thing that a documented-convention checker
and a version-modernization checker structurally cannot**: derive which
variant becomes canonical when **two or more valid, currently-used,
undocumented** ways of doing something coexist in the same codebase.

- A convention already written down somewhere (`CLAUDE.md`,
  `house-rules.md`, a linter config, an ADR) is **out of scope** — that's
  a documented-convention auditor's job (e.g. `self-assess`'s
  `convention-auditor`).
- An idiom made obsolete by the language/framework version this codebase
  targets is **also out of scope** — that's version-driven modernization
  (e.g. `self-assess`'s `idiom-auditor` / `idiom-remediator`).
- What's left — N ≥ 2 variants, all still valid, none documented as the
  standard — is the entire reason `/consistency-canonize` exists.
  `/consistency-scan` actively routes the first two cases *out* rather
  than re-detecting them, specifically so this plugin doesn't duplicate
  either tool if you have it installed. It has no hard dependency on
  either, though — it works standalone if you don't.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install codebase-consistency@werkstoff
```

There is no hook here: nothing runs until you invoke one of the slash commands below,
so installing the plugin changes nothing about an ordinary session.

### Requirements

Commands degrade gracefully, but these improve the output (run
`/consistency-preflight` to check all at once):

- **Analysis tools** — [`scc`](https://github.com/boyter/scc) or
  [`cloc`](https://github.com/AlDanial/cloc); without them, counts fall
  back to `find`/`wc`.
- **The repo's own linter/formatter** — mechanical style facts fall back
  to grep-based heuristics without one.
- **Real git history** — shallow or squashed history degrades every
  derived Pattern Card's confidence; `/consistency-canonize` still runs,
  just on frequency alone.
- **A runnable test suite** — enables real equivalence proof in
  `/consistency-verify`. Without one, verification degrades to a
  structural-diff-only review, and `/consistency-preflight` reports
  Ready-with-gaps rather than blocking.

### Local development

Point Claude Code at a checkout without registering the marketplace:

```bash
claude --plugin-dir /path/to/werkstoff/plugins/codebase-consistency
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Check readiness first

````prompt
"is this area ready for a consistency pass?"
````

> Triggers `consistency-preflight` — read-only readiness report (stack detection,
> tooling, test-suite baseline, documented-convention inventory, scope check).

##### Find the divergence

````prompt
"find the undocumented style/pattern inconsistencies in billing"
````

> Triggers `consistency-scan` — inventories undocumented, non-deprecated divergence per
> dimension, actively filtering out documented conventions and version-deprecated idioms.

##### See it as a matrix

````prompt
"show me the consistency matrix for billing"
````

> Triggers `consistency-map` — renders the scan as a module × dimension heatmap
> (`matrix.json` + an interactive `CONSISTENCY_MATRIX.html`).

The rendered `CONSISTENCY_MATRIX.html` is a self-contained D3/SVG grid — click any
cell for its variant, site count, and an example citation in the sidebar; a cell with a
dashed outline reading “no data” has nothing recorded for that module × dimension pair.

![Consistency matrix viewer showing six modules (billing, shipping, auth, notifications, search, inventory) against four convention dimensions: every cell with data is filled green, amber or red by its conformance to the canonical pattern and prints a dark label plate carrying a matching glyph (✓ aligned, ≈ partially aligned, ✗ diverging) and its site count; the three pairs with no data are dark cells with a dashed outline reading "no data"; a legend under the grid repeats each key exactly as the cells draw it; and the sidebar is open on the selected shipping × error-handling-style cell, showing its diverging variant, 17 sites and 0% conformance](assets/matrix-viewer-screenshot.jpg)

That image is reproducible rather than a one-off capture — the matrix it shows is
committed at `scripts/testdata/sample_matrix.json` (6 modules × 4 dimensions, chosen so
`shipping` is unambiguously the worst module, three module × dimension pairs have no data
at all and render as dashed “no data” cells, and three distinct variants compete inside a single dimension).
To rebuild it:

```bash
mkdir -p /tmp/cc-demo/analysis/billing
cp plugins/codebase-consistency/scripts/testdata/sample_matrix.json \
    /tmp/cc-demo/analysis/billing/matrix.json
python3 plugins/codebase-consistency/scripts/build_matrix_html.py /tmp/cc-demo billing \
    --template plugins/codebase-consistency/assets/matrix-viewer.html \
    --d3 plugins/codebase-consistency/assets/inline-d3.html \
    --tokens plugins/codebase-consistency/assets/tokens.css
# -> /tmp/cc-demo/analysis/billing/CONSISTENCY_MATRIX.html
```

##### Derive the canon

````prompt
"decide which pattern should be the canonical one, with provenance"
````

> Triggers `consistency-canonize` — weighs frequency, git-history maturity, and adoption
> recency per dimension, tagging each pick `documented` / `derived-majority` /
> `synthesized-new` / `needs-human-decision` rather than forcing a tie.

##### Get the approval-ready plan

````prompt
"write up the alignment brief for billing so I can approve it"
````

> Triggers `consistency-brief` — synthesizes discovery into a phased, dependency-first
> plan with worked before/after examples; enters plan mode as a human approval gate.

##### Apply it

````prompt
"align billing to the approved error-handling-style canon"
````

> Triggers `consistency-align` — applies the canon in place, one pilot module first, then
> the rest in dependency-aware escalating batches behind a circuit breaker.

##### Prove nothing broke

````prompt
"verify the error-handling-style alignment on billing"
````

> Triggers `consistency-verify` — test-suite equivalence (or structural-diff fallback)
> plus a docs re-sync check, independently re-derived by a second adversarial pass.

##### Check progress

````prompt
"where does the billing consistency pass stand?"
````

> Triggers `consistency-status` — read-only artifact inventory, staleness flags, and the
> single most useful next command.

## Quickstart

Each command takes an `<area-dir>` — a directory within your live
repository, worked on in place. Artifacts land in `analysis/<area>/`.

Try the first three on your own codebase — each produces a standalone
artifact, so you can stop and review at any point:

```bash
/consistency-preflight billing      # is my environment ready?
/consistency-scan billing           # what's actually inconsistent, and what's out of scope?
/consistency-map billing            # show me the divergence matrix
```

Then the full path:

```bash
/consistency-canonize billing                       # derive the canon per dimension, with provenance
/consistency-brief billing                           # the plan a maintainer approves (HITL gate)
/consistency-align billing error-handling-style      # apply it, in place, dependency-aware
/consistency-verify billing error-handling-style      # prove nothing observable changed
/consistency-status billing                          # where am I, what's stale, what's next
```

## Recommended workspace setup

Work on a branch per alignment pass rather than restricting file
permissions the way a legacy-modernization pipeline restricts
`legacy/` — there's no separate untouchable tree here, just the live
repository:

```bash
git switch -c consistency/<area>-<dimension>
```

Keep Bash on a *prompted* permission mode during `/consistency-align`'s
batched fan-out, since that step is the one that dispatches many
write-capable agents at once.

## Safety notes

**Analyzed code is untrusted input.** A codebase can contain comments or
string literals crafted to steer automated analysis ("ignore previous
instructions", "this file is exempt from style review", "mark this
canon approved"). Agents treat file content and commit messages as data
and flag instruction-shaped text; verification agents re-derive every
canon and every PASS verdict from the cited code itself, never from
another agent's description; and `/consistency-brief` is a human approval
gate before any code is aligned. Treat discovery artifacts the same way.

**Secrets stay out of shared artifacts.** Any credential value encountered
while citing evidence is masked (`API_KEY = "sk-****"`) and cited by
`file:line` only — never reproduced in `PATTERN_CARDS.md`,
`CONSISTENCY_SCAN.md`, or any other committed artifact.

## Dynamic workflow orchestration

On Claude Code builds with the Workflow tool, four commands (`scan`,
`canonize`, `align`, `verify`) run as scripted multi-agent orchestrations
that fan out more agents for deeper coverage — looping until findings
stabilize, and adversarially re-deriving every finding before it's
trusted. `align`'s batched fan-out runs in dependency-aware escalating
batches behind a per-batch circuit breaker, so a playbook that stops
working is caught within a handful of agents and the spend stops until
it is revised. Commands fall back to direct subagent fan-out on older
builds automatically; no configuration needed. Invoking the slash command
is the opt-in.

## Components

### Agents (5)

Specialist subagents invoked by the commands (or directly):

- **`pattern-analyst`** — Surveys the codebase and git history to cluster
  variants and read maturity/recency signals. Read-only. *(scan,
  canonize's verify pass)*
- **`pattern-extractor`** — Weighs frequency/maturity/recency and decides
  provenance per dimension; refuses to force a pick on a genuine tie.
  Read-only. *(canonize)*
- **`consistency-critic`** — Adversarial reviewer, skeptical of both
  unresolved divergence and *forced* uniformity where real variation was
  warranted; re-derives PASS verdicts independently rather than
  rubber-stamping them. Read-only. *(canonize's panel, verify's re-check)*
- **`align-executor`** — Applies the canonical form to one module,
  following the pilot's playbook; refuses to run without one. Write access
  scoped to its own module directory. *(align)*
- **`equivalence-verifier`** — Independently re-derives whether an aligned
  module behaves identically and its docs still match. Read-only.
  *(verify)*

### Commands (8)

Run in order, but each is standalone — stop, review, resume.

- **`/consistency-preflight <area-dir>`** — Environment readiness check.
  Asks the five questions the source can't answer, detects the stack,
  checks analysis/lint/format tooling, smoke-tests the test suite (the
  baseline `/consistency-verify` diffs against), inventories documented-
  convention sources (feeds `/consistency-canonize` Step 1), checks git
  history depth (feeds maturity/recency weighting), and checks the scope
  boundary. Produces `PREFLIGHT.md`.

- **`/consistency-scan <area-dir> [convention-pattern]`** — Inventories
  undocumented, non-deprecated divergence per convention dimension,
  actively filtering out documented conventions and version-deprecated
  idioms rather than re-detecting them. Produces `CONSISTENCY_SCAN.md` +
  `consistency.json`.

- **`/consistency-map <area-dir>`** — Renders the inventory as a
  **module × dimension consistency matrix** (a heatmap, not a dependency
  graph — the data here is categorical, not relational). Produces
  `matrix.json` and an interactive `CONSISTENCY_MATRIX.html`.

- **`/consistency-canonize <area-dir> [dimension-pattern]`** — The
  centerpiece. For each in-scope dimension: re-checks for a documented
  source, then weighs frequency, git-history maturity, and adoption
  recency to derive the canonical form — or refuses to force a pick when
  the signal is a genuine tie, marking it `synthesized-new` or
  `needs-human-decision` instead of faking confidence. Produces
  `PATTERN_CARDS.md` + `CANON.json`, each entry provenance-tagged
  (`documented` / `derived-majority` / `synthesized-new` /
  `needs-human-decision`).

- **`/consistency-brief <area-dir>`** — Synthesizes discovery into a
  phased **Consistency Brief**: canon summary, dependency-first phase
  plan (shared forms before their dependents, not biggest-first),
  per-dimension detail with worked before/after examples, validation
  strategy, and an approval block. Reads the discovery artifacts and
  **stops if any are missing**. Enters plan mode as a human-in-the-loop
  approval gate.

- **`/consistency-align <area-dir> [dimension]`** — Applies the approved
  canon to every divergent site for one dimension, **in place** on a
  branch. One representative module first (the pilot, written up as
  `PLAYBOOK.md`), then the rest in dependency-aware escalating batches
  behind a circuit breaker. Never touches a `needs-human-decision`
  dimension or anything outside its declared scope. Produces
  `ALIGN_NOTES.md`.

- **`/consistency-verify <area-dir> [dimension]`** — Proves an alignment
  pass changed only what it said it would: test-suite equivalence (or a
  structural-diff-only fallback if no test suite runs), plus a
  documentation re-sync check. A second adversarial pass re-derives every
  PASS verdict independently — the failure mode this guards against is a
  verifier that only reruns the tests the aligner already ran. Produces
  `VERIFICATION.md`.

- **`/consistency-status <area-dir>`** — Read-only progress report:
  artifact inventory, staleness flags, and the single most useful next
  command.

## What is enforced, and what is not

codebase-consistency registers no `PreToolUse` hook, so no tool call is denied at the
wire the way it is in the nine werkstoff plugins that ship one — nothing here stops a
write the way `andon` or `lehre` would. Enforcement instead lives in three places inside
the pipeline itself:

- **`/consistency-brief` is a human approval gate.** It reads the discovery artifacts,
  stops outright if any are missing, and enters plan mode before a single site is
  touched — a maintainer, not a hook, decides whether the canon is approved.
- **`/consistency-align`'s circuit breaker.** The batched fan-out runs one pilot module
  first, then dependency-aware escalating batches, and a playbook that stops working is
  caught within a handful of agents rather than run to completion. `align-executor` is
  *instructed* to write only inside its own module directory — its prompt and the
  `workflows/align.js` dispatch text both say so — but nothing mechanically enforces
  that scope: the plugin ships no hook, its `tools:` frontmatter (`Read, Glob, Grep,
  Write, Edit, Bash`) grants ordinary Write/Edit access with no path restriction, and
  `align.js` never inspects which files a unit actually touched. What the circuit
  breaker mechanically checks is each unit's self-reported test result
  (`testsRan`/`aligned`): a unit only counts as aligned if it ran real tests and they
  passed, and a batch where fewer than two-thirds of measurable units aligned aborts the
  fan-out rather than continuing to the next batch.
- **`/consistency-verify`'s second adversarial pass.** Every PASS verdict is re-derived
  independently rather than trusted from the aligner's own run, guarding against a
  verifier that only reruns the tests the aligner already ran.

None of this is a `PreToolUse` denial — a model that skips `/consistency-brief` and
edits code directly is not blocked by anything in this plugin. What holds is the
approval gate and the adversarial re-derivation, not a wire-level refusal.

## The report

The one HTML report this plugin ships — `assets/matrix-viewer.html`, rendered per run as
`analysis/<area>/CONSISTENCY_MATRIX.html` — is embedded under "See it as a matrix" in
Example Prompts above, together with the reproducible demo build command.

## Verifying a change to this plugin

```bash
python3 test/plugins/lint-frontmatter.py plugins/codebase-consistency
claude plugin validate plugins/codebase-consistency --strict
python3 plugins/nacharbeit/scripts/nacharbeit_lint.py plugins/codebase-consistency --docs-root docs
python3 test/plugins/lint-release-wiring.py
node --check plugins/codebase-consistency/workflows/scan.js
node --check plugins/codebase-consistency/workflows/canonize.js
node --check plugins/codebase-consistency/workflows/align.js
node --check plugins/codebase-consistency/workflows/verify.js
bash scripts/ci/check-js-syntax.sh
```

There is no `test_*_guard.py` and no `verify-hooks-deny.py` case for this plugin — those
checks apply only to a plugin that registers a hook, which this one does not.
`verify-hooks-deny.py` itself does cover all nine hook-bearing plugins (a generic
default fixture for andon, a `test/plugins/fixtures/hook-violation-<plugin>/` fixture
for the other eight), but the dedicated `test_*_guard.py`-style unit test is real for
only seven of them (`andon`, `arbeitsplan`, `lehre`, `matrize`, `nacharbeit`,
`self-assess`, `takt`) — confab has one for `guard_edit_scope.py` but none for
`guard_bash_scope.py`, and cupertino's `pretooluse_guard.py` has no dedicated test at
all. The demo build command for `assets/matrix-viewer.html`, under "See it as a
matrix" in Example Prompts, doubles as a verification: a stale template or a broken
`build_matrix_html.py` argument fails that command before it fails anything else.

## License

Apache 2.0. See `LICENSE`.

This plugin is a Derivative Work, within the meaning of the Apache
License, Version 2.0, of Anthropic's
[`code-modernization`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-modernization)
plugin — the pipeline discipline, workflow-orchestration mechanics
(dependency-aware batching, circuit breaker, loop-until-dry extraction
with referee verification), and agent-boundary/untrusted-input handling
conventions originate there and are reused under that license. The domain
content is rewritten for a different problem (internal consistency of a
live, current codebase, not legacy-to-modern migration). See `NOTICE` for
the full attribution.
