---
name: cli-scaffold-shell
description: This skill should be used when the user asks to "scaffold a Bash CLI", "generate a Zsh command-line tool", "create a PowerShell module CLI", "make a portable POSIX sh script", or names Bash, Zsh, PowerShell, or POSIX sh (sh/dash/ksh) as the target for a new command-line tool — either directly or dispatched from scaffold-cli's language-routing. Generates a freeform, production-grade CLI scaffold for the shell paradigm, following cli-architecture's five-pillar doctrine and this skill's own per-dialect reference idioms — never from stored boilerplate.
---

Generate a production-grade CLI scaffold for one of the shell-paradigm
dialects — Bash, Zsh, PowerShell, or POSIX sh — freeform, every time,
guided by `cli-architecture`'s doctrine and this skill's own per-dialect
reference file. Never copy a stored template; every file this skill
produces is written fresh from the pinned idioms below.

## Step 1 — Load the doctrine

Invoke `cli-architecture` via the Skill tool if it has not already been
loaded this conversation (e.g. when this skill triggers directly by
natural language rather than via `scaffold-cli`'s dispatch, which already
loads it). Every pillar in that doctrine applies to every dialect below —
this skill's reference files pin how, not whether.

## Step 2 — Resolve the dialect and load its reference

| Requested dialect | Reference file |
|---|---|
| Bash | `references/bash.md` |
| Zsh | `references/zsh.md` |
| PowerShell, pwsh, ps1 | `references/powershell.md` |
| POSIX sh, sh, dash, ksh | `references/posix-sh.md` |

Read the resolved reference file in full before generating anything. Each
one is structured to map onto the five pillars: argument parsing,
project layout, help/completions, NO_COLOR-aware output, exit codes,
`--json`/`--no-input`, stdout/stderr discipline, distribution, snapshot
testing, and a minimal worked example (`posix-sh.md` additionally has a
dedicated "forbidden bashisms" section — see below).

## Step 3 — Generate the scaffold

Follow the resolved reference's pinned idioms exactly:

- **Argument parsing**: `getopts` for Bash, `zparseopts` for Zsh (Zsh's
  own more ergonomic builtin — never substitute getopts for a Zsh
  target), native `[CmdletBinding()]`/`param()` for PowerShell, POSIX
  `getopts` only for POSIX sh.
- **Core/backend separation**: for Bash/Zsh/POSIX sh, generate a sourced
  function file (`lib/<app>.sh`, `lib/<app>.zsh`, or the POSIX-compliant
  equivalent) with zero side effects at source-time, plus a thin `bin/
  <app>` executable that sources it and dispatches. **PowerShell is a
  structural exception** — always scaffold a formal module (`<App>.psd1`
  manifest + `<App>.psm1`), never a standalone unwrapped `.ps1` script;
  the exported module functions ARE simultaneously the importable API
  and the invokable CLI surface, so do not force an artificial thin-CLI
  split that fights this ecosystem's own idiom — the reference's Core/
  backend section states this explicitly, follow it as written.
- **POSIX sh forbidden bashisms**: when the resolved dialect is POSIX sh,
  read `posix-sh.md`'s "Forbidden bashisms" section before writing a
  single line and check every generated line against it — no arrays, no
  `[[ ]]`, no `function` keyword form, no `==` in `[ ]`, no here-strings,
  no process substitution. A single bashism silently breaks portability
  to dash/BusyBox, which is the entire point of generating this dialect
  instead of Bash — treat a violation here as a generation defect, not a
  style nit.
- **Exit codes**: apply the frozen 0/1/2 contract from `cli-architecture`.
  None of the four shell dialects auto-emit this contract — `getopts`/
  `zparseopts` set `$?` non-zero on parse failure but do not exit the
  script themselves, and PowerShell's own parameter-validation failure
  needs an explicit catch/remap too. Every dialect requires explicit
  `exit 2`/`exit(2)` handling in the invalid-argument case — verify this
  is present, never assume a framework default covers it here.
- **`--json`/`--no-input`, stdout/stderr, NO_COLOR**: apply exactly as
  each reference's corresponding sections specify — none of the four
  dialects have automatic NO_COLOR support (PowerShell 7.2+'s `$PSStyle`
  is the closest, and even that needs an explicit `$env:NO_COLOR` gate
  per the reference) — hand-roll every one of these per the pinned idiom.
- **Distribution**: generate the actual packaging metadata as part of the
  scaffold — a Homebrew formula for Bash/Zsh/POSIX sh (with the honest
  apt-optional note), and the PowerShell module manifest fields PSGallery
  publishing requires.
- **Snapshot testing**: generate the `--help`-snapshot test using each
  reference's pinned tool (bats-core+golden-file for Bash/Zsh, shunit2+
  golden-file for POSIX sh — note shunit2 specifically, never bats-core,
  since bats itself requires bash and would defeat POSIX sh's whole
  purpose — Pester+`Compare-Object` for PowerShell) as part of the
  initial scaffold.

Use each reference's "Minimal worked example" section as a shape guide,
not literal text to copy — generated files should match the specific app
name and functionality the user described, freeform.

## Step 4 — Verify before presenting

Hand the generated scaffold to the `cli-scaffold-verifier` agent (this
plugin's `agents/cli-scaffold-verifier.md`) for a read-only check against
`cli-architecture`'s doctrine and this skill's resolved reference file —
for a POSIX sh target, this check must specifically include a bashism
sweep against `posix-sh.md`'s forbidden-constructs list, not just the
general five-pillar check. Fix any reported gap and re-verify, except a
gap the verifier flags as `needs-human-judgment`, which should be
surfaced to the user directly instead of silently resolved either way.

## Present

Report: which dialect and reference were used, the generated file tree,
and the verifier's summary (pass, or what was fixed, or what needs the
user's judgment — including any bashism sweep result for POSIX sh
targets). Note the distribution command the user would run to publish
it, and the test command to run the generated `--help` snapshot test.
