# Which workflow fits?

Measured evidence for the `routing` case. Fired in 1 of 4 runs -- the prompt is underdetermined, which is a finding about the prompt, not a plugin failure.

| mode | model | run | outcome | skills fired | hook denials | mode denials | diff | cost | time |
|---|---|---|---|---|---|---|---|---|---|
| `plan` | haiku | #1 | **FAIL** | -- | 0 | 2 | -- | $0.34 | 94s |
| `plan` | haiku | #2 | **FAIL** | -- | 0 | 2 | -- | $0.32 | 88s |
| `plan` | sonnet | #1 | **FAIL** | -- | 0 | 0 | -- | $0.12 | 18s |
| `plan` | sonnet | #2 | **PASS** | `arbeitsplan:arbeitsplan-start` | 0 | 0 | -- | $0.40 | 271s |

**Why the failing runs failed**

- expected skill(s) never fired: arbeitsplan:arbeitsplan-start

**What the permission mode refused** -- 4 call(s), tool(s): `Bash`. One verbatim:

> find in '/' was blocked. For security, Claude Code may only search files in the allowed working directories for this session: '/private/var/folders/pb/1z5lx35d7y99w8rsvn2t6z8r0000gp/T/arbeitsplan-cell-i9zfqjmu'.

**What the run said** (`plan`, haiku, run #1)

> The working directory is empty and not yet a git repository — so before anything else, that needs `git init` (+ an initial commit), since arbeitsplan's builder agents each work in their own git worktree. For "which arbeitsplan workflow fits": **`arbeitsplan-start`** is the entry point — run that first with a description of the feature. From there the pipeline is: 1. `arbeitsplan-start` — kicks off the run for your feature 2. `arbeitsplan-patterns` — picks the agentic shape (fan-out/build-referee

---

*Recorded 2026-09-14 from wf-2026-09-14-acceptedits, wf-2026-09-14-plan, wf-2026-09-14-plan-sonnet with 2.1.236 (Claude Code). Every number above comes from a cell record; regenerate with `test/workflows/curate.py`.*
