# Design a UI

Measured evidence for the `design-ui` case. The expected skill never fired, in 4 runs. 2 run(s) fired some other skill.

| mode | model | run | outcome | skills fired | hook denials | mode denials | diff | cost | time |
|---|---|---|---|---|---|---|---|---|---|
| `plan` | haiku | #1 | **FAIL** | -- | 0 | 0 | 0 B | $0.19 | 73s |
| `plan` | haiku | #2 | **FAIL** | -- | 0 | 0 | 0 B | $0.37 | 107s |
| `plan` | sonnet | #1 | **FAIL** | `cupertino:cupertino-council` | 0 | 0 | 0 B | $0.28 | 79s |
| `plan` | sonnet | #2 | **FAIL** | `cupertino:cupertino-council` | 0 | 0 | 0 B | $0.43 | 265s |

**Why the failing runs failed**

- expected skill(s) never fired: cupertino:cupertino-backwards

**What the run said** (`plan`, haiku, run #1)

> Now that I've read the brief and the current markup, here's what I'd change and why before touching anything. ## What's wrong with the current attempt **It ignores the brief's core ask** — "one designed object rather than four stacked rows." Right now it's literally: image → symbol → name → dl(number/mass) → button, each its own block with no visual relationship. Nothing ties the atomic data together the way an actual periodic-table tile does. **Contrast is broken, not just "ad hoc."** `#999`/`#

Both sonnet runs fired `cupertino:cupertino-council` instead of the expected `cupertino-backwards`. The plugin is reached; the documented ordering (backwards first, then council) is not what the model picks.

---

*Recorded 2026-09-14 from wf-2026-09-14-acceptedits, wf-2026-09-14-plan, wf-2026-09-14-plan-sonnet with 2.1.236 (Claude Code). Every number above comes from a cell record; regenerate with `test/workflows/curate.py`.*
