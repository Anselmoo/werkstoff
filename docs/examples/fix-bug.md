# Fix a bug

Measured evidence for the `fix-bug` case. Fired in 5 of 6 runs -- the prompt is underdetermined, which is a finding about the prompt, not a plugin failure.

| mode | model | run | outcome | skills fired | hook denials | mode denials | diff | cost | time |
|---|---|---|---|---|---|---|---|---|---|
| `acceptEdits` | sonnet | #1 | **PASS** | `superpowers:systematic-debugging`, `run` | 0 | 14 | 400 B | $0.42 | 101s |
| `acceptEdits` | sonnet | #2 | **PASS** | `superpowers:systematic-debugging` | 0 | 4 | 0 B | $0.21 | 41s |
| `plan` | haiku | #1 | **PASS** | `superpowers:systematic-debugging` | 0 | 1 | 0 B | $0.27 | 42s |
| `plan` | haiku | #2 | **FAIL** | -- | 0 | 1 | 0 B | $0.24 | 48s |
| `plan` | sonnet | #1 | **PASS** | `superpowers:systematic-debugging` | 0 | 0 | 0 B | $0.27 | 44s |
| `plan` | sonnet | #2 | **PASS** | `superpowers:systematic-debugging` | 0 | 0 | 0 B | $0.25 | 47s |

**Why the failing runs failed**

- expected skill(s) never fired: superpowers:systematic-debugging

**What the permission mode refused** -- 20 call(s), tool(s): `Bash`, `Edit`. One verbatim:

> cd in '/private/var/folders/pb/1z5lx35d7y99w8rsvn2t6z8r0000gp-T-arbeitsplan-cell-stxcy3hj' was blocked. For security, Claude Code may only change directories to the allowed working directories for this session: '/private/var/folders/pb/1z5lx35d7y99w8rsvn2t6z8r0000gp/T/arbeitsplan-cell-stxcy3hj'.

**What the run said** (`acceptEdits`, sonnet, run #1)

> Running `python3` requires approval that isn't being granted in this session (plain shell commands like `echo` work fine, but any `python3` invocation is being blocked). I don't want to keep retrying the same blocked call. Could you approve a `python3 -m unittest test_stats -v` run, or let me know if Python execution is intentionally restricted here so I can verify the fix another way?

---

*Recorded 2026-09-14 from wf-2026-09-14-acceptedits, wf-2026-09-14-plan, wf-2026-09-14-plan-sonnet with 2.1.236 (Claude Code). Every number above comes from a cell record; regenerate with `test/workflows/curate.py`.*
