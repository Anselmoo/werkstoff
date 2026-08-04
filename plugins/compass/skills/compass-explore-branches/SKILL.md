---
name: compass-explore-branches
description: >-
  Explores multiple genuinely-distinct approaches to a scoped problem in parallel,
  scores each on Feasibility/Impact/Risk, and selects a winner — so the work does
  not anchor on the first idea. Use when a task has more than one viable approach
  and picking the first that comes to mind would be a mistake: "what are our
  options here", "don't just do the obvious thing", "weigh a few approaches",
  "explore alternatives", or the Explore phase of compass-solve.
---

# compass-explore-branches

Generate branches **independently and in parallel**, score each **in isolation**,
then select by the fixed rule. Parallel independence is what prevents anchoring —
it is structural, not a suggestion.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## 0. Build or reuse the shared research snapshot

Before dispatching any `branch-proposer`, build (or reuse) compass's symbol-index
snapshot once, so every parallel proposer can query the same cached index instead
of each re-scanning the codebase independently:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_symbol_index.py" --repo-path . --plugin-name compass
```

This is a no-op if `analysis/compass/current.json`'s `source_fingerprint` already
matches the repo (see `references/parallel-safe-research-protocol.md`). Skip this
step for a repository well under roughly 50 tracked files, where the build's own
overhead may exceed what a direct `Grep` would cost — the script makes no such
size check itself, so this is your judgment call, not its.

## Preferred path: the workflow
When the Workflow tool is available, run
`${CLAUDE_PLUGIN_ROOT}/workflows/explore-branches.js`
(args `{ problem, requestedBranches?, maxBranchCount? }`). It dispatches one
`branch-proposer` agent per angle in parallel (propose), scores each in a separate
comparison-free dispatch, and selects the winner — all bounds enforced in code.

**Workflow scripts have no filesystem access.** The workflow returns
`{ branches, scores, selected, rationale }` in memory and stops there — it
cannot write `state.json` and cannot render a report. **You must still run
the Persist and Render steps below yourself** after it returns; skipping them
because "the workflow already did the work" silently drops both the
persisted run and its report, the same "ends without a trace" failure the
Manual path would have if its own step 5 were skipped.

## Manual path

### 1. Decide the branch count (guarded)
`echo '{"requested":<n or null>,"max_branch_count":<from config or null>}' | $GUARD branch-cap -`
- **Default is 3 branches.** The cap is **min(6, `max_branch_count`)** where
  `max_branch_count` comes from `.claude/compass.local.md` if present. The guard
  returns the effective `cap`; produce exactly that many.

### 2. Propose in parallel
Dispatch one `branch-proposer` agent per angle (conservative/ambitious/pragmatic/…)
**in a single message so they run concurrently and never see each other.** Each
commits fully to its angle. Do not score here.

### 3. Score each in isolation
Dispatch scoring separately — a proposer never scores its own branch, and no
scorer compares branches. Each returns Feasibility, Impact, Risk (each **1-10**)
and its biggest blocker.

### 4. Select (guarded)
```
echo '{"branches":[
  {"name":"A","feasibility":7,"impact":8,"risk":4,"biggest_blocker":"…"},
  {"name":"B","feasibility":6,"impact":9,"risk":6,"biggest_blocker":"…"}
]}' | $GUARD branch-scores -
```
The guard computes **Total = Feasibility + Impact + Risk (Risk NOT inverted)**,
selects the **highest total**, and **breaks ties by lower risk**. Use its
`selected` — do not re-derive the winner by hand.

## Persist (so a later `compass-solve` can reuse this, and so Render below has
something to render)

Regardless of which path produced the branches and scores above, generate a
run id (`python3 -c "import uuid; print(uuid.uuid4())"`), then merge each
branch's `description` (from Propose / step 2) back onto its scored object
(from Score+Select / step 3-4, or the workflow's `scores` array) **by name**
before writing — the guard does not require `description`, but the
branch-comparison report below does, and this is the only point where the
two ever meet:

```
echo '{
  "run_id": "<run-id>",
  "raw_task": "<the exact `problem` text you were given>",
  "phase": "Explore",
  "explore_ran": true,
  "explore": {"branches": [
    {"name":"A","description":"<A'\''s Propose description>","feasibility":7,"impact":8,"risk":4,"biggest_blocker":"…"},
    {"name":"B","description":"<B'\''s Propose description>","feasibility":6,"impact":9,"risk":6,"biggest_blocker":"…"}
  ]}
}' | $GUARD state-write - --output-dir .compass --to runs/<run-id>/state.json
```

`raw_task` here is the `problem` text this invocation actually scored branches for.
A later `compass-solve` run only reuses this if its own Explore step is about to
score branches for that **exact same text** (see `compass-solve`'s own "Reuse a
prior run" step) — matching is byte-for-byte, never fuzzy.

## Render the branch-comparison report

Every run that reaches Persist also gets a report — not optional, not gated on
being asked for one:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_branch_comparison_html.py" . \
    --run-id <run-id> \
    --template "${CLAUDE_PLUGIN_ROOT}/assets/branch-comparison-viewer.html" \
    --d3 "${CLAUDE_PLUGIN_ROOT}/assets/inline-d3.html" \
    --tokens "${CLAUDE_PLUGIN_ROOT}/assets/tokens.css"
```

This re-validates `runs/<run-id>/state.json` with the same guard `state-write`
used to accept it, recomputes Total and the winner from the 3 raw axes (never
trusts a stored field — none is persisted), and writes
`.compass/runs/<run-id>/branch-comparison.html`. Mention this path when
presenting the selected branch to the user.

## Output
- branches (name + description)
- scores table: branch, Feasibility, Impact, Risk, Total, biggest blocker
- selected branch name + rationale
- path to the rendered branch-comparison report
