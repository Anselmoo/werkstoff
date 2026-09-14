# Measured examples

Nothing in the approved-workflow docs is documented until it has been run. These pages are the runs: real `claude -p` cells over the synthetic fixtures in `test/workflows/fixtures/`, each in its own clean box, recorded by `plugins/arbeitsplan/scripts/subrun.py`.

| case | cells | expected skill fired | caveat |
|---|---|---|---|
| [Build a feature](build-feature) | 6 | 0/6 | see the page |
| [Design a UI](design-ui) | 4 | 0/4 | see the page |
| [Fix a bug](fix-bug) | 6 | 5/6 | -- |
| [Plan mode under an open run-scope lock](hazard-plan-under-lock) | 4 | 4/4 | see the page |
| [Review a plugin](review-plugin) | 4 | 1/4 | -- |
| [Which workflow fits?](routing) | 4 | 1/4 | -- |
| [Understand an unfamiliar repo](understand-repo) | 4 | 2/4 | -- |

Total recorded spend across these cells: $10.74. A cell that could not be measured fairly is scored `UNMEASURED` and excluded from every denominator; none of the cells here were.

*Recorded 2026-09-14 from wf-2026-09-14-acceptedits, wf-2026-09-14-plan, wf-2026-09-14-plan-sonnet with 2.1.236 (Claude Code). Every number above comes from a cell record; regenerate with `test/workflows/curate.py`.*
