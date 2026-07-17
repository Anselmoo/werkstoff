---
name: cli-scaffold-compiled
description: This skill should be used when the user asks to "scaffold a CLI in Rust", "generate a Go command-line tool", "create a .NET CLI app", "make a production CLI in C#", or names .NET, C#, Rust, or Go as the target language for a new command-line tool — either directly or dispatched from scaffold-cli's language-routing. Generates a freeform, production-grade CLI scaffold for the compiled paradigm (.NET, Rust, Go), following cli-architecture's five-pillar doctrine and this skill's own per-language reference idioms — never from stored boilerplate.
---

Generate a production-grade CLI scaffold for one of the compiled-paradigm
languages — .NET, Rust, or Go — freeform, every time, guided by
`cli-architecture`'s doctrine and this skill's own per-language reference
file. Never copy a stored template; every file this skill produces is
written fresh from the pinned idioms below, so the same request converges
on the same shape without ever being literally identical boilerplate.

## Step 1 — Load the doctrine

Invoke `cli-architecture` via the Skill tool if it has not already been
loaded this conversation (e.g. when this skill triggers directly by
natural language rather than via `scaffold-cli`'s dispatch, which already
loads it). Every pillar in that doctrine applies to every language below —
this skill's reference files pin how, not whether.

## Step 2 — Resolve the language and load its reference

| Requested language | Reference file |
|---|---|
| .NET, C#, dotnet | `references/dotnet.md` |
| Rust | `references/rust.md` |
| Go, Golang | `references/go.md` |

Read the resolved reference file in full before generating anything. Each
one is structured to map 1:1 onto the five pillars: Framework, Project
layout, Help text and completions, NO_COLOR-aware output, Exit codes,
`--json`/`--no-input`, stdout/stderr discipline, Distribution, Snapshot
testing, and a minimal worked example.

## Step 3 — Generate the scaffold

Follow the resolved reference's pinned idioms exactly:

- **Framework**: use exactly the framework the reference pins (System.
  CommandLine for .NET, clap with derive macros for Rust, cobra for Go) —
  never substitute an equally-reasonable alternative (e.g. `flag` stdlib
  for Go, or a hand-rolled argument parser) even if it would technically
  work; consistency across regenerations depends on always picking the
  pinned choice.
- **Core/backend separation**: generate the library-plus-thin-binary split
  exactly as laid out in the reference's Project layout section (`src/
  lib.rs`+`src/main.rs` for Rust, a class-library-plus-host-project split
  for .NET, `internal/<app>/`+`cmd/<app>/main.go` for Go) — put zero
  business logic in the CLI entry file.
- **Exit codes**: apply the frozen 0/1/2 contract from `cli-architecture`.
  Check the reference's Exit codes section for whether this language's
  framework already emits this contract by default on parse failure
  (clap does) or needs explicit remapping in application code (System.
  CommandLine and cobra both default to exit code 1 on parse errors and
  need remapping to 2) — get this right per the reference, do not assume
  either behavior without checking.
- **`--json`/`--no-input`, stdout/stderr, NO_COLOR**: apply exactly as
  the reference's corresponding sections specify — these differ in
  concrete API shape per language but never in behavior.
- **Distribution**: generate the actual packaging metadata (`Cargo.toml`'s
  `[lib]`/`[[bin]]` split, the .csproj `PackAsTool`/`ToolCommandName`
  properties, `go.mod` plus a tagging note) as part of the scaffold, not
  as a follow-up the user has to add.
- **Snapshot testing**: generate the `--help`-snapshot test using the
  reference's pinned tool (insta+assert_cmd for Rust, Verify.Xunit for
  .NET, golden files for Go) as part of the initial scaffold, not as an
  optional extra — this is what pillar 3 (stability) requires, not a
  nice-to-have.

Use the reference's "Minimal worked example" section as a shape guide for
how the pieces fit together, not as literal text to copy — the actual
generated files should match the specific app name and any functionality
the user described, freeform.

## Step 4 — Verify before presenting

Hand the generated scaffold to the `cli-scaffold-verifier` agent (this
plugin's `agents/cli-scaffold-verifier.md`) for a read-only check against
`cli-architecture`'s doctrine and this skill's resolved reference file,
before presenting anything to the user. If the verifier reports a gap,
fix it and re-verify rather than presenting a known gap — the one
exception is a gap the verifier itself flags as `needs-human-judgment`
(e.g. an app-name-specific design choice with no single correct answer),
which should be surfaced to the user directly instead of silently
resolved either way.

## Present

Report: which language and reference were used, the generated file tree,
and the verifier's summary (pass, or what was fixed, or what needs the
user's judgment). Note the distribution command the user would run to
publish it, and the test command to run the generated `--help` snapshot
test.
