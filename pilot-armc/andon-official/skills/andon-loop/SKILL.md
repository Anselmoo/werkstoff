---
description: Runs one pass of the andon hardening loop over this project's value stream (its ordered chain of stages, connected by wires/data-contracts). Use when the user asks to harden the pipeline, run a self-optimization loop, close gaps in a multi-stage codebase, or advance the value stream while keeping every handoff between stages proven. Also use for "andon loop", "wire proof", "andon rule", or "run a pass".
---

# Andon Loop

A value stream is the ordered chain of stages a project's work passes through
(for example: ingest -> transform -> validate -> publish). A wire is the data
contract at the boundary between two adjacent stages: what one stage promises
to hand the next.

The andon rule: never advance past a wire that has not been proven to hold.
If the current stage's outgoing wire is broken or unverified, stop there and
report it instead of moving on.

A pass is one traversal of the value stream from its first stage to wherever
the andon rule stops it (or to the end, if nothing stops it). A cycle is a
converged run of one or more passes: it ends when a full pass finds no more
gaps to fix.

## Running one pass

1. **Find the value stream.** Identify the project's stages and the wire
   between each adjacent pair. Look for existing documentation of this
   (architecture docs, a pipeline config, a stage list) before inferring it
   from the code's own module/package boundaries.

2. **Scan the current stage for gaps.** A gap is anything about the current
   stage or its outgoing wire that falls short of what the next stage
   requires: a missing field, an unhandled case, absent error handling, a
   contract violation. List every gap you find in this stage before picking
   one.

3. **Fix exactly one gap.** Pick the highest-priority gap in the current
   stage and fix it. Do not fix multiple gaps in the same stage before the
   wire is re-checked — one fix, then verify.

4. **Verify the wire.** Before advancing past the stage you just touched,
   use the `andon-wire-verifier` agent to check whether the outgoing wire
   now holds. Give it the wire's contract (what the next stage expects) and
   the evidence that the fix satisfies it (the changed code, a test result,
   a reproduction).

5. **Apply the andon rule.**
   - If the wire is proven: advance to the next stage and repeat from step 2.
   - If the wire is not proven: stop. Report which wire failed, why, and
     what would need to change to prove it. Do not advance past it.

6. **Close the pass into a cycle.** When a full pass from the first stage
   reaches the last stage with no gaps found anywhere along the way, the
   loop has converged: report the cycle as complete. Otherwise, the next
   invocation of this skill starts a new pass picking up where the last one
   stopped.

## Reporting

After each pass, report:
- which stage(s) you scanned and what gaps you found in each
- the one gap you fixed and how
- the wire-verifier's verdict on the wire you just crossed
- whether you advanced, and if not, exactly which wire is still broken
