# Strategy d: agentic-reliability dispatch

For wires whose contract concerns the reliability of an *autonomous-fix
loop itself* -- retry bounds, escalation paths, tool scope creep -- rather
than the correctness of the fix's output.

## Exact dispatch target

Dispatch the skill **`zeugnis:zeugnis-agentic-reliability`** by exact name.
Do **not** dispatch a similarly-named but wrong target such as
`zeugnis:zeugnis-agentic-reliability-auditor` -- that name does not exist in
the `zeugnis` plugin and is a common typo-shaped mistake to avoid.

If only the agent `zeugnis:agentic-reliability-auditor` resolves (the skill
itself unavailable), you **may** fall back to dispatching that agent
directly, but you must still have attempted the skill dispatch first and
note in the evidence doc that this run used the agent fallback, not the
preferred skill path.

Confirm the name before dispatching, in code, not by re-reading this
paragraph:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py" check-strategy-d-target "<dispatch_name>" [--used-fallback]
```

This raises on anything other than the exact preferred name (or, with
`--used-fallback`, anything other than the exact fallback agent name) --
including the specific typo `zeugnis:zeugnis-agentic-reliability-auditor`.

## Prerequisite and degradation

Prerequisite: the `zeugnis` plugin installed with the
`zeugnis-agentic-reliability` skill (or, as fallback, the
`agentic-reliability-auditor` agent) present. If neither resolves, this
strategy is unavailable for this wire -- report that plainly and let
`andon-verify`'s classifier route to the next applicable strategy per
`wire-classifier.md`'s graceful-degradation order. Do not attempt to
reimplement agentic-reliability auditing logic inline here; that duplicates
strategy logic this reference doc explicitly delegates elsewhere.

## What the dispatched skill/agent evaluates

Retry/repeat bounds actually enforced in code (not just documented), presence
of an escalation path when an autonomous loop can't make progress, and
whether tool access granted to the autonomous loop matches its stated role
(no scope creep). Feed it the wire's contract and the specific autonomous
loop's definition (workflow script, agent file, or skill) under review.

## Verdict mapping

Use the dispatched skill/agent's own verdict categories, translated to
`green`/`red`/`unknown`:

- Explicit reliability defect found (unbounded retry, no escalation path,
  scope mismatch) -> `red`.
- Clean bill of health against all checked criteria -> `green`.
- Skill/agent could not reach a verdict (e.g. the loop under review has no
  clear termination condition to evaluate) -> `unknown`.

## Untrusted content and NO-PERSONA

Fence and mask any workflow-script or agent-definition source you quote into
the dispatch prompt. The dispatched skill/agent's findings must trace to
observable code properties (a retry counter, a catch block, a tool
allowlist) -- never to a named person's general reputation for writing
reliable agents.
