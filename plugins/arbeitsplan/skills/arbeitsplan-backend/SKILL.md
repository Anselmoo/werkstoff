---
name: arbeitsplan-backend
description: Decides whether a compiled arbeitsplan run executes in-session, as a headless matrix of fresh claude -p processes, or inside the Workflow tool, and emits the checked backend object workflow.json requires. Use when the user asks whether to run something as a workflow or a matrix, whether a job should run in parallel agents or in this session, or why a run had to be forced into one. Recommend-only. For which pattern fits, hand off to arbeitsplan-patterns; for which of the four approved workflows applies, to arbeitsplan-start.
argument-hint: "<runId, or the work in a sentence>"
---

# Which backend runs it

A spec that names a backend without a reason gets run in whichever one the session reaches for.
That is how a run ends up forced into an agentic workflow by hand. This skill makes the choice
from a frozen table and records which row made it, so the compiler can check it.

## Steps

1. **Read `references/backend-selection.md` in full, every time.** It holds the three backends,
   the ordered decision table, the closed `why` vocabulary and the refusals. Never answer from
   memory.
2. **Read the run's `workflow.json`** if a runId was given, or the user's description if not.
   You need three facts from it: does any phase write the shared tree, is the fan-out width
   fixed, and was anything under test edited in this session.
3. **Walk the decision table top to bottom.** The first matching row decides the backend.
   Collect every row that matches, not just the first, as `why` ids.
4. **Check the refusals** before answering. `workflow` with a `shared` writer is refused — say
   which phase and offer the fix: that phase returns its diff as data (`writes: worktree`) and
   `land_candidate.py` lands it in-session. `workflow` always carries
   `acknowledgedGaps: ["workflow-tool-unhooked"]`; say what that gap is.
5. **Emit the object** and validate it through the compiler, never by eye:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compile_spec.py" --spec analysis/arbeitsplan/<runId>/workflow.json
   ```

## Rules

- **Never pick `workflow` for a phase that writes the shared tree.** No hook sees a Workflow
  dispatch's writes, which is the whole reason the compiler refuses it.
- **Never write a free-text `why`.** Only the table's ids compile, and each must select the
  kind it sits next to.
- **Recommend a matrix whenever the thing under test was edited in this session**, however
  convenient in-session would be: a definition loads once per session, so in-session grades the
  old file.
- **Report the token argument as `reasoned`.** It is plausible and unmeasured here; never quote
  it as a rate.
- This skill never writes `workflow.json` and never launches a run. `arbeitsplan-compile`
  writes; `arbeitsplan-run` and `arbeitsplan-matrix` execute.

## Output format

```
arbeitsplan backend — ap-2026-09-18-6a6a
  phases writing the shared tree   none (synthesize writes: worktree)
  fan-out width                    fixed (4, 1, 3, 3, 1, 1)
  edited this session              no
  matched rows                     7 fixed-graph-returns-data, 8 context-exceeds-session
  backend                          workflow
  acknowledged gap                 workflow-tool-unhooked — no hook matches the Workflow
                                   tool; the synthesized diff is landed in-session by
                                   land_candidate.py, where the writeScope check runs

  "backend": {"kind": "workflow",
              "why": ["fixed-graph-returns-data", "context-exceeds-session"],
              "acknowledgedGaps": ["workflow-tool-unhooked"]}

  compile_spec.py: spec is valid
  plan-node stops: contract, adjudicate — run.js halts before each and returns
  pending_plan_node; run that phase here, then relaunch from the next one.
```

## Resources

- `references/backend-selection.md` — the backends, the decision table, the `why` vocabulary,
  the refusals, the unhooked gap and the token argument.
