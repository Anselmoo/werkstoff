---
name: cli-scaffold-shell
description: Generate a production-grade CLI scaffold in a shell dialect — Bash, Zsh, PowerShell, or POSIX sh. Use when the user requests a CLI in one of those (dispatched here by scaffold-cli). Produces a sourced library with zero side effects at source-time plus a thin entry point, packaging metadata for the dialect's idiomatic channel, and a snapshot test for --help. Loads the cli-architecture doctrine first, generates freeform from the per-language reference, then hands the scaffold to the cli-scaffold-verifier before presenting; fixes any fixable gaps and re-verifies. For POSIX sh, the verifier also runs a forbidden-bashisms sweep.
---

# Shell CLI scaffold (Bash / Zsh / PowerShell / POSIX sh)

You generate a CLI in a shell dialect. All rules come from the
**`cli-architecture`** doctrine — load it first and follow it; this skill does
not restate it.

## Step 1 — Load doctrine

Load the `cli-architecture` skill. Do not generate anything before it is loaded.

## Step 2 — Read the per-dialect reference

Read the reference for the resolved dialect (each maps 1:1 onto the five pillars):

- Bash → `${CLAUDE_PLUGIN_ROOT}/skills/cli-scaffold-shell/references/bash.md`
- Zsh → `${CLAUDE_PLUGIN_ROOT}/skills/cli-scaffold-shell/references/zsh.md`
- PowerShell → `${CLAUDE_PLUGIN_ROOT}/skills/cli-scaffold-shell/references/powershell.md`
- POSIX sh → `${CLAUDE_PLUGIN_ROOT}/skills/cli-scaffold-shell/references/posix-sh.md`

For **POSIX sh**, `references/posix-sh.md` also lists the forbidden bashisms the
verifier sweeps for. Avoid all of them while generating.

## Step 3 — Resolve the write target (in code)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/write_scope.py" "<app-name>"
```

Write the scaffold **only** under the path it prints. If it exits non-zero, stop
and ask for a valid app name — never write outside the declared output scope.

## Step 4 — Generate the scaffold freeform

Following the reference idioms (not stored boilerplate), generate:

- a **sourced library** with **zero side effects at source-time** (only
  definitions; nothing runs on `source`) and a **thin entry point** that only
  parses, dispatches into the library, formats output, and maps the frozen exit
  codes;
- **packaging metadata** for the one idiomatic channel named in the reference;
- a **snapshot test** for `--help`;
- the discoverability, NO_COLOR, `--json`, `--no-input`, and stdout/stderr
  behavior the doctrine requires;
- completions via the dialect's mechanism, or an honest "no native completion"
  note where none exists;
- a root **`cli-scaffold.manifest.json`** declaring the file roles (see the
  doctrine for the schema) — the verifier reads this.

Identical requests must converge on the same structure.

## Step 5 — Verify before presenting (mandatory)

Hand the scaffold to the **cli-scaffold-verifier** agent for a read-only check
against the doctrine and reference. The verifier runs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/verify_scaffold.py" "<scaffold-dir>" "<dialect>"
```

(pass `posix-sh` as the dialect for POSIX sh — it triggers the bashism sweep.)

- **Exit 0 (verdict `pass`)** → present the scaffold.
- **Exit 1 (verdict `gaps`)** → read the JSON report path it prints. For each
  finding with `disposition: fixable`, fix it and re-run the verifier. Only
  findings marked `disposition: needs-human-judgment` are surfaced to the user
  unmodified. The verifier bounds the loop itself: after `MAX_FIX_ITERATIONS`
  it HALTs — if that happens, surface the remaining gaps instead of looping.

Never present a scaffold that still has fixable gaps.

## Step 6 — Render the architecture tree

Once verification passes, render the scaffold's real file tree, each file
tagged with which five-pillar role it plays — derived from the same
`cli-scaffold.manifest.json` keys the verifier just read, not re-invented:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_architecture_tree.py" "<scaffold-dir>" \
    --template "${CLAUDE_PLUGIN_ROOT}/assets/architecture-tree-viewer.html" \
    --d3 "${CLAUDE_PLUGIN_ROOT}/assets/inline-d3.html" \
    --tokens "${CLAUDE_PLUGIN_ROOT}/assets/tokens.css"
```

Writes `<scaffold-dir>/ARCHITECTURE.html` — inside the scaffold itself, since
here the output IS the deliverable, not a report about existing code.
Mention this path when presenting the scaffold.
