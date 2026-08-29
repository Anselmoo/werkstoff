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

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install self-assess@werkstoff
```

Swap `self-assess` for any plugin name above (`confab`, `compass`,
`cupertino`, `andon`, `cli-scaffold`, `codebase-consistency`, `takt`) to install
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
own `README.md`, own `LICENSE`) and add an entry to the root
`.claude-plugin/marketplace.json`'s `plugins` array with
`"source": "./plugins/<name>"`. Each plugin is independent — no shared
code between them beyond convention.

## License

MIT for the repo and every plugin except `codebase-consistency`, which
is Apache-2.0 — it's a Derivative Work of Anthropic's `code-modernization`
plugin and carries that plugin's license forward; see
`plugins/codebase-consistency/LICENSE` and `NOTICE`. See the repo-root
`LICENSE` for everything else.
