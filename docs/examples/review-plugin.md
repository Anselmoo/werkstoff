# Review a plugin

Measured evidence for the `review-plugin` case. Fired in 1 of 4 runs -- the prompt is underdetermined, which is a finding about the prompt, not a plugin failure.

| mode | model | run | outcome | skills fired | hook denials | mode denials | diff | cost | time |
|---|---|---|---|---|---|---|---|---|---|
| `plan` | haiku | #1 | **FAIL** | -- | 0 | 2 | 0 B | $0.48 | 149s |
| `plan` | haiku | #2 | **FAIL** | -- | 0 | 1 | 0 B | $0.48 | 140s |
| `plan` | sonnet | #1 | **FAIL** | -- | 0 | 0 | 0 B | $0.30 | 101s |
| `plan` | sonnet | #2 | **PASS** | `nacharbeit:nacharbeit-preflight`, `nacharbeit:nacharbeit-lint` | 0 | 0 | 0 B | $0.52 | 135s |

**Why the failing runs failed**

- expected skill(s) never fired: nacharbeit:nacharbeit-lint

**What the permission mode refused** -- 3 call(s), tool(s): `Bash`. One verbatim:

> Permission to use Bash has been denied because Claude Code is running in don't ask mode. IMPORTANT: You *may* attempt to accomplish this action using other tools that might naturally be used to accomplish this goal, e.g. using head instead of cat. But you *should not* attempt to work around this den

**What the run said** (`plan`, haiku, run #1)

> No ExitPlanMode tool is available in this session, and the budget is nearly exhausted, so I'll present the finished review directly. ## Review of the `toy-check` plugin against skill/manifest standards The plugin is deliberately minimal (per its own README), but checked against Claude Code's plugin.json/SKILL.md standards, here's what's wrong: 1. **`SKILL.md` `description` is non-compliant.** "A skill that checks things in the repository and reports what it finds" names no domain and no trigger 

---

*Recorded 2026-09-14 from wf-2026-09-14-acceptedits, wf-2026-09-14-plan, wf-2026-09-14-plan-sonnet with 2.1.236 (Claude Code). Every number above comes from a cell record; regenerate with `test/workflows/curate.py`.*
