# Strategy d — "Did the autonomous fix stay reliable" wire

For wires where the concern is not the fix's *correctness* but its
*process reliability* as an agentic loop — did the autonomous fix that
was just applied introduce an unbounded retry, leave itself with no
escalation path, or grant itself more tool access than the task needed.
This strategy is a direct cross-plugin dispatch, not a reimplementation.

## Dispatch target — the exact, correct name

Dispatch the skill **`confab:confab-agentic-reliability`** via the
`Skill` tool.

**Do not write `confab:confab-agentic-reliability-auditor`** — that
name does not exist. It was a drafting error caught during this plugin's
design and is called out here explicitly so it is never reintroduced.
The underlying **agent** (a separate, lower-level dispatch target) is
named `confab:agentic-reliability-auditor` (no `quality-` prefix
repetition, no `confab-agentic-reliability-` compound) — use the agent
name only if a direct agent dispatch is ever needed in place of the
skill; the skill is the normal entry point and already orchestrates the
agent internally per `plugins/confab/skills/confab-agentic-reliability/SKILL.md`.

## When this strategy fires

The gap or fix concerns an autonomous fix's own reliability as a process
— not ordinary application code. Concretely: `andon-loop` ran in `fix`
mode (see the personal `andon-loop` skill's mode concept, though this
plugin's `andon-loop` skill defaults to recommend-only per its own
SKILL.md) and just applied a change to a skill/agent/workflow definition
file, or the gap itself is "audit our own plugin reliability."

## Workflow

1. **Confirm `confab` is installed.** If the `confab:confab-agentic-reliability`
   skill does not resolve, degrade gracefully: report strategy d as
   unavailable for this wire, and if a plugin-reliability concern still
   needs checking, fall back to a plain-text description of the four
   anti-pattern categories (unbounded retry loops, no escalation path,
   Find-phase-with-no-Verify-wiring, excessive tool grants) as a manual
   checklist for the user — never silently skip the concern, and never
   reimplement `confab-agentic-reliability`'s own scan logic here.
2. **Dispatch.** Invoke the skill with the scope narrowed to the
   specific skill/agent/workflow file(s) the fix touched — do not trigger
   a whole-repo sweep for a single-wire proof unless the gap itself is
   "audit everything."
3. **Map the result to a wire verdict.** Any High-severity finding on the
   touched file(s) → 🔴. Medium/Low-only findings, or zero findings → 🟢.
   The skill's own `AGENTIC_RELIABILITY.md` and
   `agentic_reliability_summary.json` are the evidence artifact — link
   them from this wire's OKF evidence doc (`resource` field) rather than
   re-deriving a summary.

## Relationship to strategy g

Strategy d asks "is this agent/skill/workflow reliable as a process."
Strategy g asks "does the test that proves some other wire actually
assert anything." They can both apply to the same fix (e.g. a fix that
both touched an agent definition *and* added a wired test for it) — run
both when both questions are live; neither substitutes for the other.
