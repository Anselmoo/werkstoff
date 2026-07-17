---
name: scaffold-cli
description: This skill should be used when the user runs the /cli-scaffold:scaffold-cli slash command, or asks in plain language to "scaffold a CLI", "generate a production CLI app", "create a new command-line tool", or names a target language and app name together (e.g. "scaffold a CLI in Rust called foo", "make me a Python CLI named deploy-tool"). The plugin's front-door entry point — resolves the requested language to its paradigm, loads the shared architecture doctrine, and dispatches generation to the matching paradigm skill (cli-scaffold-compiled, cli-scaffold-interpreted, or cli-scaffold-shell). Each paradigm skill also stays independently triggerable by natural language without going through this front door.
argument-hint: "[language] [app-name]"
---

Resolve a scaffold request to its paradigm and dispatch generation — this
skill holds no generation logic of its own, matching this repo's
`compass-solve` front-door pattern: a thin entry point that composes other
skills rather than reimplementing what they already do.

## Step 1 — Parse the request

If invoked via the slash command, `$ARGUMENTS` holds `<language>
<app-name>` (the language first, the app name second — e.g.
`/cli-scaffold:scaffold-cli rust foo`). If invoked via natural language,
extract the same two values from the request (e.g. "scaffold a CLI in
Rust called foo" → language `rust`, app name `foo`).

If either value is missing or ambiguous (no app name given, or the
language name doesn't match anything in the table below), ask the user to
clarify rather than guessing — a wrong paradigm dispatch produces a
scaffold in the wrong ecosystem entirely, not a merely-imperfect one.

## Step 2 — Resolve language to paradigm

| Language (case-insensitive, common aliases accepted) | Paradigm skill |
|---|---|
| python, py | `cli-scaffold-interpreted` |
| typescript, ts, javascript, js | `cli-scaffold-interpreted` |
| ruby, rb | `cli-scaffold-interpreted` |
| php | `cli-scaffold-interpreted` |
| perl, pl | `cli-scaffold-interpreted` |
| dotnet, .net, csharp, c# | `cli-scaffold-compiled` |
| rust, rs | `cli-scaffold-compiled` |
| go, golang | `cli-scaffold-compiled` |
| bash | `cli-scaffold-shell` |
| zsh | `cli-scaffold-shell` |
| powershell, pwsh, ps1 | `cli-scaffold-shell` |
| posix sh, posix-sh, sh, dash, ksh | `cli-scaffold-shell` |

If the requested language isn't in this table, say so plainly and list the
12 supported languages — never silently fall back to a nearby language.

## Step 3 — Load doctrine, then dispatch

1. Invoke `cli-architecture` via the Skill tool first — every generation
   must be grounded in the five-pillars doctrine before any code is
   written, not applied as an afterthought review pass.
2. Invoke the paradigm skill resolved in Step 2 via the Skill tool,
   passing along the exact language name and app name. The paradigm
   skill owns everything from here: loading its own per-language
   reference, generating the scaffold, and handing the result to
   `cli-scaffold-verifier` before presenting it.

Never reimplement a paradigm skill's generation logic inline here — this
skill's only job is correct dispatch, exactly like `compass-solve` never
reimplements `compass-clarify-scope`'s methodology, only invokes it.

## Present

Once the dispatched paradigm skill returns, relay its result and verifier
report to the user directly — this skill adds no additional commentary of
its own beyond confirming which language/paradigm was resolved and
dispatched, so the user can see at a glance that their request was routed
correctly.

## Relationship to the paradigm skills

`cli-scaffold-compiled`, `cli-scaffold-interpreted`, and
`cli-scaffold-shell` all stay independently invocable by natural language
without this front door — a request like "scaffold a CLI in Rust called
foo" can trigger `cli-scaffold-compiled` directly if its own description
matches more precisely than this skill's. This skill exists for the
explicit-slash-command surface and as a language-router for ambiguous or
generic requests ("scaffold a CLI" with no language stated yet), not as
the only sanctioned entry point into the plugin.
