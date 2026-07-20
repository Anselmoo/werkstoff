# self-assess code-quality-coverage design — Part A + Part B deliverable

Produced by a background agent in response to
[`2026-07-19-code-quality-gap-analysis-prompt.md`](2026-07-19-code-quality-gap-analysis-prompt.md),
after a full `self-assess` audit sweep against `spectrafit-core` (a real
Rust+Python+TypeScript repo) landed almost entirely documentation/CI-config
fixes and essentially zero application-code changes — the repo owner asked
directly: "do we get really so little ideas from our analysis out?" This
document is the analysis-and-design answer. **Everything below was proposed
before any implementation** — see `../skills/self-assess-modernization-scan/`,
`../skills/self-assess-architecture-audit/`, `../skills/self-assess-code-smell/`,
and the `commit-provenance` addition to `self-assess-ci-topology` for what was
actually built from this design (implemented 2026-07-19/20; check those
`SKILL.md`/`workflows/*.js` files directly for the current, authoritative
behavior — this document is a frozen record of the design rationale, not a
living spec).

## Task 0 — What "grey commit" means

**Conclusion: hypothesis 1 (commit signing/verification inconsistency) is confirmed, not just inferred.** Ran the check against the real repo's full history (`git log --all --pretty=format:'%G?' | sort | uniq -c`):

```
  34 E
 847 G
  47 N
 184 U
```

1112 commits total, and the signature status genuinely varies: 847 `G` (good, trusted — GitHub renders this **green "Verified"**), and 265 non-`G` (`N`=no signature, `U`=good signature but the key's trust can't be established, `E`=can't verify, missing key) — all of which GitHub renders as a **grey "Unverified" badge**. That's a real, literal "sometimes grey, sometimes not" pattern, and it isn't confined to old history — it recurs within a handful of commits by the same author: `92fc4b4` ("fix(F13): repoint remaining benchmark.* refs...", Anselm Hahn) is `U`, while `ba073bd`/`8db9acd`/`193a60b` (recent docs-drift-fix commits, "spectrafit-core CI" identity) are all `G`. A contributor scanning the commit graph on GitHub would see exactly the grey/green flicker described.

Checked the two fallback hypotheses and found them weak by comparison:
- **Hypothesis 2 (marker comments):** near-zero density — `grep -rn '#\s*(HACK|TODO|FIXME|WIP|XXX)'` over `python/` returned **0** matches; the Rust equivalent over `crates/` returned **1**. No "sometimes many, sometimes none" pattern to detect here.
- **Hypothesis 3 (commit message density):** plausible in the abstract but not checked in depth — deprioritized since hypothesis 1's evidence was already strong enough.
- The literal phrase "grey commit" does not appear anywhere in the repo — confirming it's the repo owner's own description of the GitHub UI, not an established codebase term.

**Flagged as an inference, not a confirmed-by-the-requester fact** — the agent had no way to ask directly in that session.

## Task 1 — Is this already covered by `code-modernization`?

**Conclusion: no, the gap is real** — for both the Task 0 finding and the three Part B dimensions — and it's structural, not a documentation oversight.

- `~/.claude/plugins/cache/claude-plugins-official/code-modernization/unknown/README.md` and this plugin's own `README.md` (opening paragraphs) confirm the intended split: `code-modernization` = `legacy/<system>/` → `modernized/<system>/`, a discovery-and-rebuild pipeline; `self-assess` = live/maintained repos, read-only, "nothing to migrate, only drift to catch."
- Read `commands/modernize-harden.md` and `commands/modernize-uplift.md` in full (the plugin has no `skills/` directory — commands live in `commands/`, orchestration in `workflows/harden-scan.js` and `workflows/uplift-deltas.js`). Both **require** the `legacy/$1` convention as a hard input:
  - `modernize-harden.md` writes remediation as unified diffs "relative to the project root (`legacy/$1/...`)" and its own apply instructions handle the case where "`legacy/$1` is a symlink" — i.e. symlinking is the documented workaround for a live repo, not a first-class supported target.
  - `modernize-uplift.md` is worse for this use case: Step 1 explicitly copies the **whole system** to `modernized/$1-uplifted/` and edits there, which is fundamentally incompatible with `self-assess`'s "read-only except a scoped output dir" invariant.
- Checked whether `code-modernization` already has *any* equivalent of the three Part B dimensions. `agents/legacy-analyst.md` and `commands/modernize-assess.md` **do** cover complexity/dead-code/god-object/magic-number detection conceptually (runs `lizard`/`scc --by-file -s complexity`; the analyst agent is briefed to find "dead code, deprecated APIs, copy-paste duplication, god objects/programs"). But this capability is architecturally locked inside the one-time legacy-inventory step of the rebuild pipeline — requires `legacy/$1`, writes to `analysis/$1/ASSESSMENT.md`, no sidecar/settings/dashboard contract compatible with `self-assess-status`/`self-assess-portfolio`. The *concept* exists upstream; not in a form reachable without adopting the legacy/modernized framing.

No skill in either plugin did commit-signature-provenance checking, deprecated-idiom-in-place detection scoped to a live repo, or god-module/circular-dependency detection over an already-built stage map, at the time this analysis ran.

## Part B — Proposed design: 3 new skills + 1 extension

All four: read-only, respect `.claude/self-assess.local.md` exactly as documented in `references/settings.md` (no new settings fields required), follow the Extract→Find→Verify / Find→Verify shape from `workflows/lint-audit-scan.js` and `workflows/stage-map-scan.js`.

### Extension: `self-assess-ci-topology` gains a commit-signature-provenance Check

**Why an extension, not a standalone skill:** `self-assess-ci-topology` already scopes itself as "git remote/config health" for a live repo with real history; commit signing is squarely that. It's also a single deterministic `git log` computation — no Find/Verify agents needed, since `%G?` is git's own ground truth with no false-positive risk to adjudicate the way a code-smell finding has.

**Real example finding (spectrafit-core):** "76% of commits (847/1112) carry a trusted-verified signature; the remaining 265 split across `N` (47), `U` (184), and `E` (34). Not a stale-history artifact — `92fc4b4` is `U` while three recent commits from the same contributor-identity class are `G`. Recommend: pin one signing method (the `G`-rate shows GPG/SSH signing is already the norm) and either fix the trust-store gap causing `U`, or document it."

### New skill 1 — `self-assess-modernization-scan`

Detects deprecated/legacy language idioms in a live codebase — derived from each language's **manifest-pinned version** (e.g. `pyo3 = "0.22"` in `Cargo.toml`), never a fixed universal list. Per-language Find-phase finders, adversarial Verify phase refuting deliberate compat shims / already-acknowledged-with-suppression-comment cases.

**Real example findings (spectrafit-core, actually checked, not hypothetical):**
1. Clean pass, Python: `Optional[X]` → **0** hits; `X | None` → **201** hits. Migration already fully complete — an honest "no finding" is itself useful signal.
2. Clean pass, Rust/pyo3: zero legacy pre-Bound-API calls found.
3. Real Low finding: every crate pins `edition = "2021"` with 2024 available, paired with `crates/spectrafit-builder/src/lib.rs`'s 45 near-identical `add_<model>()` builder methods plus a blanket `#![allow(clippy::too_many_arguments)]` — real boilerplate, not a manufactured finding.

The 2-clean/1-real mix was itself evidence the skill wouldn't manufacture findings to justify its own existence.

### New skill 2 — `self-assess-architecture-audit`

**Design decision:** reuse `self-assess-stage-map`'s already-built graph rather than re-deriving it, but as its *own* skill (not folded into `stage-map`) — because (1) `self-assess-status`'s dashboard aggregation deliberately excludes `stage-map` (it has its own interactive viewer), and deficiency findings need severity-bucketed dashboard treatment like the other three domains; (2) `stage-map`'s own description scopes it as *building* the map, not judging it — folding in "is this graph well-architected" would blur that boundary.

**One required additive change:** `stage-map-scan.js` computes full edge data in memory but only persists 5 sample edges per wire. God-module detection needs real per-file fan-in/fan-out degree, which is available mid-run but discarded before return — needs one additive field, not a breaking change to `stage-map`'s existing report/sidecar contract. Circular-dependency and layering-violation detection need no extension — pure graph math over the `wires` array `stage-map-scan.js` already returns.

**Real example findings (spectrafit-core, actually checked):**
1. Refuted god-module candidate: `python/oracles/cases.py` (fan-in 31, the highest in the repo) — correctly refuted after reading it: it's a declarative `CATEGORY_COUNTS` registry (exactly the "registry-over-map" pattern the repo's own conventions mandate), not a coupling defect.
2. Refuted size-without-coupling candidate: `crates/spectrafit-solver/src/dispatch.rs` (1678 LOC, the largest file in the repo) has fan-in of only 3 — a naive "biggest files" list would flag it; the fan-in/fan-out signal correctly doesn't, because it's a large `match` dispatch table, not a god module.
3. Historical validation: project memory records `python/oracles/engine.py` *was* a real god-module (1480 LOC) before a manual split into 4 leaf modules. This design would have flagged that pre-split state structurally rather than requiring an ad hoc review to notice it.

