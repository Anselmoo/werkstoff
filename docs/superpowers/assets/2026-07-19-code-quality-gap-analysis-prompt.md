# Task: Design (and, if confirmed, build) code-quality coverage for the `self-assess` plugin

## Who you are, what you're picking up

You're a fresh agent with no memory of the session that wrote this prompt. Everything you
need is below or discoverable via the paths given — don't assume anything not stated here.

`self-assess` is a Claude Code plugin (marketplace: `werkstoff`, installed at
`~/.claude/plugins/cache/werkstoff/self-assess/0.1.0/`) that audits **live, actively-
maintained** codebases. It currently has 7 skills:

| Skill | What it actually checks |
|---|---|
| `self-assess-preflight` | is the repo ready for the other skills (languages detected, tooling present) |
| `self-assess-docs-drift` | do `CLAUDE.md`/`README.md`/`DECISIONS.md`/`ARCHITECTURE.md`'s claims still match the code |
| `self-assess-ci-topology` | do git remotes / CI config match what the docs say about them |
| `self-assess-lint-audit` | does the code follow rules the repo owner wrote themselves in `.claude/house-rules.md` |
| `self-assess-stage-map` | what's the real import/dependency graph, clustered into stages+wires |
| `self-assess-status` | dashboard aggregating the above four's JSON sidecars |
| `self-assess-portfolio` | same, across multiple repos |

**A full run of every one of these skills was just completed against a real repo
(`spectrafit-core`, a Rust+Python+TypeScript scientific-computing project) in a separate
session.** Every fix that came out of it was overwhelmingly a **documentation, comment, or
CI-config** change. Tallied precisely: `web/src` had zero lines touched across the whole
session; `crates/` got a doc-comment fix (`frac`→`fraction`), two `Cargo.toml`
dependency-line removals, and one string-literal→method-call swap — no algorithm, data
structure, or error path changed; `python/` changes were mostly `formula_latex` *display
strings* (cosmetic, not computation) and `if/elif`→`match` idiom conversions (behaviorally
identical). Not one fix touched the actual *quality, architecture, or idiom* of the
application code itself. That's not a fluke — it's structural: every skill run compares
"does X match Y," where X and Y are both metadata about the code (docs vs code, CI config vs
docs, code vs house-rules the repo owner already wrote down, import-graph shape vs itself).
**None of them has an opinion on whether the code itself is well-designed.** The one
code-structural finding that came out all session (2 vestigial Cargo dependencies) was a
side effect of `stage-map`'s import-graph math, not a code-quality judgment — `stage-map`
doesn't have a "is this graph well-architected" pass, only a "does this edge exist" pass.

The repo owner who ran that session also flagged a second, more concrete observation:
**inconsistent inline marker comments across the codebase** — described to me as "sometimes
we have many `# grey commit`, sometimes not" (their exact words; the meaning is not yet
confirmed — see Task 0, don't skip it).

## Your task, in two parts

