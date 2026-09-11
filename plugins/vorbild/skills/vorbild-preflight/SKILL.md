---
name: vorbild-preflight
description: "Use to find out what a design-system derivation can honestly measure in this project before any tokens are spent: the questions no reference can answer (what artefact, screen or print, which render targets, what is already fixed, what is off limits), the existing CSS/token/framework footprint already in the repo, and a reliability and rights grade per intended reference. Trigger on 'what can vorbild actually measure here', 'is anything blocking a design-system run', 'grade these references before we start', 'vorbild preflight'. Writes PREFLIGHT.md with a per-phase Ready / Ready-with-gaps / Not-ready verdict and never proceeds into decode itself."
---

Establish what this environment can and cannot support before a single reference is
read. A phase that runs without its inputs produces numbers with invented precision,
and invented precision is indistinguishable from measurement once it is written down.

## Step 1 — ask, then do not block on the answers

Ask all six at once, then start the checks immediately:

1. What artefact is being produced? (a product UI, a print piece, a docs site, a brand
   system with no single artefact yet)
2. Screen, print, or both?
3. Which render targets are in play? (CSS, Tailwind, SCSS, a docs generator, a native
   platform, PDF)
4. What is already fixed and not up for derivation? (an existing brand, a mandated
   framework, a locked typeface licence)
5. What is off limits?
6. What prior attempts exist, and why did they stop?

An interactive user answers while the checks run. A headless run still produces a
complete `PREFLIGHT.md`. Any question still unanswered goes into the report
**verbatim, marked as an open item a human must fill in** — never dropped, never
guessed at. A readiness report silently missing its own questions is the one outcome
that must not happen.

## Step 2 — detect what is already here

Read-only. Record, with paths:

- existing token files (`*.tokens.json`, `tokens.css`, `theme.*`, Tailwind config)
- CSS custom properties already declared, and how many distinct values each role has
- the framework footprint, and whether it dictates a token shape
- whether a previous `vorbild` run left a design root behind

Two or more values for the same role is not a defect to fix here — it is the material
`vorbild-retrofit` exists to name.

## Step 3 — grade every intended reference, twice

Every reference gets **both** grades. They answer different questions and conflating
them is the trap: a published design guideline under a NoDerivatives licence is grade A
for reliability and R3 for rights *at the same time*.

Read `${CLAUDE_PLUGIN_ROOT}/references/reliability-grading.md` for how to assign A/B/C,
and `${CLAUDE_PLUGIN_ROOT}/references/rights-grading.md` for R1/R2/R3 and how to find a
licence before assuming one.

State the consequence plainly for each: a grade-C reference cannot set a token alone, and
an R3 reference cannot have its prose reproduced at all.

## Step 4 — write PREFLIGHT.md

Lead with the Step 1 answers **verbatim**, then the reference grade table, then a status
table (one row per check: ✅ / ⚠️ / ❌, what was found, the fix for anything not green).

End with a verdict **per phase**, not one global verdict:

- `collect` — needs at least one reference and a reachable source for it
- `decode` — needs Step 2 complete and every reference graded
- `name` — needs `DECODE.md`; no tooling
- `brief` — needs `DECODE.md` and `LEXIKON.md`; no tooling
- `retrofit` — needs an existing CSS/token footprint from Step 2. No footprint is
  **Not-ready** for this phase specifically, and says nothing about the others
- `emit --target pdf` — needs a Chromium-family browser on PATH. Absent, this is
  **Ready-with-gaps**, not Not-ready: `--target html` still produces the portfolio
- every other `emit` target — needs `tokens.json`, so it is gated on `decode` + `name`

Print the table in the session too, and end with the single most important fix if
anything is red.

## Resources

- `references/reliability-grading.md` — the A/B/C rubric and what each grade licenses a
  Design Card to claim. Read before grading anything.
- `references/rights-grading.md` — R1/R2/R3, how to establish a licence rather than
  assume one, and what each grade forbids downstream.
