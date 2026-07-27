# andon

Walks a repository's value stream stage-by-stage, proposing fixes for
discovered gaps, proving each wire before advancing via seven
evidence-grounded strategies, and halting rather than passing broken or
unproven handoffs -- the andon rule.

## Install

```bash
cc --plugin-dir /path/to/andon
```

Or copy this directory under a project's `.claude-plugin/` for project-scoped
testing.

## Components

### Skills

| Skill | Purpose |
|---|---|
| `andon-loop` | Orchestrates Phases 0-6: detect topology, init/resume the ledger, scan the cursor's stage for gaps, dispatch propose/verify, enforce the andon rule, advance the cursor, detect convergence. The sole writer to the ledger. |
| `andon-preflight` | Read-only readiness report: stage legibility, ledger writability, house-rules presence, cross-plugin availability. Never creates the ledger. |
| `andon-propose` | Proposes a fix for one gap maximally from the ledger/codebase/house-rules, then grills the user one question at a time only on genuinely load-bearing forks (gated by blast-radius tag). |
| `andon-verify` | Routes a wire to one of seven evidence-grounded strategies via a deterministic classifier, runs the matching reference doc, and returns a structured verdict. Never writes to the ledger. |
| `andon-status` | Read-only board: stream table, cursor, cycle/pass counters, active constraint, open gap counts, evidence-strategy mix, non-overridable holds. |

### Agents (tribunal strategy, dispatched by `andon-verify`)

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

### Hooks

`hooks/hooks.json` registers a `PreToolUse` hook (`hooks/pre_tool_use.py`) on
`Write`/`Edit` that holds regardless of model cooperation:

1. **Disabled-plugin halt** -- refuses any write into the ledger/output
   directory when `.claude/andon.local.md` has `enabled: false`.
2. **Write-scope** -- refuses path traversal, absolute paths, and any target
   outside the declared ledger/output directory, including traversal
   segments embedded inside an otherwise-andon-looking path.
3. **`log.md` append-only** -- refuses a `Write` that would overwrite an
   existing `log.md`, and refuses any `Edit` on it outright.
4. **Gap-closure gating** -- refuses writing a gap doc with `status: closed`
   unless its linked evidence doc has `verdict: green` and is not a Tier 1
   `non_overridable` contradiction (andon rule conditions 1 and 3).

The hook is **inert** in any repository that hasn't started using andon yet
(no `analysis/andon` or configured ledger/output directory present) --
it exits 0 immediately in that case, so it never polices unrelated repos.
It fails **closed** on any internal error (malformed payload, import
failure, unexpected exception), always naming the escape hatch: set
`enabled: false` in `.claude/andon.local.md`, or delete the ledger
directory.

## Settings: `.claude/andon.local.md`

Optional. See `references/okf-ledger-schema.md` for the full field table and
defaults. Every andon skill reads this file first and halts immediately if
`enabled: false` is set -- before running any phase, before touching the
repo.

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

## Design decisions

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

## Testing

```bash
# Enforcement library smoke tests
python3 scripts/andon_core.py load-settings .
python3 scripts/andon_core.py route-wire '{"is_numerical": true}' '{}'
python3 scripts/andon_core.py check-stop-conditions --verdict red --authorization-level local+reversible

# Preflight against this repo (read-only)
python3 scripts/andon_core.py preflight .
```

For the skills/agents themselves, run `andon-preflight` first in a target
repo, then `andon-loop` to start a pass, and `andon-status` at any point to
see the board without advancing anything.
