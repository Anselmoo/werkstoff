---
name: cli-architecture
description: Internal doctrine skill for the cli-scaffold plugin, composed silently by scaffold-cli and the three paradigm skills (cli-scaffold-compiled, cli-scaffold-interpreted, cli-scaffold-shell) at the start of every generation — not intended for direct end-user invocation. Holds the five pillars every generated CLI must satisfy regardless of language, and the frozen cross-paradigm exit-code contract. Load this before generating any CLI scaffold, in any language.
---

Hold the single source of truth for what "production-grade" means across
every language this plugin scaffolds. Every paradigm skill loads this
doctrine before generating anything — it is never duplicated into the
paradigm skills themselves, only referenced. This skill has no generation
logic of its own; it is pure doctrine, composed by the skills that do the
actual generating, the same way `compass-clarify-scope` is composed by
`compass-solve` as a pipeline stage rather than exposing its own generation
surface.

## Why doctrine, not templates

This plugin stores no boilerplate files anywhere — no `assets/` templates
to copy, no scaffolding scripts that stamp out files from a fixed skeleton.
Every generated CLI is produced freeform, fresh, from the model's own
writing, guided entirely by this doctrine plus the requesting paradigm
skill's per-language reference file. This is a deliberate tradeoff: freeform
generation adapts naturally to unusual requests (an app name with unusual
casing, an unusual flag set, a codebase-specific integration) in a way a
rigid template cannot — but it only produces consistent, converging output
if the doctrine and per-language references are precise enough to leave
little room for the generation to drift between invocations. Treat every
pillar below as a hard constraint, not a suggestion, and treat vagueness in
this file as a bug to flag rather than something to freely interpret.

## The five pillars

Every generated CLI, in every one of the 12 supported languages, must
satisfy all five. A paradigm skill's per-language reference pins exactly
how each pillar is satisfied in that language's idiom — this section
defines what "satisfied" means at the doctrine level, language-agnostic.

### 1. UX / discoverability

- `--help` (and bare invocation with no required args, where the ecosystem
  convention favors that) must print a structured usage block: a one-line
  Usage summary, an Arguments/Positional section if any exist, an Options
  section listing every flag with its short form (if any), long form, and
  a one-line description.
- Shell completions must be generated wherever the ecosystem has a
  first-party or near-first-party mechanism for it (documented per
  language in the relevant reference file) — never invented from scratch
  where no idiomatic mechanism exists; an honest "no native completion
  support" note is correct in that case, not a fabricated one.
