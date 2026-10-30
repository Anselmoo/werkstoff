# zeugnis-142-mutmut-run-working-tree

Reproduces issue #142's guard premise: the probe repository has `analysis/zeugnis/`
(so the hook is active), and the Bash command runs `mutmut run` in the working tree.

## old=allow (the defect)

At base `9a80186`, `guard_bash_scope.py` denied only `mutmut apply` and `--patch`
and allowed `mutmut run` as a "default dry/report mode" (its docstring said so).
mutmut 3 has no such mode: `run` creates `./mutants/` in the cwd and resumes any
leftover state there (checked against mutmut 3.8.1). The guard allowed a command
that writes into the repository and silently reuses stale results.

## new=deny (the fix)

The fixed guard allows a copy-only verb only when the command's effective cwd is
inside a marker-bearing `git archive` copy under `analysis/zeugnis/mutation/<runId>/`
(`lib.mutation_scope.copy_root_for`). The probe's cwd is the repository root, which
is not one, so the run is denied with a pointer to `scripts/mutation_harden.py`.
Its pair, `zeugnis-142-heredoc-mentions-mutmut`, must stay allowed: the fix closes a
hole without gating every mention of the tool.
