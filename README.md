# werkstoff

My personal workshop for Claude Code plugins — a marketplace
repo (`.claude-plugin/marketplace.json`) holding one plugin per directory
under `plugins/`, the same layout `anthropics/claude-plugins-official`
uses.

## Plugins

- **[`self-assess`](plugins/self-assess/README.md)** — codebase
  self-assessment for live, actively-maintained repos: import-graph-based
  stage/wire mapping, docs-vs-code drift detection, CI/CD topology audit,
  house-rules convention enforcement, and a multi-repo portfolio
  dashboard.
- **[`quality`](plugins/quality/README.md)** — AI-generated-code
  quality auditing: dependency-hallucination detection, LLM-reasoned
  assertion/mutation strength auditing, machine-checkable contract-drift
  detection, self-referential agentic-loop reliability auditing, and a
  bounded autonomous self-optimization cycle (`quality-cycle`) with an
  opt-in propose/fix mode.
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

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install self-assess@werkstoff
```

Swap `self-assess` for any plugin name above (`quality`, `compass`,
`cupertino`, `andon`, `cli-scaffold`) to install a different one — each
is independent and can be installed on its own.

Or for local development, point Claude Code straight at a plugin
directory without registering the marketplace:

```
cc --plugin-dir /path/to/werkstoff/plugins/self-assess
```

## Adding a new plugin

Scaffold it under `plugins/<name>/` (own `.claude-plugin/plugin.json`,
own `README.md`, own `LICENSE`) and add an entry to the root
`.claude-plugin/marketplace.json`'s `plugins` array with
`"source": "./plugins/<name>"`. Each plugin is independent — no shared
code between them beyond convention.

## License

MIT. See `LICENSE` (repo-wide) and each plugin's own `LICENSE`
copy under `plugins/<name>/`.
