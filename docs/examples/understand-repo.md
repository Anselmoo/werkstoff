# Understand an unfamiliar repo

Measured evidence for the `understand-repo` case. Fired in 2 of 4 runs -- the prompt is underdetermined, which is a finding about the prompt, not a plugin failure.

| mode | model | run | outcome | skills fired | hook denials | mode denials | diff | cost | time |
|---|---|---|---|---|---|---|---|---|---|
| `plan` | haiku | #1 | **PASS** | `befund:befund-stage-map` | 0 | 0 | 0 B | $0.26 | 61s |
| `plan` | haiku | #2 | **FAIL** | -- | 0 | 0 | 0 B | $0.24 | 65s |
| `plan` | sonnet | #1 | **FAIL** | -- | 0 | 0 | 0 B | $0.35 | 97s |
| `plan` | sonnet | #2 | **PASS** | `befund:befund-stage-map` | 0 | 0 | 0 B | $0.40 | 95s |

**Why the failing runs failed**

- expected skill(s) never fired: befund:befund-stage-map

**What the run said** (`plan`, haiku, run #1)

> Full picture confirmed — that's every import in the repo. Here's the real module map, in a repo that turns out to be a small, deliberately booby-trapped teaching example. ## Modules (5 files, one package) | Module | Role (per docstring) | Imports out | |---|---|---| | `pipeline/__init__.py` | package marker | none | | `pipeline/ingest.py` | Stage 1: read raw records | none | | `pipeline/normalize.py` | Stage 2: normalize records | `pipeline.score` | | `pipeline/score.py` | Stage 3: score records

---

*Recorded 2026-09-14 from wf-2026-09-14-acceptedits, wf-2026-09-14-plan, wf-2026-09-14-plan-sonnet with 2.1.236 (Claude Code). Every number above comes from a cell record; regenerate with `test/workflows/curate.py`.*
