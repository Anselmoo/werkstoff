---
name: arbeitsplan-matrix
description: Compiles and runs a headless sweep — cases x models x plugin-states x repeats, one fresh `claude -p` process per cell — after proving the environment can authenticate. Use when the user wants genuinely independent candidates, a real per-candidate --model, a plugin-present versus plugin-absent comparison, or asks to benchmark or ablate a plugin. Also use afterwards to read results back. A cell that could not be fairly measured is UNMEASURED, never FAIL.
argument-hint: "[runId | matrix.json]"
---

# The matrix backend

The second way to run a swarm: **one fresh `claude -p` process per candidate** instead of one
in-session dispatch.

It buys what in-session dispatch structurally cannot. A fresh process has a fresh registry,
so a just-edited skill is actually loaded. A cell's `--model` cannot be inherited from the
caller — the failure named as *"an omitted model inherits your session's model, which
silently defeats this section"* is impossible here. And plugin-present versus plugin-absent
arms are expressible at all, which in-session they are not.

`cases × models × plugin_states × repeats` at **1 × 1 × 1 × N** *is* the swarm: N independent
candidates over one scope.

## Run it, after proving it can

One cheap `claude -p` call establishes whether the environment can authenticate at all, then
the sweep runs. If the probe fails, `run_matrix.sh` refuses **and prints what the probe got
back** — which is the information a blanket refusal could never give you.

This replaced an unconditional refusal-when-nested that was imported from another repository's
measurement and never tested here. It does not reproduce in this environment, and it was
redundant besides: a cell that hits an auth banner is already scored `UNMEASURED` with its
reason, and excluded from every denominator.

Two honest caveats that survive the change:

- A long sweep is still better run from a terminal, where it is not competing with a session
  for attention and where you can watch it.
- `--skip-probe` exists for someone who knows more than the probe does. Reaching for it to get
  past a genuine failure buys a sweep of identical `UNMEASURED` rows.

## Steps

1. **Read `references/matrix-schema.md`.** It is the authority on every key, on the two
   ablation modes, and on the five outcomes.

2. **Derive `matrix.json`** from `workflow.json` when a run exists, or from the user's
   description when it does not. Pick `repeats` to match the fan-out you want, and give both
   arms when the question is about a plugin's own contribution.

3. **Choose the ablation deliberately.** The two answer different questions and neither
   replaces the other: `isolated` asks whether the plugin's description fires *at all*, with
   no competitor; `installed` asks whether it wins in the environment users actually have. A
   case that fails the second and passes the first is a routing loss, not a description gap —
   say which one you set and why.

4. **Validate without running anything:**

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/run_matrix.sh" --selftest
   ```

5. **Hand over the command.** Print it for the user to run in a terminal:

   ```bash
   bash plugins/arbeitsplan/scripts/run_matrix.sh --matrix analysis/arbeitsplan/<runId>/matrix.json --out analysis/arbeitsplan/<runId>/matrix
   ```

6. **Read the results back** when they return: `summary.json` plus one file per cell. Feed
   the outcomes into the same selection rules `arbeitsplan-run` uses.

## Rules

- **Never reach for `--skip-probe` to get past a failing probe.** The probe failing means
  every cell would fail the same way; skipping it buys a sweep of identical `UNMEASURED` rows.
- **`UNMEASURED` is excluded from every denominator and never triggers a re-run of the work.**
  It means the environment failed. Fix the environment; re-running against a broken one
  measures the weather.
- **`UNSTABLE` is a finding, not a retry trigger.** Repeats disagreeing means the prompt is
  underdetermined; the answer is a better prompt, not more repeats.
- **Never set `allowed_tools`.** It is a permission allowlist and does not restrict the tool
  surface — the runner rejects it and says so. `disallowed_tools` restricts; `expected_tools`
  is the assertion that actually gates.
- **Never quote a pass rate over a sweep with unmeasured cells** without saying how many.

## Output format

```
arbeitsplan matrix — ap-2026-09-12-a3f1
  cases          1  (ratelimit)
  models         1  (sonnet)
  plugin states  2  (with=plugins/arbeitsplan, without=null)
  repeats        3
  cells          6
  ablation       isolated — empty cwd, --setting-sources project, --strict-mcp-config,
                 --plugin-dir on the enabled arm only
  expected tools Skill, ToolSearch  (asserted after the fact; a cell outside it is UNMEASURED)

wrote analysis/arbeitsplan/ap-2026-09-12-a3f1/matrix.json
selftest passed (13 validation + 2 end-to-end against a stub; no real cells run)

auth probe       : ok
  selfheal__sonnet__with__1              PASS         exit=0   7s
  selfheal__sonnet__without__1           UNMEASURED   exit=1   2s

A long sweep is still worth running from a terminal, where you can watch it:

    bash plugins/arbeitsplan/scripts/run_matrix.sh \
      --matrix analysis/arbeitsplan/ap-2026-09-12-a3f1/matrix.json \
      --out analysis/arbeitsplan/ap-2026-09-12-a3f1/matrix
```

Reading results back:

```
arbeitsplan matrix results — ap-2026-09-12-a3f1
  case       model    arm       outcome     measured  distinct stdout
  ratelimit  sonnet   with      PASS        3/3       1
  ratelimit  sonnet   without   UNSTABLE    3/3       3

  The enabled arm gave the same answer three times; the disabled arm gave three
  different ones. That is the plugin's contribution showing up as determinism,
  which is the only thing this sweep can actually establish.
  0 cells unmeasured, so both rates are real.
```

## Resources

- `references/matrix-schema.md` — the schema, the two ablation modes, the five outcomes, and
  why `--allowedTools` is refused.
- `scripts/run_matrix.sh` — the runner; `--help` for its flags, `--selftest` to validate.
