# Known-answer calibration for the kept judges

[`judge-contract.md`](judge-contract.md) kept three high-stakes judges as they are and marked
them **kept-unmeasured**: arbeitsplan's candidate-referee, matrize's decode-referee and andon's
tribunal. This page records how each one was measured against answers a command had
established, what the measurement found, and what it does not show.

The instrument is in `tools/judge-calibration/` and the fixtures are in
`test/judge-calibration/<judge>/`. Run it like this:

```bash
python3 tools/judge-calibration/calibration.py selftest   # the scorer on fabricated judges, the oracles sabotaged
python3 tools/judge-calibration/calibration.py check      # keys re-derived, prompts still render, records recomputed
python3 tools/judge-calibration/calibration.py report     # agreement, precision, recall and the confusion matrix per judge
```

## The result

Each sealed set was run once, after tuning, against prompts frozen at commit `5119c36`.

| judge | model it ran on | sealed | agreement | false passes | false fails | precision pass / fail | record |
|---|---|---|---|---|---|---|---|
| arbeitsplan candidate-referee | sonnet (agent default) | 10 (4 pass, 4 fail, 2 abstain) | 1.0 | 0 | 0 | 1.0 / 1.0 | `{sealed: 10, agreement: 1.0, floor: 0.8}` |
| matrize decode-referee | sonnet (agent default) | 10 (4, 4, 2) | 1.0 | 0 | 0 | 1.0 / 1.0 | `{sealed: 10, agreement: 1.0, floor: 0.8}` |
| andon tribunal, four roles | the session's model (opus): the andon agents declare none | 8 (3, 3, 2) | 1.0 | 0 | 0 | 1.0 / 1.0 | `{sealed: 8, agreement: 1.0, floor: 0.8}` |

So `judge_contract.is_calibrated()` is true for all three rubrics
(`test/judge-calibration/<judge>/rubric.json`). Tuning scored 6/6, 6/6 and 4/4.

### What a perfect score does not show

These are small sets. For a perfect score, the exact (Clopper–Pearson) 95% lower bound on
the true agreement is **0.69 at n=10 and 0.63 at n=8**, which is below the 0.8 floor. The
records clear the floor as it was defined before the run, and that definition is not
tightened after the result was seen, because doing so would be retuning. But the honest
reading is narrower:

- The judges are not bad at these cases.
- The sets cannot show an agreement of 0.8 with confidence.
- They may be too easy to tell a good judge from a great one. Every case was decided
  correctly, including every native verdict (10/10, 10/10, 8/8 exact).

