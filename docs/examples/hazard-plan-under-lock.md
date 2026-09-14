# Plan mode under an open run-scope lock

Measured evidence for the `hazard-plan-under-lock` case. Fired as intended in every run (4/4).

| mode | model | run | outcome | skills fired | hook denials | mode denials | diff | cost | time |
|---|---|---|---|---|---|---|---|---|---|
| `plan` | haiku | #1 | **PASS** | -- | 0 | 0 | 0 B | $0.18 | 29s |
| `plan` | haiku | #2 | **PASS** | -- | 0 | 0 | 0 B | $0.33 | 77s |
| `plan` | sonnet | #1 | **PASS** | -- | 0 | 0 | 0 B | $0.22 | 51s |
| `plan` | sonnet | #2 | **PASS** | -- | 0 | 0 | 459 B | $0.36 | 70s |

**What the run said** (`plan`, haiku, run #1)

> I don't have a clarifying-question tool available in this environment, so I'll ask directly in text. What kind of change to the scoring stage did you have in mind? A few plausible directions given what's there: 1. **Add/adjust a weight** — e.g., support a new field beyond `mass`/`charge`, or change the weighting values. 2. **Change the aggregation** — e.g., weighted sum/average instead of plain `sum(record.values())` after normalization (right now weights are applied in `normalize`, then just su

**These PASSes are vacuous, and the page says so rather than counting them.** The cells attempted no write at all -- only Read, Bash and ToolSearch -- so the guard they exist to exercise was never reached, and `hook denials` is 0 for a reason that has nothing to do with the guard working. The real evidence for this hazard is `test/workflows/evidence/plan-file-under-lock.md`, reproduced deterministically by `bash test/workflows/reproduce_hazard.sh` in under a second. A case whose outcome does not depend on the thing it measures is a case that needs a better prompt.

---

*Recorded 2026-09-14 from wf-2026-09-14-acceptedits, wf-2026-09-14-plan, wf-2026-09-14-plan-sonnet with 2.1.236 (Claude Code). Every number above comes from a cell record; regenerate with `test/workflows/curate.py`.*
