---
name: nacharbeit-review
description: "Use to run the calibrated judgement review of one or more Claude Code plugins against the nacharbeit rubric: a sonnet finder tuned on planted-defect fixtures until it clears a recall floor for every rule family, measured once on a sealed hold-out, then two-lens finders with gap rounds per (plugin, kind) batch, a haiku routing simulation for cannibalization, an adversarial refuter, and an opus synthesis into a tiered backlog and a findings report. Trigger on 'review this plugin against the Anthropic standard', 'where do these skills and hooks fall short', 'run the nacharbeit review', 'prompt-quality review'. Runs nacharbeit-lint first; never applies a fix (that is nacharbeit-fix). Writes only analysis/nacharbeit/ and, inside werkstoff, the generated findings report."
---

Measure before asserting. The finder that grades real files is the one that first
passed a planted-defect calibration for every family it will grade; a finder that has
not is a reviewer with an unknown false-negative rate, and its output is an opinion.

## Steps

1. **Preflight.** Run `nacharbeit-preflight`. Stop on an open fix lock. Note every
   skipped checker; the report will carry the same gaps.

2. **Build and bake the args** (this also runs the lint; every path is a flag with a
   werkstoff default — `--help` lists them):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_args.py" [--plugin <name> ...] [--docs-root docs]
   ```

   It refuses when a batch kind has no tuning + sealed fixture pair under the fixtures
   root: a finder cannot grade what it was never calibrated on. It prints the batch
   list; tell the user the plugin count, the batch count and the fixture count before
   launching anything.

3. **Launch the review** with the Workflow tool, by the baked script path and never
   with hand-built args — the args are 170+ KB and the leak assertions live in them:

   ```
   Workflow({ scriptPath: "analysis/nacharbeit/run.js" })
   ```

   The workflow calibrates (up to three rounds, an opus rewriter between them), measures
   the sealed hold-out, refuses to grade if any family falls below its floor, then finds,
   routes, judges, verifies and synthesizes. Expect on the order of forty agent calls per
   plugin. A return with `completed: false` names the calls that returned nothing;
   resume it with `resumeFromRunId`, never persist it.

   *Without the Workflow tool*: dispatch the `component-finder` agent once per batch and
   lens from the printed batch list, collect its findings, and label every one
   **uncalibrated** in the report. Do not run `write_results.py` on them — it refuses
   a return value without a calibration block, and so does the fix pass. An uncalibrated
   review is a reading, not a measurement, and is presented as one.

4. **Persist, or refuse.** Save the workflow's return value to
   `analysis/nacharbeit/return.json`, then:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/write_results.py" analysis/nacharbeit/return.json
   ```

   It writes `run.json` last, so its presence means the other three are complete. A
   refusal leaves a `FAILED-<stamp>` marker and nothing else; report the reason and
   stop — a stale `run.json` under a fresh marker is exactly the state `build_report.py`
   refuses to render.

5. **Render the report** and present it:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_report.py"
   ```

   Inside werkstoff this writes `docs/prompt-quality-findings.md`; elsewhere pass
   `--out` and `--no-vitepress`. Lead with section 1 (how much to trust the rest: recall
   per family, sealed recall, router accuracy), then the per-plugin verdicts, then the
   backlog by tier with every opus- and human-tier entry named — those are the ones a
   person must decide.

## Output format

```
nacharbeit review 2026-09-09T06:12:04Z · rubric 3f9c1a2b7d0e · 3 plugins, 19 batches, 20 fixtures (kinds: assets, docs, hooks, manifest, scripts, skills)
calibration: r1 recall 0.76 (min angle 0.40, min family 0.50) → rewrite → r2 recall 0.83 (min angle 0.60, min family 0.67)
sealed hold-out: 0.79 overall; Q 0.81, HQ 0.75, SQ 0.67, AQ 0.75, PQ 0.80, DQ 1.00 — every family above its floor, finder frozen
router proxy: 0.97 top-1 on 70 known-answer prompts → collisions are measured (24 pairs judged)
raw 312 → verified 164 (+9 from the critic round); lint 41

  plugin   verdict      verified  lint  summary
  andon    needs-work   38        9     andon-loop's argument-hint promises a filter no phase reads; …
  takt     sound        2         3     …
  lehre    needs-work   57        8     …

backlog: haiku 31 · sonnet 96 · opus 2 · human 4
held for a person (never auto-applied):
  [opus ] compass: plugins/compass/workflows/solve.js — design a real gate for each stage's output_contract …
  [human] andon:   plugins/andon/skills/andon-loop/SKILL.md — decide whether andon-loop supports scoped runs …

report: docs/prompt-quality-findings.md (682 lines)
next: nacharbeit-fix applies the haiku and sonnet tiers under the lock; the four held entries need you.
```

## Rules

- **Never retune the finder by hand**, and never edit a fixture after seeing what the
  finder missed on it. Fix the rubric or add a fixture, then rerun from step 2.
- **Never pass `args` inline.** The baked `run.js` is the only launch path.
- **A `completed: false` return is resumed, not persisted.** `write_results.py` would
  refuse it anyway; do not work around the refusal.
- **Never grade a kind that has no sealed fixture.** `build_args.py` refuses; do not
  remove the fixture requirement to make it pass.
- **Read the transcript of any single-pass surprise** before believing a tally.

## Resources

- `scripts/build_args.py`, `scripts/write_results.py`, `scripts/build_report.py` — run, in that order.
- `workflows/review.js` — read to understand the phases; never edit it mid-run (its baked copy is what runs).
- `agents/component-finder.md` — the fallback finder for sessions without the Workflow tool.
- `references/rubric.md` — the standard every finding cites; read a rule before disputing a finding.
- `scripts/ambiguous-prompts.json` — werkstoff's hand-written ambiguous prompts for the routing simulation; another repository passes its own with `--ambiguous`.