The next step is a larger, harder sealed set, not a re-run of this one. See
[What would strengthen it](#what-would-strengthen-it).

## How an answer is known

An answer key written from intuition is an uncalibrated oracle. So no `answers.json` is
trusted on its own: `oracles.py` re-derives every expected verdict from the case's own files,
and `check` fails if the two disagree.

| judge | what decides the known answer |
|---|---|
| referee | the candidate is applied to a copy of the base tree and each acceptance command runs. All exit 0 gives pass, any non-zero gives fail. An **abstain** case carries two variants of a file the diff does not show; it is an abstain exactly when the commands disagree across them, so the diff alone cannot decide it |
| decode | the cited CSS location is resolved, re-measured (`var()` resolved, rem converted at 16px) and compared: the citation does not resolve → `cannot_reproduce`; the values differ → `not_reproduced`; the stated ratio or grid does not follow → `reproduced_different_relation`; else `reproduced` |
| tribunal | one probe per contract criterion runs inside the post-fix tree: exit 0 holds, 1 is violated, 3 cannot be decided in a test environment (a criterion about a production service). Any 1 gives red; else any 3 gives unknown; else green |

The tribunal's contested-wire cases are the three single-side repairs that
`test/plugins/verify-contested-fixture.py` already proves cannot satisfy every consumer,
plus two variants with one consumer removed, which a single-side fix *can* satisfy.

`selftest` sabotages each oracle and requires the verdict to change. It breaks a passing
candidate, collapses an abstain's two variants into one, edits a measured value, deletes a
cited selector, and appends a raise to a green fix.

## What counts as a pass

Each judge's native verdict is mapped to pass, fail or abstain the way its **workflow acts
on it**, not the way its prose describes it.

| judge | pass | fail | abstain |
|---|---|---|---|
| referee (`run.js`) | `accepted` with at least one criterion met (`LANDS` plus `withEvidence`) | `rejected`, `accepted_different_approach` (not in `LANDS`), `accepted` with no met criterion | `cannot_judge`, or no report |
| decode-referee (`decode.js`) | `reproduced` (the `confirmed` allowlist) | `reproduced_different_relation`, `not_reproduced` | `cannot_reproduce`, or no report |
| tribunal (`tribunal-protocol.md`) | overall `green` | overall `red` | overall `unknown`, or no report |

An abstain is expected only where an abstain is the right answer by construction, and it
matches only an abstain. An abstain on a pass or fail case is a disagreement, never excused.

## The record is the weakest figure, not the fraction

`judge_contract.is_calibrated()` reads one number, `agreement`, against the floor. The
plain fraction of matches can be cleared by a judge that passes everything when most
cases are passes, and the contract says so in section 4. So the record's `agreement` is the
**weakest of six figures**:

- overall agreement
- one minus the false-pass rate
- the precision of the pass class and of the fail class
- the recall of the pass class and of the fail class

The figure is rounded down, so rounding never lifts it over the floor. This makes the
existing gate carry the precision requirement without changing the vendored contract.

`selftest` holds that to account in three ways:

- a matrix for each of the six figures where that figure alone is the weakest, so dropping
  any one of them goes red
- judges that always pass, always fail or never answer, scored on the real fixtures, each
  of which must miss the floor
- a run with a missing or a doubled result, which is refused rather than scored

Each sealed set is balanced: at least three known-pass, three known-fail and one
known-abstain case, and no class above half the set. A constant judge cannot clear it.

## The seal is the commit order

1. `522559e`: fixtures, answer keys, oracles, floors (0.8 for all three) and the scorer,
   before any judge ran.
2. `f8524fe`: the one fixture correction tuning found. In tune case `tune-06`, a known
   abstain, the builder had reported an honest `exit 0` for the criterion's own command.
   The referee used that as its evidence, which its agent definition allows, so the diff
   could not decide the case but the report could. The three referee abstain cases now
   report no check. That fix came from a tuning case and from the fixture's own logic, before
   any sealed case had run. No judge prompt and no agent file was changed at any point.
3. `5119c36`: tuning results, with the prompts frozen.
4. `04a09f6`: the sealed results, verbatim, and the derived records.

The order is the seal, not the hashes. A rebase would change the hashes and keep the order,
and the subjects above identify each step. Do not squash this history. This branch was rebased onto `main` after #118 and #119 squash-merged (2026-10-21); the `note` fields in each `results/sealed.json` still cite the pre-rebase hashes (`97a59ca` is `5119c36`, `99b71c4` is `04a09f6`) and are left as recorded, since `check` verifies the fingerprints, not the hashes.

## Trusting the run

These steps protect the run:

- **The judge's own prompt.** The referee and decode prompts are **extracted** from
  `run.js` and `decode.js` at render time, so a prompt edit changes what is measured, and an
  edit the renderer cannot follow raises an error. The only addition is a fixed
  return-format footer: the workflows pass a schema to `agent()`, and the Agent tool used
  here has none.
- **Blindness.** Each case is staged alone, under an opaque name, with no key inside it.
  Each tribunal role's prompt lives in its own directory. A scan of all 81 judge
  transcripts (277 tool calls, tune and sealed) found no tool **input or result** naming
  `test/judge-calibration/`, an `answers.json` or an oracle file. It also found no Grep or
  Glob whose path lay outside the case's stage directory. One referee ran a filesystem-wide
  `find` for the files its diff did not show. It found nothing, because the hidden base files
  exist only inside oracle JSON. A content search could have found them, so the keys stay
  readable in principle, and blindness is a property this run had, not one the layout
  guarantees.
- **No retyping.** Every report was taken from its agent's transcript by script and
  relayed to the next tribunal role the same way.
- **Stale records fail.** `results/sealed.json` stores a hash of each judge's agent files
  and prompt template, and a fingerprint of the sealed cases, their oracles and their keys.
  `check` fails when any of these has changed since the measurement, or when a record
  differs from the one recomputed from the committed results. A sealed case edited together
  with its key would score the same, so the fingerprint is what makes that edit visible. It
  was added after the run, which is noted in the file, and checked equal to the tree at
  `04a09f6`.
- **The coupling this creates.** Any edit to `candidate-referee.md`, `decode-referee.md`,
  the four andon agent files, `tribunal-protocol.md`, or the referee prompts in `run.js` or
  `decode.js` turns `plugin-checks` red until the judge is re-measured on a new sealed set,
  or its record is removed. That is the point: a record that no longer describes the judge
  must not stay green.

## Findings about the judges

- **The referee's landing gate is weaker than its verdict.** `run.js` lands a candidate when
  the verdict is `accepted` and **at least one** criterion is met (`per.some(met)`). The
  agent's own definition of `accepted` is that every criterion is met. Sealed case
  `sealed-07` (two of three criteria met) probes this gap: the referee said `rejected`, so
  the gap did not fire. It is still reachable: an `accepted` with an unmet criterion would
  land.
- **The referee trusts a reported exit code when the diff cannot decide.** This is by
  design, since its definition names "the check whose exit code decided it" as evidence. It
  means a builder's false `exit 0` on a check the diff cannot contradict is believed.
- **`accepted_different_approach` never lands** (`LANDS` holds `accepted` alone). No sealed
  verdict used it.
- **The tribunal reads contracts literally and says so.** On `sealed-05` it marked the wire
  green while noting that `apply()` now returns a dict's keys instead of rows, a change no
  criterion covers. That is the right verdict for the contract and a reminder that green
  means "the stated criteria hold".
- **`decode.js` still returns `calibrated: false`.** It is hard-coded, and a workflow cannot
  read the record. The record exists, but the runtime label does not follow it yet.

## What would strengthen it

- **A larger sealed set.** At n=30 a perfect score has a lower bound near 0.88. That needs
  new cases written before the run, never this set re-run.
- **Harder cases.** Lies the diff cannot contradict, near-miss values (21.3 vs 21.33px),
  `accepted` with one unmet criterion, a contract whose criteria conflict.
- **A second model.** The andon agents inherit the session's model. This run measured
  opus. A sonnet session is a different judge.
- **Repeats.** One pass per case is a single sample of a stochastic judge.

## The paired measurement

The tribunal's `resolves_if` asked whether four agents earn their cost over **one contract
judge** on the same items. That question was measured. The design, the items and the
decision rule were committed before either arm ran (`fa751ba`), and the run was workflow
`wf_589ce94f-c60` on 2026-10-21. The evidence is in `test/judge-calibration/paired/results/`,
and `paired.py check` recomputes the score from the committed raw run.

### The design

- **Items.** 20: the tribunal's 8 sealed cases plus 12 paired-only cases
  (`test/judge-calibration/paired/`). They split 7 green, 8 red and 5 unknown, and every key
  is re-derived by its probes. The new cases are harder:
  - a contested wire fixed on *both* sides (green)
  - a float rounding bug
  - a missing cache invalidation
  - a shipped test that pins the wrong behaviour and passes
  - a failed criterion **and** an unverifiable one (red, not unknown)
  - three criteria only production could settle
- **Arm A, the tribunal.** Defender and challenger blind in parallel, then the verifier,
  then the adjudicator, with the same prompts as the calibration.
- **Arm B, one verdict@1 judge.** Rubric `andon-wire@1`: one criterion per contract
  criterion, threshold 0.7. It is a general-purpose agent told to change nothing, so it can
  run what the verifier ran. It is decided by `decide()`: `pass` gives green, `fail` gives
  red, `abstain` gives unknown. The prompt told it to abstain if any criterion could not be
  decided in the environment.
- **Repeats.** Five per item per arm. An item's outcome is the one at least 3 of 5 runs
  agree on, else it scores as an abstain.
- **Same model.** Neither arm names one, so all 500 agents ran on the session's
  (`claude-opus-5-5`).
- **Decision rule, fixed before the run.** Keep the tribunal only if arm B has more false
  passes, or a lower six-figure record, on the same items. Otherwise collapse it.

### The result

| arm | per-item agreement | false passes | record | per-run agreement | items unanimous over 5 runs | output tokens per run | agents per run |
|---|---|---|---|---|---|---|---|
| tribunal | 1.00 | 0 | **1.0** | 0.94 | 16/20 | ~7,000 | 4 |
| contract judge | 0.95 | 0 | **0.875** | 0.95 | 20/20 | ~730 | 1 |

**The rule, applied as committed, keeps the tribunal**: arm B's record is lower. The mapping
row now carries that measured reason. But the margin is one item. Only one pair is
discordant (only the tribunal right, never the other way), and the exact McNemar p is 1.0.

**The one item is a shape effect, not a judgement effect.** `paired-12` has a failed
criterion and a criterion only production could settle. The tribunal says red on all five
runs, because a fail dominates a `neither`. The contract judge abstains on all five, because
verdict@1 can only abstain on the **whole** item, and arm B's prompt said to abstain whenever
any criterion cannot be decided. verdict@1 has no way to say "c1 fails, c2 is unknown,
therefore red". That is a gap in the contract, found by this run.

**Run by run, the single judge was the steadier one.** The tribunal's six wrong runs all
come from making an outcome up:

- `sealed-04` is green, and once went red and once unknown.
- Three unknown items (`paired-09` twice, `paired-11` and `sealed-08`) were turned red in
  four runs.

The contract judge's five wrong runs are all `paired-12`. Neither arm ever passed a wire
that should not pass.

### What it settles, and what it does not

- **Settled.** On these 20 items and this model, the tribunal is not better at catching
  bad wires: neither arm has a false pass. It is about ten times as expensive in output and
  four times in agent calls, and less consistent run to run.
- **Kept, for a measured reason.** The tribunal is kept because the committed rule says so,
  and the reason is specific: it expresses per-criterion `neither` where verdict@1 cannot.
- **Not settled.** Whether a verdict@1 judge with **fail-dominates-abstain**
  (a criterion-level undecidable, reduced as `red` if any criterion fails) would close the
  gap. Deciding that needs a contract change (verdict@2) and a **new** paired run on new
  items. Re-scoring this run under a changed rule would be retuning after the fact.
- **The limits that still apply.** 20 items, one model, and items authored by the same
  hand that wrote both arms' prompts.
