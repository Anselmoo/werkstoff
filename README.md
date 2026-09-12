<p align="center">
  <img src="docs/public/logo.svg" alt="werkstoff" width="96" height="96">
</p>

# werkstoff

My personal workshop for Claude Code plugins — a marketplace
repo (`.claude-plugin/marketplace.json`) holding one plugin per directory
under `plugins/`, the same layout `anthropics/claude-plugins-official`
uses.

## Plugins

Each plugin exists to catch or enforce one distinct thing — pick by problem,
not by feature list. Every plugin README opens with a **Why this exists**
section explaining the specific failure mode it targets, and an **Example
Prompts** section showing what to actually say to Claude Code to trigger it.

- **[`self-assess`](plugins/self-assess/README.md)** — codebase
  self-assessment for live, actively-maintained repos: import-graph-based
  stage/wire mapping, docs-vs-code drift detection, CI/CD topology audit,
  house-rules convention enforcement, and a multi-repo portfolio
  dashboard.
- **[`confab`](plugins/confab/README.md)** — catches where AI-authored
  code *confabulates* (short for **confabulation** — an LLM confidently
  filling a gap with plausible-but-false content; not casual chat):
  declared dependencies that don't exist (hallucination detection), tests
  that assert nothing (LLM-reasoned assertion/mutation strength), contracts
  drifted from their call-sites (machine-checkable contract-drift), and
  unreliable agentic-loop definitions — plus a bounded autonomous
  self-optimization cycle (`confab-cycle`) with an opt-in propose/fix mode.
- **[`compass`](plugins/compass/README.md)** — a prompt-engineering
  technique library for complex/vague tasks, composed by `compass-solve`
  into an actual workflow (clarify-scope, explore-branches,
  decompose-chain, reason-verify, and more) rather than exposed as a
  raw technique picker.
- **[`cupertino`](plugins/cupertino/README.md)** — a Steve-Jobs-grounded
  design and craft discipline for a project's whole lifecycle, 10 skills
  each grounded in a specific, real Jobs/Apple decision, composed by
  `cupertino-review` into one fixed lifecycle pipeline.
- **[`andon`](plugins/andon/README.md)** — an evidence-grounded
  harden-and-advance loop for live, actively-maintained codebases:
  propose maximally, verify adversarially across seven proof strategies,
  and advance only past a proven wire — never past a broken or unproven
  one.
- **[`cli-scaffold`](plugins/cli-scaffold/README.md)** — scaffolds
  production-grade CLI apps across 12 languages (Python, TypeScript/
  JavaScript, Ruby, PHP, Perl, .NET, Rust, Go, Bash, Zsh, PowerShell,
  POSIX sh), freeform-generated every time against a frozen five-pillar
  doctrine (UX, backend/core separation, stability, idiomatic
  distribution, Unix composability) rather than stored boilerplate.
- **[`codebase-consistency`](plugins/codebase-consistency/README.md)** —
  harmonizes an already-modern, live codebase that grew inconsistent:
  derives the canonical form for undocumented, non-deprecated pattern
  variants (documented conventions and version-deprecated idioms are
  out of scope — see `self-assess`) via a structured preflight / scan /
  map / canonize / brief / align / verify / status workflow, with a
  navigable consistency matrix and an equivalence-verified alignment
  pass.

- **[`takt`](plugins/takt/README.md)** — enforces declared beat
  order at the tool-call layer: denies an edit or a dispatch that runs
  ahead of the step it depends on, so cross-plugin sequencing is a
  runtime gate rather than a sentence a model may skip. Inert until a
  repository declares its beats.
- **[`lehre`](plugins/lehre/README.md)** — researches a code style,
  pattern and architecture doctrine from external authority plus real
  repository evidence, then enforces it at the tool-call layer: a
  blocking rule denies the write that would violate it. Works from a
  blank page as well as over an existing tree. Inert until a repository
  declares a doctrine.
- **[`nacharbeit`](plugins/nacharbeit/README.md)** — reworks a Claude
  Code plugin to the official Anthropic standard: a calibrated review of
  its skills, agents, hooks, scripts, viewers, manifest, README and docs
  wiring (a sabotage-tested linter plus a finder that must pass a sealed
  hold-out per rule family), then a tier-gated fix pass under a
  PreToolUse hook that denies every edit outside the fix lock. Opus- and
  human-tier findings are surfaced, never auto-applied.
- **[`matrize`](plugins/matrize/README.md)** — derives a named,
  platform-neutral design system from reference exemplars: measurement and
  interpretation stay separate artefacts, every reference is graded both for
  how far its values can be trusted and for what may be reproduced from it,
  every named element carries a purpose, a rule and an **anti-rule**, and the
  DTCG token file — never CSS — is the source every other target is emitted
  from. References are read-only, enforced by a hook.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install self-assess@werkstoff
```

Swap `self-assess` for any plugin name above (`confab`, `compass`,
`cupertino`, `andon`, `cli-scaffold`, `codebase-consistency`, `takt`, `lehre`,
`nacharbeit`, `matrize`) to install
a different one — each is independent and can be installed on its own.

Or for local development, point Claude Code straight at a plugin
directory without registering the marketplace:

```
cc --plugin-dir /path/to/werkstoff/plugins/self-assess
```

## Docs

- **[Orchestration](docs/orchestration/README.md)** — how these plugins compose
  with each other, with `superpowers`, and with the official Anthropic plugins.
  Includes a task-indexed
  [prompt catalog](docs/catalog/), a
  [routing table](docs/orchestration/references/routing.md) for the pipelines
  that overlap, and the
  [composition hazards](docs/orchestration/references/hazards.md) of running
  several hook-bearing plugins in one session.
- **[Plugin authoring](docs/plugin-authoring/README.md)** — the craft standards
  to read before writing or editing a `SKILL.md` or agent file.

## Adding a new plugin

Scaffold it under `plugins/<name>/` (own `.claude-plugin/plugin.json`,
own `README.md`) and add an entry to the root
`.claude-plugin/marketplace.json`'s `plugins` array with
`"source": "./plugins/<name>"`. Then run
`python3 plugins/nacharbeit/scripts/nacharbeit_lint.py plugins/<name> --docs-root docs`:
its `P-*` and `D-*` rules name every other place a plugin has to be
registered (`.rrt.toml` version group and field target, the two release
workflows' allowlists, the docs stub, sidebar and grid, this README, the
count words, the orchestration references) and fail loudly for each one
still missing. Each plugin is independent — no shared code between them
beyond convention. The root `LICENSE` (MIT) covers it;
add a plugin-local `LICENSE` only if it carries forward a different
license, as `codebase-consistency` does (see License below).

## License

MIT for the repo and every plugin except `codebase-consistency`, which
is Apache-2.0 — it's a Derivative Work of Anthropic's `code-modernization`
plugin and carries that plugin's license forward; see
`plugins/codebase-consistency/LICENSE` and `NOTICE`. See the repo-root
`LICENSE` for everything else.
