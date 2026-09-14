# Academic example projects

Synthetic teaching fixtures. **None of these is werkstoff's own code, and no task here is
"fix a bug in werkstoff".** Each project is a small, self-contained example with one planted
property a workflow is expected to find or build.

A fixture is copied into a throwaway cell directory by `plugins/arbeitsplan/scripts/subrun.py`,
`git init`-ed there, and the cell's `git diff` afterwards is the evidence of what the workflow
actually did. Nothing here is imported by the repository's own code.

| fixture | planted property | the workflow it exercises |
|---|---|---|
| `numerics-greenfield/` | `logsumexp` is missing; its test suite fails until someone writes it | Build a feature |
| `toy-pipeline/` | a real import cycle between `normalize` and `score` | Understand a repo |
| `median-seeded/` | `median()` is off by one on even-length input; a test pins the correct answer | Fix a bug |
| `element-card-ui/` | an image with no `alt`, and raw hex colours instead of tokens | Design UI |
| `toy-plugin/` | a SKILL.md whose description says what it *is*, never when to use it | Review a plugin |
| `plan-under-lock/` | an open `run_scope.json`, so a write outside the scope is denied | The plan-file hazard |

`verify_fixtures.py` asserts every planted property is still mechanically detectable. A fixture
whose defect has been accidentally fixed would make a sweep measure nothing, and that check is
what stands between this set and a green run over an empty instrument.
