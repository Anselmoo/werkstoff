# Craft standards for werkstoff skills and agents

These rules govern the **craft** of a skill/agent (how it's built) — frontmatter shape,
progressive disclosure, writing voice, structure, wiring. They say nothing about a
skill's **content** (what sections a report/rule-card/finding should contain) — that
stays the author's per-plugin call, graded against real evidence, the way
[`output-shape-findings.md`](output-shape-findings.md) is.

Adapted from `Wirasm/prp`'s `.agents/skills/prp-meta-skill/references/skill-standards.md`
(commit `11427384c7609227f20c1d57e6c39de47ccf73c5` — the same commit as this session's
installed `prp-core` plugin; see `output-shape-findings.md` §2e for how that identity was
established). Every rule below is checked against what werkstoff's six plugins actually
do, not copied blind — where werkstoff already follows a rule, that's stated as
confirmed; where it doesn't, that's a named gap, not a silent assumption.

## Skill types

Classify a skill before applying craft rules — guidance is proportional, not
one-size-fits-all:

| Type | What it is | werkstoff examples |
|---|---|---|
| **Workflow** | a multi-step procedure with gates | `self-assess-extract-rules`, `compass-solve`, `andon-loop`, `confab-cycle` |
| **Artifact-generator** | produces a document/output | `self-assess-transform-brief` (writes `MODERNIZATION_BRIEF.md`) |
| **Knowledge / reference** | domain facts the agent consults, no phases, no validation loop | `cli-scaffold`'s per-language `references/*.md` files |
| **Tool-wrapper** | drives a script/CLI deterministically | `self-assess-status` (reads artifact staleness via `self_assess_cli.py`) |

A skill can blend types. What you never do is impose a workflow skill's machinery
(phases, validation loops, output skeletons) on a skill that isn't one — this is a real
werkstoff-relevant caution, since `compass` and `cupertino`'s advisory skills are
deliberately *not* gated the way `andon`/`confab`'s enforcement skills are (see
`CLAUDE.md`'s "Enforcement: only hooks actually enforce" section — the same
type-proportionality point, arrived at independently).

## Anatomy

```
skill-name/
├── SKILL.md          # required: YAML frontmatter + markdown body
├── references/       # docs the agent READS on demand (schemas, patterns, edge cases)
├── templates/         # files reused in OUTPUT (report skeletons, output formats)
├── assets/            # non-text output resources (images, boilerplate projects, fonts)
└── scripts/            # executable code, RUN without loading source into context
```

