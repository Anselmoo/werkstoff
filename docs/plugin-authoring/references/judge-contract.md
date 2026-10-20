# One LLM-as-judge contract for every plugin

Issue #119. Every werkstoff plugin that asks a model whether something holds, whether a
finding is real, a rule is grounded, a candidate meets its criteria or a wire is proven,
follows one contract, **verdict@1**. The model reports evidence and code decides. This
page gives the rationale, explains how to adopt and calibrate a judge, and maps every
judge in the twelve plugins onto the contract.

The canonical files are in `tools/judge-contract/`:

| file | what it is | how a plugin gets it |
|---|---|---|
| `judge_contract.py` | `decide()`, `validate()`, `spot_check()`, `check_rubric()`, a CLI, and `--selftest` | copied byte for byte into `plugins/<p>/scripts/` |
| `verdict.inline.js` | the block between `// judge-contract:start verdict@1` and `// judge-contract:end`: `JUDGE_VERDICT_SCHEMA`, `decideVerdict()`, `spotCheck()` | pasted verbatim into a Workflow script |
| `verdict.schema.json` | JSON Schema (draft 2020-12) for the **decided** verdict | referenced, not vendored |
| `judge-contract.md` | the plugin-neutral contract text | copied into `plugins/<p>/references/` and cited from a SKILL |
| `test_parity.py` | holds the JS block and the Python module to identical verdicts, and sabotages both | run in CI |

`scripts/ci/check_judge_contract.py` keeps every copy byte-identical. It also fails when a
workflow on its `REQUIRED_WORKFLOWS` list carries no block, so a judge workflow cannot leave
the contract by deleting its marker.

## The five points

1. **A command decides first.** An exit code, a parser, a test or a probe answers whatever
   it can. No model judges where a command can decide.
2. **Otherwise, one judge call per item.** Each item is judged against a named rubric
   (`<plugin>-<name>@<int>`) whose criteria are listed in that plugin's references. The
   judge gives each criterion a score from 0.0 to 1.0, a pass flag and evidence. The rubric
   states its threshold, and every plugin uses the same strict JSON schema.
3. **Calibrated.** Each rubric has known-answer cases. A judge is trusted only once it
   clears its floor on a sealed set, and its agreement is reported.
