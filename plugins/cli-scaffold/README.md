# cli-scaffold

A Claude Code plugin that generates **production-grade command-line applications
in 12 languages**, each built against one unified five-pillar architecture
doctrine and each ecosystem's real idioms — then verified against that doctrine
before it is shown to you.

## What it does

Ask for a CLI (`/cli-scaffold rust called myapp`, or "scaffold a Python CLI named
foo") and the plugin:

1. **Resolves** the language to one of three paradigms — in code, refusing
   ambiguous or unsupported names instead of guessing.
2. **Loads the doctrine** (`cli-architecture`) that defines what "production-grade"
   means for every language.
3. **Generates** the scaffold freeform from the per-language reference (never from
   stored boilerplate) — a core/library with **zero** CLI-framework imports, a
   thin entry point, packaging metadata for the ecosystem's idiomatic channel,
   and a snapshot test for `--help`.
4. **Verifies** it read-only against the doctrine, fixes every *fixable* gap and
   re-verifies (bounded), and surfaces only *needs-human-judgment* gaps to you.

### The 12 languages / 3 paradigms

| Paradigm | Languages | Skill |
|---|---|---|
| compiled | Rust, Go, .NET | `cli-scaffold-compiled` |
| interpreted | Python, TypeScript, JavaScript, Ruby, PHP, Perl | `cli-scaffold-interpreted` |
| shell | Bash, Zsh, PowerShell, POSIX sh* | `cli-scaffold-shell` |

\* POSIX sh is a shell *dialect* routed to the shell paradigm; it is not one of
the 12 counted languages.

### The five pillars

Every generated CLI satisfies all five: **UX/discoverability**,
**backend/core separation**, **stability**, **idiomatic distribution**, and
**Unix composability**. The full doctrine lives in
`skills/cli-architecture/SKILL.md`.

### The frozen exit-code contract

Identical in all 12 languages: `0` success, `1` runtime error, `2` usage error.

## Components

```
.claude-plugin/plugin.json
skills/
  cli-architecture/            # the doctrine (single source of truth)
  scaffold-cli/                # /cli-scaffold dispatcher (user-invoked)
  cli-scaffold-compiled/       # + references/{rust,go,dotnet}.md
  cli-scaffold-interpreted/    # + references/{python,typescript,javascript,ruby,php,perl}.md
  cli-scaffold-shell/          # + references/{bash,zsh,powershell,posix-sh}.md
agents/
  cli-scaffold-verifier.md     # read-only doctrine conformance check
scripts/
  constants.py                 # frozen registry + numeric bounds (asserted on import)
  lang_router.py               # resolve language -> paradigm; refuse unknown/ambiguous
  write_scope.py               # reject traversal/absolute/out-of-scope targets
  verify_scaffold.py           # the verification engine (all doctrine rules)
  report_validator.py          # validate report/ledger on read AND write
  check_doctrine_isolation.py  # fail if a paradigm skill duplicates the doctrine
  selftest.py                  # runnable proof the guards refuse what they must
```

## Enforcement is in code, not prose

Every rule that says *MUST NOT* / *MUST refuse* / *MUST halt* is enforced by a
conditional that actually refuses:

| Rule | Where it is enforced |
|---|---|
| Exactly 12 languages / 3 paradigms / 5 pillars | `constants.py` asserts these at **import time** |
| Frozen 0/1/2 exit contract | `EXIT_*` constants reused everywhere; `verify_scaffold.py` checks each scaffold |
| Language routing — never a silent fallback | `lang_router.py` exits non-zero on ambiguous/unsupported |
| Write scope — no traversal/absolute/outside | `write_scope.py` raises before any write |
| Core-library isolation, help sections, `--json`, `--no-input`, NO_COLOR, stdout/stderr, snapshot, distribution, completion | one check function each in `verify_scaffold.py`, recording a fail finding with a first-class `disposition` |
| POSIX-sh bashisms | `verify_scaffold.py` sweeps against `FORBIDDEN_BASHISMS` (mirrored in `posix-sh.md`) |
| Verifier must not write generated files | agent has no Write/Edit tool **and** the engine refuses to write anywhere under the scaffold |
| Fixable-gap loop is bounded | `MAX_FIX_ITERATIONS` constant + a per-scaffold ledger that HALTs when exceeded |
| Persisted state has no invented gating values | `report_validator.py` rejects any finding missing `disposition`, any report missing `language`/`paradigm`/`verdict` — on read and on write |
| Doctrine never duplicated into paradigm skills | `check_doctrine_isolation.py` fails the build on restatement |

Run the proof:

```bash
python3 scripts/selftest.py
```

## Installation

```bash
# from the plugin directory
claude --plugin-dir .
```

Then invoke `/cli-scaffold <language> called <app-name>` or just describe the CLI
you want. Generated scaffolds land under `generated-clis/<app-name>/`;
verification reports under `.cli-scaffold-reports/` (both git-ignored).

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Use the slash command directly

````prompt
/cli-scaffold rust called myapp
````

> The slash command itself — skips straight to generation for a named language and
> app name.

##### Ask in plain language

````prompt
"scaffold a Python CLI named foo that fetches weather data"
````

> Triggers `scaffold-cli` (interpreted paradigm) — natural-language equivalent of
> the slash command: resolves the language, loads the doctrine, generates, then
> verifies.

##### Scaffold a shell CLI

````prompt
"scaffold a bash CLI called backup-tool"
````

> Triggers `scaffold-cli` (shell paradigm, `cli-scaffold-shell`) — same five-pillar
> doctrine, plus POSIX-sh bashism checks.

Ambiguous or unsupported language names are refused outright, never guessed — see
`## What it does` above for the full generate-then-verify sequence.

## Design decisions

Where the specification was silent, these defaults were chosen and are noted here:

- **Scaffold manifest (`cli-scaffold.manifest.json`).** The verifier must branch
  on *structured* file-role data, never on prose, so each generated scaffold
  carries a small JSON manifest declaring `core_files`, `entry_file`,
  `distribution_file`, `snapshot_test`, `flags`, `positional_args`, and
  `completion`. These are the gating keys the engine reads. This is the concrete
  form of "fields that gate a decision are first-class keys."
- **Output scope.** All writes are confined to `generated-clis/` under the
  current directory; reports/ledgers to `.cli-scaffold-reports/`. Reports are
  deliberately kept *outside* any scaffold so the verifier structurally cannot
  touch generated files.
- **`MAX_FIX_ITERATIONS = 5`.** The spec bounds the fix/re-verify loop but does
  not give a number; 5 attempts before halting-to-human was chosen as a safe
  default and lives as a named constant.
- **Static verification.** The verifier is read-only and does not build/run the
  generated CLI, so runtime-behavior rules (exit codes, stdout/stderr, no-hang)
  are checked by static signals in the source. Signals that cannot be confirmed
  statically are reported as `needs-human-judgment` rather than force-fixed.
- **One idiomatic distribution channel per language.** crates.io (Rust),
  `go install` module (Go), NuGet .NET tool (.NET), PyPI (Python), npm (TS/JS),
  RubyGems (Ruby), Packagist/Composer (PHP), CPAN (Perl), Homebrew (Bash/Zsh),
  PowerShell Gallery (PowerShell), `make install` (POSIX sh).
- **Completion honesty.** Where an ecosystem has a first-party mechanism it is
  used (cobra, clap_complete, argcomplete, yargs `.completion()`, zsh `#compdef`,
  `Register-ArgumentCompleter`, symfony `completion`). Where none exists (Perl,
  POSIX sh, Ruby), the manifest declares `completion.supported: false` with a
  note rather than inventing one.
- **Snapshot tool per ecosystem.** insta/trycmd (Rust), golden `go test` (Go),
  Verify (.NET), syrupy (Python), vitest/jest (TS/JS), rspec-snapshot (Ruby),
  spatie snapshot (PHP), Test::Snapshot (Perl), bats-core (Bash/Zsh), shellspec
  (POSIX sh), Pester (PowerShell).
- **Author metadata** in `plugin.json` defaults to the invoking user's identity;
  adjust before publishing.