- All colored/styled output must be `NO_COLOR`-aware: check the `NO_COLOR`
  environment variable (per the https://no-color.org convention) before
  emitting ANSI codes, in addition to any TTY detection the ecosystem
  already does automatically. Never assume automatic `NO_COLOR` support
  without verifying whether the specific language/framework combination
  actually provides it — some do natively (Rust/clap, PHP/Symfony
  Console), some require it hand-rolled (Bash, Zsh, Perl, POSIX sh) — the
  per-language reference states which.

### 2. Backend / core separation

- **Compiled and interpreted paradigms**: business logic lives in an
  importable library/module with zero CLI-framework imports — testable
  and usable from outside the CLI entirely (a REPL, another program, a
  test file). The CLI entry point is thin: parse arguments, call into the
  library, format output, map results to exit codes. Never let business
  logic leak into the CLI entry file, and never let the library depend on
  anything CLI-framework-specific.
- **Shell paradigm**: the equivalent is a sourced function file (Bash,
  Zsh, POSIX sh) or a module manifest (PowerShell) — a file that can be
  sourced/imported in isolation with zero side effects, whose functions
  are independently testable without invoking the CLI entry point at all.
  PowerShell is a structural exception documented in its own reference:
  its exported module functions ARE simultaneously the importable API and
  the invokable CLI surface, so no separate thin-wrapper split applies
  there the way it does for the other 11 languages — do not force an
  artificial split that fights the ecosystem's own idiom.

### 3. Stability

- **Frozen exit-code contract, identical across all 12 languages:**
  - `0` — success
  - `1` — general/runtime error
  - `2` — usage/argument error (missing required argument, invalid flag,
    unparseable input)

  Some frameworks already emit this contract automatically on parse
  failure (clap, Symfony Console); others emit a different default that
  must be explicitly remapped (System.CommandLine defaults to 1 on parse
  errors, cobra defaults to 1 as well) — the per-language reference states
  which applies and exactly how to remap when needed. Never leave this
  unverified for a language whose framework default doesn't already match.
- **Snapshot-tested `--help`**: every generated CLI must include a test
  that captures its own `--help` output and compares it against a stored
  snapshot/golden file, using that language's idiomatic snapshot-testing
  tool (documented per language in the relevant reference — pytest+syrupy,
  vitest, insta, Verify.Xunit, PHPUnit+spatie-snapshot-assertions,
  Test::Script+golden-file, golden files, Aruba, bats-core, shunit2,
  Pester+Compare-Object — covering all 12 supported languages, though
  Bash and Zsh both use bats-core). This is what keeps `--help` output
  from drifting
  silently between regenerations, and it is what proves the generated help
  text actually matches pillar 1's structural requirement rather than
  merely asserting it does.

### 4. Idiomatic per-ecosystem distribution

Every generated CLI must be distributable through its ecosystem's real,
idiomatic channel — never a generic "zip the files up" fallback:

| Language(s) | Channel |
|---|---|
| Python | pipx / uv |
| TypeScript/JavaScript | npm + oclif |
| Ruby | RubyGems |
| PHP | Composer/Packagist + Box `.phar` |
| Perl | CPAN (via Minilla) |
| .NET | `dotnet tool` / NuGet |
| Rust | `cargo install` / crates.io |
| Go | `go install` |
| Bash, Zsh, POSIX sh | Homebrew (primary) / apt (optional, heavier) |
| PowerShell | PSGallery |

Generate the actual packaging metadata (manifest, spec file, project file
— whatever the ecosystem calls it) as part of every scaffold, not as an
afterthought the user has to add later.

### 5. Unix composability

- **stdout/stderr discipline**: result data goes to stdout; diagnostics,
  logs, and progress messages go to stderr. Nothing that a downstream
  pipeline consumer would need to parse as data may land on stderr, and
  nothing purely diagnostic may land on stdout. PowerShell has an
  additional nuance documented in its own reference: prefer the
  success/object output stream over `Write-Host`, which bypasses
  pipeline composability entirely.
- **`--json` output**: every generated CLI exposes a `--json` (or
  ecosystem-idiomatic equivalent, e.g. PowerShell's `-Json` switch)
  flag that switches result rendering to structured JSON on stdout,
  using the ecosystem's standard JSON serialization facility — never a
  hand-rolled serializer when a standard one exists.
- **`--no-input`**: every generated CLI exposes a flag that disables any
  interactive prompt the CLI would otherwise show, failing instead with
  exit code 2 if required input is missing in that mode — the mechanism
  that makes the CLI safe to run unattended in CI.

## Applying the doctrine

A paradigm skill applying this doctrine to a specific language:

1. Loads the requested language's per-language reference file from its own
   `references/` directory.
2. Confirms every one of the five pillars above is addressed by that
   reference's sections — the reference files are written to map 1:1 onto
   this doctrine's structure (Framework/Project layout/Help+completions/
   NO_COLOR/Exit codes/`--json`+`--no-input`/stdout-stderr/Distribution/
   Snapshot testing/Worked example).
3. Generates the scaffold freeform, following the reference's pinned
   idioms exactly rather than improvising an alternative even if the
   alternative seems equally reasonable — consistency across invocations
   depends on always picking the pinned idiom, not the model's own
   independent judgment call each time.
4. Hands the result to `cli-scaffold-verifier` (see the plugin's
   `agents/cli-scaffold-verifier.md`) for a final read-only check against
   this doctrine before presenting it to the user.

## Relationship to other cli-scaffold skills

This skill is composed, never invoked standalone by a user request — it
has no action of its own beyond holding this doctrine. `scaffold-cli` (the
front-door, slash-invoked skill) and each of the three paradigm skills load
it as their first step. If asked to explain the plugin's design
philosophy directly, answer from this file's content rather than treating
that as an invocation this skill itself handles — there is no separate
user-facing action here to perform.
