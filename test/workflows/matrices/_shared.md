# Matrix templates

Committed with **placeholders, never absolute paths**: `${FIXTURE:<name>}`,
`${REPO_PLUGIN:<name>}`, `${PLUGIN:<installed name>}`. `../build_matrices.py --out <dir>`
resolves them for this machine and writes the result under `analysis/`, which is gitignored.

Every template sets `runner: "subrun"`, so each cell runs under the clean box, the isolation
self-check and the fixture seeding that `plugins/arbeitsplan/scripts/subrun.py` provides.

`disallowed_tools` is set explicitly in each template. The runner's built-in default strips
`Read`/`Write`/`Bash`/`Agent`, which is right for a one-shot routing probe and wrong for a real
workflow — a cell that cannot read or write cannot do the task being measured.

**The control template is not a spare copy.** `plan-haiku-control` runs the same prompts with no
plugins loaded and asserts, via `forbid_skills`, that the workflow skills do not fire. A PASS
there means the control is clean; a FAIL means a name resolved with the plugin absent, which
would make every "the plugin fired" result in the enabled arm meaningless.