### New skill 3 — `self-assess-code-smell`

Detects generic code smells that don't require a `house-rules.md` entry to exist first — distinct from `self-assess-lint-audit`, which has zero opinion on anything not already written down. Deliberately useful even with **no** `house-rules.md` present at all (confirmed: `spectrafit-core` has none, so `lint-audit` currently has nothing to check there).

**Real example findings (spectrafit-core, actually checked):**
1. missing-type-coverage (Medium, real): `grep -rn ": any" web/src` → **52** occurrences in a repo whose typed contract surface (Pydantic → OpenAPI → generated TS) is otherwise end-to-end typed by design — each `: any` punches a hole in that specific, documented guarantee.
2. broad-exception-handling — mostly refuted, showing the Verify phase earning its keep: 8 candidate `except Exception:` sites found; 7 carry explicit justification (`# noqa`, `# pragma: no cover`), 1 (`reports.py:423`) re-raises after cleanup rather than swallowing. Correct output: 0 survivors, 8 refuted — not "report something anyway."
3. magic-number — refuted, showing domain-awareness matters: the FWHM↔σ factor `2.355` appears only in a doc comment (clean); the repeated `1e-3` gate threshold is a properly named, documented module constant (`_GATE_DEFAULT_MAX_DR2`), not an unexplained literal.

## Integration touch points (all implemented alongside the 3 skills)

- `self-assess-status/SKILL.md` — 3 new dashboard keys (`architectureAudit`, `modernizationScan`, `codeSmell`), same "present only if sidecar exists" discipline as the original three.
- `self-assess-portfolio/SKILL.md` — 3 more sidecar filenames in its Step 2 read list, or new skills silently don't factor into the portfolio heat-map for any repo.
- `stage-map-scan.js` — the additive `fileDegrees`-equivalent data (architecture-audit's one real prerequisite).
- `assets/findings-dashboard.html` — the hardcoded `DOMAINS` array needs 3 new entries or the new sidecars exist on disk but never render.
- Per the "don't repeat the exact bug you'd be fixing" instruction in the originating prompt: this plugin's own `README.md` skill table/count (was 7) updated in the same change as the new skill files, not as a follow-up — the whole reason this gap analysis started was a *different* project's `CLAUDE.md` having the identical stale-skill-count bug, caught by `self-assess-docs-drift` itself.
