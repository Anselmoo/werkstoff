---
name: compass-explore-branches
description: This skill should be used when a task has multiple genuinely viable approaches and the risk of anchoring on the first idea matters — the user asks to "explore different approaches", "what are my options here", "don't just go with the first idea", "compare a few strategies before we commit", or a scoped problem (from compass-clarify-scope, or compass-solve's Explore stage) needs a decision among distinct paths rather than a single obvious next step. Not for tasks with only one reasonable approach, or for expanding an already-chosen approach into stages (that is compass-decompose-chain's job).
---

Generate several genuinely distinct approaches to a scoped problem, score
each one, and select the best — rather than expanding and committing to
whichever approach came to mind first. This is Tree-of-Thoughts, generalized
from strategic planning to any complex decision with meaningful tradeoffs
(built on `../../references/knowledge/tree-of-thoughts.md`'s
three-phase generate-branches / score-branches / select-and-expand
structure — see `../../references/knowledge/index.md`). See
`../../references/constraints.md` for the context-rot and
plausible-vs-verified constraints that apply across every `compass-*` skill.

This skill's own methodology stops at selection — it does not expand the
winning branch into concrete stages or actions. That expansion is
`compass-decompose-chain`'s job (the source template's own "Phase 3 —
expand" content), kept separate so the two skills aren't duplicating each
other's methodology.

## Step 0 — Confirm the scoped problem and branch count

This skill needs a `scopedProblem`: a well-scoped problem statement, usually
produced by `compass-clarify-scope`. If invoked standalone with no prior
scoping step, ask for (or construct from the immediate conversation) a
problem statement concrete enough that "genuinely distinct approaches" is a
meaningful question — a problem so vague that every approach would just be a
restatement of the same idea should go through `compass-clarify-scope`
first instead.

Default `branchCount` to 3 (or `.claude/compass.local.md`'s
`branch_count`, if that file exists and sets it), matching the source
template's Branch A/B/C. Use a different count only when the user
explicitly asks for more or fewer options, or the scoped problem's own
complexity clearly warrants it (cap at 6, or `.claude/compass.local.md`'s
`max_branch_count` if lower — see the workflow's angle pool).

Unlike `self-assess`/`quality`, `compass` has no `output_dir` — every
`compass-*` skill (including this one) returns its result into the
conversation rather than writing a persistent artifact. An optional
`.claude/compass.local.md` may still exist for `branch_count`/
`max_branch_count` overrides (see above); there is nothing else to load
here beyond the inputs above and that one optional file.

## Step 1 — Run the exploration

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/explore-branches-scan.js",
  args: { scopedProblem: "<scoped problem statement>", branchCount: <default 3>, _contractVersion: "compass-contract-v1" }
})
```

It runs a **Propose** phase — `branchCount` `branch-proposer` agents in
parallel, each assigned a distinct angle (conservative/incremental,
ambitious/reimagine, resource-minimal/pragmatic, and further named angles
beyond 3) so the branches are forced apart rather than converging on the
same safe middle ground — then a **Score** phase — one `branch-proposer`
agent per branch (a separate dispatch from the one that proposed it) scores
Feasibility, Impact, and Risk 1-10 each and names the branch's biggest
blocker. Selection then runs **deterministically in the workflow script
itself**: highest total (the three raw dimension scores summed, Risk not
inverted, matching the source template's own Total row), ties broken by
lower risk — mirroring `stage-map-scan.js`'s pattern of doing the actual
decision in plain JS after the agent-driven phases hand off structured data,
never asking an agent to also pick the winner. The proposer/scorer agents
are read-only by design.

**Fallback** (no Workflow tool) — spawn `branchCount` **branch-proposer**
subagents directly in parallel via the Agent tool, one per angle (see
`workflows/explore-branches-scan.js`'s `ANGLE_POOL` for the exact angle
briefs if reconstructing them), each producing one `{name, description}`
branch. Then dispatch one more subagent per branch (or score them yourself)
using the identical Feasibility/Impact/Risk/blocker rubric. Compute each
branch's total yourself (sum of the three raw scores) and select the
highest, breaking ties by lower risk — the same deterministic rule the
workflow script applies, done by hand instead of in JS.

## Step 2 — Present branches, selection, and rationale

Present, in this order:

1. **Branches** — each branch's name and description.
2. **Scores** — a table: branch, Feasibility, Impact, Risk, Total, biggest
   blocker.
3. **Selected branch** and the **rationale** (why it beat the alternatives,
   including the tie-break note if one applied).

If continuing within `compass-solve`'s pipeline (its Explore stage), hand
the selected branch's `description` to `compass-decompose-chain` as that
skill's input contract for its Decompose stage. If running standalone,
suggest `compass-decompose-chain` as the natural next step for turning the
selected branch into concrete, verifiable stages.

## Optional — render an interactive trace

`compass` has no `output_dir`/settings file, so this is opt-in
visualization, not a required report — offer it, don't gate on it. After
presenting Step 2, optionally render the workflow's result (the object
returned in Step 1: `{branches, selected, rationale, ...}`) as an
interactive branch diagram via
`${CLAUDE_PLUGIN_ROOT}/assets/reasoning-trace-viewer.html`, using the same
injection approach `self-assess-stage-map` uses for `topology-viewer.html`
(JSON-safe-escape `<`/`>`/`&` before injecting into the `<script>` block —
do not reimplement that escaping ad hoc):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/render_trace.py" \
  "${CLAUDE_PLUGIN_ROOT}/assets/reasoning-trace-viewer.html" <output-path> <<'JSON'
<the workflow's actual JSON result, verbatim>
JSON
```

Pick a reasonable `<output-path>` (a scratch/tmp file, or a path the user
suggests). If it renders, tell the user they can view the reasoning trace
interactively at that path — never present this as a required step.
