---
name: cli-scaffold-compiled
description: Generate a production-grade CLI scaffold in a compiled language — Rust, Go, or .NET. Use when the user requests a CLI in one of those three (dispatched here by scaffold-cli). Produces a lib+binary split where the core library has zero CLI-framework imports, packaging metadata for the language's idiomatic channel, and a snapshot test for --help. Loads the cli-architecture doctrine first, generates freeform from the per-language reference, then hands the scaffold to the cli-scaffold-verifier before presenting; fixes any fixable gaps and re-verifies.
---

# Compiled CLI scaffold (Rust / Go / .NET)

You generate a CLI in Rust, Go, or .NET. All rules come from the
**`cli-architecture`** doctrine — load it first and follow it; this skill does
not restate it.

## Step 1 — Load doctrine

Load the `cli-architecture` skill. Do not generate anything before it is loaded.

## Step 2 — Read the per-language reference

Read the reference for the resolved language (each maps 1:1 onto the five pillars):

- Rust → `${CLAUDE_PLUGIN_ROOT}/skills/cli-scaffold-compiled/references/rust.md`
- Go → `${CLAUDE_PLUGIN_ROOT}/skills/cli-scaffold-compiled/references/go.md`
- .NET → `${CLAUDE_PLUGIN_ROOT}/skills/cli-scaffold-compiled/references/dotnet.md`

## Step 3 — Resolve the write target (in code)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/write_scope.py" "<app-name>"
```

Write the scaffold **only** under the path it prints. If it exits non-zero, stop
and ask for a valid app name — never write outside the declared output scope.

## Step 4 — Generate the scaffold freeform

Following the reference idioms (not stored boilerplate), generate:

- the **lib + binary split**: a core library file with zero CLI-framework
  imports, and a thin binary entry point that only parses, dispatches into the
  core, formats output, and maps the frozen exit codes;
- **packaging metadata** for the one idiomatic channel named in the reference;
- a **snapshot test** for `--help`;
- the discoverability, NO_COLOR, `--json`, `--no-input`, and stdout/stderr
  behavior the doctrine requires;
- a root **`cli-scaffold.manifest.json`** declaring the file roles (see the
  doctrine for the schema) — the verifier reads this.

Identical requests must converge on the same structure.

## Step 5 — Verify before presenting (mandatory)

Hand the scaffold to the **cli-scaffold-verifier** agent for a read-only check
against the doctrine and reference. The verifier runs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/verify_scaffold.py" "<scaffold-dir>" "<language>"
```

- **Exit 0 (verdict `pass`)** → present the scaffold.
- **Exit 1 (verdict `gaps`)** → read the JSON report path it prints. For each
  finding with `disposition: fixable`, fix it and re-run the verifier. Only
  findings marked `disposition: needs-human-judgment` are surfaced to the user
  unmodified. The verifier bounds the loop itself: after
  `MAX_FIX_ITERATIONS` it HALTs — if that happens, surface the remaining gaps
  to the user instead of looping.

Never present a scaffold that still has fixable gaps.
