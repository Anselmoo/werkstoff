---
description: Where does harmonization of this area stand — artifact inventory, staleness, next step
argument-hint: <area-dir>
---

Report where harmonization of `$1` stands, in one screen. Read-only —
inspect, never modify.

## 1 — Artifact inventory

| Stage | Artifacts |
|---|---|
| preflight | `PREFLIGHT.md` (note whether Check 0 answers and the Check 6 scope note are present) |
| scan | `CONSISTENCY_SCAN.md`, `consistency.json` |
| map | `matrix.json`, `CONSISTENCY_MATRIX.html` |
| canonize | `PATTERN_CARDS.md`, `CANON.json` (note split by provenance) |
| brief | `CONSISTENCY_BRIEF.md` (note whether the Approval Block is signed, and which phases) |
| align | `PLAYBOOK.md`, `ALIGN_NOTES.md` (note per phase: pilot done? fan-out complete or stopped early?) |
| verify | `VERIFICATION.md` (note per phase: clean, or blockers outstanding) |

## 2 — Staleness

- `CONSISTENCY_BRIEF.md` older than `consistency.json`, `matrix.json`, or
  `PATTERN_CARDS.md` → the brief no longer reflects discovery; recommend
  re-running `/consistency-brief`.
- `CONSISTENCY_MATRIX.html` older than `matrix.json` → re-run the
  injection step from `/consistency-map`.
- Any `ALIGN_NOTES.md` phase older than the `PATTERN_CARDS.md` entry it
  implements → the applied alignment may not match the current canon;
  flag which phase.
- `VERIFICATION.md` older than its phase's `ALIGN_NOTES.md` → re-run
  `/consistency-verify` for that phase.

## 3 — Verdict

End with three lines:
- **Where you are** — furthest completed stage, and roughly how much of
  the area it covers (e.g. "3 of 6 dimensions canonized, 1 of those
  aligned and verified").
- **What's stale** — or "nothing".
- **Next command** — the single most useful next step, with a one-line
  reason.
