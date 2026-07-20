# self-assess idiom-remediator — design spec

Date: 2026-07-20
Status: Approved (design), pending implementation plan

## Context

A real coding-session retrospective (quoted verbatim during design discussion)
found that a whole session's worth of `self-assess`-style analysis produced
almost no real code-behavior change: zero lines touched in the web frontend,
only doc-comment/manifest edits in the Rust crate, mostly cosmetic string
changes in Python. The root cause was structural — every skill run that
session compared *metadata about the code* to *other metadata* (docs↔code,
CI config↔docs, code↔house-rules, manifest↔registry), never the code's own
design.

Earlier in this work session, `self-assess-code-idiom` and
`self-assess-arch-health` were built specifically to close that gap — the
first skills that judge the code itself (deprecated idioms, generic smells,
architecture deficiencies) rather than checking it against something else.
`self-assess-transform-brief` and `self-assess-transform-execute` followed,
turning `arch-health`'s findings into a plan and, for authorized phases, an
actual multi-file architectural edit — proven by `andon-verify`'s adversarial
tribunal, never self-reviewed (motivated by a research finding that models
reviewing their own code changes miss roughly a third of their own semantic
errors).

This spec closes the parallel gap on the *other* new skill:
`self-assess-code-idiom` can find a real, mechanical, single-location
deprecated-idiom finding but has no way to apply it — a human has to do so
by hand. This is exactly the kind of finding a real session is least likely
to act on (per the retrospective's own evidence), because there's friction
between "here's a finding" and "the fix is applied."

**Empirical validation (post-design-approval addition):** an independent
gap-analysis run against a real repo (`spectrafit-core`,
`docs/superpowers/assets/2026-07-19-code-quality-gap-analysis-design.md`)
confirms this exact class of finding is real, not hypothetical — its
canonical example was `Optional[X]` → `X | None` in Python (0 hits for the
old form vs. 201 for the new one in that repo — migration already
complete there, but the same idiom-class finding pattern generalizes to any
repo mid-migration). That same run also validated, independently, that
`modernization`-class findings and `smell`-class findings (broad-except,
magic-number) genuinely need different handling — its design went further
than this one and split them into two separate skills entirely, which is
stronger evidence for this spec's permanent exclusion of `smell` from
auto-fix than the reasoning available when this spec was first drafted.

## Decisions made during brainstorming

- **Scope: `code-idiom`'s `modernization` category only, permanently.**
  `smell`-category findings (overlong functions, broad excepts, magic
  numbers, deep nesting) are excluded not just for a first increment but
  for good — fixing a smell requires design judgment (what should this
  function be split into? what exception type *should* be caught?) that a
  mechanical rewrite cannot supply. This mirrors `confab-cycle`'s existing
  split between `fixable_domains` and `draft_domains`.
- **Approach chosen: every fix — no exception — is proven by `andon-verify`'s
  adversarial tribunal before being trusted**, even a fix as mechanical as
  a one-line `Optional[int]` → `int | None` rewrite. This was an explicit
  choice over a cheaper same-domain re-check, prioritizing a single
  consistent safety story ("nothing this plugin auto-fixes is ever
  self-reviewed") over proportionality to blast radius.
- **A separate skill + agent, not a mode inside `self-assess-code-idiom`.**
  Mirrors the existing `self-assess-transform-brief`
  (read-only) / `self-assess-transform-execute` (the plugin's other Edit
  exception) separation. `self-assess-code-idiom` remains unconditionally
  read-only; its read-only guarantee never becomes configurable.
- **Explicitly out of scope for this spec** (parked as a separate,
  later project): the multi-language, extensible fixture-validation harness
  that would prove this (and the rest of the new self-assess capability)
  actually works against planted gaps, "language independent." That
  project depends on this one existing first, so it was sequenced after.
  Also out of scope: any auto-fix path for `lint-audit` violations (house
  rules are too heterogeneous per-repo to safely generalize a mechanical
  fixer over) or for `smell`-category findings (see above).
- **Execution note (not part of the design itself):** once this spec is
  turned into an implementation plan, the user wants it executed via the
  `subagent-driven-development` process rather than built inline in a
  single session.

## Architecture

Self-assess gains a **second** narrow Edit path, alongside — not replacing —
the existing `self-assess-transform-brief` → `self-assess-transform-execute`
→ `transform-executor` trio. Same three-part separation applies: a read-only
finder (`self-assess-code-idiom`, unchanged) → a gated Edit skill
(`self-assess-idiom-fix`, new) → independent proof (`andon-verify`, never a
self-review, no exception for this second path either).

```
self-assess-code-idiom (read-only, unchanged)
        │  writes code_idiom_summary.json { findings: [...] }
        ▼
self-assess-idiom-fix (new, gated)
        │  filters findings to category:"modernization", no severityNote
        │  dirty-tree gate
        ▼
idiom-remediator (new agent, Read+Edit only)
        │  applies ONE syntactic rewrite for ONE finding
        ▼
andon-verify (existing, adversarial tribunal — every fix, no exception)
```

## Components

### 1. `idiom-remediator` agent (new)

- **Tools:** `Read`, `Edit` only. No `Write` (no new files — these are
  always same-file rewrites by construction), no `Bash`, no `Glob`/`Grep`
  (a `code-idiom` finding's evidence is always exactly one file:line; unlike
  `transform-executor`, this agent never needs to search for other call
  sites).
- **Contract:** given exactly ONE already-verified `modernization` finding
  (file:line, description, suggested fix), apply exactly ONE syntactic
  rewrite. Never a broader cleanup. Returns `blocked` if:
  - the finding is ambiguous or would require touching more than the cited
    location,
  - the finding is `smell`-category (defensive check — should never be
    dispatched one, but the agent itself refuses if it happens),
  - the cited line's content has changed since the scan (stale-finding
    guard — re-reads it first).
- Never verifies its own work, never commits or pushes. Same untrusted-content
  discipline as every other self-assess/confab agent.

### 2. `self-assess-idiom-fix` skill (new)

- **Step 0:** load `.claude/self-assess.local.md`; if `idiom_fix.mode` is not
  `fix` (default `propose`), refuse and explain the gate. (`propose|fix`
  matches `confab-cycle`'s existing enum, chosen over `transform.mode`'s
  `plan|execute` because this path is closer in shape and blast radius to
  `confab-cycle`'s mechanical-fix loop than to `transform-execute`'s
  per-phase architectural gate.)
- **Step 1:** read `<output_dir>/code_idiom_summary.json`, filter
  `findings[]` to `category === "modernization"` AND no `severityNote`
  present (code-idiom's own Verify phase already flagged uncertainty on
  anything carrying one — this remediator never second-guesses that by
  attempting a fix anyway). This yields the full **eligible-findings list**
  for the run, not a single finding.
- **Step 2:** dirty-tree gate (`git status --porcelain`; refuse or ask to
  confirm on a dirty tree, matching `self-assess-transform-execute`'s Step
  2 exactly). Checked once per skill invocation, before touching anything.
- **Step 3:** loop over the **entire eligible-findings list** from Step 1
  within this one invocation — dispatch `idiom-remediator` once per
  finding, sequentially, each with only that one finding's file:line and
  description (never batched into a single dispatch covering multiple
  findings; "one dispatch, one report" means one `idiom-remediator` call
  per finding, not one skill invocation per finding).
- **Step 4:** immediately after each fix `idiom-remediator` applies — no
  exception, and before moving to the next finding in the loop — report
  explicitly: **"This change is unverified. Hand off to `andon-verify`
  (adversarial tribunal) before trusting it."** Each fix gets its own
  hand-off message (N findings fixed this run → N separate hand-offs), never
  one summary claiming the batch as a whole is "done." If `andon` isn't
  installed, refuse to proceed past reporting the *proposed* fixes in
  `propose` mode; do not silently skip verification for any of them.
- Never commits or pushes, at any point in the loop.

### 3. Settings

New field in `references/settings.md` and `examples/self-assess.local.md`,
alongside the existing `transform.*` block:

```yaml
idiom_fix:
  mode: propose   # or "fix"
```

## Data flow

`self-assess-code-idiom` (unchanged) writes `code_idiom_summary.json`'s
`findings[]` (already carries `category`, per earlier work this session) →
`self-assess-idiom-fix` filters to eligible `modernization` findings →
dispatches `idiom-remediator` per finding → agent returns a diff description
→ skill reports "unverified — hand off to `andon-verify` now," never a
self-declared success.

**Zero eligible findings is a valid, expected outcome, not an error path.**
The same empirical run cited above found 0 hits for its target deprecated
idiom in one language and a clean pass in another — a fully-migrated repo
genuinely has nothing to fix. `self-assess-idiom-fix` must report "0
eligible findings — nothing to do" plainly and stop, the same honest-signal
principle `self-assess-code-idiom` itself already follows; it must never
manufacture a finding, lower its own filter criteria, or otherwise "find
something to justify the run" when the eligible-findings list is empty.

## Error handling / safety

- BLOCKED-on-ambiguity and the stale-finding guard mirror
  `confab-remediator`/`transform-executor` exactly.
- Dirty-tree gate before any fix.
- Never commits or pushes.
- Zero exceptions to the andon-verify hand-off, including for trivial
  single-line rewrites (the explicit choice made over a cheaper same-domain
  re-check).

## Testing (for this implementation only)

No new `workflow.js` — single-finding dispatch, no parallel-finder pattern,
plain skill logic (same shape as `self-assess-transform-execute`). Verify:
YAML frontmatter on the new SKILL.md + agent, the settings example parses,
and a synthetic `code_idiom_summary.json` payload correctly exercises the
`modernization`/`smell` filter and the `severityNote` skip.

**Explicitly deferred:** real end-to-end proof that this actually fixes a
real idiom, in a real language, is the fixture-validation harness project —
parked as a separate follow-on, not part of this implementation's test plan.

## Explicitly out of scope

- The multi-language, extensible fixture-validation harness (follow-on
  project; depends on this one).
- Auto-fix for `code-idiom`'s `smell` category (permanent exclusion, not a
  future increment).
- Auto-fix for `self-assess-lint-audit` violations (house rules are too
  repo-specific/heterogeneous to safely generalize a mechanical fixer over).

## Documentation wiring (implementation-plan detail, noted here so it isn't dropped)

This adds a 14th self-assess skill and a 10th agent. The same
documentation-consistency sweep already done once for `transform-execute`
needs to happen again: skill/agent counts in `README.md`, the "one Edit
exception" framing in Safety notes (which becomes "two Edit exceptions" —
`transform-executor` and `idiom-remediator`, each independently gated),
`CHANGELOG.md`, and the settings example file. The implementation plan
should enumerate the exact files, mirroring the prior sweep's file list
rather than re-deriving it from scratch.
