# plan-under-lock

`toy-pipeline`, plus one extra thing: an **open arbeitsplan run-scope lock** at
`analysis/arbeitsplan/run_scope.json`.

While that lock exists, arbeitsplan's `PreToolUse` guard denies any write outside the declared
`writeScope` -- including a path that resolves outside the repository, which is where the
plan-mode plan file lives. This fixture exists to measure that interaction rather than assert it
from reading hook source.
