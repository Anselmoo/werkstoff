---
name: andon-loop
description: "Runs or resumes an evidence-grounded hardening loop over a repository's value stream (its stages and the wires between them), closing one gap per stage and refusing to advance past a broken or unproven wire. Use when the user wants to harden a repo, run the andon loop, resume the ledger, scan for gaps and fix them in order, or iterate a multi-stage codebase closing gaps while proving each handoff before moving on."
allowed-tools: "Read, Write, Edit, Bash, Glob, Grep, Agent"
argument-hint: "[stage-or-gap-filter]"
---

# andon-loop

Orchestrates Phases 0-6 below over the OKF ledger. This skill is the **sole
writer** to the ledger. `andon-propose` and `andon-verify` only ever return
structured results for you (the orchestrator) to persist -- never call them
expecting them to write files.

Every phase below names the exact `andon_core.py` subcommand that performs
the mechanical check. Treat a non-zero exit code or `"allowed": false` in its
JSON output as a hard stop, not a suggestion: do not re-derive the decision
in prose, and do not proceed past it without the specific explicit-user-input
the phase describes.

`SCRIPTS` below means `${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py`.

## Phase -1: settings gate (every invocation, before anything else)

```
python3 SCRIPTS enforce-enabled <repo_root>
```

If this exits non-zero, the settings file has `enabled: false`. Print the
error message verbatim and **stop** -- do not run Phase 0 or any later phase,
do not read the repo, do not touch the ledger. This is not a soft suggestion;
the script raised, so you halt.

If it succeeds, its JSON `settings` object gives you `output_dir`,
`ledger_dir`, `authorization_level`, `skip_verification`, `gap_source`, and
`self_assess_output_dir` for every phase below (defaults documented in
`${CLAUDE_PLUGIN_ROOT}/references/okf-ledger-schema.md` apply when the
settings file is absent -- the script already applied them, just use the
returned values).

## Phase 0: topology detection

If `gap_source` is `self-assess-brief` (ingest mode), **skip all heuristic
steps below** and check the prerequisite in code first:

```
python3 SCRIPTS check-ingest-prereqs <repo_root> <gap_source> <self_assess_output_dir>
```

If this exits non-zero, `MODERNIZATION_BRIEF.md` or `transform_brief_summary.json`
is missing from `self_assess_output_dir`. **Stop** and tell the user to run
`self-assess:self-assess-transform-brief` first -- never silently fall back to
self-scan; that silent fallback is exactly the failure mode this check exists
to prevent. If it succeeds, take the stream from the brief's phases (already
leaf-first / Kahn-sorted) with confidence `self-assess-backed`, and go straight
to Phase 1 using those stages.

Otherwise (`gap_source: self-scan`, the default), detect stages and wires:

1. Prefer dispatching the `self-assess:stage-mapper` agent if the `self-assess`
   plugin is installed. Confidence: `self-assess-backed`.
2. If unavailable, degrade to a built-in heuristic: `Glob` for manifest files
   (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, ...)
   and cluster by directory. Confidence: `heuristic` (flag this in the stage
   docs you write in Phase 1 -- the `confidence` field is a required,
   first-class key on every stage doc, never a prose caveat).
3. A repo with exactly one package is valid as a single stage with no
   inter-stage wire. Confidence: `single-package`.
4. If the user declared an explicit stream (stage list) in their request,
   that overrides detection entirely.

## Phase 1: ledger init or resume

```
python3 SCRIPTS init-or-resume <repo_root> <ledger_dir>
```

If `resumed: false`, this already created `ledger_dir/{stages,gaps,evidence}`
and an empty `log.md`. Immediately write one `type: stage` doc per detected
stage using `write-doc` (below) -- `order` and `confidence` are required
fields, not optional metadata.

If `resumed: true`, its JSON gives you `stages`, `gaps`, `evidence`, and a
reconstructed `cursor` -- derived from the first `status:open` gap doc in
stage order, or `{"state": "converged, no open gaps"}`. **Never guess the
cursor yourself**; this script's reconstruction is the only source of truth
(`ledger-cursor-reconstruction-from-gaps`).

To write any OKF doc (stage, gap, or evidence), always go through:

```
python3 SCRIPTS write-doc <repo_root> <ledger_dir> <relative_path> '<fields_json>' [--body TEXT]
```

`<relative_path>` is relative to `<ledger_dir>` itself, e.g. `stages/s1.md`,
`gaps/g1.md`, `evidence/ev1.md` -- the script joins it onto `ledger_dir`
before validating, matching the on-disk layout
`ledger_dir/{stages,gaps,evidence}/*.md`.

This validates write-scope (rejects traversal/absolute/outside-ledger paths)
and the OKF schema (rejects a doc missing a gating field) **before** touching
disk. If it exits non-zero, the doc was not written -- fix the fields, don't
retry with a workaround.

## Phase 2: scan the cursor's stage for gaps

