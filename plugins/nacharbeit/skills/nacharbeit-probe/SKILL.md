---
name: nacharbeit-probe
description: "Use to measure whether a documented example prompt actually fires the skill it names, by running it headless in fresh claude -p processes — the real answer the review's haiku routing simulation only approximates. Trigger on 'does this prompt actually fire the skill', 'did my description fix work', 'why does this skill never trigger', 're-measure routing after the fix'. Costs real money per cell, so it always dry-runs and states the estimate first. Not for grading prompt quality (nacharbeit-review) or for benchmarking plugin-present versus plugin-absent sweeps (arbeitsplan-matrix)."
argument-hint: "<skill id> [--model haiku|sonnet]"
---

# Does it fire?

The review's routing simulation asks a small model which component a *description* would
route to. That is a proxy, and it is the only routing signal the review has. This skill asks
the question itself: it runs the documented prompt headless, in a clean box, and records
which skill actually fired — so a description fix is verified by re-measurement, the only way
it can be, since definitions load once per session.

## Steps

1. **Name the scope.** One or more skill ids from `docs/prompt-index.md`'s `> Triggers` lines.
   `--only` is the default; the whole corpus (`--all`) is opt-in because every cell is paid.
2. **Dry-run first, always**, and quote the estimate to the user before spending anything:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/trigger_probe.py" --model haiku --only <skill-id> --dry-run
   ```

3. **Run it on a yes**, with an output directory, and the review's routing file when one exists
   so the simulation is compared against reality:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/trigger_probe.py" --model haiku --only <skill-id> --out analysis/nacharbeit/probe --routing analysis/nacharbeit/routing.json
   ```

4. **Read the verdicts back** from `summary.json`: `fired`, `captured` (the capturing skill is
   named), `silent`, `UNSTABLE`, `UNMEASURED`.

## Rules — four limits, stated before anyone relies on a number

- **Cost.** About $0.34 per cell, measured. Never run `--all` without the user seeing the dry
  run's estimate.
- **N ≥ 2.** One repeat cannot separate a fix from noise; the script refuses `--repeats 1`.
  `UNSTABLE` is a finding about an underdetermined prompt — never a reason to add repeats.
- **The arm is the question.** `isolated` asks "does it fire at all" with only its own plugin
  loaded; `installed` asks "does it win where users are". A misroute to a sibling is an
  `installed` fact — say which arm a result came from.
- **The tier travels with the rate.** haiku and sonnet route differently (3/14 vs 8/14 on one
  measured set). Never quote a rate without its model, and never compare rates across models.
- **Seed a repository for repo-shaped prompts.** In an empty directory the model runs
  `ls`, finds nothing and asks instead of acting — measured: 21 of 23 prompts silent. Pass
  `--mount .=<fixture>` (repeatable, `SUB=DIR`) to compose an academic probe repo; every cell
  gets its own git-initialised copy. Quote the conditional agreement (`firedAgreement`, over
  prompts where a skill fired) beside the raw one: the simulation cannot express silence.
- **`UNMEASURED` has no rate.** A logged-out CLI or a failed sentinel means nothing was
  measured; fix the environment, never re-run into it.

## Output format

```
trigger probe — 2 prompt(s) x 2 repeat(s) = 4 cell(s), model haiku, arm isolated; estimate ~$1.36 at $0.34/cell
  captured   zirkel-clarify-scope            measured 2/2  captured by zirkel-solve
  fired      cupertino-backwards              measured 2/2
simulation vs probe: 1/2 agree (0.50)
0 prompt(s) unmeasured (excluded from every rate); spent $1.29; wrote analysis/nacharbeit/probe/summary.json
```

## Resources

- `scripts/trigger_probe.py` — the probe; `--selftest` needs no tokens.
- `scripts/route_sim.py` — the review's routing simulation alone, to calibrate against the
  probe with `--routing`; use the `werkstoff` arm for that comparison.
- `scripts/subrun.py` — the single-cell executor it runs each cell through (vendored from
  `tools/subrun/`, shared with arbeitsplan's matrix).
- `scripts/post_fix_check.py` — `--probe MODEL` re-measures every routing-family fix after a
  fix pass; without it the re-measurement is recorded as pending, with this command.
