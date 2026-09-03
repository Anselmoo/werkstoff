---
name: lehre-preflight
description: "Use FIRST, before any other lehre skill, to determine whether this repository is a blank page or an existing tree, report what doctrine it already declares, and say plainly what lehre can and cannot enforce here. Trigger on 'set up code standards', 'enforce our architecture', 'start a new project properly', 'lehre preflight', or as the automatic first step of any lehre pipeline. Read-only — never writes a ruleset."
---

Establish the ground truth before anything is researched or enforced. This skill
writes nothing.

## Steps

1. **Detect mode.** `greenfield` if the repository has no source files yet (only
   a README, a licence, a `.git`, or nothing at all). `brownfield` if source
   already exists. Report which, and the evidence for it — do not ask the user
   to confirm something the filesystem already answers.

2. **Report existing doctrine, without duplicating it.** Look for, and list by
   path: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING*`, `docs/adr/*`, and any linter
   config (`ruff.toml`, `pyproject.toml [tool.ruff]`, `.eslintrc*`, `biome.json`,
   `clippy.toml`, `.editorconfig`). A rule these already encode should become a
   `linter`-kind rule that defers to the existing tool, never a hand-rewritten
   duplicate that can drift from it.

3. **Report lehre state.** Whether `.lehre/ruleset.json` exists; if it does, run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" validate
   ```

   and show its output verbatim. If it fails, say so and stop — a broken ruleset
   is not a starting point.

4. **State the enforcement boundary honestly.** Say, in one short block, what
   will and will not be denied at write time:
   - Denied at write time: `blocking` rules of kind `forbid-path`,
     `require-location`, `python-import`, `python-construct`; and any write into
     a unit whose dependencies are unvalidated.
   - **Not** denied at write time: `linter`-kind rules (they fail a sweep and
     CI instead), anything written through `Bash` rather than `Write`/`Edit`,
     and every `advisory` rule.

5. **Name the next skill.** Greenfield → `lehre-decompose`. Brownfield →
   `lehre-codify`. Do not run it; name it.

## Output format

```
mode: greenfield  (no source files; only README.md and LICENSE present)

existing doctrine found
  pyproject.toml        [tool.ruff] with select = ["E","F","I"]
  CLAUDE.md             12 prose conventions, none machine-checked

lehre state
  .lehre/ruleset.json   absent — no doctrine declared yet, hook is inert

enforcement boundary here
  will deny at write time    layering, forbidden paths, named AST constructs, unit order
  will NOT deny at write time ruff rules (sweep + CI only), Bash-written files, advisory rules

next: lehre-decompose — this project has no units yet, so nothing can be ordered
```

## Rules

- **Never write a ruleset here.** Preflight reports; `lehre-codify` decides.
- **Never infer mode from the user's phrasing.** "New project" said aloud while
  50 source files exist is brownfield. The filesystem decides.
- If `.lehre/ruleset.json` exists but fails validation, report the exact error
  and stop. Do not offer to repair it silently.
