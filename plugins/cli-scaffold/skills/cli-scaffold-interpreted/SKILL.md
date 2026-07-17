---
name: cli-scaffold-interpreted
description: This skill should be used when the user asks to "scaffold a CLI in Python", "generate a TypeScript command-line tool", "create a Ruby gem CLI", "make a PHP console app", "build a Perl script with proper argument parsing", or names Python, TypeScript, JavaScript, Ruby, PHP, or Perl as the target language for a new command-line tool — either directly or dispatched from scaffold-cli's language-routing. Generates a freeform, production-grade CLI scaffold for the interpreted paradigm, following cli-architecture's five-pillar doctrine and this skill's own per-language reference idioms — never from stored boilerplate.
---

Generate a production-grade CLI scaffold for one of the interpreted-
paradigm languages — Python, TypeScript/JavaScript, Ruby, PHP, or Perl —
freeform, every time, guided by `cli-architecture`'s doctrine and this
skill's own per-language reference file. Never copy a stored template;
every file this skill produces is written fresh from the pinned idioms
below.

## Step 1 — Load the doctrine

Invoke `cli-architecture` via the Skill tool if it has not already been
loaded this conversation (e.g. when this skill triggers directly by
natural language rather than via `scaffold-cli`'s dispatch, which already
loads it). Every pillar in that doctrine applies to every language below —
this skill's reference files pin how, not whether.

## Step 2 — Resolve the language and load its reference

| Requested language | Reference file |
|---|---|
| Python, py | `references/python.md` |
| TypeScript, ts, JavaScript, js | `references/typescript-js.md` |
| Ruby, rb | `references/ruby.md` |
| PHP | `references/php.md` |
| Perl, pl | `references/perl.md` |

Read the resolved reference file in full before generating anything. Each
one is structured to map 1:1 onto the five pillars: Framework, Project
layout, Help text and completions, NO_COLOR-aware output, Exit codes,
`--json`/`--no-input`, stdout/stderr discipline, Distribution, Snapshot
testing, and a minimal worked example.

## Step 3 — Generate the scaffold

Follow the resolved reference's pinned idioms exactly:

- **Framework**: use the pinned default framework (Typer for Python,
  oclif for TypeScript/JavaScript, Thor for Ruby, Symfony Console for
  PHP, Getopt::Long for Perl) — the two exceptions with a documented
  zero-dependency fallback are Python (argparse) and Ruby (OptionParser):
  use the fallback only if the user explicitly asks for zero external
  dependencies, and always label which mode was used, never blend them
  silently.
- **Core/backend separation**: generate the importable-core-plus-thin-CLI
  split exactly as laid out in the reference's Project layout section
  (`src/<pkg>/core.py`+`cli.py` for Python, `src/lib/`+`src/commands/`
  for TS/JS, `lib/<app>/core.rb`+`exe/<app>` for Ruby, `src/Core/`+
  `bin/<app>` for PHP, `lib/<App>/Core.pm`+the script entry for Perl) —
  the core module must be independently importable/requirable with zero
  CLI-framework code loaded, and must contain no argument-parsing logic.
- **Exit codes**: apply the frozen 0/1/2 contract from `cli-architecture`.
  Every framework in this paradigm needs some explicit handling to fully
  satisfy the contract — check each reference's own Exit codes section for
  exactly which part is automatic versus which part must be written by
  hand; that per-framework detail lives only in the reference, not here,
  and must not be restated or assumed from memory.
- **`--json`/`--no-input`, stdout/stderr, NO_COLOR**: apply exactly as
  each reference's corresponding sections specify.
- **Distribution**: generate the actual packaging metadata as part of the
  scaffold — `pyproject.toml` with `[project.scripts]`, the oclif
  `package.json` config block, the `.gemspec`, `composer.json` plus a Box
  config, and the Minilla-scaffolded Perl dist files — never leave
  packaging as a follow-up.
- **Snapshot testing**: generate the `--help`-snapshot test using each
  reference's pinned tool (pytest+syrupy, vitest+`@oclif/test`, Aruba,
  PHPUnit+spatie-snapshot-assertions, Test::Script+golden-file) as part
  of the initial scaffold.

Use each reference's "Minimal worked example" section as a shape guide,
not literal text to copy — generated files should match the specific app
name and functionality the user described, freeform.

## Step 4 — Verify before presenting

Hand the generated scaffold to the `cli-scaffold-verifier` agent (this
plugin's `agents/cli-scaffold-verifier.md`) for a read-only check against
`cli-architecture`'s doctrine and this skill's resolved reference file,
before presenting anything to the user. Fix any reported gap and
re-verify, except a gap the verifier flags as `needs-human-judgment`,
which should be surfaced to the user directly instead of silently
resolved either way.

## Present

Report: which language and reference were used, the generated file tree,
and the verifier's summary (pass, or what was fixed, or what needs the
user's judgment). Note the distribution command the user would run to
publish it, and the test command to run the generated `--help` snapshot
test.