**Part A (do this first, it's cheap and it might reframe everything):** ground the actual
gap. Don't assume the framing above is complete or correct — verify it.

**Part B:** design (and only build if explicitly told to — see "Stop and ask" below) new
`self-assess` skill(s) that close whatever gap Part A confirms.

---

## Part A — Ground the gap before designing anything

### Task 0 — Figure out what "grey commit" actually means

This is unconfirmed. Three hypotheses, in the order I'd check them:

1. **Commit signing/verification inconsistency.** GitHub (and GitLab) render a commit's
   author badge grey ("Unverified") vs green ("Verified") based on GPG/SSH signature status
   matching a known key. If some commits in a repo's history are signed and others aren't,
   a contributor scanning the commit graph would see exactly "sometimes grey, sometimes
   not." Check: `git log --pretty=format:'%h %G? %an' | sort -k2 | uniq -c -f1` (or similar)
   across a real repo's history — do signature statuses (`G`/`B`/`U`/`N`/`X`/`Y`/`R`/`E`)
   actually vary? This is the leading hypothesis because it's the only one where "grey" is
   a literal, standard term (GitHub's own UI language for unverified commits) rather than a
   guess.
2. **Marker-comment inconsistency.** Some codebases use a literal comment convention (e.g.
   `# HACK`, `# TODO`, `# WIP`, a project-specific tag) inconsistently — present in some
   files/functions, absent where it should logically also apply. Check: grep a few real
   repos for short all-caps or tagged comment markers and see if density/consistency varies
   by file or author in a way that reads as "sometimes present, sometimes not."
3. **Commit-message quality/density inconsistency.** Some commits carry rich explanatory
   bodies (this session's own commits are an example — multi-paragraph rationale), others
   are one-line stubs. This is a real, checkable "grey" pattern too (terse commits could
   colloquially read as "flatter"/"greyer" against detailed ones) but is the weakest textual
   match for the literal phrase.

**Do not build a detector for the wrong thing.** If you have a way to ask the person who
gave you this task a clarifying question, use it. If not, build the detection logic for
hypothesis 1 first (it's the most concrete and most valuable regardless — commit-signing
inconsistency is a real, useful security/provenance signal no existing skill catches), but
explicitly flag in your deliverable that this was inferred, not confirmed, and name the
other two as fallback interpretations you did *not* build.

### Task 1 — Check whether this gap is already covered by a sibling plugin

Before designing anything, read `~/.claude/plugins/cache/claude-plugins-official/code-modernization/unknown/README.md`
in full. It is explicitly positioned (and `self-assess`'s own README says so too — read
`~/.claude/plugins/cache/werkstoff/self-assess/0.1.0/README.md`'s opening paragraph) as
`self-assess`'s sibling: `code-modernization` handles **legacy systems being discovered and
rebuilt** (`legacy/<system>/` → `modernized/<system>/`, with an `assess → map →
extract-rules → brief → transform/reimagine/uplift → harden` pipeline). `self-assess`
handles **live, actively-maintained systems where there's nothing to migrate, only drift to
catch**.

This matters because `code-modernization` already has a `modernize-harden` skill
("security pass on the still-running legacy system") and `modernize-uplift-deltas`
(same-stack version-bump migration) — read both
(`~/.claude/plugins/cache/claude-plugins-official/code-modernization/unknown/skills/`,
look for the `modernize-harden` and `modernize-uplift` or equivalent skill directories)
before proposing anything that would duplicate them. Specifically confirm: does
`modernize-harden` require the `legacy/<system>/` symlink convention to run, or can it be
pointed at a live repo directly? If it genuinely requires the `legacy/` framing, that's real
friction for a live/maintained repo and strengthens the case for a `self-assess`-native
equivalent. If it doesn't, that changes what Part B should propose (maybe the answer is
"tell users to use `modernize-harden` directly," not "build a new skill").

**Write down your Task 0 and Task 1 conclusions explicitly before starting Part B.** If Task
1 concludes the gap is already covered, say so and stop — don't build a redundant skill
just because you were asked to.

---

## Part B — Design the new skill(s)

Assuming Task 1 confirms a real gap (this is the expected outcome based on the
`legacy/`-vs-`live` framing above, but verify it yourself), design **new `self-assess`
skills** — not modifications to `code-modernization` — for the three code-level dimensions
the 7 existing skills don't cover:

1. **Modernization-in-place** — deprecated/legacy language or library idioms in a codebase
   that is *not* being rebuilt, just improved incrementally. Concrete examples you'd need to
   derive per-language (don't hardcode a universal list — read
   `~/.claude/plugins/cache/werkstoff/self-assess/0.1.0/references/language-support.md`
   for the per-language extraction-idiom precedent this plugin already follows, and extend
   that pattern): old-style `Optional[X]` vs `X | None` in Python 3.10+, deprecated pyo3
   API surface in Rust code that binds to Python, React patterns predating hooks, `var` vs
   `let`/`const` in older TS, etc. — but genuinely detected against what's actually present
   in a target repo's languages, not asserted from a fixed list.
2. **Architecture-deficiency detection.** **Important:** `self-assess-stage-map` *already
   builds a real import graph* (`stage_map.json` — read
   `~/.claude/plugins/cache/werkstoff/self-assess/0.1.0/skills/self-assess-stage-map/SKILL.md`
   and `workflows/stage-map-scan.js` in full to understand its exact output shape:
   `{stages, wires, deadEnds, observations}`). Decide — and justify your decision — whether
   architecture-deficiency detection should be:
   (a) a **new analysis pass over stage-map's existing output** (god-module detection via
   fan-in/fan-out thresholds per stage, circular-dependency detection between stages,
   layering-violation detection — e.g. a "web" stage's files importing from a
   test-only stage), reusing the graph that's already built rather than re-deriving it, or
   (b) a wholly separate skill with its own extraction pass.
   Option (a) is very likely cheaper and more consistent with how this plugin is built
   (`stage-map`'s own `deadEnds` field is already a primitive form of this — "stages with no
   confirmed wire to any other stage" — you'd be extending that idea, not inventing it).
3. **Code-pattern / anti-pattern analysis**, distinct from `lint-audit`: `lint-audit` only
   checks rules a human already wrote in `.claude/house-rules.md` — it has zero opinion on
   anything not in that file. This new dimension should catch **generic code smells that
   don't require a house-rules entry to exist first**: long functions/files, deep nesting,
   duplicated logic blocks, overly-broad exception handling that silently swallows errors,
   magic numbers, missing type coverage in an otherwise-typed codebase. (If Task 0 resolves
   to hypothesis 2 — marker-comment inconsistency — that finding folds in here too: stale or
   inconsistently-applied `TODO`/`FIXME`/`HACK` markers are exactly this class of smell.)

For whichever of these you design (plus the commit-signing/provenance finding from Task 0,
which is likely its own small addition rather than a full skill — possibly a new Check
inside `self-assess-ci-topology`, since that skill already owns "git remote/config health,"
rather than a standalone skill; use your judgment and justify it), your design **must**
match the existing plugin's conventions exactly — read enough of the existing skills to
get every one of these right, don't guess:

- **Two-phase Workflow pattern**: one Find-phase finder per detected language/dimension, then
  an adversarial Verify-phase pass on every candidate finding before it's reported (see
  `workflows/lint-audit-scan.js` or `workflows/docs-drift-scan.js` for the exact shape:
  `Extract → Find → Verify`, `skipVerification` escape hatch, `injectionFlags` handling for
  untrusted repo content).
- **Read-only.** Every existing skill is read-only except writing to a single scoped output
  directory. Do not propose anything that edits source code directly, even for
  "safe" mechanical modernization changes — that's a `code-modernization`-style transform
  operation and out of scope for what `self-assess` is.
- **Settings.** Respect `.claude/self-assess.local.md` (`output_dir` default
  `analysis/self-assess`, `skip_verification`, `house_rules_path`) exactly like every other
  skill — read `references/settings.md` for the authoritative field list.
- **JSON sidecar + dashboard integration.** Every domain skill writes a `<NAME>_summary.json`
  that `self-assess-status` aggregates into `findings_dashboard_data.json` and
  `self-assess-portfolio` reads for its multi-repo view. Your new skill(s) need the same
  sidecar contract (read `self-assess-status/SKILL.md` Step 3 for the exact aggregation
  shape) or they won't show up on the dashboard the repo owner already relies on.
- **SKILL.md frontmatter** must be specific enough to trigger correctly (read all 7 existing
  `SKILL.md` `description:` fields for the calibration — they're long, example-rich, and
  explicitly say what NOT to use the skill for).

## Stop-and-ask gate

This is an **analysis and design task**, not an implementation task, unless the person
running this session tells you otherwise. Produce:

1. Your Task 0 conclusion (what "grey commit" actually means, with evidence).
2. Your Task 1 conclusion (is this genuinely uncovered by `code-modernization`, with
   evidence — cite the specific skill files you read).
3. A concrete design per new skill/extension you're proposing: name, `SKILL.md`-shaped
   description, exact Find/Verify phase behavior, exact sidecar JSON shape, and — critically
   — 2-3 *real* example findings you'd expect it to surface if pointed at a mature codebase
   (not hypothetical placeholder examples — actually reason through what a Rust+Python
   scientific-computing repo's real deficiencies in each dimension would look like, the way
   the rest of this prompt did for modernization idioms).

**Do not start writing `workflows/*.js` or `SKILL.md` files until this design has been
presented and confirmed** — this plugin's existing skills are dense and convention-heavy
(read the two-phase pattern, the settings contract, and the dashboard sidecar contract
*correctly* the first time; getting any of the three wrong means every new skill silently
fails to integrate with `self-assess-status`/`self-assess-portfolio`, which is a worse
outcome than asking first).

## One more thing — don't repeat the exact bug you'd be fixing

If your design is approved and you do implement new skill(s), you MUST update
`self-assess`'s own `README.md` skill count/table to include them (currently says "7
skills" — grep for that number). The session that produced this prompt spent a full pass
fixing `spectrafit-core`'s `CLAUDE.md`, which claimed "7 consolidated skills" when the real
count was 9 — a doc-drift bug in a *different* project's skill catalog, caught by
`self-assess-docs-drift` itself. Shipping a `self-assess` skill-count bump without updating
`self-assess`'s own README would be the identical bug, in the plugin whose entire purpose is
catching that class of bug. Update it in the same commit as the new skill files, not as a
follow-up.
