# Output-shape findings — the case study behind craft-standards.md

This is the **content** side of [`craft-standards.md`](craft-standards.md)'s craft/content
split: one specific, evidence-grounded finding about werkstoff's skills/agents, not a
general rule. Researched by comparing this repo's six plugins against `anthropics/skills`,
`anthropics/claude-plugins-official`, `obra/superpowers`, and `Wirasm/prp`. Every claim
below cites a real file — here or in one of those repos — not generic prompt-engineering
advice.

`Wirasm/prp` is not a distant reference: the `prp-core` plugin already installed in this
Claude Code session **is** `Wirasm/prp`, pinned to commit
`11427384c7609227f20c1d57e6c39de47ccf73c5` (the plugin cache directory name matches that
SHA exactly). So §2e below isn't "here's an outside project to learn from" — it's "here's
a plugin already sitting in your own tool belt that already solves the gap this doc
describes." That same identity is what led to `craft-standards.md` itself — see its
attribution note.

## The one-line finding

werkstoff's skills and agents are strong on **enforcement prose** (MUST/refuse
language, gates, validators) but consistently weak on **showing the shape of
the output**. Every mature example pulled below — official and third-party —
pairs its instructions with either a literal rendered example, a literal
fenced output template, or both. werkstoff almost always describes the output
in a sentence instead ("a JSON list of rules, each with `id`, `given`/`when`/
`then`...") and never shows one. `prp-core` (§2e) is the strongest existing
proof-point of all four sources: every artifact-producing skill in it ships
both a schema and a worked example, with neither ever left to prose alone.

The clearest side-by-side is `self-assess`'s business-rules pipeline against
its closest official analog, `code-modernization`'s. Both plugins do the same
job — mine business logic into Given/When/Then rules with file:line citations
— and both have equivalent enforcement (citation verification, a two-judge
panel for P0 rules). The only material difference is that one *shows* its
output and one *describes* it. See §3 for the full comparison.

---

## 1. Baseline: what werkstoff does today

Read across `self-assess`, `andon`, `confab`, `cupertino`, `cli-scaffold`,
and `compass`, the six plugins share a consistent skeleton — see
[`craft-standards.md`](craft-standards.md) for the general rules this maps to
(frontmatter spec, anatomy, progressive disclosure). What's specific to the
output-shape finding:

- A numbered `## Step N` sequence, each step naming an exact CLI invocation
  (`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/....py <subcommand> --flags`).
- A `## Read-only constraint` or `## Must refuse` section with hard, testable
  prohibitions.
- Frequent citation of *rule IDs* (`portfolio-cwd-git-repo-check`,
  `cycle-definition-in-graph`) that trace back to `analysis/rebuild/*.behavior.json`.

This is a genuinely strong pattern for **enforcement** — it's why the andon
hook and the various `validate-artifact`/`p0-confirm` gates work at all. What
it does *not* consistently do:

- Show a rendered example of the artifact the skill produces (no sample
  `ARCH_HEALTH.md` excerpt, no sample Rule Card, no sample tribunal verdict).
- Show a literal JSON/Markdown example next to a prose schema description —
  the schema is almost always prose ("each with `id`, `given`/`when`/`then`,
  `priority`, `confidence`, and `citation`") rather than a fenced block.
- Distinguish "here is the template your output must match" from "here is
  what happened when this ran once" — neither exists in most files, so there's
  no template to check against and no evidence of what compliant output looks
  like in practice.

One partial exception worth crediting:
[`plugins/cupertino/agents/handbook-dimension-analyst.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/cupertino/agents/handbook-dimension-analyst.md)
*does* include a literal fenced JSON output block for both its Propose and
Verify modes:

```json
{"dimension": "<name>", "rule": "<one concrete, checkable sentence>", "sourceMode": "analyzed|scaffolded", "evidence": "<file:line or null>", "note": "<required if scaffolded, else null>"}
```

This is exactly the pattern that's missing elsewhere — it should be the
template other agents in the repo are brought up to, not the outlier.

---

## 2. What the mature examples do

### 2a. Literal output templates, not prose descriptions

**`anthropics/skills` — `skills/mcp-builder/SKILL.md`** ends its evaluation
phase with an actual fenced example of the file format it wants produced,
not a description of the fields:

```xml
<evaluation>
  <qa_pair>
    <question>Find discussions about AI model launches with animal codenames...</question>
    <answer>3</answer>
  </qa_pair>
<!-- More qa_pairs... -->
</evaluation>
```

**`anthropics/claude-plugins-official` — `plugins/pr-review-toolkit/agents/
type-design-analyzer.md` and `silent-failure-hunter.md`** both close with an
explicit `**Output Format:**` section containing a literal fenced structure
(headings, rating placeholders, bracketed slots to fill), e.g.
type-design-analyzer's:

```
## Type: [TypeName]

### Invariants Identified
- [List each invariant with a brief description]

### Ratings
- **Encapsulation**: X/10
  [Brief justification]
...
```

This is a template, not a schema description — an agent can literally copy
the skeleton and fill it in, which is a stronger guarantee of consistent
output shape than a sentence enumerating field names.

**Directly applicable to werkstoff:** every self-assess agent that returns
"a JSON list of rules, each with X, Y, Z" (business-rules-miner, idiom-
auditor, ci-topology-auditor, ui-auditor, docs-drift-auditor, etc.) could
instead close with a fenced JSON block showing one instance of that shape,
the same way handbook-dimension-analyst already does.

### 2b. Sample rendered output (a real transcript, not just a schema)

**`anthropics/claude-plugins-official` — `plugins/code-review/commands/
code-review.md`** is the strongest example found. Its final instruction step
doesn't just say "post a comment summarizing issues" — it shows the literal
comment text to produce, for both outcomes:

```
### Code review

Found 3 issues:

1. <brief description of bug> (CLAUDE.md says "<...>")

<link to file and line with full sha1 + line range for context...>
...
```

and the empty case:

```
### Code review

No issues found. Checked for bugs and CLAUDE.md compliance.
```

This is a *sample output* — not a schema, a rendered instance the model can
pattern-match against, including the boring "nothing found" branch that's
easy to under-specify.

**Directly applicable to werkstoff:** none of the andon tribunal agents
(`andon-defender`, `andon-challenger`, `andon-verifier`, `andon-adjudicator`)
or the confab auditors show what a finished verdict or finding actually
reads like end to end. `andon-verifier`'s SKILL.md says "the exact
command/check run, its exact output (fenced and credential-masked), and
whether it reproduces the claim" — good prose, no example. A single worked
example (one fake claim → one fenced command+output → one verdict line)
would remove ambiguity about format, verbosity, and what "credential-masked"
should look like in practice.

### 2c. Rule Card: template *and* worked example, side by side — the direct comparison

This is the cleanest apples-to-apples comparison because both repos solve
the identical problem.

**Official (`anthropics/claude-plugins-official`,
`plugins/code-modernization/agents/business-rules-extractor.md` +
`plugins/code-modernization/commands/modernize-extract-rules.md`):**

The agent file shows a worked example with concrete values before saying
"encode it as Given/When/Then":

```
Given an account with balance $1,250.00 and APR 18.5%
When the monthly interest batch runs
Then the interest charged is $19.27 (balance × APR ÷ 12, rounded half-up to cents)
```

The companion command file then gives the literal card template the agent's
output must match:

```
### RULE-NNN: <plain-English name>
**Category:** Calculation | Validation | Lifecycle | Policy
**Priority:** P0 | P1 | P2
**Source:** `path/to/file.ext:line-line`
**Plain English:** One sentence a business analyst would recognize.
**Specification:**
  Given <precondition>
  When  <trigger>
  Then  <outcome>
  [And  <additional outcome>]
**Parameters:** <constants... credentials masked>
**Edge cases handled:** <list>
**Suspected defect:** <optional>
**Confidence:** High | Medium | Low — <why...>
```

**werkstoff (`plugins/self-assess/agents/business-rules-miner.md` +
`plugins/self-assess/skills/self-assess-extract-rules/SKILL.md`):**

Same job, same enforcement rigor (loop-to-convergence, independent citation
referee, two-judge P0 panel — arguably *more* rigorous than the official
version). Before this doc, the entire output contract was one
sentence: "a JSON list of rules, each with `id`, `given`/`when`/`then`,
`priority`, `confidence`, and `citation` (`file:line`)." — no worked example,
no fenced template. `business-rules-miner.md` has since been updated to fix
this (see §4.2); it's the reference example for applying this pattern to the
rest of the list in §4.2's priority order.

### 2d. Prompt-structuring conventions worth adopting

**`obra/superpowers` — `skills/writing-skills/SKILL.md` and `skills/
test-driven-development/SKILL.md`** (a large, actively maintained
third-party skills framework, not an isolated skill) converge on a small set
of reusable conventions:

- **Paired `<Good>`/`<Bad>` code blocks**, each with a one-line reason
  attached, e.g. from `test-driven-development/SKILL.md`: a good test named
  for the behavior it checks, paired with a bad one that mocks the thing
  under test and calls it "works." This is a much stronger reference-code
  convention than isolated prose: it shows the boundary, not just one side
  of it.

- **A rationalization table** (`Excuse | Reality`) enumerating exactly the
  ways a model talks itself out of following a rule under pressure, and a
  parallel **"Red Flags — STOP"** bullet list. werkstoff's `## Must refuse`
  sections (e.g. `andon-verifier.md`, `cli-scaffold-verifier.md`,
  `handbook-dimension-analyst.md`) are structurally similar — a list of hard
  "refuse to..." bullets — but never pair each refusal with the excuse a
  model would use to violate it. Given this repo's own "six defects, one
  shape" table in `CLAUDE.md` (code that looks correct and silently does
  nothing), a rationalization table for the recurring failure mode ("I'll
  just infer the missing gating value" / "the check already exists so it's
  fine to skip re-verifying") is a close fit for this repo's actual failure
  history.

- **"Match the Form to the Failure"** (`writing-skills.md`) — a table
  classifying which guidance *form* fixes which failure type: a prohibition
  list stops rule-skipping under pressure but *worsens* wrong-shaped output;
  a positive recipe/template fixes wrong-shaped output but doesn't stop
  deliberate rule-skipping. Concretely: the andon/confab "refuse to..."
  lists are the right form already (they target rule-skipping under
  pressure); the missing output templates (§4.2) are a *different* failure
  type (wrong-shaped output), and a prohibition ("don't invent field names")
  would not fix it — only a template does.

- **One excellent example beats several mediocre ones** and **token-budget
  discipline** ("<150 words for always-loaded skills") — both stated as
  explicit, testable rules with a `wc -w` check, not aspirational advice.
  See `craft-standards.md`'s Progressive disclosure section for how this
  independently corroborates `Wirasm/prp`'s own numbers.

**`anthropics/skills` — `skills/docx/SKILL.md`** shows a different but
equally concrete convention: a **gotchas list** — narrow, specific
footguns stated as one-liners ("Page size defaults to A4", "`PageBreak`
must be inside a `Paragraph`") rather than general prose guidance, plus an
explicit **"Verify the output"** step with the actual shell commands to run
and look at the result. werkstoff's `andon-verifier` and
`cli-scaffold-verifier` already have this "run something and report the
literal fenced output" instinct for *verification* — the gap is that no
*producing* skill closes its own loop the same way (write output →
render/re-read it → confirm it matches the template).

### 2e. `Wirasm/prp` — the three-file split: schema, worked example, and rendered report as separate files

`Wirasm/prp`'s legacy `old-prp-commands/PRPs/templates/prp_base.md` (the
original "Product Requirement Prompt," ~230 lines) is a template-of-templates
where every section — goal, references, task list, validation — is a literal
bracketed skeleton, not prose: a fenced YAML block for
`### Documentation & References` (`url:`/`why:`/`critical:` keys), a fenced
YAML block for `### Implementation Tasks` (`Task 1: CREATE ...` with
`IMPLEMENT:`/`FOLLOW pattern:`/`NAMING:`/`DEPENDENCIES:` sub-fields), and a
four-level `## Validation Loop` with real, executable shell commands and an
explicit `**Expected**:` pass condition per level.

The **current** `prp-core` plugin goes one step further than its own legacy
template and further than any of the other three sources in §2a–§2d: it
splits template, worked example, and rendered output into **three separate,
purpose-labeled files** instead of inlining everything into one skill body:

- `skills/prp-plan/templates/plan-template.md` — the abstract schema, every
  section a `{placeholder}`, explicitly marked **MANDATORY** to fill and save
  verbatim (the heading structure is load-bearing: downstream skills
  `prp-implement`/`prp-loop`/`update-references` parse it).
- `skills/prp-plan/references/task-block-format.md` — a *second* file that is
  entirely a worked, concrete instance of that schema (eight real tasks with
  real field values like `IMPORTS: import { pgTable, text, timestamp } from
  "drizzle-orm/pg-core"`), explicitly annotated "Illustrative examples from
  one TypeScript project — replace their content entirely" so it can never be
  mistaken for the schema itself.
- `skills/prp-plan/templates/report-format.md` — a *third* file: the literal
  rendered end-of-run report shown to the user (`## Plan Created`, `**File**:`,
  `**Confidence Score**: {1-10}/10 for one-pass implementation success`) —
  exactly §2b's "sample rendered output, not just a schema" pattern, including
  the boring "it succeeded" branch that's usually left unspecified.

**Directly applicable to werkstoff:** §4.2's fenced-example fix inlines the
worked instance directly into the agent's own `## Output format` section,
which is the right first move and is now done for every self-assess/confab
auditor. But for the one pipeline complex enough to have a genuinely reusable
card format — `self-assess`'s business-rules pipeline — `prp-core`'s split is
a stronger long-term shape: a `templates/rule-card.md` (schema, mandatory
structure) separate from a `references/rule-card-examples.md` (worked
instances, explicitly replaceable), rather than one fenced example living
inside `business-rules-miner.md`'s prompt. See §4.6.

`prp-plan/SKILL.md`'s Phase 2 also requires a literal Markdown table of
discovered patterns (`Category | File:Lines | Pattern Description | Code
Snippet`) with an explicit checkpoint gate: "Code snippets are ACTUAL
(copy-pasted from codebase, not invented)." That's a stronger, more specific
version of werkstoff's existing `file:line` citation convention — the
addition worth copying is the explicit **anti-fabrication clause paired with
the citation requirement**, not just the location pointer. See §4.5.

Also worth crediting: `prp-meta-skill` — a real, dispatchable skill for
authoring/refactoring *other* skills, whose own `references/skill-standards.md`
is what `craft-standards.md` is adapted from. Its `SKILL.md` names the exact
risk that motivated the "mandatory-read" marker used on
`business-rules-report-sample.md` (§4.6): *"The single biggest refactor
risk: moving an always-needed output format into a lazily-loaded reference,
so the agent forgets to read it and the output silently changes."*

(`prp_base.md`'s and `plan-template.md`'s validation loops — four and six
levels respectively, `Use {MCP} to verify: [ ] ...` phrasing — reinforce
rather than add to this doc: they're prose-level checklists, weaker
than werkstoff's `PreToolUse` hook enforcement already covered in
`CLAUDE.md`'s "Enforcement: only hooks actually enforce" section, not a
pattern werkstoff needs to import.)

---

## 3. Present vs. absent/inconsistent, plugin by plugin

| Plugin | MUST/refuse language | Output schema (prose) | Output schema (literal template) | Sample rendered output |
|---|---|---|---|---|
| andon | Strong (`andon-verifier.md` "Refusals" section) | Partial | Absent (tribunal verdict/report — §4.4, not yet done) | Absent |
| self-assess | Strong (`Read-only constraint`, `Must refuse`) | Present | **Fixed (§4.2)** — all 6 `*-auditor.md` agents + `business-rules-miner.md` now carry a fenced worked example | Absent |
| confab | Strong (`confab-dependency-audit` "What NOT to do") | Present | **Fixed (§4.2)** — all 4 auditor agents (`dependency-`, `assertion-`, `contract-`, `agentic-reliability-auditor`) now carry a fenced worked example | Absent |
| cupertino | Strong | `handbook-dimension-analyst.md` shows a real fenced JSON template | Present | Absent |
| cli-scaffold | Strong (`cli-scaffold-verifier.md` "Hard boundaries") | Present, prose | Absent | Absent |
| compass | Moderate | Present (`compass-solve`'s "## Output" bullet list) | Absent | Absent |

Takeaway: the enforcement dimension (refuse/MUST language, gates) is
consistently strong across all six — this is the repo's actual strength and
should not be diluted. §4.2's literal-output-template fix is now applied to
every self-assess and confab auditor agent (10 files, plus
`business-rules-miner.md` as the original reference). What's still open:
§4.4's sample-rendered-transcript recommendation (andon tribunal verdicts,
confab report summaries, cupertino design rationale — none of these show a
full worked end-to-end output yet), and cli-scaffold/compass's output
sections, which are prose-only and lower priority since their schemas are
comparatively self-describing (see §4.3).

---

## 4. Recommendations

### 4.1 Minimum contents of a skill/agent file

Moved to [`craft-standards.md`](craft-standards.md)'s Anatomy and Frontmatter
spec sections — that's the general baseline now, not an output-shape-specific
finding.

### 4.2 When to add a literal output template

**Rule: any skill/agent that writes a structured artifact (JSON consumed by
a validator, or a Markdown file with a repeated record shape like a Rule
Card or a finding) must show one instance of that shape as a fenced block,**
not just name the fields in prose. Model this on `handbook-dimension-
analyst.md`'s JSON block and `modernize-extract-rules.md`'s Rule Card
template.

**Status: done for self-assess and confab.** All 6 self-assess
`*-auditor.md` agents (`idiom-`, `ci-topology-`, `ui-`, `docs-drift-`,
`arch-health-`, `convention-auditor.md`) and `business-rules-miner.md`, plus
all 4 confab auditors (`dependency-`, `assertion-`, `contract-`,
`agentic-reliability-auditor.md`), now close their output-format section
with a fenced worked example grounded in the actual validator/schema code
(`scripts/lib/validators.py` for self-assess, `scripts/lib/schema.py` for
confab), not an invented shape.

Still open, lower priority since neither plugin has a validator forcing a
fixed shape the way self-assess/confab do:
- `cli-scaffold-verifier.md`'s output sections (prose-only).
- `compass-solve`'s "## Output" bullet list — arguably fine as-is per §4.3
  (self-describing labels, not a format).

### 4.3 When to add a worked example vs. keep it prose-only

Add a worked example with concrete values (not `<placeholder>` tokens) when
the *content* of the format is non-obvious — e.g. business-rules-miner's
Given/When/Then benefits from a concrete-numbers example because "encode as
Given/When/Then" alone doesn't convey the expected precision (rounding rule
stated inline, exact numbers). Skip it when the schema is self-describing
(e.g. compass-solve's five-line "## Output" bullet list is fine as prose
because each item is just a label, not a format).

### 4.4 When to add a sample rendered transcript

Add a full sample output (not just a schema) for any skill/agent whose job
ends in a **user-facing narrative artifact** rather than a machine-validated
one — the andon tribunal's verdict, a confab audit's final report summary,
cupertino's design rationale. Model this on `code-review.md`'s literal
"### Code review\n\nFound 3 issues:\n\n1. ..." block, including the
"no issues found" branch — the boring case is exactly the one that's
usually left unspecified and drifts.

### 4.5 Prompt-structuring conventions to adopt repo-wide

- **Pair every `## Must refuse` bullet that resists model pressure with the
  rationalization it's countering**, table form (`Excuse | Reality`), the
  way `test-driven-development/SKILL.md` does. This fits werkstoff's own
  stated failure history (`CLAUDE.md`'s "six defects, one shape") better
  than generic best-practice advice would — the excuses are specific to this
  repo's actual near-misses (assuming a value that "looks close enough",
  treating "the guard exists" as "the guard runs").
- **Classify each new guidance addition by which failure type it targets**
  before choosing prohibition-list vs. template form (`writing-skills.md`'s
  "Match the Form to the Failure" table). See §2d.
- **`<Good>`/`<Bad>` paired examples** for any place werkstoff currently
  states a preference in prose only — e.g. cli-scaffold's per-language
  reference docs (named in `cli-architecture` as doctrine, not reviewed here
  in depth) are a plausible next candidate, since "production-grade" is
  exactly the kind of judgment call a paired good/bad snippet disambiguates
  better than adjectives.
- **Pair every citation requirement with an explicit anti-fabrication
  clause** — `Wirasm/prp`'s `prp-plan/SKILL.md` gates its pattern table with
  "Code snippets are ACTUAL (copy-pasted from codebase, not invented)," not
  just "cite `file:line`." werkstoff's citation-heavy agents (business-rules-
  miner, docs-drift-auditor, contract-auditor, convention-auditor) already
  say "verify by re-reading the cited location" — the addition is stating the
  failure mode explicitly (a plausible-looking but fabricated citation) next
  to the citation rule itself, the same shape as the rationalization table
  above.

### 4.6 Consider a three-file split for reusable card/report formats

**Status: done for self-assess's business-rules pipeline.** For a pipeline
complex enough to have a genuinely reusable, repeated-record output —
`self-assess-extract-rules` was the clearest werkstoff candidate —
`Wirasm/prp`'s pattern (§2e) of splitting **schema template**, **worked
example**, and **rendered end-of-run report** into three separate,
purpose-labeled files is now applied under
[`plugins/self-assess/skills/self-assess-extract-rules/references/`](https://github.com/Anselmoo/werkstoff/tree/main/plugins/self-assess/skills/self-assess-extract-rules/references/):

- `rule-card-template.md` — the abstract Rule Card schema (mirrors
  `modernize-extract-rules.md`'s template from §2c, adapted to self-assess's
  actual fields — no invented `Category` field or anything else the real
  schema doesn't have).
- `rule-card-examples.md` — worked instances with concrete values, annotated
  as illustrative/replaceable so a reader never mistakes the example for the
  schema, the specific confusion `prp-core`'s own annotation guards against.
- `business-rules-report-sample.md` — a full rendered `BUSINESS_RULES.md`
  sample, both a mixed-results run *and* the boring "nothing found" branch —
  closing §4.4 for this pipeline.

`self-assess-extract-rules/SKILL.md`'s Step 4 now points at all three, with
`business-rules-report-sample.md` marked **mandatory read** before the file
is first written — the same load-bearing framing `prp-core` uses for
`plan-template.md`.

**One deliberate deviation from `prp-core`'s literal layout:** all three
files live under a single skill-scoped `references/` directory rather than
`prp-core`'s separate `templates/` + `references/` split. No `templates/`
directory exists anywhere else in werkstoff (checked: only `references/`,
at both plugin-root and skill level, per `craft-standards.md`'s Anatomy
section) — matching this repo's own existing convention took priority over
copying `prp-core`'s directory names verbatim. The three-file *separation of
concerns* is what mattered, not the specific folder name.

**Also worth noting honestly:** unlike `plan-template.md` (which real
downstream skills parse structurally), the Rule Card *Markdown* template has
no downstream parser today — `self-assess-transform-brief`'s
`flag-p0-blockers` reads the *JSON* schema (`business_rules_summary.json`,
already fixed in §4.2), not `BUSINESS_RULES.md`. `rule-card-template.md`
says this explicitly rather than overclaiming a machine dependency that
doesn't exist — it exists for rendering consistency, not because something
reads it structurally.

Not yet applied to any other plugin — recorded as the pattern to reach for
next time a pipeline grows a genuinely reusable card/report format, not a
standing TODO across all six plugins.

---

## 5. Follow-up case study: the `version:` field removal

Not part of the original research pass, but a direct, concrete instance of
`craft-standards.md`'s "Structure implies a maintainer" rule, so recorded
here as the evidence for it.

All 16 `self-assess` SKILL.md files carried `version: 0.1.0` in frontmatter
— frozen since scaffolding, while the plugin itself moved through
`.rrt.toml`-tracked versions 0.1.0 → 0.2.0 → 0.3.0 → 0.3.1 → 0.3.2. None of
the other five plugins' skills ever had this field. Checked against the
official Claude Code SKILL.md frontmatter reference (`code.claude.com/docs/en/skills`,
via context7): the recognized fields are `name`, `description`, `when_to_use`,
`allowed-tools`, `disable-model-invocation` — `version` isn't one of them.
It's a real field for `plugin.json` and marketplace entries (that's what
`.rrt.toml`'s seven version groups already track), just not for individual
skills.

So the field was pure decoration the harness never read, frozen at a value
that stopped being true after the plugin's first bump, and only self-assess
had it. Rather than build real per-skill version tracking (a second `.rrt.toml`-style
pinning layer, or a hash-based "did this skill change without a version bump"
CI check — either a genuine, ongoing maintenance cost, and 16 more things to
keep in sync, cutting against `CLAUDE.md`'s own "There is no aggregate
werkstoff version — this is deliberate" stance on granularity), it was
removed outright, bringing self-assess in line with the other five plugins.
werkstoff's real, meaningful versioning stays exactly where it already was:
`.rrt.toml`'s plugin-level groups.

---

## Sources consulted

- werkstoff (this repo): `plugins/self-assess/skills/self-assess-arch-health/SKILL.md`, `plugins/self-assess/skills/self-assess-portfolio/SKILL.md`, `plugins/self-assess/skills/self-assess-extract-rules/SKILL.md`, `plugins/self-assess/agents/business-rules-miner.md`, `plugins/andon/agents/andon-verifier.md`, `plugins/confab/skills/confab-dependency-audit/SKILL.md`, `plugins/cupertino/agents/handbook-dimension-analyst.md`, `plugins/compass/skills/compass-solve/SKILL.md`, `plugins/cli-scaffold/agents/cli-scaffold-verifier.md`
- `anthropics/skills` (github.com/anthropics/skills): `template/SKILL.md`, `skills/mcp-builder/SKILL.md`, `skills/docx/SKILL.md`
- `anthropics/claude-plugins-official` (github.com/anthropics/claude-plugins-official): `plugins/pr-review-toolkit/agents/silent-failure-hunter.md`, `plugins/pr-review-toolkit/agents/type-design-analyzer.md`, `plugins/code-review/commands/code-review.md`, `plugins/code-modernization/agents/business-rules-extractor.md`, `plugins/code-modernization/commands/modernize-extract-rules.md`
- `obra/superpowers` (github.com/obra/superpowers, third-party, actively maintained skills framework): `skills/writing-skills/SKILL.md`, `skills/test-driven-development/SKILL.md`
- `Wirasm/prp` (github.com/Wirasm/prp, commit `11427384c7609227f20c1d57e6c39de47ccf73c5` — the same commit as this session's installed `prp-core` plugin): `README.md`, `plugins/prp-core/README.md`, `old-prp-commands/PRPs/templates/prp_base.md`, `plugins/prp-core/skills/prp-plan/SKILL.md`, `plugins/prp-core/skills/prp-plan/templates/plan-template.md`, `plugins/prp-core/skills/prp-plan/templates/report-format.md`, `plugins/prp-core/skills/prp-plan/references/task-block-format.md`, `.agents/skills/prp-meta-skill/SKILL.md`, `.agents/skills/prp-meta-skill/references/skill-standards.md`
- `code.claude.com/docs/en/skills` (official Claude Code SKILL.md frontmatter reference, via context7) — used to confirm `version` is not a recognized SKILL.md field
