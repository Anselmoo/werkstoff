# PREFLIGHT — werkstoff docs site + report viewers

Run: 2026-09-12, `matrize-preflight` 0.2.0, against `origin/main` @ `9077ce3`
(branch `docs/design-token-docs-harmonization`). Mode: interactive.

## Step 1 — the questions no reference can answer

Answers are recorded as given. Where the user answered through a multiple-choice prompt,
the chosen option is quoted; where the repository answered, the evidence is named.

| # | Question | Answer | Source |
|---|---|---|---|
| 1 | What artefact is being produced? | "Docs site + viewers" — the VitePress docs site (`docs/`) AND the `plugins/*/assets/*-viewer.html` report viewers share one token source, enforced for both | user |
| 2 | Screen, print, or both? | Screen. Viewers are dark-only; the docs site ships light + dark. No print target requested | repository (`docs/.vitepress/theme/werkstoff.css`, viewer `<head>`s) |
| 3 | Which render targets are in play? | CSS custom properties; VitePress default theme (`--vp-*` overrides); self-contained HTML viewers filled through the `<!--__DESIGN_TOKENS__-->` marker | repository |
| 4 | What is already fixed? | "Retrofit existing tokens" — `tools/design-tokens/tokens.css` (the silica-aerogel brand) stays the source; missing roles may be **added**, existing values are not changed | user |
| 5 | What is off limits? | "No version bumps/tags" — docs-only pass; every commit is `docs:`/`ci:`/`style:`/`chore:` | user |
| 6 | What prior attempts exist, and why did they stop? | The cupertino-council verdict preserved in commit `821a14a` and the rationale header of `tools/design-tokens/tokens.css`. They stopped at *declaring* the brand: the docs theme re-states it by hand and no check detects a value that bypasses it | repository |

Open items a human must fill in: **none.**

## Step 2 — what is already here

| Found | Path | Detail |
|---|---|---|
| Token source | `tools/design-tokens/tokens.css` | 50 custom properties, 67-line rationale header |
| Token copies | `plugins/*/assets/tokens.css` (12) | byte-identical, synced by `.rrt.toml` `artifact_targets` |
| Hand-mirrored theme | `docs/.vitepress/theme/werkstoff.css` | 30 `--wk-*` declarations restating token values; 28 hex, 22 `rgba()`, 0 `var()` references to the source |
| Component literals | `docs/.vitepress/theme/components/{PairingCards,RecipeBeats}.vue` | 12 `rgba()` restatements of token colours |
| Viewers | `plugins/*/assets/*-viewer.html` (13 files, 12 plugins) | all use the tokens marker; leftover off-token hex in matrix (8-hue ramp), architecture-tree, stage-map, derivation, sketchbook template |
| Framework | VitePress default theme | dictates `--vp-*` names for its own surfaces, not a token shape |
| Previous matrize run | — | none (`.design/` did not exist) |

Roles with more than one value — the material `matrize-retrofit` names, not a defect to fix here:
accent (`#348ad9` + light-mode `#1874c2`/`#0f66ae`), monospace stack (no token; first counted
as 12 literal repeats, re-measured by the brief as 9 across six viewers — `system/BRIEF.md`),
radius (tokens 4/6/8 vs 12 literal values in viewers), font size (one token vs ~14 literal sizes),
spacing (docs scale 4–96px vs token scale 4–20px).

## Step 3 — reference grades

| Reference | Reliability | Rights | Consequence |
|---|---|---|---|
| `tools/design-tokens/tokens.css` | **A** — the user's own token file | **R1** — user's own material | values usable as stated; prose may be reproduced |
| `docs/.vitepress/theme/werkstoff.css` | **A** — declared, user-authored | **R1** | usable, but it is a *derived duplicate*: where it disagrees with the source it is a finding, never a second original |
| 13 report viewers | **A** — declared, user-authored | **R1** | consumers; their literals are findings, not references |

No grade-C reference is in play, so no token rests on an estimate.

## Status

| Check | | Found | Fix |
|---|---|---|---|
| Reference reachable | ✅ | all three are local files | — |
| Every reference graded twice | ✅ | table above | — |
| CSS/token footprint | ✅ | 50-token source + mirrored theme | — |
| Token → DTCG retrofit | ✅ | `retrofit_css.py` deterministic over two runs | — |
| Vocabulary terms on tokens | ⚠️ | `validate_tokens.py`: 50× `V-VOCAB-MISSING` | name each token's term in `LEXIKON`/`BRIEF`; recorded in `system/retrofit-report.md` |
| `$type` on alias tokens | ⚠️ | 10× `V-TYPE-MISSING` on `var()` aliases (`--accent`, `--cat-*`, `--diverging-*`) | a matrize tooling gap — follow-up, out of scope for a no-bump pass |
| Enforcement of token usage | ❌ | no check flags a hard-coded colour, font or radius anywhere | `scripts/ci/check_design_tokens.py` + shrink-only baseline |
| Chromium for `emit --target pdf` / visual arm | ✅ | Google Chrome at `/Applications` | — |
| Node deps for docs build | ❌ | `node_modules` absent; install refused by the confab guard in this session | user runs `npm ci` once |

## Verdict per phase

| Phase | Verdict | Why |
|---|---|---|
| `collect` | Not applicable | no external reference; the brand is the user's own file |
| `decode` | Not applicable | nothing to measure — values are declared, grade A |
| `name` | Ready-with-gaps | 50 tokens carry no vocabulary term |
| `brief` | Ready | contested values listed above |
| `retrofit` | **Ready** | footprint present; proof via `prove_retrofit.py` |
| `emit --target css` / `vitepress` | **Ready** | `tokens.json` exists; `emit_vitepress.py --adopt --prefix --wk-` |
| `emit --target pdf` | Ready | Chrome present |
| other `emit` targets | Not requested | — |

**Single most important fix:** nothing mechanically stops a value from bypassing the tokens. Until
a check fails CI on a hard-coded colour, every harmonization below decays back to the current state.
