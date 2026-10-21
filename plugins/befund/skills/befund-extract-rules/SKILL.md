---
name: befund-extract-rules
description: Mines executable calculations, validations, and state transitions into Given/When/Then rules, looping to convergence and requiring a scored judge verdict to pass for any P0 rule. Use when the user asks to "extract business logic", "document the domain rules hidden in this code", "turn tribal knowledge into a spec", or as part of befund-autopilot's CHECK phase. Not for code style, naming, layering, dependency-direction or other architecture conventions — use lehre-codify for those. This skill extracts what the code decides, not how it is written.
---

# befund-extract-rules

Mine business/domain logic from executable code -- never from comments or docstrings alone --
into testable Given/When/Then rule specs.

## Step 0: Settings gate

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" check-enabled --repo <repo_root> --skill befund-extract-rules
```

## Step 1: Loop rounds to convergence, capped

Dispatch `business-rules-miner` per round, lens-scoped (calculations / validations-and-
eligibility / state-and-lifecycle) to cover different logic shapes each round. After each
round, check whether to continue -- do not decide this by feel:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" rules-loop-check --round-number <N> --consecutive-dry-rounds <M> --max-rounds <settings.extract_rules.maxRounds>
```

`should_continue: false` means stop -- either because two consecutive rounds found nothing new
(`stopped_reason: "converged"`) or because the hard cap of 4 rounds was reached
(`stopped_reason: "max_rounds_reached"`), even if the last round still found new rules. The cap
is enforced inside the controller: passing `--max-rounds 4` (or omitting it) never allows a 5th
round regardless of what the settings claim.

## Step 2: Verify every citation independently

For each candidate rule, independently confirm its `file:line` citation actually contains the
logic claimed -- dispatch a fresh read of that exact location rather than trusting the miner's
own citation. Only mine logic that executes; a rule "supported" solely by a comment or
docstring is not a rule.

## Step 3: Judge every P0 rule

Any rule rated `P0` MUST pass ONE judge before it enters the confirmed set. No command can
say whether cited code implements a stated rule, so a model is asked -- once per rule, against
the `befund-p0-rule@1` rubric in `${CLAUDE_PLUGIN_ROOT}/references/judge-rubrics.md`
(contract: `${CLAUDE_PLUGIN_ROOT}/references/judge-contract.md`).

1. Dispatch ONE `business-rules-miner` as P0 judge for each P0 rule. Give it the rule, the
   rule's `id` as the item to echo back verbatim, and every rubric criterion id with its
   question. Do not tell it what any other agent concluded.
2. The judge returns only `{item, criteria: [{id, score, pass, evidence}], abstain,
   abstainReason}` -- scores and evidence for each criterion, never an overall pass or fail.
3. Code decides. Pass the rule and the raw report, or `null` if the judge returned nothing:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" p0-confirm --rule <json rule> --verdict <json judge report, or null>
```

   It prints `{rule, confirmed, downgrade_reason}`. Use the returned `rule` -- it carries the
   decided `p0_verdict` -- in the summary. Only `confirmed: true` (the verdict's `outcome` is
   `pass`) survives into the confirmed set. A `fail`, an `abstain` (including a missing,
   malformed or wrong-item report) is downgraded to `unconfirmed`, reported with its
   `downgrade_reason`, and never silently promoted. Report an abstain separately from a fail.
   Never re-dispatch a judge to obtain a different outcome; one judge call per rule.
4. Show the user a sample of the verdicts, every run, before Step 4:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" p0-spot-check --rules <json list of every judged P0 rule, confirmed or not, each with its p0_verdict>
```

   Print each sampled verdict's `item`, `outcome`, and per-criterion `evidence`. This rubric
   has no calibration record, so label every one **uncalibrated** (`calibrated: false`): no
   one has measured this judge against known answers, and the sample is how a human checks it.

## Step 4: Validate and write

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" validate-artifact --kind business_rules_summary --file <path-or-inline-json>
```

The validator refuses any P0 rule whose `p0_verdict` is missing, malformed, from another
rubric, about another rule, or has an `outcome` other than `pass` -- there is no way for an
unconfirmed P0 rule to pass validation. The old `panel_confirmed: true` is not honoured.
The summary's `rules` list therefore holds confirmed rules only; a downgraded P0 rule
stays out of it and appears in the "Unconfirmed rules" section of `BUSINESS_RULES.md`.

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" resolve-output-path --repo <repo_root> --filename BUSINESS_RULES.md
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" resolve-output-path --repo <repo_root> --filename DATA_OBJECTS.md
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" resolve-output-path --repo <repo_root> --filename business_rules_summary.json
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py" resolve-output-path --repo <repo_root> --filename business_rules.json
```

Render `BUSINESS_RULES.md` as one Rule Card per confirmed rule, in the exact
shape defined by `references/rule-card-template.md` (worked instances in
`references/rule-card-examples.md`) -- a P0 rule downgraded to
`unconfirmed` in Step 3 goes in a separate "Unconfirmed rules" section with
its downgrade reason, never as a card, never silently dropped. If mining
found nothing across all rounds, write the explicit empty-run form, not a
missing or partial file. Both forms are shown end to end in
`references/business-rules-report-sample.md` -- **mandatory read** before
writing the file the first time.

## Read-only constraint

Never use Write/Edit outside the four resolved output paths. Never invent business logic not
present in the code.

## Resources

- `${CLAUDE_PLUGIN_ROOT}/references/judge-rubrics.md` -- the `befund-p0-rule@1` rubric
  (criteria, threshold, report shape, calibration status). Read before dispatching the
  Step 3 judge.
- `${CLAUDE_PLUGIN_ROOT}/references/judge-contract.md` -- the shared judge verdict contract
  (vendored copy; why code, not the judge, decides the outcome). Read if a verdict's
  `abstainReason` is unfamiliar.
- `references/rule-card-template.md` -- the Rule Card schema every confirmed rule renders
  as in `BUSINESS_RULES.md`. Read before writing that file the first time.
- `references/rule-card-examples.md` -- worked Rule Card instances with concrete values.
  Read alongside the template if the schema's field shapes aren't already obvious.
- `references/business-rules-report-sample.md` -- a full rendered `BUSINESS_RULES.md`
  sample, mixed-results and empty-run cases. **Mandatory read** before writing the file
  the first time (see Step 4).
