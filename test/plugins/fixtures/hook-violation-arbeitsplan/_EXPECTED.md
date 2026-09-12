# Expected: DENY

`arbeitsplan_guard.py` is scope-conditional — it is inert in any repository with no
`analysis/arbeitsplan/run_scope.json`, which is every repository not currently executing a
compiled workflow. Probed with the generic fixture it therefore correctly **allows**, and the
prober would report that as a hook that does nothing.

This fixture puts one run in flight: phase `build`, kind `fanout-redundant`,
`sharedTreeWritable: false`. The prober's default target `src/api.py` is in the shared tree,
so the guard must deny it — during a fan-out every candidate writes only inside its own
worktree, and exactly one diff is applied afterwards by the calling skill. That is the
property which makes a merge conflict impossible here, so a guard that allowed this write
would have given up the plugin's central claim.
