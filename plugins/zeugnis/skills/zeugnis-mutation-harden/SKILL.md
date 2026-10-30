---
name: zeugnis-mutation-harden
description: "Use when the user wants a REAL mutation tool run over one module or package, the surviving mutants triaged, and tests written that kill them -- 'harden these tests with mutmut', 'raise the mutation score of this module', 'run mutation testing and kill the survivors'. Runs the tool on fresh git-archive copies as background scripts, proves every kill by applying the mutant, and reports score per module before and after with untested mutants, equivalents and unreached survivors listed apart. Not for estimating assertion strength without running a tool -- use zeugnis:zeugnis-assertion-audit; not for proving that a change is correct -- use andon:andon-verify."
---

Run a real mutation tool over one module or package, triage what survives,
and write the tests that kill it. Every number in the result comes from the
tool, and every kill from a proof the harness recorded. Nothing here is a
model's estimate except the one-line reason an equivalent mutant carries,
and that is reported as such.

Scope is small on purpose: one module or package, one pull request. A
repository-wide baseline (a matrix of shards with agent lanes per package)
is not shipped; see "Repository-wide runs" below.

The rules that must hold no matter what this file says are enforced in code:

| rule | enforced by |
|---|---|
| a mutant exists only inside a fresh `git archive HEAD` copy | `scripts/hooks/guard_bash_scope.py` denies `mutmut run`/`apply`/`browse`, `cosmic-ray exec`/`apply`, `cargo mutants --in-place` and `stryker --inPlace` outside one; `scripts/mutation_harden.py` refuses to start the tool anywhere else |
| a copy is run once, never resumed | `run-shard` refuses a copy that already has `mutants/` |
| a killing test never edits source | the `open-tests` lock: `scripts/hooks/guard_edit_scope.py` allows writes only under its test roots, never under its source paths or into `conftest.py`/`pyproject.toml`, up to its edit budget |
| a kill is proven, not claimed | `prove` passes only if the new test exits 0 unmutated and exactly 1 with the mutant applied; `report` and `cycle_engine.py` reject a kill without such a proof |
| a real-tool finding cites the tool's output | `lib/mutation_results.verify_citation` re-hashes and re-parses mutmut's `.meta` sidecar |

## Steps

`H` below is `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/mutation_harden.py"`.

1. **Detect the stack and the tool.** Only Python with mutmut 3 is driven.
   For any other stack, stop and say so, naming the tool
   `references/mutation-tools.md` lists for it and what the harness lacks.
   Never fall back to reasoning out a score. Find the mutmut binary in the
   project's own test environment (not on a global PATH that may hold a
   different interpreter); its sibling `python` runs the proofs.
2. **Fix the shard.** One shard is the module or package the user named.
   Agree with the user:
   - `--source`: the code to mutate.
   - `--test`: the **fast unit tests only**. Every mutant reruns every
     selected test that covers it, so one slow test multiplies the whole
     run; integration tests stay out of mutation runs.
   - `--exclude 'GLOB=reason'`: code whose behaviour is pinned another way
     (a generator pinned by committed hashes, a vendored file). A reason is
     required and goes into the report.

   Pick a new `runId` (e.g. `2026-10-30-pricing`); every run gets fresh copies.
3. **Prepare and run the baseline as a background script.**
   ```bash
   $H prepare <repo> --run-id R --shard S --source src/pkg --test tests/unit [--exclude 'GLOB=reason']
   $H run-shard <repo> --run-id R --shard S --time-box 1800 --mutmut <path>
   ```
   Start `run-shard` with the Bash tool's `run_in_background`. Neither you
   nor an agent waits on the tool: long runs dispatched to agents lost
   their result 3 times in 5, while the same runs as scripts all finished.
   While it runs, read
   `analysis/zeugnis/mutation/R/records/shards-S.run.json`; its `state`
   leaves `running` when the tool ends or the time box kills it.
4. **Collect and show the baseline.**
   ```bash
   $H collect <repo> --run-id R --shard S --mutmut <path>
   ```
   Show the user the module scores, `noTests` beside the score (never
   folded into it), and `complete`. A shard that timed out leaves
   `notChecked` mutants and `complete: false`; say so before anything else.
5. **Triage into lanes.** From `records/shards-S.results.json`, take every
   mutant with status `survived` or `no tests`. Sort them first by how much
   the module matters: code that computes or checks results comes before
   glue and formatting. Then sort by `kindHeuristic` (comparison,
   boolean-logic, constant, value-replaced-by-None, string-literal, ...).
   Give each module one lane with a budget (a mutant count, e.g. 20). Show
   the user the lane plan before writing anything. Thousands of survivors
   are normal, and a lane reports what its budget did not reach.