- **references/** = "read this to inform the work."
- **templates/** = "fill this in / follow this shape when producing output."
- **assets/** = "copy or embed this into the result."
- **scripts/** = "execute this for deterministic, token-free work."

**werkstoff status:** `references/` is already an established pattern (`andon`,
`cli-scaffold`, `confab`, `cupertino`, `self-assess` all use it, at both plugin-root and
skill-scope — see `CLAUDE.md`'s own note on `self-assess-extract-rules/references/`).
`templates/` and `assets/` are not used anywhere in werkstoff today — the `templates/`
vs `references/` distinction (schema-you-fill-in vs. detail-you-read) is currently
collapsed into `references/` everywhere, including the three-file split just added to
`self-assess-extract-rules/references/` (`rule-card-template.md` plays the `templates/`
role by content, but lives under `references/` by directory, matching this repo's
existing single-directory convention — see `output-shape-findings.md` §4.6 for why that
deviation from `Wirasm/prp`'s literal layout was made deliberately, not by oversight).

## Context sources

A skill draws context from four places — use the cheapest that fits:

1. **Inline** — in `SKILL.md` itself. Always loaded; keep it to the spine.
2. **Bundled** — `references/`/`templates/`/`assets/`/`scripts/`. Loaded on demand.
3. **External pointers** — repo file paths and URLs, read/fetched when a step needs them.
   werkstoff's `file:line` citation convention (business rules, docs-drift claims,
   contract-drift findings) is this category — nothing is copied in, the agent reads the
   real location.
4. **Runtime-gathered** — the skill instructs the agent to obtain context when it runs.
   `self-assess-code-idiom`'s manifest-detected-version-per-language is this category:
   gathered fresh each run, never hardcoded.

Choose by ownership and volatility: bundle what you own and want versioned; point to
what you don't own or what changes upstream; gather at runtime what only exists in the
moment (current repo state, the user's actual intent).

## Frontmatter spec

| Field | Wirasm/prp's rule | werkstoff's actual usage |
|---|---|---|
| `name` | ≤64 chars, lowercase+hyphens, matches directory | Followed — `name:` always matches the skill's directory name across all 63 SKILL.md files |
| `description` | ≤1024 chars, third person, WHAT + WHEN + literal phrases | Followed — longest is 647 chars (`cli-scaffold-shell`), well under the ceiling; all use the "Use this skill when the user asks to..." trigger-phrase pattern |
| `version` | not a field Wirasm/prp's spec lists at all (nor is it a documented Claude Code SKILL.md field — see `output-shape-findings.md` §5) | Was present, frozen at `0.1.0`, in all 16 `self-assess` skills only — removed; matches the other five plugins, which never had it |
| `allowed-tools` / `disable-model-invocation` / `user-invocable` | invocation-control fields; a **distributed** skill auto-invoking a **side-effecting** action (commits, writes, deletes) should set `disable-model-invocation: true` in the shipped copy | Not used anywhere in werkstoff's SKILL.md frontmatter today. Worth a deliberate look, not an automatic change: `andon-loop`, `self-assess-idiom-fix`, `self-assess-transform-execute`, and `confab-cycle` (fix mode) are auto-invocable, side-effecting workflow skills shipped in a plugin — exactly the case this rule is written for. Whether werkstoff wants that invocation-control tightening is a product decision for whoever maintains those plugins, not something this doc decides on its own. |

## Progressive disclosure

Three load levels: metadata (`name`+`description`, ~100 words, always in context) → body
(`SKILL.md`, target 1,500–2,000 words, hard ceiling ~5k) → resources (`references/` etc.,
loaded only on demand, effectively unlimited).

**werkstoff status: confirmed clean.** Across all 63 SKILL.md files, body word counts
range 196–1,381 words (average 411) — comfortably under even the 1,500–2,000 target, let
alone the 5k ceiling. This independently corroborates `output-shape-findings.md`'s
`obra/superpowers` citation of the same "<150 words for always-loaded skills, one
excellent example beats several mediocre ones" discipline — two unrelated sources
converging on the same number is a stronger signal than either alone.

## Writing style — two voices

- **`description` → third person, trigger-rich.** Confirmed followed across werkstoff.
- **Body → imperative/infinitive, NOT second person.**
  Good: `"Compose the five phases in order."` (`compass-solve/SKILL.md`)
  Bad (per this rule): `"You route a scaffold request to the correct paradigm skill... You never generate code yourself."` (`cli-scaffold/skills/scaffold-cli/SKILL.md`)

**werkstoff status: inconsistent, confirmed by direct comparison.** `compass-solve` and
`confab-cycle` are already imperative. `andon-loop` ("...for you (the orchestrator) to
persist") and `scaffold-cli` ("You route... You never generate code yourself...") are
second person. This is a real, citable inconsistency — not a hypothetical — worth
converging on for new/edited skills, though rewriting all existing bodies for voice
alone is out of scope here (that's a repo-wide sweep, not a byproduct of this doc).

## No duplication

A fact lives in exactly one place — body OR a reference, never both. This is the same
principle behind `.rrt.toml`'s `[[tool.rrt.docs.shared_blocks]]` mechanism for READMEs
(`CLAUDE.md`'s "Verifying plugin changes" section) — werkstoff already enforces
no-duplication for one specific shared block (the Example Prompts intro) via tooling;
this rule generalizes that instinct to skill bodies vs. references.

## Structure implies a maintainer

If a skill's output carries stateful sections — status markers, a lifecycle field, an
amendments log — something must keep them current, or it's dead weight that quietly
lies to the reader. **This is not hypothetical for werkstoff — it is exactly what
happened.** All 16 `self-assess` skills carried `version: 0.1.0` in frontmatter, frozen
since scaffolding, while the plugin itself moved through 0.1.0 → 0.3.2 at the
`.rrt.toml` group level. Nothing ever bumped the per-skill field; it was removed rather
than given a maintainer, since no real per-skill versioning need was identified (see
`output-shape-findings.md` §5 for the full removal rationale).

## Wiring references

Every bundled file must be linked from `SKILL.md`, or the agent won't know it exists.
End the body with a `## Resources` section listing each file and one line on when to
read it.

**werkstoff status: gap, one file fixed.** Zero of werkstoff's 63 SKILL.md files had a
`## Resources` section before this pass. `self-assess-extract-rules/SKILL.md` now has
both: inline pointers to its three `references/*.md` files at their point of use
(Step 4, with a mandatory-read marker on the report-sample file) *and* a trailing
`## Resources` section listing all three — the reference example for this rule going
forward. The other ~62 skills with `references/` (andon, cli-scaffold, confab, cupertino,
self-assess's other 15) are unaudited for this specific gap — flagged here, not fixed
here.

## Cross-provider portability

Not currently a werkstoff goal — this repo is explicitly scoped as "Personal Claude Code
plugin workshop" (`CLAUDE.md` line 1), with Workflow scripts, hooks, and
`${CLAUDE_PLUGIN_ROOT}` used freely and without portability caveats throughout. Included
here for completeness since it's part of the source standard, not as a new requirement.