4. **Human spot checks.** Every run shows the user a deterministic sample of its verdicts.
5. **Existing tribunals and panels are mapped.** Each one either moves onto the contract
   or is kept with a recorded reason, and that reason is never invented. See the
   [mapping](#every-judge-in-every-plugin).

## What the sources say, and what they do not

Two Anthropic sources were checked before this was written. They are quoted only where the
wording matters.

- **Anthropic engineering, *How we built our multi-agent research system*.** It reports
  that one LLM call with one prompt, producing 0.0–1.0 scores and a pass or fail grade,
  was "the most consistent and aligned with human judgements". **Scope:** that finding
  comes from an **evaluation harness** run over test cases, and the article notes the
  approach was "especially effective when the eval test cases did have a clear answer". It
  compares judge designs for grading eval outputs. It does not compare a single judge with
  a multi-agent tribunal that runs **inside a pipeline** over open-ended items. The same
  article says "Even in a world of automated evaluations, manual testing remains
  essential", which is the basis for point 4.
- **Claude, *Building agents with the Claude Agent SDK*.** It says "Code linting is an
  excellent form of rules-based feedback", and it calls an LLM judge "generally not a very
  robust method, and can have heavy latency tradeoffs". That is the basis for point 1.

**What this justifies.** The single-judge shape is the default for **new** judges, and
the passung and befund panels can be collapsed (the user's decision for this pass). It
does **not** show that the tribunals kept below are worse. They are marked
**unmeasured**, not wrong, and each row names the paired measurement that would settle
it.

## A command decides first

The evidence for point 1 comes from this repo, not from the sources above. CLAUDE.md
measured how often a rule actually runs, across about 40 runs:

| layer | invocation |
|---|---|
| prose in a SKILL.md | baseline |
| a fenced `python3 ...` command in a skill | 1 run in 3 |
| a guard inside the Workflow script | workflow dispatched 1 run in 14 |
| **PreToolUse hook, `type: "command"`** | **blocks, first attempt** |

A judge is the weakest kind of check: it is probabilistic, it can be persuaded, and it is
slow. When a command can decide, use the command, and record its result as a verdict with
`decidedBy: "command"`. Each criterion the command checked scores `1.0` with
`pass: true`, or `0.0` with `pass: false`, and its evidence is the command and its output.
The command's verdict goes through the same `decide()` as a judge's, so a malformed
command report abstains rather than passing.

## The contract, in brief

The full text is in `tools/judge-contract/judge-contract.md`. The parts that matter for
implementation:

- **The judge returns** `{item, criteria: [{id, score, pass, evidence}], abstain,
  abstainReason}` and nothing else. Code derives the rest.
- **`decide()` / `decideVerdict()`** return `{item, rubric, decidedBy, criteria, abstain,
  abstainReason, threshold, score, outcome, calibrated}`:
  - `outcome` is `"abstain"` if the report is missing, null or not an object, names no
    item or a different one, has a non-boolean or true `abstain`, has any rubric
    criterion missing, duplicated or unknown, has any score that is not a number in
    [0, 1] (a boolean is not a number, even though Python says `True` is an `int`), has
    any `pass` that is not a boolean, or has empty evidence.
  - Otherwise `"fail"` if any `pass` is false or the **minimum** score is below the
    threshold.
  - Otherwise `"pass"`.
- **An abstain is never a pass.** `score` is the minimum and never an average. On an
  abstain, `score` is 0 and `criteria` is empty.
- **`abstainReason`** is either a fixed code (`verdict-missing`, `missing-item`,
  `item-mismatch`, `malformed:abstain`, `malformed:criteria`, `malformed-criterion:<i>`,
  `duplicate-criterion:<id>`, `unknown-criterion:<id>`, `bad-score:<id>`, `bad-pass:<id>`,
  `bad-evidence:<id>`, `missing-criterion:<id>`) or `judge:<text>`. Python and JS emit the
  same string.
- **`calibrated`** is derived from the rubric's `calibration: {sealed, agreement, floor}`
  record and is true only when `sealed > 0` and `agreement >= floor`. A bare
  `"calibrated": true` on a rubric is ignored. No rubric has a record yet, so every
  verdict today carries `calibrated: false`.
- **A malformed rubric throws.** It is an author's bug and must not hide inside an
  abstain.
- **`spotCheck(verdicts, k = 3)` / `spot_check()`** sorts by item id (stable sort) and
  takes the first, the middle and the last, at index `floor(i·(n−1)/(k−1))`. It never
  uses `Math.random` or `Date.now`, which a workflow cannot call anyway. (Python sorts by
  code point and JS by UTF-16 unit, so the two orders differ only for item ids containing
  characters outside the Basic Multilingual Plane.)

## Adopting it

### In a Workflow script

1. Paste the whole block from `tools/judge-contract/verdict.inline.js` at column 0,
   from `// judge-contract:start verdict@1` to `// judge-contract:end`. Put it **above
   the first line that uses any of its three names**. A `const` read before its
   declaration throws a `ReferenceError`, and that includes reads inside the `schema` of
   an `agent()` call placed above the block.
2. Define the rubric next to it, and keep the same rubric in the plugin's references:

   ```js
   const RUBRIC = {
     id: 'passung-provenance@1',
     threshold: 0.7,
     criteria: [
       { id: 'basis-supports-winner', question: 'Does the cited basis actually show this variant winning?' },
       { id: 'form-faithful', question: 'Is the stated canonical form what the code actually does?' },
     ],
   }
   const raw = await parallel(cards.map((c) => () =>
     agent(`<prompt naming every rubric criterion id and question>`, { schema: JUDGE_VERDICT_SCHEMA, label: `judge:${c.id}` })))
   const verdicts = cards.map((c, i) => decideVerdict(raw[i], RUBRIC, { item: c.id }))
   // gate on verdict.outcome === 'pass'; report 'abstain' separately from 'fail'
   return { /* ... */ verdicts, spotCheck: spotCheck(verdicts, 3) }
   ```

3. Add the file to `REQUIRED_WORKFLOWS` in `scripts/ci/check_judge_contract.py`.
4. The calling SKILL.md shows `spotCheck` to the user every run, with each verdict's
   evidence and outcome and its `calibrated` label.

A failed `agent()` returns `null`, and `decideVerdict(null, ...)` abstains with
`verdict-missing`. Do not filter out nulls before deciding, because that would drop the
abstain the user needs to see. Under biome's `noUnusedVariables`, which every plugin
except passung, cupertino and nacharbeit enforces, a vendored block whose `spotCheck` is
never called fails lint.

### In a script

Copy `tools/judge-contract/judge_contract.py` into `plugins/<p>/scripts/` (or
`scripts/lib/`) byte for byte and import `decide`, `validate` and `spot_check`. Add the
path to `VENDORED_PY` in `scripts/ci/check_judge_contract.py`, although the check also
finds any `judge_contract.py` under `plugins/*/scripts/` by glob. The vendored copy runs
on the 3.11 hook floor and uses only the standard library.

### In a skill

Copy `tools/judge-contract/judge-contract.md` into `plugins/<p>/references/` byte for byte
(`JC-MD-DRIFT` checks it) and cite it from the SKILL.md that runs the judge, because
`M-REF-UNWIRED` fails a reference that no SKILL names. The text names no plugin and holds
no relative links, so every copy is identical. List the plugin's own rubric ids and
criteria in a separate reference that cites the vendored contract.

## Calibrating a judge

Follow nacharbeit, the only plugin that calibrates a judge today.

- **The split.** `plugins/nacharbeit/scripts/build_args.py` (`build_fixtures`) sorts
  fixture directories into a tuning set and a sealed set. A directory whose name starts
  with `sealed` is held out. The script refuses to run without at least one of each, and
  refuses any batch kind that lacks a tuning and sealed pair, because "a finder cannot
  grade what it was never calibrated on".
- **The loop.** `plugins/nacharbeit/workflows/review.js` (Loop A, "Calibrate") runs the
  finder over the tuning fixtures. If recall is below `RECALL_TARGET` (0.8), or the
  per-angle or per-family minimum is below 0.6, opus rewrites the finder prompt from the
  misses and the false positives on clean files, for up to `MAX_CAL_ROUNDS` (3) rounds.
  The prompt is then frozen (`const FINDER = finderPrompt`) and measured **once** on the
  sealed set. Below `SEALED_FLOOR` (0.7) overall, or `FAMILY_SEALED_FLOOR` (0.6) for any
  family, the workflow throws and grades nothing real.

[`judge-calibration.md`](judge-calibration.md) does this for three kept judges, and its
scorer (`tools/judge-calibration/calibration.py`) is the one to reuse.

Applied to a judge rubric, each known-answer case is an item, its expected outcome
(`pass`/`fail`) and the evidence that settles it. Tune the prompt on the tuning cases,
freeze it, then run the sealed cases once. Agreement is the fraction of sealed cases where
the outcome matched. Record `calibration: {sealed, agreement, floor}` on the rubric. An
abstain on a known-answer case counts as a disagreement, never as excused.

nacharbeit's pattern has **two known gaps**. Do not copy them:

1. **Only the finder is calibrated.** The refuter, the fix-impact lens, the collision
   judge, the completeness critic, synthesis and the fix-verifier all run uncalibrated,
   and the refuter is the kill switch for every finding.
2. **The sealed set measures recall, not precision.** False positives on clean files are
   counted in the tuning rounds only. The sealed measurement checks how many planted
   defects were found, so a finder that flags everything clears it. Report false passes
   and false fails separately on the sealed set, as `judge-contract.md` §4 requires.

## Every judge in every plugin

Status vocabulary:

- **conforms**: a command decides, or the judge already has the contract's shape.
- **collapsed**: replaced by one contract judge in this change.
- **fixed**: a fail-open default closed in this change.
- **kept-unmeasured**: kept as it is, with `resolves_if` naming the paired measurement
  that would justify it or retire it. No row with this status claims a measured reason.
- **kept-calibrated**: kept as it is, and measured once on a sealed known-answer set whose
  record clears its floor (`is_calibrated()` is true). It is calibrated against known
  answers. It is not yet compared with a single contract judge, so the paired measurement
  in `resolves_if` is still open. See
  [`judge-calibration.md`](judge-calibration.md).

### Andon and arbeitsplan

| plugin | judge (where) | shape today | status | resolves_if / note |
|---|---|---|---|---|
| andon | tribunal: defender, challenger, verifier, adjudicator (`skills/andon-verify/references/tribunal-protocol.md`; `agents/andon-adjudicator.md`) | per-criterion `pass`/`fail`/`neither` → wire `green`/`red`/`unknown`, with "not an average" stated outright | **kept-calibrated** | measured: sealed 8 (3 green, 3 red, 2 unknown, the reds being the `contested-wire-halts` repairs `verify-contested-fixture.py` proves cannot work), agreement 1.0 against floor 0.8, 0 false passes. It ran on the session's model (opus), because the andon agents declare none, and n=8 bounds a perfect score only at 0.63 (95%). The paired run against a single contract judge is designed in [`judge-calibration.md`](judge-calibration.md#the-paired-measurement-designed-not-run) and not run. Maps closely: `neither` = abstain on that criterion, `red` if any fails = min-not-average. Step 3's detection ladder in `andon-verify` already climbs only as far as the defect class needs, which is "a command decides first" in andon's terms |
| andon | epistemic rubric, strategy (c) (`skills/andon-verify/references/epistemic-rubric.md`) | five criteria (falsifiability, generalization, evidence-grounding, honesty-of-framing, accessibility), each pass/fail/neither, "do not average" | kept-unmeasured | the same paired run on falsifiability-rubric wires. The closest existing match to verdict@1: five named criteria and no averaging. Only the 0–1 score and the fixed threshold are missing |
| arbeitsplan | candidate-referee (`workflows/run.js` `REFEREE_SCHEMA`, `agents/candidate-referee.md`) | blind, one candidate per call; `accepted`/`accepted_different_approach`/`rejected`/`cannot_judge` with required `perCriterion[{id, met, evidence}]` | **kept-calibrated** | measured with the `run.js` prompt itself: sealed 10 (4 pass, 4 fail, 2 abstain), agreement 1.0 against floor 0.8, 0 false passes and 0 false fails (sonnet). The 95% bound on a perfect 10/10 is only 0.69. Still not migrated (no 0–1 scores, threshold in effect 1.0). Found: `withEvidence` lands an `accepted` with **one** met criterion, which is weaker than the agent's own "every criterion met". The case probing it did not trigger it, but the gap is reachable. See [`judge-calibration.md`](judge-calibration.md#findings-about-the-judges) |
| arbeitsplan | waves blind referee (`workflows/waves.js` `REFEREE_SCHEMA`, ~line 69; separate from the `run.js` referee) | blind, branch names only; the referee runs every acceptance command in its own worktree and returns `winner` (a branch or `null`) plus `perCandidate[{branch, allPassed, failing}]`. A `null` winner halts the row with "NO CANDIDATE ACCEPTED" | kept-unmeasured | maps partly: `allPassed` = pass, and a `null` winner is a fail. The schema has no per-criterion `score` or `evidence`, no abstain (a dead referee and "no branch passed" both end in the same halt) and no calibration, and the winner is a first-in-list tie-break rather than a threshold. A command decides in principle (the exit codes), so the referee only reports them. Settled by a sealed set of candidate pairs with known acceptance, measuring whether the referee ever reports a different winner than the exit codes alone |
| arbeitsplan | adjudicator (`agents/adjudicator.md`) | judges the round, not an item; may not overturn a referee and records disagreement as doubt | kept-unmeasured | a paired measurement of rounds adjudicated against rounds decided by `scripts/rounds.py decide` alone. It does not fit per-item verdict@1 by design |
| arbeitsplan | script phases (`workflows/run.js`, `sc.expectExit`) | the exit code must be in `expectExit`, or the run halts | conforms | the command decides |

### Befund and cli-scaffold

| plugin | judge (where) | shape today | status | resolves_if / note |
|---|---|---|---|---|
| befund | P0 two-judge panel (`skills/befund-extract-rules/SKILL.md` Step 3; `scripts/lib/p0_panel.py`) | two judges, each `confirms: bool`, and both must confirm | **collapsed** | one contract judge per P0 rule (rubric `befund-p0-rule@1`), decided through the vendored `scripts/lib/judge_contract.py`. `JC-PY-DRIFT` holds the copy byte-identical, but byte identity does not show the copy is **called**. Proof: `p0_panel.py` and Step 3 of the SKILL call `decide()`, and `validate-artifact` accepts a P0 rule only with a stored decided verdict whose `outcome` is `pass` |
| befund | docs-drift auditor (`agents/docs-drift-auditor.md`) | per claim `confirmed`/`contradicted`/`unverifiable` | kept-unmeasured | maps: `unverifiable` = abstain. Settled by a sealed set of documented claims with known truth, measured as a single judge against the current auditor |
| befund | stage-map wire verification and code-idiom finding verification (`skills/befund-stage-map/SKILL.md`, `skills/befund-code-idiom/SKILL.md`) | re-read and refute each candidate, skipped when `skip_verification` is set | kept-unmeasured | a sealed set of known wires and idioms, with recall and precision measured separately |
| cli-scaffold | `scripts/verify_scaffold.py` | exit code | conforms | the command decides |

### Cupertino and lehre

| plugin | judge (where) | shape today | status | resolves_if / note |
|---|---|---|---|---|
| cupertino | handbook-check, handbook-fix and handbook-draft verifiers (`workflows/handbook-*.js`) | blind, one per item; `confirmed`/`false_positive` | kept-unmeasured | a sealed set of planted handbook violations, with a single contract judge compared against the current verifier |
| cupertino | `isConfirmed` in `workflows/handbook-fix.js` | `!f.verification \|\| verdict === "confirmed"`, which treats an unverified finding as confirmed (fail-open) | **fixed** | an unverified finding is not confirmed. Proof: `grep -c 'isConfirmed = (f) => !f.verification' plugins/cupertino/workflows/handbook-fix.js` prints 0 |
| lehre | ruleset `check.kind` (`references/ruleset-schema.md`) | closed vocabulary; `enforcement` is derived from it and never hand-written | conforms | command first: only `check.kind: "judgement"` reaches a model |
| lehre | violation-verifier (`agents/violation-verifier.md`) | `CONFIRMED`/`FALSE POSITIVE`/`INCONCLUSIVE` | kept-unmeasured | maps: `INCONCLUSIVE` = abstain. Settled by a sealed set from `test/plugins/fixtures/lehre-*` with known violations |
| lehre | rule-critic, decomposition-critic, spec-fidelity-auditor (`agents/*.md`) | adversarial review of a whole ruleset, a whole decomposition, or one unit against its intent | kept-unmeasured | per-item known-answer sets (planted forced-consistency rules, invented edges, unmet intents) |

### Matrize and nacharbeit

| plugin | judge (where) | shape today | status | resolves_if / note |
|---|---|---|---|---|
| matrize | decode-referee (`workflows/decode.js`, `agents/decode-referee.md`) | blind re-derivation per card: `reproduced`/`reproduced_different_relation`/`not_reproduced`/`cannot_reproduce`; only `reproduced` is accepted | **kept-calibrated** | measured with the `decode.js` prompt itself: sealed 10 (4 reproduced, 2 different-relation, 2 not-reproduced, 2 cannot-reproduce), agreement 1.0 against floor 0.8, all 10 native verdicts exact (sonnet). The 95% bound on a perfect 10/10 is only 0.69. `decode.js` still hard-codes `calibrated: false`, because a workflow cannot read the record. See [`judge-calibration.md`](judge-calibration.md) |
| matrize | design-critic (`agents/design-critic.md`) | judges a **set** of cards or lexicon entries per call, giving a verdict for each | kept-unmeasured | a paired run of one call per entry against one call per set on a sealed set of copies and honest defaults. Its prompt already says "Judge each entry on its own evidence" |
| matrize | fact-checker (`agents/fact-checker.md`) | resolves the named thing itself (package, URL, expiry) | conforms | the command or probe decides |
| nacharbeit | finder (`workflows/review.js` Loop A) | tuned, then a sealed hold-out measured once with recall floors | conforms | **the only calibrated judge in the repo**: a tuning set and a sealed set with a floor. Its two gaps are described above |
| nacharbeit | refuter, fix-impact lens, collision judge, completeness critic, synthesis (`workflows/review.js`); fix-verifier (`agents/fix-verifier.md`, `workflows/fix.js`) | uncalibrated. The refuter batches findings: one call per file with three or more findings, smaller files pooled into groups of about six (`groupForVerify`), so it is not one call per item | kept-unmeasured | a sealed known-answer set per role. For the refuter, a paired run of one finding per call against today's batching |
| nacharbeit | mechanical rules (`scripts/nacharbeit_lint.py`) | sabotage-tested linter | conforms | the command decides |

### Passung, takt and zeugnis

| plugin | judge (where) | shape today | status | resolves_if / note |
|---|---|---|---|---|
| passung | scan referee (`workflows/scan.js`, Verify phase) | one referee per dimension card: is this divergence genuinely in scope | kept-unmeasured | a sealed set of dimension cards with known in- or out-of-scope answers |
| passung | canonize referee (`workflows/canonize.js`) | per-candidate maturity and recency re-derivation | kept-unmeasured | a sealed set of candidates with known canon |
| passung | canonize two-judge provenance panel (`workflows/canonize.js`) | two judges per derived-majority card; a split or a fidelity doubt becomes an open question | **collapsed** | one contract judge per card (rubric `passung-provenance@1`). Standing proof: `canonize.js` is on `REQUIRED_WORKFLOWS`, so `JC-REQUIRED` fails if the block is removed, and `JC-DRIFT` and `JC-SHADOW` fail if the block is edited or its names are rebound |
| passung | verify.js PASS re-check (`workflows/verify.js`, Re-check phase) | a second agent re-derives every PASS, **non-blind**: it is shown the first verifier's verdict, reason and test result | **collapsed** | one contract judge per module (rubric `passung-equivalence@1`). Standing proof: `verify.js` is on `REQUIRED_WORKFLOWS`, so `JC-REQUIRED` fails if the block is removed, and `JC-DRIFT` and `JC-SHADOW` fail if the block is edited or its names are rebound. The judge is now **blind** (it is not shown the first verifier's verdict) and carries the criterion `no-behavior-change` in `passung-equivalence@1` (threshold unchanged, 0.7). Its outcome maps to the module verdict as `pass` → `PASS`; a `fail` where `no-behavior-change` failed → `FAIL`; any other `fail`, an `abstain` or a dead judge → `PASS-WITH-GAPS` |
| takt | none | the PreToolUse hook decides | conforms | no model judges |
| zeugnis | reconcile default (`scripts/{assertion_audit,contract_drift,agentic_reliability}.py`) | read `f.get("confirmed", True)`, so a verify finding missing the key counted as confirmed (fail-open) | **fixed** | proof: `grep -c 'confirmed", True' plugins/zeugnis/scripts/{assertion_audit,contract_drift,agentic_reliability}.py` prints 0 for each file |
| zeugnis | Find→Verify (`skills/zeugnis-*`, the same agent finds and verifies) | the finder confirms its own findings | kept-unmeasured | a paired run of the same agent against a blind verifier on a sealed set of planted assertion and contract defects |

### Zirkel

| plugin | judge (where) | shape today | status | resolves_if / note |
|---|---|---|---|---|
| zirkel | explore-branches scorer (`workflows/explore-branches.js`) | integer 1–10 per axis (feasibility, impact, risk), one branch per call | kept-unmeasured | a paired run of 1–10 scores against 0–1 contract scores on known-better branch pairs |
| zirkel | optimize-instruction (`workflows/optimize-instruction.js`: Score phase, then Critique) | the Score phase has one agent per candidate report an integer `passed` against the fixed test cases, and the highest count wins (framing order breaks ties). The Critique phase then applies a checklist to the winner alone. The same agent type generates the candidates and scores them | kept-unmeasured | a paired run of the agent's own count against a command or a separate blind judge on candidates with known pass counts, and of the critique against a held-out test case set. There is no per-case evidence, no abstain and no threshold, and a candidate that cannot be scored is silently dropped by `.filter(Boolean)` before the count check |
| zirkel | solve.js Revise (`workflows/solve.js`) | integer 1–5 per criterion, and the same call revises the draft it scored, so it **judges its own work** | kept-unmeasured | a paired run of self-scoring against a separate contract judge on drafts with known defects |
| zirkel | reason-verify (`workflows/reason-verify.js`) | three isolated attempts, majority vote | kept-unmeasured | self-consistency is a reasoning method rather than a judge of an item. A paired measurement of majority against single-attempt accuracy on questions with known answers would settle whether it earns its 3× cost |

## Verifying the instrument

```bash
python3 tools/judge-contract/judge_contract.py --selftest   # planted cases, one per decide() branch
python3 tools/judge-contract/test_parity.py                 # JS == Python, then sabotage: each branch blanked must go red
python3 scripts/ci/check_judge_contract.py --selftest       # planted drift, missing marker, double block, required, copies
python3 scripts/ci/check_judge_contract.py                  # the gate over the real tree
```

`test_parity.py` runs its own sabotage every time:

- It flips `<` to `<=` in the threshold comparison on each side. That flip shows up only
  because the case set includes a score exactly at threshold.
- It blanks several JS branches.
- It blanks each of `decide()`'s branches on a scratch copy and requires `--selftest` to
  go red.
- A sabotage whose target text is not found exactly once exits 2 rather than reporting a
  pass.

## Not done in this change

- **Sealed calibration sets for the other kept judges.** The candidate-referee, the
  decode-referee and the tribunal now have sealed sets and records
  ([`judge-calibration.md`](judge-calibration.md)). Every other kept-unmeasured judge
  still carries `calibrated: false` until it has one too.
- **The paired tribunal measurement.** It is designed (same sealed items, one
  `andon-wire@1` contract judge as the second arm, five repeats per item, and a decision rule
  fixed in advance) but not run. Until it is, the tribunal is calibrated but not shown to
  be better than one judge.
- **Precision on a sealed set** is now measured for the three judges above. Their record's
  agreement is the weakest of six figures, the pass and fail precision among them. Every
  calibration added later should use the same scorer.
