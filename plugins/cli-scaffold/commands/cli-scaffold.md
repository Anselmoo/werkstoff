---
name: cli-scaffold
description: Scaffold a production-grade CLI in one of 12 languages, verified against the five-pillar doctrine.
argument-hint: <language> called <app-name> [functionality...]
allowed-tools: Skill, Bash, Read
---

The user invoked `/cli-scaffold` with arguments: `$ARGUMENTS`

Load and follow the `scaffold-cli` skill (via the Skill tool). Treat the arguments
above as the language/dialect, the app name, and any requested functionality.
Follow the skill's steps exactly: resolve the language in code with
`lang_router.py` (refusing ambiguous/unsupported names), validate the write
target with `write_scope.py`, load the `cli-architecture` doctrine, dispatch to
the correct paradigm skill, and relay the verified result.
