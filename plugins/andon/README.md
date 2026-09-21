# andon

**Walks a repository's value stream stage-by-stage, proposing fixes for
discovered gaps, proving each wire before advancing via seven
evidence-grounded strategies, and halting rather than passing broken or
unproven handoffs -- the andon rule.**

## Why this exists

Automated "fix loops" have an obvious failure mode: they propose something
that looks right, move on, and the next stage inherits a fix that was never
actually checked. andon borrows the Toyota andon cord — stop the line the
moment a defect is found, rather than pass it downstream — and applies it to
an AI hardening loop: every fix must be proven against its wire's contract by
one of seven evidence-grounded strategies (adversarial tribunal, numerical
V&V, and others) before the loop is allowed to advance to the next stage. A
halt is the intended outcome for an unproven fix, not a bug in the loop.

## What it is not

- **Not for applying a single authorized phase from a `MODERNIZATION_BRIEF.md`.**
  That belongs to `befund` (`befund-transform-execute`) — return to
  `andon-loop`, or straight to `andon-verify`, only for the proof afterward
  (`skills/andon-loop/SKILL.md`).
- **Not for judging whether an existing test suite's assertions would catch a
  mutation.** That is `zeugnis`'s job (`zeugnis:zeugnis-assertion-audit`), not
  `andon-verify`'s (`skills/andon-verify/SKILL.md`).

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install andon@werkstoff
```

The `PreToolUse` hook (see [What is enforced, and what is
not](#what-is-enforced-and-what-is-not)) is inert until a repo already has an
andon ledger directory (`analysis/andon/ledger` by default, or wherever
`ledger_dir` in `.claude/andon.local.md` points it) — the settings file only
relocates or disables the check, it does not by itself activate anything — so
installing andon changes nothing until `andon-loop` actually starts a pass.

### Local development

Point Claude Code at a checkout without registering the marketplace:

```bash
claude --plugin-dir /path/to/werkstoff/plugins/andon
```

Or copy this directory under a project's `.claude-plugin/` for project-scoped
testing.

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Check readiness first

````prompt
"run andon-preflight against this repo"
````

> Triggers `andon-preflight` — read-only readiness report (stage legibility, ledger
> writability, house-rules presence); never creates the ledger.

##### Start hardening

````prompt
"harden this repo, one gap at a time"
````

> Triggers `andon-loop` — detects the value stream, proposes and verifies a fix for
> the current stage's gap, and halts rather than advancing past a broken or
> unproven wire.

##### Check the board

````prompt
"what does the andon board look like right now"
````

> Triggers `andon-status` — read-only: stream table, cursor, pass/cycle counters,
> open gap counts; nothing advances.

Alongside the markdown board, `andon-status` can render the same evidence as a
self-contained HTML report -- see [The board, as an HTML
report](#the-board-as-an-html-report) below.

##### Propose a fix

````prompt
"propose a fix for this gap, only ask where it actually matters"
````

> Triggers `andon-propose` — proposes maximally from the ledger/codebase/house-rules,
> then grills you one question at a time, only on genuinely load-bearing forks.

##### Prove a wire

````prompt
"prove this wire is actually proven"
````

> Triggers `andon-verify` — routes the wire to one of seven evidence-grounded
> strategies and returns a structured green/red verdict.

##### Resume a paused pass

````prompt
"resume the andon ledger from where we left off"
````

> Triggers `andon-loop` — continues an existing ledger's cycle rather than
> starting fresh, still refusing to advance past whatever gap stopped the
> last pass.

Run `andon-preflight` first in any repo — it's read-only and never creates the
ledger — then `andon-loop` to start a pass, and `andon-status` at any point to see
the board without advancing anything.

## The andon rule

Three non-negotiable stop conditions enforced in code
(`check_stop_conditions()` in `scripts/andon_core.py`), explained in full in
`references/andon-rule.md`:

1. A red wire verdict blocks advance until an explicit user re-run or
   override.
2. A proposal's blast radius exceeding the configured authorization level
   blocks advance until the user explicitly confirms.
3. A Tier 1 structural-evidence contradiction is **never** overridable, by
   anyone, under any circumstance -- there is no parameter in the enforcing
   function that can waive it.

## Components

### Skills (5)

| Skill | Purpose |
|---|---|
| `andon-loop` | Orchestrates Phases 0-6: detect topology, init/resume the ledger, scan the cursor's stage for gaps, dispatch propose/verify, enforce the andon rule, advance the cursor, detect convergence. The sole writer to the ledger. |
| `andon-preflight` | Read-only readiness report: stage legibility, ledger writability, house-rules presence, cross-plugin availability. Never creates the ledger. |
| `andon-propose` | Proposes a fix for one gap maximally from the ledger/codebase/house-rules, then grills the user one question at a time only on genuinely load-bearing forks (gated by blast-radius tag). |
| `andon-verify` | Routes a wire to one of seven evidence-grounded strategies via a deterministic classifier, runs the matching reference doc, and returns a structured verdict. Never writes to the ledger. |
| `andon-status` | Read-only board: stream table, cursor, cycle/pass counters, active constraint, open gap counts, evidence-strategy mix, non-overridable holds. |

### Agents (4, tribunal strategy, dispatched by `andon-verify`)

`andon-defender`, `andon-challenger`, `andon-verifier`, `andon-adjudicator` --
see `agents/*.md` for their exact refusal contracts. All four are read-only
except `andon-verifier`, which may execute deterministic checks (tests,
greps) but never modifies the artifact under review.

### Scripts

`scripts/andon_core.py` is the single enforcement library + CLI. Every
mechanical guarantee in the spec is implemented here as a real conditional
that raises/exits non-zero on violation -- settings gating, OKF schema
validation, write-scope enforcement, the three andon-rule stop conditions,
sub-cycle bounds, the wire classifier, the Detection Ladder, the NO-PERSONA
check, and untrusted-content fencing/masking. Skills invoke it as a CLI;
the hook imports it as a library. No third-party dependencies.

`scripts/build_board_html.py` renders the andon board as a self-contained
HTML report -- see [The report](#the-report) below.

## What is enforced, and what is not

### Hooks

`hooks/hooks.json` registers a `PreToolUse` hook (`hooks/andon_enforce.py`) on
`Write`/`Edit` that holds regardless of model cooperation. On every matched
call it:

1. **Checks the escape hatch first** -- if `.claude/andon.local.md` sets
   `enforcement: off` (or `false`/`disabled`), the hook allows unconditionally.
2. **Is inert until a ledger exists** -- if the configured ledger directory
   (`analysis/andon/ledger` by default; `ledger_dir` in the same settings
   file) is not a directory, the hook allows -- so it never polices a repo
   that hasn't started using andon.
3. **Always allows a write targeting the ledger itself** -- the loop must
   always be able to record its own halt.
4. **Otherwise evaluates the andon rule's stop conditions** (`stop_reason()`
   in `hooks/andon_enforce.py`): an open or reopened gap with no
   `blast_radius` value, a `blast_radius` that exceeds the configured
   `authorization_level`, a gap that has reopened `MAX_CONSECUTIVE_REOPENS`
   (3) times, or an evidence doc recording a `red` or `unknown` verdict --
   any of these denies the `Write`/`Edit` outright, regardless of which file
   was targeted.

Gating values are read tolerantly: a frontmatter key first (`status`,
`blast_radius`, ...), then the legacy `tags: ["kind:wire", "status:open"]`
array, then treated as genuinely absent -- a missing value is never inferred,
only surfaced as a stop.

The hook fails **closed** on any internal error (malformed payload, import
failure, unexpected exception), always naming the escape hatch -- see
[Escape hatch](#escape-hatch) below.

## Settings

`.claude/andon.local.md` is optional. See `references/okf-ledger-schema.md`
for the full field table and defaults. Every andon skill reads this file
first and halts immediately if `enabled: false` is set -- before running any
phase, before touching the repo.

## The report

### The board, as an HTML report

`scripts/build_board_html.py` renders the same evidence `andon-status` prints to
the chat as one self-contained HTML file, written to `<ledger_dir>/ANDON_BOARD.html`.

The report answers one question -- *where is the line stopped, and why?* -- and
states its answer in a sentence before any chart appears. Below it, a left-to-right
value-stream diagram carries a labelled edge per handoff: green when linked evidence
says green, amber when verification was attempted and hung, and **dashed when no
evidence doc exists at all**. Those last two are different failures, not degrees of
one, so the edge label spells the state out in words rather than leaving it to
colour. Stage nodes carry a red open-gap badge and open a sidebar listing that
stage's gaps with kind and blast-radius badges.

![andon board for a stopped five-stage feature pipeline: a verdict panel reading "The line is stopped at enrich->score by a Tier 1 structural-evidence contradiction — the one verdict nothing in this loop can override. 3 of 4 handoffs carry no green proof, and 7 gaps are open across 4 of 5 stages"; a red non-overridable-hold banner naming enrich->score; four tiles of which three are outlined in red — 7 open gaps, 3 handoffs without green proof, 1 non-overridable hold — beside an un-outlined 1 cycle converged; and a value-stream diagram of ingest, normalize, enrich, score and publish whose four edges are each labelled in words, ingest->normalize proven green, normalize->enrich verdict hung, enrich->score proven red, score->publish dashed with no evidence yet, with red gap-count badges on the first four stages and none on publish](assets/board-viewer-screenshot.jpg)

That image is reproducible rather than a one-off capture — the ledger it shows is
committed at `scripts/fixtures/sample_ledger/`, a real OKF directory tree
(`log.md` + `stages/` + `gaps/` + `evidence/`) authored in the schema
`render_board()` actually reads: `status`, `kind`, `blast_radius`, `verdict` and
`tier` as first-class frontmatter keys, never buried in a `tags:` array. Its five
stages are wired so that one handoff is proven, one hung, one contradicted by the
structural index at Tier 1, and one never verified at all. To rebuild it:

```bash
python3 plugins/andon/scripts/build_board_html.py \
    plugins/andon/scripts/fixtures sample_ledger \
    --template plugins/andon/assets/board-viewer.html \
    --d3 plugins/andon/assets/inline-d3.html \
    --tokens plugins/andon/assets/tokens.css \
    --out /tmp/andon-demo/ANDON_BOARD.html
```

`scripts/fixtures/sample_ledger/README.md` documents exactly which defect each
stage, gap and evidence doc is there to expose.

## Design decisions

*(spec was silent here)*

The behavioral spec states obligations, not implementations. Where it was
silent on a mechanical detail, these choices were made:

- **Ledger doc parser is hand-rolled, not PyYAML.** andon controls both the
  writer and reader of every OKF doc, so a minimal frontmatter codec
  (`parse_frontmatter`/`dump_frontmatter` in `andon_core.py`) covers the
  constrained subset needed (scalars, bools, ints, flow/block lists) without
  adding a third-party dependency that might not be installed in every
  target repo's Python.
- **NO-PERSONA detection is a denylist + regex heuristic**, not a semantic
  understanding of "appeal to authority." The spec requires this be checked
  in code rather than left to model discipline; a heuristic that catches
  common named-authority patterns (a curated denylist of frequently-invoked
  names, plus a regex for "as/per/according to `<Proper Name>` said/argued")
  is a real, testable check, even though it cannot catch every phrasing.
- **Wire-classifier trigger order** (`e -> b -> f -> g -> d -> c -> a`) is
  the plugin's own choice, reasoned in `skills/andon-verify/references/wire-classifier.md`:
  strongest ground-truth evidence class first (structural index), then
  strategies with no external prerequisite (numerical, property,
  verify-the-verifier), then strategies with a plugin dependency
  (agentic-reliability), then epistemic claims, with tribunal as the
  universal prerequisite-free fallback -- never a starting default.
- **Detection Ladder defect-class taxonomy** (`type-or-schema`,
  `structure-or-lint`, `deterministic-behavior`, `rendered-assertion`,
  `subjective-quality`) is this plugin's own vocabulary mapped 1:1 onto the
  spec's five rungs, since the spec named the rungs but not a defect-class
  enum to key off of.
- **Sub-cycle escalation fires on the 3rd reopen**, matching "reopens 3 or
  more times" literally (`new_count >= SUB_CYCLE_REOPEN_LIMIT` where
  `SUB_CYCLE_REOPEN_LIMIT = 3`) rather than waiting for a 4th.
- **The hook only guards `Write`/`Edit`.** The spec's mechanically-checked
  rules that are inherently semantic (strategy routing correctness, NO-PERSONA
  phrasing, Detection Ladder rung necessity) are enforced by the CLI script
  the skills are instructed to call, not by a blind file-content hook --
  a `PreToolUse` hook can reliably gate *where* a write lands and *whether*
  the ledger's own gating fields are internally consistent, but cannot
  itself judge whether, say, the right verification strategy was chosen.
- **`okf visualize` is treated as an external, optional tool** the plugin
  does not ship or implement -- `andon-status`'s instructions say to attempt
  it best-effort and fall back to the markdown board (which is always
  authoritative) when it's absent, per the spec's own "never fail or delay
  the primary path" requirement.
- **`plugin.json` author is a placeholder** (`andon plugin` /
  `noreply@example.com`) -- update it to the actual maintainer before
  publishing to a marketplace.

## Verifying a change to this plugin

```bash
# Enforcement library smoke tests
python3 scripts/andon_core.py load-settings .
python3 scripts/andon_core.py route-wire '{"is_numerical": true}' '{}'
python3 scripts/andon_core.py check-stop-conditions --verdict red --authorization-level local+reversible

# Preflight against this repo (read-only)
python3 scripts/andon_core.py preflight .
```

## Escape hatch

Set `enforcement: off` (also accepts `false` or `disabled`) in
`.claude/andon.local.md` to disable the `PreToolUse` hook outright --
`hooks/andon_enforce.py` reads it in `settings()` and allows every
`Write`/`Edit` once set.

This is a separate switch from `enabled: false` in the same file: that one is
read by `scripts/andon_core.py`'s `enforce_enabled_or_halt()`, and it is the
**skills** (`andon-loop`, `andon-status`, ...) that read it and halt before
running any phase -- it does nothing to the hook. The hook and the skills
each have their own kill switch, and both live in `.claude/andon.local.md`.

Deleting the ledger directory (`analysis/andon/ledger` by default, or
whatever `ledger_dir` names in that file) also makes the hook inert, since it
allows immediately once the configured ledger directory does not exist.
