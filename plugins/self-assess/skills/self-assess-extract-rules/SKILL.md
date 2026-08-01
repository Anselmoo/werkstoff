---
name: self-assess-extract-rules
description: This skill should be used when the user asks to "extract business logic", "document the domain rules hidden in this code", "turn tribal knowledge into a spec", or as part of self-assess-autopilot's CHECK phase. Mines executable calculations, validations, and state transitions into Given/When/Then rules, looping to convergence and requiring a two-judge panel to confirm any P0 rule.
---

# self-assess-extract-rules

Mine business/domain logic from executable code -- never from comments or docstrings alone --
into testable Given/When/Then rule specs.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-extract-rules
```

## Step 1: Loop rounds to convergence, capped

Dispatch `business-rules-miner` per round, lens-scoped (calculations / validations-and-
eligibility / state-and-lifecycle) to cover different logic shapes each round. After each
round, check whether to continue -- do not decide this by feel:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py rules-loop-check --round-number <N> --consecutive-dry-rounds <M> --max-rounds <settings.extract_rules.maxRounds>
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

## Step 3: P0 panel confirmation

Any rule rated `P0` MUST go through an independent two-judge panel before it enters the
confirmed set:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py p0-confirm --rule <json rule> --judges <json list of {"judge_id":..., "confirms":...}>
```

Dispatch two independent judge agents (distinct `judge_id`s) for every P0 rule. Only
`panel_confirmed: true` (both judges confirm) survives into the confirmed set; anything else
(fewer than 2 distinct judges, or disagreement) is downgraded to `unconfirmed` and reported
separately, never silently promoted.

## Step 4: Validate and write

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind business_rules_summary --file <path-or-inline-json>
```

The validator refuses any P0 rule missing `panel_confirmed` or carrying anything other than
`panel_confirmed: true` -- there is no way for an unconfirmed P0 rule to pass validation.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename BUSINESS_RULES.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename DATA_OBJECTS.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename business_rules_summary.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename business_rules.json
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

- `references/rule-card-template.md` -- the Rule Card schema every confirmed rule renders
  as in `BUSINESS_RULES.md`. Read before writing that file the first time.
- `references/rule-card-examples.md` -- worked Rule Card instances with concrete values.
  Read alongside the template if the schema's field shapes aren't already obvious.
- `references/business-rules-report-sample.md` -- a full rendered `BUSINESS_RULES.md`
  sample, mixed-results and empty-run cases. **Mandatory read** before writing the file
  the first time (see Step 4).