Scan **only** the cursor's current stage -- never re-scan completed stages
every pass. In self-scan mode look for: failing tests, wires with no
evidence doc or a red/unknown one, TODOs, schema drift, dead handoffs. In
ingest mode, gaps come from the brief's Work Items for this phase instead
(pre-classified: code-idiom/lint/ui-audit/confab findings become `kind:bug`,
architectural Merge/Split/layering decisions become `kind:wire`,
documented-absent behavior becomes `kind:feature`; carry `file:line` and the
fix-owner agent name into the gap doc; the phase's Behavior Contract becomes
the wire's verification contract; Advisory notes go on the stage doc's body,
never converted into auto-fixable gaps).

Classify each gap with exactly one `kind` (`bug`, `feature`, or `wire`) and
write it with `status: open` via `write-doc`. `select-next-gap` enforces
priority when more than one gap is found:

```
python3 SCRIPTS select-next-gap '<json array of {kind, on_constraint, blast_radius, slug}>'
```

Priority is fixed in code: `on_constraint:true` first, then wire before bug
before feature, then smallest blast radius as tiebreak. Do not eyeball a
"more important-looking" gap instead.

## Phase 3: propose

Dispatch the `andon-propose` skill with the selected gap, the stage doc, and
any linked gap/evidence docs. It returns a proposal (fix description, files
touched, chosen `andon-verify` strategy + rationale, and **exactly one**
blast-radius tag). Record the proposal onto the gap doc via `write-doc`
(this re-validates the blast-radius tag as part of schema validation -- a
proposal with zero, two, or an undefined tag is rejected, not coerced).

**Stop condition 2 check**, before doing anything else with this proposal:

```
python3 SCRIPTS check-stop-conditions --verdict unknown \
  --blast-radius <tag> --authorization-level <settings.authorization_level>
```

If this exits non-zero, the blast radius exceeds the configured
authorization level. Halt and ask the user to either explicitly confirm
raising authorization (`--confirm-authorization-raise` on the recheck) or
explicitly skip this gap. Do not apply the fix in the meantime.

## Phase 4: verify

Dispatch the `andon-verify` skill with the wire, its contract, and the
proposed fix. It returns a verdict (`green`/`red`/`unknown`) plus evidence
content -- **you** persist it via `write-doc` into `evidence/`, never
`andon-verify` itself.

Run the full stop-condition check now that you have a real verdict and tier:

```
python3 SCRIPTS check-stop-conditions --verdict <verdict> \
  --blast-radius <tag> --authorization-level <settings.authorization_level> \
  [--tier <1|2|3>] [--non-overridable]
```

- Non-zero + `condition_1_red_verdict`: halt. Do not advance past this wire.
  It may only advance later on an explicit user re-run with new evidence, or
  an explicit user override/defer of the gap.
- Non-zero + `condition_3_tier1_non_overridable`: halt, **permanently, for
  this evidence**. There is no flag on this script that waives it, by
  construction -- do not attempt to route around it by re-running with
  different arguments or asking the adjudicator to reconsider.
- Success: close the gap (`status: closed`, `resolved_by: [[evidence/<slug>]]`)
  via `write-doc`.

**Sub-cycle backtracking**: if the fix touched a contract an upstream wire
depends on,

```
python3 SCRIPTS track-subcycle <repo_root> <ledger_dir> <wire_id> <requested_upstream_depth>
```

`effective_upstream_depth` is clamped to at most 2 stages back, regardless of
what you requested -- never re-verify further upstream than that. If
`escalate: true` (this wire has now reopened 3+ times), **stop sub-cycling
it**: record the escalation as the active constraint in `log.md` instead of
looping again. Every sub-cycle attempt gets its own `log.md` entry
(`append-log ... sub-cycle ...`), win or lose.

## Phase 5: advance cursor, log the pass

```
python3 SCRIPTS append-log <repo_root> <ledger_dir> pass '<fields_json>'
```

Required fields: `stage`, `wire`, `gap`, `strategy`, `verdict`, `next_cursor`,
`cycle`, `pass_number`. This appends -- it never rewrites `log.md`; the hook
in `hooks/` will independently refuse a `Write` that would overwrite an
existing `log.md`, so there is no path to "fixing" a bad entry by rewriting
the file. Advance the cursor to the next stage; wrap to the first stage past
the last one.

## Phase 6: convergence check

At each pass boundary (cursor wraps to the first stage):

```
python3 SCRIPTS check-convergence <gaps_closed_this_pass> '<json array of wire statuses>'
```

Only when `converged: true` (zero gaps closed this pass AND every inter-stage
wire is green) do you declare "Cycle N converged" and append a
`cycle-converged` log entry (`passes`, `cycle` fields required). Otherwise,
start the next pass in the same cycle.

## Reference

See `${CLAUDE_PLUGIN_ROOT}/references/okf-ledger-schema.md` for the doc schema
and settings defaults, and `${CLAUDE_PLUGIN_ROOT}/references/andon-rule.md`
for the three stop conditions in full. Do not duplicate that content here --
read it when a decision needs it.
