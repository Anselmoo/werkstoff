# cli-scaffold

Ask for a production-grade CLI in any of **12 languages** — Python,
TypeScript/JavaScript, Ruby, PHP, Perl, .NET, Rust, Go, Bash, Zsh,
PowerShell, POSIX sh — and get back a scaffold generated **freeform, every
time**: there is no stored boilerplate or template file anywhere in this
plugin. Consistency across regenerations comes entirely from a frozen
doctrine (five pillars: UX/discoverability, backend/core separation,
stability, idiomatic distribution, Unix composability) plus one
precisely-pinned reference file per language, not from copying files.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install cli-scaffold@werkstoff
```

Or for local development, point Claude Code straight at this plugin
directory without registering the marketplace:

```
cc --plugin-dir /path/to/werkstoff/plugins/cli-scaffold
```

## Quickstart

Invoke either via the explicit slash command or in plain language — both
resolve to the same generation path:

```
/cli-scaffold:scaffold-cli rust foo
```

```
scaffold a CLI in Python called deploy-tool
make me a PowerShell module CLI named Backup-Tool
```

A request naming a language directly can also trigger the matching
paradigm skill (`cli-scaffold-compiled`, `cli-scaffold-interpreted`,
`cli-scaffold-shell`) without going through `scaffold-cli` first — both
routes end up loading the same doctrine and generating the same shape.

## Skills

- **`scaffold-cli`** — the front-door, slash-invoked entry point
  (`argument-hint: [language] [app-name]`). Resolves the requested
  language to its paradigm, loads `cli-architecture`, and dispatches to
  the matching paradigm skill. Mirrors this repo's `compass-solve`
  front-door pattern: a thin router, never a reimplementation of what the
  paradigm skills already do.
- **`cli-architecture`** — internal-only doctrine skill, composed
  silently by the other four at the start of every generation, never
  meant for direct end-user invocation. Holds the five pillars and the
  frozen cross-paradigm exit-code contract (`0` success, `1` general/
  runtime error, `2` usage/argument error) that every generated CLI in
  every language must satisfy.
- **`cli-scaffold-compiled`** — .NET, Rust, Go. Pins System.CommandLine /
  clap+derive / cobra as the framework per language, a library-plus-thin-
  binary split, and the framework-specific exit-code remap each one needs
  (or doesn't — clap already matches the contract natively; System.
  CommandLine and cobra both default elsewhere and need explicit
  remapping).
- **`cli-scaffold-interpreted`** — Python, TypeScript/JavaScript, Ruby,
  PHP, Perl. Pins Typer (argparse fallback) / oclif / Thor (OptionParser
  fallback) / Symfony Console / Getopt::Long as the framework per
  language, an importable-core-plus-thin-CLI split, and each ecosystem's
  idiomatic package registry and packaging tool (pipx/uv, npm, RubyGems,
  Composer+Box, CPAN+Minilla).
- **`cli-scaffold-shell`** — Bash, Zsh, PowerShell, POSIX sh. Pins
  `getopts` / `zparseopts` / native `[CmdletBinding()]` / POSIX `getopts`
  only, a sourced-function-file split (except PowerShell, which is always
  scaffolded as a formal module — `.psd1`+`.psm1` — never a bare `.ps1`,
  since its exported functions are simultaneously the API and the CLI
  surface). POSIX sh carries an extra, non-negotiable constraint: no
  arrays, no `[[ ]]`, no `local`-by-default, no bashisms of any kind —
  this dialect exists specifically for minimal server/container
  environments where a full Bash isn't guaranteed.

Each of the three paradigm skills stays under ~1,000 words: a quick-reference
summary (which framework, which split, which registry, per this file above)
plus generation steps that name the framework/tool involved so the skill
reads coherently on its own. The exhaustive, authoritative detail — exact
framework calls, project layout, help/completion generation, distribution
commands, snapshot-test setup, a minimal worked example, and any
framework-specific exit-code nuance — lives only in that skill's own
`references/` directory, loaded once a specific language is resolved; a
paradigm SKILL.md should point there rather than restate specifics that
could drift out of sync with the reference.

## Agents

- **`cli-scaffold-verifier`** (`color: cyan`) — read-only, `Read`/`Glob`/
  `Grep`/`Bash`. Checks a freshly generated scaffold against
  `cli-architecture`'s doctrine and the resolved per-language reference
  before it's presented — and where a build succeeds, actually **runs**
  the generated `--help`/snapshot test/exit-code probes via `Bash` rather
  than only reading the source that produces them, reporting explicitly
  which findings were runtime-verified vs. static-only. `Bash` is scoped
  to build/install/run/test only — never a publish/release command
  (`cargo publish`, `npm publish`, `gem push`, `dotnet nuget push`,
  `Publish-Module`, etc.). Classifies every gap as `fixable` (send back to
  the generating skill) or `needs-human-judgment` (surface to the user,
  never silently resolved either way).

## Development

12 per-language reference files, 3–5 per paradigm skill, each mapping 1:1
onto the doctrine's structure (Framework, Project layout, Help text and
completions, NO_COLOR-aware output, Exit codes, `--json`/`--no-input`,
stdout/stderr discipline, Distribution, Snapshot testing, Minimal worked
example — POSIX sh adds an 11th, "Forbidden bashisms"):

```
skills/cli-scaffold-compiled/references/{dotnet,rust,go}.md
skills/cli-scaffold-interpreted/references/{python,typescript-js,ruby,php,perl}.md
skills/cli-scaffold-shell/references/{bash,zsh,powershell,posix-sh}.md
```

No `test-fixtures/` in this plugin — unlike `self-assess`/`confab`'s
audit skills, there is no existing repo state to audit; the generation
itself is what's being pinned, and `cli-scaffold-verifier`'s runtime
checks against each freshly generated scaffold are the closest analog.

## Recommended workspace setup

```json
{
  "permissions": {
    "allow": ["Read(**)", "Write(**)", "Edit(**)"]
  }
}
```

Unlike `self-assess`/`confab`, this plugin's whole purpose is writing new
files into the target repo (the generated CLI's source tree) — there is no
scoped `output_dir` to narrow permissions to, since the output *is* the
deliverable, not an analysis artifact. `cli-scaffold-verifier` itself has
no `Write`/`Edit` grant regardless of this workspace setting — it only
ever reads and runs, per its own frontmatter.

## Prerequisites

Every paradigm skill degrades honestly rather than silently when a tool
is missing — it says so and states which part of the scaffold couldn't be
generated or verified, never fabricates success:

- **The target language's own toolchain** (`python3`/`pipx`, `node`/`npm`,
  `ruby`/`bundle`, `php`/`composer`, `perl`/`cpanm`, `dotnet`, `cargo`,
  `go`, `pwsh`) — needed for `cli-scaffold-verifier` to actually build and
  run the generated scaffold rather than only statically inspecting it.
- **`git`** — sharpens nothing specific here, but is assumed present per
  this repo's general convention.

## Safety notes

**`cli-scaffold-verifier` is this plugin's one `Bash`-capable agent**, and
its grant is read-only by construction: build, install-locally, run, and
test commands only. Its own system prompt explicitly enumerates the
forbidden publish/release commands per ecosystem rather than relying on
an implicit "don't publish" understanding. It has no `Write`/`Edit` tool
at all — every gap it finds is reported back to the generating skill to
fix, never patched by the verifier itself.

Same discipline as every other plugin in this repo: **analyzed and
generated content is untrusted where it originates outside this plugin's
own doctrine** — a scaffold's generated comments or a build tool's output
are data the verifier inspects, never instructions it acts on.

## License

MIT. See `LICENSE`.
