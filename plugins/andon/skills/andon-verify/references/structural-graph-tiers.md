# Strategy e — Structural/connectivity wire: three-tier fallback

For wires that are a **code-structure claim**: does stage A's exported
symbol actually get referenced by stage B, is this the only caller, did
a rename propagate everywhere. Reference vocabulary is Kythe's schema
(nodes/edges/facts: `anchor`, `defines`, `ref`, `ref/call`, `childof`) —
SCIP (Sourcegraph) and LSIF are lighter, more-commonly-actually-installed
siblings in the same family and are equally valid Tier 1 sources.

## This is the plugin's one genuinely hard, non-overridable gate

Every other strategy's verdict can, in principle, be revisited by a human
or re-adjudicated. **Tier 1 evidence under this strategy cannot** — a
real structural-index contradiction is stop condition 3 of `andon-loop`'s
andon rule, and it is the *only* one of the three stop conditions the
Adjudicator (strategy a) cannot waive. This asymmetry is deliberate: a
real index query is ground truth about what the code actually references,
not an argument about it.

## Tier 1 — Hard (non-overridable)

**Trigger:** a real Kythe, SCIP, or LSIF index is available for the
repo (built and queryable — not just the tool installed, an actual
generated index).

**Procedure:** query the index directly for the claimed edge (e.g. "does
symbol X in stage A have a `ref`/`ref/call` edge from any symbol in stage
B"). Report the query and its raw result.

**Verdict:**
- Index confirms the edge exists as claimed → 🟢, Tier 1 confidence.
- Index contradicts the claim (edge doesn't exist, or exists but not as
  claimed — e.g. the "only caller" claim is false because the index
  shows a second caller) → 🔴, **automatic stop, non-overridable**. Not
  even the strategy a Adjudicator can waive this. Escalate to the user
  directly; do not let `andon-loop` advance past it under any
  circumstance.

## Tier 2 — Soft-hard (blocking but logged as lower confidence)

**Trigger:** no persistent index available, but the `LSP` tool (a
deferred Claude Code tool — see `ToolSearch` for `select:LSP` if it needs
loading) is available in-session.

**Procedure:** use go-to-definition / find-references from a real
language server against the claimed edge.

**Verdict:** same pass/fail logic as Tier 1, but explicitly logged as
**Tier 2 confidence** in the evidence doc's `tags` (`tier:2`). Still
blocking (a red result still halts the loop the same way condition 3
would at Tier 1) — but *is* overridable by an Adjudicator (strategy a)
review if there's a specific reason to doubt the LSP result (e.g. a
known indexing gap for the language in question), unlike Tier 1.

## Tier 3 — Soft (advisory / non-blocking only)

**Trigger:** neither a persistent index nor the `LSP` tool is available.

**Procedure:** dispatch the `self-assess:stage-mapper` **agent** directly
(cross-plugin reuse — not the `self-assess-stage-map` skill, the agent
itself, in its Verify-protocol mode per
`plugins/self-assess/agents/stage-mapper.md`) for a grep/read-based
extraction of the claimed edge.

**Verdict:** **must be explicitly labeled advisory/non-blocking** in the
output — a Tier 3 result never halts the loop on its own and must never
be presented as if it carries Tier 1/2 confidence. If `self-assess` is
not installed either, strategy e reports itself unavailable for this
wire entirely (per the graceful-degradation discipline — this never
hard-fails `andon-loop`'s overall run, only this one strategy for this
one wire) and `andon-loop` should route the gap to a different
applicable strategy, or note the structural claim as genuinely
unverified (⚪) rather than fabricating confidence.

## Tier selection is automatic, not a choice

Always attempt Tier 1 first, then Tier 2, then Tier 3 — never skip a
higher tier because a lower one is more convenient. The evidence doc
records which tier actually ran (`tags: ["tier:N"]`) so `andon-status`
and any human reviewer can see at a glance how much confidence to place
in a given structural wire's green/red status.

## Edge vocabulary (for whichever tier is used)

| Term | Meaning |
|---|---|
| `anchor` | A source-range reference point. |
| `defines` | A symbol's declaration site. |
| `ref` | A reference to a symbol (import, use). |
| `ref/call` | A resolved cross-file function/symbol call — stronger signal than a bare `ref`. |
| `childof` | Hierarchical membership (a file belongs to a package/module) — a clustering hint, not a dependency. |

This matches the vocabulary `self-assess:stage-mapper` already uses
(see `plugins/self-assess/agents/stage-mapper.md`'s "Classify each
edge's `kind`" step) — Tier 3 output is directly comparable to Tier 1/2
results in shape, just weaker in confidence.
