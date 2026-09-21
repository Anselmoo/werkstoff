# Build a feature

Measured evidence for the `build-feature` case. The expected skill never fired, in 6 runs. 2 run(s) fired some other skill.

| mode | model | run | outcome | skills fired | hook denials | mode denials | diff | cost | time |
|---|---|---|---|---|---|---|---|---|---|
| `acceptEdits` | sonnet | #1 | **FAIL** | `superpowers:brainstorming` | 0 | 0 | 0 B | $0.22 | 36s |
| `acceptEdits` | sonnet | #2 | **FAIL** | -- | 0 | 8 | 839 B | $0.42 | 93s |
| `plan` | haiku | #1 | **FAIL** | -- | 0 | 3 | 0 B | $0.41 | 79s |
| `plan` | haiku | #2 | **FAIL** | -- | 0 | 1 | 0 B | $0.45 | 76s |
| `plan` | sonnet | #1 | **FAIL** | -- | 0 | 0 | 0 B | $0.46 | 85s |
| `plan` | sonnet | #2 | **FAIL** | `superpowers:brainstorming`, `superpowers:using-superpowers` | 0 | 0 | 0 B | $0.56 | 101s |

**Why the failing runs failed**

- expected skill(s) never fired: zirkel:zirkel-clarify-scope

**What the permission mode refused** -- 12 call(s), tool(s): `Bash`. One verbatim:

> This Bash command contains multiple operations. The following part requires approval: python3 -m unittest discover -s tests -t . 2>&1

**What the run said** (`acceptEdits`, sonnet, run #1)

> **Context:** The repo is a tiny `numerics` package (`kahan_sum` in `summation.py`). The README already specifies the task precisely: implement `logsumexp(values)` in `numerics/stable.py`, export it from `numerics/__init__.py`, and it must pass the existing (currently failing) `tests/test_logsumexp.py`. **Design:** - `numerics/stable.py`: `logsumexp(values: Iterable[float]) -> float` using the standard max-shift trick: materialize `values` into a list, find `m = max(values)`, return `m + log(sum(

`zirkel:zirkel-clarify-scope` did not fire in any run, across two models and two permission modes, with zirkel the only werkstoff plugin loaded and a prompt that says "scope the work before writing code". That is not a model-tier result: it points at the skill's own description.

---

*Recorded 2026-09-14 from wf-2026-09-14-acceptedits, wf-2026-09-14-plan, wf-2026-09-14-plan-sonnet with 2.1.236 (Claude Code). Every number above comes from a cell record; regenerate with `test/workflows/curate.py`.*
