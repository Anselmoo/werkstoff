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

## Preferred path: the workflow
When the Workflow tool is available, run
`${CLAUDE_PLUGIN_ROOT}/workflows/explore-branches.js`
(args `{ problem, requestedBranches?, maxBranchCount? }`). It dispatches one
`branch-proposer` agent per angle in parallel (propose), scores each in a separate
comparison-free dispatch, and selects the winner — all bounds enforced in code.

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

### 5. Persist (so a later `compass-solve` can reuse this)

Generate a run id (`python3 -c "import uuid; print(uuid.uuid4())"`), then write:

```
echo '{
  "run_id": "<run-id>",
  "raw_task": "<the exact `problem` text you were given>",
  "phase": "Explore",
  "explore_ran": true,
  "explore": {"branches": [<the same scored branches from step 3>]}
}' | $GUARD state-write - --output-dir .compass --to runs/<run-id>/state.json
```

`raw_task` here is the `problem` text this invocation actually scored branches for.
A later `compass-solve` run only reuses this if its own Explore step is about to
score branches for that **exact same text** (see `compass-solve`'s own "Reuse a
prior run" step) — matching is byte-for-byte, never fuzzy.

## Output
- branches (name + description)
- scores table: branch, Feasibility, Impact, Risk, Total, biggest blocker
- selected branch name + rationale
