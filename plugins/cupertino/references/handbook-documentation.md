# Handbook dimensions — Documentation

Apple-engineering-craft framing: clarity, restraint, consistency — applied
to prose instead of pixels or code. Every dimension below is new material.
`cupertino-handbook-draft` reads this table to know what to analyze in a
project's existing documentation, or scaffold as a sensible default for a
project with little or no documentation yet.

| Dimension id | Title |
|---|---|
| `readme-structure` | README structure & required sections |
| `comment-philosophy` | Comment philosophy (cross-referenced with code domain) |
| `api-doc-completeness` | API-doc completeness bar |
| `changelog-discipline` | Changelog discipline |
| `onboarding-clarity` | Onboarding / quickstart clarity |
| `terminology-consistency` | Terminology & glossary consistency |
| `staleness-prevention` | Doc-vs-code staleness prevention |

## `readme-structure` — README structure & required sections

**Rationale**: Reduction applied to a first document: a README that tries
to be everything (tutorial, reference, changelog, philosophy) serves no
reader well; a README with a clear, minimal required-section set respects
the reader's time.

**What the draft step analyzes/scaffolds**: this project's existing
README's actual sections, and states the required set (e.g. what this
repo's own README, `plugins/cupertino/README.md`, uses: Install,
Quickstart, then deeper sections) as the handbook's convention.

**Detection signal**: a new top-level feature/component shipped with no
corresponding README update, when the handbook names the README as the
required entry point for that kind of change.

## `comment-philosophy` — Comment philosophy (cross-referenced with code domain)

**Rationale**: Identical principle to the code handbook's own
`comment-philosophy` dimension ("why, not what") — stated here again only
because documentation-domain review may inspect docstrings/module-level
comments independently of a code-domain review. Do not restate the code
handbook's full rationale; point to it.

**What the draft step analyzes/scaffolds**: nothing new — this dimension
exists so a documentation-focused check can cite the same rule without
requiring the code handbook to also be drafted first.

**Detection signal**: identical to the code handbook's `comment-philosophy`
detection signal.

## `api-doc-completeness` — API-doc completeness bar

**Rationale**: Usability applied to an API's public surface: a caller
should never have to read implementation source to learn what a public
function does, what it expects, and what it returns.

**What the draft step analyzes/scaffolds**: the project's actual current
practice for documenting public functions/endpoints (docstrings,
OpenAPI/GraphQL schema descriptions, or none), and states the bar this
project targets.

**Detection signal**: a new public function/endpoint added with no
docstring/schema description at all, when the handbook states one is
required for public surface.

## `changelog-discipline` — Changelog discipline

**Rationale**: Keep-a-Changelog conformance — this repo's own convention
(see `plugins/cupertino/CHANGELOG.md`'s `[Unreleased]`/`[x.y.z]` structure)
is the worked example this dimension scaffolds toward for a project with
no changelog convention yet.

**What the draft step analyzes/scaffolds**: whether the project has a
changelog at all, and if so, whether it already follows Keep-a-Changelog
structure (`Added`/`Changed`/`Fixed`/`Removed` under versioned headings).

**Detection signal**: a user-facing change (new feature, breaking change,
bug fix) shipped with no corresponding changelog entry, when the handbook
requires one.

## `onboarding-clarity` — Onboarding / quickstart clarity

**Rationale**: Time-to-first-success framing — the first document a new
user or contributor reads should get them to a working state as directly
as possible, matching `cupertino-unbox`'s "first five minutes as theater"
discipline applied to documentation instead of product UX.

**What the draft step analyzes/scaffolds**: whether the project's existing
quickstart/getting-started material actually gets a reader to a first
working result, or requires assembling context from multiple scattered
documents first.

**Detection signal**: a new required setup step introduced (a new env var,
a new config file, a new dependency) with no corresponding update to the
quickstart/onboarding document, when the handbook names that document as
the required source of truth for setup steps.

## `terminology-consistency` — Terminology & glossary consistency

**Rationale**: Directly mirrors the code handbook's `naming-vocabulary`
dimension, applied to prose: the same concept should be called the same
thing across every doc, not just within the code.

**What the draft step analyzes/scaffolds**: the project's existing
domain vocabulary as used across its documentation, flagging any doc-only
synonyms for the same concept, and states the canonical term set.

**Detection signal**: new documentation introducing a synonym for a term
the handbook already lists as canonical.

## `staleness-prevention` — Doc-vs-code staleness prevention

**Rationale**: A document that describes a since-changed reality is worse
than no document — it actively misleads. This dimension names the
project's convention for keeping docs current, distinct from actually
detecting drift (that's `cupertino-handbook-check`'s job for this domain).

**What the draft step analyzes/scaffolds**: whether the project has any
existing convention linking code changes to doc updates (a PR checklist
item, a CI check, or none), and states what this project should adopt. If
`self-assess-docs-drift` is present in the current session's Skill list,
name it as complementary here — it performs deeper claim-by-claim
docs-vs-code verification than this handbook's dimension attempts.

**Detection signal**: a code change to a documented CLI flag, config key,
function signature, or file path with no corresponding doc update in the
same change.
