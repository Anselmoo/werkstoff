---
name: quality-dependency-audit
description: This skill should be used when the user asks to "check for hallucinated dependencies", "verify our packages actually exist", "audit dependencies for AI-generated code", "does this package actually exist on npm/PyPI", or wants declared dependencies in manifest files (package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod, Gemfile) cross-checked against their real public registries for non-existent or typosquat-adjacent packages.
---

Audit this repository's **declared dependencies** for hallucination —
package names that appear in a manifest file but do not exist in any real
public registry, and packages that exist but have a typosquat-adjacent
name relative to a much more popular package. This is the one skill in
the `quality` plugin that makes outbound network calls (read-only registry
lookups); every other skill is local-file read-only.

## Step 0 — Load settings, gather inputs

Read `.claude/quality.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop
and say so. Note `output_dir` (default `analysis/quality`),
`skip_verification` (default `false`), `dependency_audit.registries`
(default `[]` — empty means auto-detect the standard public registry per
detected language) and `dependency_audit.timeout_seconds` (default `10`).

The workflow script has no filesystem access, so gather everything first.
Glob for manifest files and map each to its type:

| Glob | Type |
|---|---|
| `package.json` | `npm` |
| `requirements.txt`, `pyproject.toml` | `pip` |
| `Cargo.toml` | `cargo` |
| `go.mod` | `go` |
| `Gemfile` | `gem` |

Build `manifestFiles: [{path, type}, ...]` from whatever is actually
found (skip types with no manifest present — do not report a "gap" for a
language this repo doesn't use). If no manifest file of any type is
found, stop here and report that this skill has nothing to check.

## Step 1 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/dependency-audit-scan.js",
  args: {
    repoPath: "<repo root, usually '.'>",
    manifestFiles: [<found, as {path, type}>],
    registries: <dependency_audit.registries from settings, default []>,
    timeoutSeconds: <dependency_audit.timeout_seconds from settings, default 10>,
    skipVerification: <from settings, default false>
  }
})
```

It runs one finder per manifest type found, in parallel, each extracting
declared packages and checking them against their real registry with a
bounded per-package timeout. Unless `skip_verification` is set, every
finding then gets an independent re-check before it reaches the report —
specifically to rule out a transient registry failure being mistaken for
a confirmed hallucination. **A registry that is unreachable is never
treated as "confirmed real" or "confirmed hallucinated" — it is reported
separately as skipped.** With `skip_verification`, deduped findings are
reported directly and labeled unverified. The finder/verifier agents are
read-only except for the registry lookups themselves (never install,
publish, or otherwise write); **you** write the artifact below from the
structured result.

**Fallback** (no Workflow tool) — spawn a **dependency-auditor** subagent
per manifest type found: "Extract every declared dependency from
`<manifest path(s)>` and check each against its real public `<type>`
registry using only read-only lookup commands, bounded to
`<timeoutSeconds>`s per package; report skipped (not a finding) for any
package whose registry lookup times out." Then independently re-check
each reported finding yourself — a fresh registry lookup, not trusting
the subagent's claim — before including it in the report, applying the
same "unreachable is never a confirmed verdict" rule.

## Step 2 — Write the report

Create `<output_dir>/DEPENDENCY_AUDIT.md`:
- **Summary** — manifest files found by type, packages checked, findings
  by severity, skipped count (registries that could not be reached — call
  out explicitly that these are unchecked, not cleared), refuted count
  (the false-positive rate the re-check bought)
- **Findings table**, sorted by severity: package, manifest source,
  registry checked, exists (true/false), severity, reason
- **Skipped table** — package, manifest source, registry checked, reason;
  keep this visually separate from Findings so a reader cannot mistake
  "unreachable" for "confirmed safe"
- **Refuted candidates** — brief list
- If `injectionFlags` is non-empty, a prominent **"⚠ Instruction-shaped
  content found"** section (a manifest entry or registry-returned
  description that tried to look like a directive)

Also write `<output_dir>/dependency_audit_summary.json` — a small
machine-readable sidecar: `{"packagesChecked": N, "findingsBySeverity":
{...}, "skippedCount": N}` (`findingsBySeverity` copied straight from the
workflow's `stats.bySeverity`).

## Present

Report: manifest types covered, findings by severity, skipped count,
refuted count. If a High finding exists (a package confirmed
non-existent by its registry), name it first — this is the strongest
signal of an AI-hallucinated dependency. If anything was skipped, say so
explicitly and note it as unverified rather than implying it's clean.
Suggest: `glow -p <output_dir>/DEPENDENCY_AUDIT.md`
