---
name: self-assess-transform-execute
description: This skill should be used when the user explicitly asks to "execute phase N from the modernization brief", "apply this transform phase", or "run the merge/split transform-execute proposed". Applies exactly one human-authorized phase from MODERNIZATION_BRIEF.md, gated behind transform.mode="execute", a clean tree, and every Open Question resolved -- then hands off to andon-verify without self-verifying.
---

# self-assess-transform-execute

Apply one, and only one, already-authorized phase's structural change from
`MODERNIZATION_BRIEF.md`. This is the plugin's most dangerous skill -- every gate below is a
hard refusal, not a suggestion, and every one of them is enforced by the CLI, not by this
document's prose.

## Step 1: The mode gate -- refuse outright in 'plan' mode

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py transform-mode-gate --repo <repo_root> --phase <N>
```

A non-zero exit here means either `transform.mode` is not `"execute"` in
`.claude/self-assess.local.md`, or phase `<N>` is not listed in
`transform.authorized_phases`. In either case: stop immediately, tell the user plainly what
setting is required, and do not proceed under any circumstance -- there is no override flag for
this gate.

## Step 2: Read the brief and reject a Keep(1:1) phase

Read `MODERNIZATION_BRIEF.md` and `transform_brief_summary.json` for phase `<N>`'s recorded
`decision`:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py keep-phase-gate --decision "<phase N's decision>"
```

A `Keep` or `Keep(1:1)` decision has nothing to execute -- refuse and tell the user this phase
requires no structural change.

## Step 3: Every Open Question for this phase must be resolved by a human

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py open-questions-gate --open-questions <json list from the brief's phase N> --resolutions <json map the user has provided>
```

If any Open Question lacks a resolution, this call refuses -- ask the user directly for each
missing resolution (do not guess a design judgment call on the user's behalf) and re-run once
answers are in hand.

## Step 4: Dirty-tree gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py dirty-tree-gate --repo <repo_root>
```

Add `--allow-dirty` only when the user has set `require_clean_tree: false` in
`.claude/self-assess.local.md` AND you have told them plainly what changed paths exist. A
non-zero exit with a dirty tree and no override means: stop, show the user the changed paths,
and ask them to commit, stash, or explicitly confirm proceeding anyway.

## Step 5: Dispatch transform-executor

Only after all four gates above pass, dispatch the `transform-executor` agent with exactly
phase `<N>`'s decision, its declared stage scope, and its (now-resolved) Open Questions. The
agent refuses to touch files outside that stage scope and refuses a second phase in the same
dispatch -- one phase, one dispatch.

## Step 6: Hand off to verification -- never self-verify

Rule `verify-dispatch-handoff`: this skill's own edit is unverified the moment it lands. Do not
run any check of its own correctness here. Explicitly tell the user: "This change is
unverified -- hand off to `andon:andon-verify` for an independent adversarial tribunal, or to
`andon:andon-loop` if you want the proof recorded in an OKF ledger." Then stop.

## Never commit or push

This skill has no code path that invokes `git commit` or `git push` -- integrating the change
into history stays a manual human decision, always.
