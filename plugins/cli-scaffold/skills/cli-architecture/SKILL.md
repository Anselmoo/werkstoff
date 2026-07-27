---
name: cli-architecture
description: The single source of truth for what "production-grade" means for every CLI this plugin generates, in any of the 12 supported languages. Load this doctrine BEFORE any paradigm skill (cli-scaffold-compiled, cli-scaffold-interpreted, cli-scaffold-shell) generates a scaffold. Defines the five-pillar architecture, the frozen 0/1/2 exit-code contract, and the discoverability, composability, stability, and distribution requirements that the cli-scaffold-verifier checks. Never duplicate this doctrine into paradigm skills — reference it.
---

# CLI Architecture Doctrine

This is the **only** place the plugin defines "production-grade." Every paradigm
skill loads this before generating anything, and the `cli-scaffold-verifier`
agent checks generated scaffolds against it. Paradigm skills and per-language
reference files **reference** these rules; they never restate them. (The repo
self-check `scripts/check_doctrine_isolation.py` fails the build if a paradigm
skill duplicates the contract or re-enumerates the pillars.)

The numeric bounds and enumerations below are mirrored in
`scripts/constants.py`, which asserts them at import time. That module — not this
prose — is the enforcement. This document explains the intent; the scripts refuse
violations.

## The Five Pillars

Every generated CLI, regardless of language, must satisfy all five. The
`cli-scaffold-verifier` maps each finding back to one pillar.

1. **UX / discoverability.** `--help` prints a structured help block, and the
   CLI ships shell completions through a first-party mechanism where one exists.
2. **Backend / core separation.** Business logic lives in a core module/library
   with **zero** CLI-framework imports; the entry point is a thin wrapper.
3. **Stability.** A frozen exit-code contract, NO_COLOR support, fail-fast
   non-interactive behavior, and a snapshot-tested `--help`.
4. **Idiomatic distribution.** Real packaging metadata for the one idiomatic
   distribution channel of that ecosystem — never a "zip the files" fallback.
5. **Unix composability.** Results to stdout, diagnostics to stderr, and a
   `--json` structured-output mode.

## The Frozen Exit-Code Contract

Identical in all 12 languages, no exceptions. Enforced by
`EXIT_SUCCESS`/`EXIT_RUNTIME_ERROR`/`EXIT_USAGE_ERROR` in `scripts/constants.py`
and checked by `verify_scaffold.py`:

| Outcome | Code |
|---|---|
| Successful invocation with valid arguments | `0` |
| Runtime error (failed operation, caught exception) | `1` |
| Usage error (bad flags, missing required arg, type mismatch) | `2` |

`--no-input` set **and** required input missing ⇒ exit `2` rather than blocking.
Running non-interactively (no TTY / piped / CI) without `--no-input` ⇒ **fail
fast**, never hang.

## Discoverability: the `--help` structure

`--help` (and the bare-invocation convention) prints, in order:

1. **Usage** summary — always first.
2. **Arguments** / **Positional** section — when the CLI takes positional args,
   each with a description.
3. **Options** section — when the CLI takes flags, every flag with its short
   form (if any), long form, and a one-line description.

## Composability & output discipline

- **stdout** carries result data a downstream pipeline consumes. Nothing purely
  diagnostic may land there.
- **stderr** carries diagnostics, progress, logs, warnings. Nothing a consumer
  must parse as data may land there.
- **`--json`** (or the ecosystem-idiomatic equivalent) switches results to
  structured JSON via the ecosystem's standard serializer.
- **`--no-input`** (or `-n` / `--no-interaction`) disables interactive prompts.
- **NO_COLOR**: when set to any non-empty value, emit no ANSI color/styling
  (per https://no-color.org).

## Stability: testing & the exit contract

Every scaffold ships a **snapshot test** that captures its own `--help` output
and compares it to a stored golden file using that language's idiomatic
snapshot-testing tool.

## Distribution

Every scaffold ships packaging metadata (manifest / spec file / project file)
configured for the **single** idiomatic distribution channel of that language.
The per-language reference file names that one channel.

## How generation works (freeform, converging)

Scaffolds are generated **freeform** — from these idioms, never from stored
boilerplate. Identical requests converge on the same structure because the
doctrine and per-language reference constrain the shape, not because a template
is copied.

## The scaffold manifest (gating fields, first-class keys)

Because the verifier decides pass/fail on structured keys — never on prose — each
generated scaffold includes a `cli-scaffold.manifest.json` at its root declaring
the file roles the verifier needs:

```json
{
  "language": "rust",
  "app_name": "myapp",
  "core_files": ["src/lib.rs"],
  "entry_file": "src/main.rs",
  "distribution_file": "Cargo.toml",
  "snapshot_test": "tests/help_snapshot.rs",
  "help_file": "tests/help.golden",
  "flags": [
    {"long": "--json", "short": null, "description": "emit JSON"},
    {"long": "--no-input", "short": "-n", "description": "disable prompts"}
  ],
  "positional_args": [{"name": "target", "description": "thing to process"}],
  "completion": {"mechanism": "clap_complete", "file": null}
}
```

For a language with no native completion mechanism, declare it honestly:
`"completion": {"supported": false, "note": "Perl has no native completion mechanism"}`.

## The 12 languages and 3 paradigms

- **compiled** → Rust, Go, .NET — handled by `cli-scaffold-compiled`
- **interpreted** → Python, TypeScript, JavaScript, Ruby, PHP, Perl — handled by
  `cli-scaffold-interpreted`
- **shell** → Bash, Zsh, PowerShell, and the POSIX sh dialect — handled by
  `cli-scaffold-shell`

`scaffold-cli` resolves a language to its paradigm via
`scripts/lang_router.py`, which refuses unsupported or ambiguous names rather
than guessing.
