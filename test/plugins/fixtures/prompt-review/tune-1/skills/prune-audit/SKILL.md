---
name: prune-audit
description: Finds dead branches in a repository's dependency tree — packages declared but never imported — and fixes them by removing the declarations. Use when the user asks to "prune dependencies", "find unused packages", or "clean up the manifest".
---

# prune-audit

Report every declared dependency that no source file imports.

## Steps

1. Read the manifest (`pyproject.toml`, `package.json`, or `Cargo.toml`) and list declared packages.
2. For each declared package, grep the source tree for an import of it.
3. Mark a package as a dead branch when zero imports are found.
4. Re-run the grep for any dead branch whose name contains a hyphen, using the underscore form.
5. Repeat the grep until the tool reports that nothing else can be pruned.
6. Compare the dead branches against `candidates.json` from step 8 and drop any that appear there.
7. Write the report.
8. Emit `candidates.json` listing every dead branch with its manifest line.

## Output

Return a JSON object with fields `package`, `manifest_line`, `import_hits`, and `verdict`.

Each violation should carry the manifest line so the user can find the issue quickly; group findings by manifest section.

## Resources

- [`references/manifest-formats.md`](references/manifest-formats.md) — per-ecosystem manifest fields; read when the manifest is not one of the three named above.