6. **Kill, one lane at a time, under the test-scope lock.**
   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/remediation_scope_cli.py" open-tests <repo> \
       --lane-id L --test-root tests/unit --source-path src/pkg --edit-budget N
   ```
   Dispatch the `mutation-killer` agent with the lane's mutants (id, diff,
   `module:line`, kind), the test roots, and the budget. It writes tests
   and returns, per mutant, a candidate test id or an equivalence reason.
   Then run `remediation_scope_cli.py close <repo>`. Exit code 3 or 4 from
   `open-tests` is a refusal: fix the arguments, do not work around it.
7. **Prove every candidate.**
   ```bash
   $H prove <repo> --run-id R --shard S --mutant ID --test-file tests/unit/test_x.py \
       --test-id tests/unit/test_x.py::test_name --mutmut <path>
   ```
   `verdict: killed` (clean exit 0, mutant exit 1) is the only kill.
   `survives` means the test does not reach or assert the mutated
   behaviour. `invalid` means the test fails unmutated, or the mutant
   breaks import or collection. A candidate that does not prove may get
   one more dispatch while the lane's budget lasts; otherwise it stays
   unreached. Never record it as killed.
8. **Re-measure the survivors only, on a fresh copy.**
   ```bash
   $H prepare <repo> --run-id R --shard S --kind remeasure --overlay tests/unit/test_x.py [...]
   $H run-shard <repo> --run-id R --shard S --kind remeasure --time-box 1800 --mutmut <path>   # background
   $H collect <repo> --run-id R --shard S --kind remeasure --mutmut <path>
   ```
9. **Report.** Write `triage.json` in this shape:
   ```json
   {"lanes": [{"lane": "pricing", "module": "src/shop/pricing.py", "budget": {"mutants": 20},
     "entries": [
       {"mutantId": "shop.pricing.x_discount__mutmut_3", "disposition": "killed",
        "proof": "analysis/zeugnis/mutation/R/records/proof-shop.pricing.x_discount__mutmut_3.json"},
       {"mutantId": "shop.pricing.x_clamp_qty__mutmut_1", "disposition": "equivalent",
        "reason": "qty < 0 vs qty <= 0 differ only at qty == 0, where both branches return 0"}]}]}
   ```
   Then run `$H report <repo> --run-id R --triage triage.json`. It writes
   `analysis/zeugnis/mutation_harden_summary.json`,
   `analysis/zeugnis/reports/MUTATION_HARDEN.md` and
   `records/pass.json`. A survivor with no entry is counted unreached. A
   kill whose proof does not hold, or that the re-measure contradicts, is
   listed under rejected claims.
10. **Show the user.** Show the per-module before/after table, the kills
    with their tests, and the rejected claims. Show **every** equivalent
    mutant with its reason: equivalence is the one model judgement here, no
    command checked it, and the user is the spot check. It never counts as
    a kill. Also show the unreached count per lane.
11. **Optionally record it in the ledger**:
    `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/cycle_engine.py" record-pass-result <repo> --pass-json analysis/zeugnis/mutation/R/records/pass.json`.
    Proven kills close as `fixed`. Everything else stays open as `blocked`
    with its reason. `zeugnis-cycle`'s `plan-next-pass` never picks this
    domain.

## Repository-wide runs

Not shipped. The shape the issue describes still applies: one shard per
package (or per module, for a large package), each a script node with a
time box, run on a schedule or on request and never on push, then agent
lanes per package within a budget. GitHub Actions stops a hosted job after
6 hours, so shards are sized to fit. Run this skill once per shard until a
workflow mode exists.

## What NOT to do

- Do not run `mutmut run` or `mutmut apply` yourself in the working tree.
  The hook denies it, and on a machine without the hook it would write
  `mutants/` into the repository or a mutant into the source.
- Do not edit source to make a mutant die. A survivor is a missing test,
  and the lock denies the edit anyway.
- Do not report an LLM-reasoned score as a mutation score, and do not
  count an equivalent mutant as killed.
- Do not reuse a copy or a `runId` to save time; a stale copy is how
  leftover state gets resumed.
- Do not delete `analysis/zeugnis/mutation/R/` before the report is
  written: findings cite the tool's sidecars there and are dropped when
  those are gone.
