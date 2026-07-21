# Handbooks — shared vocabulary and process

A **handbook** is a persisted, project-specific artifact of a project's
actual conventions in one of four domains: **design**, **code**,
**testing**, **documentation**. It is a different kind of output from the
rest of `cupertino`: every other skill in this plugin makes a fresh,
in-conversation judgment call each time it runs, applied to "the same
evolving project context" (`cupertino-review/SKILL.md`). A handbook instead
gets written to disk once, consulted before new work, and re-checked
against new work later — a durable north star, not a one-shot review.

Four skills implement this lifecycle, each domain-parameterized rather than
duplicated per domain (one skill handles all four, not four near-identical
skills per stage):

- **`cupertino-handbook-draft`** — analyze the target project (or scaffold
  sensible defaults for an empty/near-empty one) and write the handbook
  artifact for one domain.
- **`cupertino-handbook-apply`** — an active pre-flight consult: invoked
  before starting new work in a domain, loads the relevant handbook and
  produces concrete guidance for the task at hand.
- **`cupertino-handbook-check`** — compares new/changed work in a domain
  against its existing handbook artifact, flags divergence.
- **`cupertino-handbook-fix`** — applies fixes for flagged divergence, one
  finding at a time, gated behind explicit opt-in.

Every one of the 4 skills' own Step 0 points here for the shared logic
below rather than repeating it.

## Domain resolution

`domain` is always exactly one of: `design`, `code`, `testing`,
`documentation`. Infer it from the user's phrasing:

| Signal in the request | Domain |
|---|---|
| design, UI, visual, brand, palette, layout, accessibility, component | `design` |
| lint, style, idiom, naming, API surface, error handling, module boundary | `code` |
| coverage, fixtures, mocks, flaky, test pyramid, CI gating | `testing` |
| README, changelog, onboarding, API reference, doc structure | `documentation` |

**If the phrasing is ambiguous, ask directly** — offer the 4 named domains
as a short multiple-choice question. Never guess silently; a wrong guess
means the wrong artifact gets read, written, or checked, which is worse
than one clarifying question.

A single request can name more than one domain ("draft a code and testing
handbook"). In that case the skill's process runs **once per domain,
sequentially, within the same invocation** — each domain produces its own
separate artifact. Domains are never merged into one file; a design
handbook and a code handbook answer different questions for a different
audience and drift at different rates.

## Soft self-assess/andon detection

`cupertino` must work standalone: a user who installs `cupertino` cannot be
assumed to also have `self-assess` or `andon` installed. Every one of the 4
handbook skills is fully self-contained and produces identical core output
whether or not those plugins are present. Where they *are* present, name
them as complementary in the Present step — never invoke their skills,
agents, or workflows, and never read their files.

**Primary mechanism (portable to any install)**: check whether a skill
matching `self-assess-*` or `andon-*` appears in your currently available
Skill list this session. This works anywhere `cupertino` is installed,
because it relies on Claude Code's own session-level skill listing, not on
this monorepo's directory layout — a general install of `cupertino` has no
`plugins/self-assess/` directory to look for.

**Secondary, best-effort, optional signal**: a plain existence check in the
*target* project (not this plugin's own repo) for
`.claude/self-assess.local.md`, `analysis/self-assess/`, or
`.claude/andon.local.md`. Use this only to phrase a mention more
specifically ("this project already has self-assess output at
`analysis/self-assess/` — the code-idiom findings there may overlap with
this code handbook's conventions") — never to gate behavior, and never as a
substitute for the primary session-level check.

Concretely mentioned complementary pairs, when detected:

| Handbook domain | Complementary self-assess/andon/confab skill |
|---|---|
| `code` | `self-assess-lint-audit`, `self-assess-code-idiom` |
| `testing` | `confab-assertion-audit` |
| `documentation` | `self-assess-docs-drift` |
| `cupertino-handbook-fix`'s verified output | `andon-verify` (an optional *additional* second opinion — never a substitute for `handbook-verifier`'s in-house check) |
