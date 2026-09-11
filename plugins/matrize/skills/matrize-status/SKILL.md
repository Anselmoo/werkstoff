---
name: matrize-status
description: "Use to report where a design-system derivation stands — which artefacts exist and when they were written, which are stale against inputs they derive from, whether the survey is past its expiry and which claim forces it, whether the approval block is signed, and whether a spread choice is still unanswered. Trigger on 'matrize status', 'where are we with the design system', 'is the brief signed', 'what should I run next'. Read-only; it reports on matrize's own artefacts and has nothing to say about a repository matrize has not run in."
argument-hint: "<system>"
---

Report what has already happened. Change nothing.

If there is no design root, say exactly that and stop. This skill has nothing to say
about a project it has not been run in, and inventing a reading would be worse than
silence.

## 1 — artefact inventory

One row per artefact under `<root>/`: present or absent, and its modification time.

`references/` (count and grades) · `STATE-OF-THE-ART.md` · `DECODE.md` · `LEXIKON.md` ·
`BRIEF.md` (**and whether its approval block is signed**) · `spread-choice.json` (**and
whether `chosen` is filled**) · `tokens.json` · everything under `out/`.

## 2 — staleness

Flag any artefact older than something it derives from:

- `DECODE.md` older than anything in `references/` → the measurement predates the
  material; re-run `matrize-decode`
- `LEXIKON.md` older than `DECODE.md` → names rest on superseded measurements
- `BRIEF.md` older than `DECODE.md` or `LEXIKON.md` → the brief no longer reflects
  discovery, and the signature on it covers something that has changed. Say that
  explicitly: a signed-but-stale brief is worse than an unsigned one, because it looks
  settled
- anything in `out/` older than `tokens.json` → emitted output no longer matches source;
  re-emit rather than hand-editing
- `STATE-OF-THE-ART.md` past its expiry → **name the claim that forces it**, so a
  re-survey can be targeted instead of total

## 3 — open gates

Two gates block real work, and each has a specific consequence worth stating rather than
listing:

- **unsigned brief** — the build methods have no approved entry criteria to read
- **unanswered `spread-choice.json`** — the `PreToolUse` guard is actively denying every
  write to `tokens.json` and `out/`. Anyone hitting a denial here should see it named
  in status rather than discovering it as a mysterious refusal

Also list every open question carried from `preflight`, `decode` (grade-C-only findings)
and `brief`, since those are what a human still owes the pipeline.

## 4 — verdict

End with three lines, and no more:

- **Where you are** — the furthest completed phase, with rough coverage
  ("11 references collected, 34 cards, 2 roles still contested")
- **What is stale** — or "nothing"
- **Next command** — the single most useful next step, with a one-line reason

A status report that ends in a list of everything possible has not done the one thing it
was asked for, which is to say what to do next.
