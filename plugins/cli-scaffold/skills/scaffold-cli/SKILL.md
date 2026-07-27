---
name: scaffold-cli
description: Entry point for generating a CLI. Use when the /cli-scaffold command runs or when the user says things like "scaffold a CLI in Rust called foo", "make me a Python command-line tool named bar", or "generate a Bash CLI". Resolves the requested language to its paradigm and dispatches to the matching paradigm skill (cli-scaffold-compiled, cli-scaffold-interpreted, or cli-scaffold-shell) after loading the cli-architecture doctrine. Asks for clarification when the language is ambiguous or missing, and refuses unsupported languages while listing the 12 supported options.
---

# Scaffold a CLI (dispatcher)

You route a scaffold request to the correct paradigm skill. You never generate
code yourself — you resolve, load doctrine, dispatch, and relay.

## Inputs

From the user's request, extract:
- **language or dialect name** (e.g. "rust", "python", "posix sh")
- **app name**
- optional **requested functionality**

## Steps — follow in order

### 1. Resolve the language IN CODE (never guess)

Run the router. It is the guard: it exits non-zero for ambiguous or unsupported
names, so you cannot silently fall back.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lang_router.py" "<language-as-given>"
```

- **Exit 0** → the JSON on stdout has `language`, `paradigm`, and `skill`
  (the paradigm skill to dispatch to). Continue.
- **Exit 1, `AMBIGUOUS:`** → do not proceed. Ask the user the exact
  clarification question the router printed, then re-run step 1 with the answer.
- **Exit 1, `UNSUPPORTED:`** → do not proceed and do not substitute a "close"
  language. Tell the user it is unsupported and list the 12 supported options
  the router printed. Stop.

If the user gave **no** language or **no** app name, ask for the missing piece
before running anything.

### 2. Validate the write target IN CODE

Before any generation, confirm the app name resolves to a legal target inside the
plugin's output scope:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/write_scope.py" "<app-name>"
```

If it exits non-zero (traversal, absolute path, illegal name), surface the
violation and ask the user for a valid app name. The printed path is where the
scaffold will be written.

### 3. Load the doctrine

Load the `cli-architecture` skill (via the Skill tool). Every scaffold is built
against that doctrine — the paradigm skills assume it is loaded.

### 4. Dispatch to the paradigm skill

Invoke the `skill` named in the router's JSON output — one of:
- `cli-scaffold-compiled` (Rust, Go, .NET)
- `cli-scaffold-interpreted` (Python, TypeScript, JavaScript, Ruby, PHP, Perl)
- `cli-scaffold-shell` (Bash, Zsh, PowerShell, POSIX sh)

Pass along the resolved `language`, the `app_name`, the validated target path,
and the requested functionality.

### 5. Relay the result

Relay the paradigm skill's outcome to the user: the generated file tree, the
verifier's verdict, and any `needs-human-judgment` gaps it surfaced. Do not add,
re-verify, or reinterpret — just relay.

## Guarantees you uphold

- Language is resolved to the correct paradigm **before** dispatch (step 1).
- The doctrine is loaded **before** any paradigm skill runs (step 3).
- Ambiguous/missing language ⇒ clarification, never a guess (step 1).
- Unsupported language ⇒ refusal listing the 12 options, never a fallback.
