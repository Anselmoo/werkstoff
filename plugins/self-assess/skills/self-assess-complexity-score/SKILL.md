---
name: self-assess-complexity-score
description: This skill should be used when the user asks "which module needs attention first", "score complexity per stage", "what's our tech debt hotspot", or as part of self-assess-autopilot's CHECK phase. Computes a relative complexity index per stage using the fixed formula 2.94 x (KSLOC)^1.10, and lists unmeasured stages plainly rather than inventing numbers.
---

# self-assess-complexity-score

Compute a relative complexity/attention-priority index per stage or module.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-complexity-score
```

This skill has no Verify phase -- do not gate anything here on `skip_verification`; that
setting simply does not apply to a pure measurement.

## Step 1: Determine the stage list

Prefer `<output_dir>/stage_map.json` if it exists (reuse `self-assess-stage-map`'s stages).
Otherwise fall back to the detected-languages list from `detect-languages`, treating each
language's file set as one pseudo-stage.

## Step 2: Measure each stage

Dispatch `complexity-surveyor` per stage to measure SLOC, file count, and cyclomatic complexity
(via whatever tool is available for that language -- `radon`, `lizard`, `gocyclo`, etc.). If no
tool is available for a stage's language, the surveyor reports `-1`/`0` per its own refusal
list rather than fabricating a plausible-looking number -- when that happens, mark the stage
`unmeasured: true` in the output and list it plainly in `COMPLEXITY_SCORE.md` instead of
computing an index for it.

## Step 3: Apply the exact formula -- no substitutes

Rule `complexity-score-formula`: the index MUST be `2.94 x (KSLOC)^1.10` and nothing else.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py complexity-index --ksloc <stage_sloc / 1000>
```

Use this for every measured stage rather than restating the constants inline -- the formula
lives in one place (`scripts/lib/formulas.py`) so no per-skill copy can drift from it.

## Step 4: Validate and write

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind complexity_score_summary --file <path-or-inline-json>
```

The validator recomputes `2.94 x (KSLOC)^1.10` for every non-`unmeasured` stage and rejects the
artifact if the persisted `complexity_index` does not match to within floating-point tolerance
-- a hand-typed or LLM-guessed number cannot pass.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename COMPLEXITY_SCORE.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename complexity_score_summary.json
```

## Read-only constraint

Never use Write/Edit outside the resolved output paths.
