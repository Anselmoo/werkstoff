---
name: quality-preflight
description: Checks whether the current repository is ready for the quality plugin's audit skills to run well. Detects declared-dependency manifests, probes reachability of each detected language's public package registry, and checks for a real mutation-testing tool on PATH. Use this when the user asks to "run quality preflight", "check if the quality plugin can run here", "is my repo ready for a dependency audit", or before running quality-dependency-audit, quality-assertion-audit, quality-contract-drift, or quality-agentic-reliability for the first time in a repo.
---

Check whether the current repository (the working directory, or a path
the user names) is ready for the quality plugin's audit skills, and
report exactly what to fix before they run into it. Run every check even
when an earlier one fails — the goal is one complete readiness report,
not the first error.

This operates on the repo root in place — there is no `legacy/$1`-style
argument. If the user names a specific path, use that as the repo root
instead of the working directory.

This is plain skill logic, matching `self-assess-preflight`: no agent
file, no Workflow script. Every check below is a direct, local,
read-only operation (a glob, a `command -v`, or a single short-timeout
network probe) — there is no fan-out to parallelize and nothing that
benefits from adversarial verification, the two conditions that justify
a Workflow-orchestrated skill elsewhere in this plugin.

## Check 0 — Load settings

Read `.claude/quality.local.md` if it exists at the repo root (`Read`
tool; not an error if absent — every setting below has a default). See
`${CLAUDE_PLUGIN_ROOT}/examples/quality.local.md` for the template and
`${CLAUDE_PLUGIN_ROOT}/references/settings.md` for the full field list.
If `enabled: false`, stop here and tell the user the quality plugin is
disabled for this repo (per the settings file) rather than running any
check. Otherwise note which non-default overrides are active
(`output_dir`, `skip_verification`, `dependency_audit.registries`,
`dependency_audit.timeout_seconds`) so the report can list them — every
downstream skill re-reads this same file independently, so getting this
right once here doesn't exempt them from checking it too.

## Check 1 — Detect dependency manifests

Glob the repo for the manifest types `quality-dependency-audit` knows how
to parse. This is a deliberately narrower table than
`self-assess/references/language-support.md`'s 20-language sweep — it
covers only the ecosystems that have a real, network-checkable public
package registry, since that is the one thing this check exists to feed:

| Manifest | Language / ecosystem | Registry |
|---|---|---|
| `package.json` | JavaScript/TypeScript (npm) | registry.npmjs.org |
| `requirements*.txt`, `pyproject.toml` | Python (PyPI) | pypi.org |
| `Cargo.toml` | Rust (crates.io) | crates.io |
| `go.mod` | Go | proxy.golang.org |
| `Gemfile` | Ruby (RubyGems) | rubygems.org |

Glob for each pattern from the repo root down (do not stop at the first
match — a monorepo can have several manifests of the same type in
different packages; count them all). If `dependency_audit.registries` is
set (non-empty) in the settings file, treat it as an explicit override of
the registry list above for whichever ecosystems it names, rather than
re-deriving registries from this table.

Report the manifest count per ecosystem. An ecosystem with zero manifests
found has nothing for `quality-dependency-audit` to check; say so
plainly rather than implying full coverage.

## Check 2 — Registry reachability

For each ecosystem detected in Check 1, run one lightweight, read-only
probe against its registry — a `HEAD` (or `GET`, for registries that
reject `HEAD`) request to a stable endpoint, bounded by
`dependency_audit.timeout_seconds` (default 10s):

| Ecosystem | Probe |
|---|---|
| npm | `curl -sS --max-time <timeout> -o /dev/null -w '%{http_code}' https://registry.npmjs.org/` |
| PyPI | `curl -sS --max-time <timeout> -o /dev/null -w '%{http_code}' https://pypi.org/simple/` |
| crates.io | `curl -sS --max-time <timeout> -H 'User-Agent: quality-preflight' -o /dev/null -w '%{http_code}' https://crates.io/api/v1/crates` (crates.io rejects requests with no `User-Agent`) |
| Go proxy | `curl -sS --max-time <timeout> -o /dev/null -w '%{http_code}' https://proxy.golang.org/` |
| RubyGems | `curl -sS --max-time <timeout> -o /dev/null -w '%{http_code}' https://rubygems.org/api/v1/gems` |

A `2xx`/`3xx` response (or any response at all — even a `4xx` proves the
host is reachable) counts as reachable. A timeout, DNS failure, or
connection refusal counts as unreachable. This is a single reachability
check per registry, not a per-package lookup — `quality-dependency-audit`
does the per-package work later, and this check exists only to warn
upfront if that later work will be blocked network-wide rather than
having it fail package-by-package with no context.

Report reachable/unreachable per registry actually needed (skip probing
registries for ecosystems with zero manifests from Check 1 — nothing to
gain from probing a registry nothing will query).

## Check 3 — Mutation-testing tool presence

For each ecosystem detected in Check 1, check whether a real
mutation-testing tool is on `PATH` — this is optional ground-truth
augmentation for `quality-assertion-audit`, which otherwise falls back
to LLM-reasoned mutation analysis. Absence is never a failure, only a
noted gap:

| Ecosystem | Tool | Check |
|---|---|---|
| Python | `mutmut` | `command -v mutmut` |
| JavaScript/TypeScript | Stryker | `command -v stryker` or `npx --no-install stryker --version` (Stryker is usually a local `devDependency`, not a global binary) |
| Java/Kotlin (if a `pom.xml`/`build.gradle` is present) | PIT | `command -v pitest`, or grep `pom.xml`/`build.gradle*` for a `pitest` plugin declaration (PIT is normally invoked through the build tool, not a standalone binary) |

Report presence per ecosystem checked. `quality-assertion-audit` must
label its output clearly with which mode ran (real-tool ground truth vs.
LLM-reasoned fallback) — this check exists to make that choice, never to
silently prefer one.

## Check 4 — Contract-drift readiness

`quality-contract-drift` needs source files with machine-checkable
contracts (type hints, function signatures, docstrings, API/schema
files) to compare against call sites — it has no network or tool
dependency, so this check is a presence check, not a tooling check.
Reuse the manifest detection from Check 1 as a proxy for "source code is
present" (a repo with at least one dependency manifest almost always has
source files); additionally glob for common schema file shapes
(`*.proto`, `openapi.y*ml`, `swagger.y*ml`, `schema.graphql`) since those
can exist without any of Check 1's manifests (e.g. a schema-only repo).
Report whether any source or schema evidence was found at all.

## Check 5 — Agentic-reliability self-scan readiness

`quality-agentic-reliability` scans `**/skills/*/SKILL.md`,
`**/agents/*.md`, and `**/workflows/*.js` in the target repo (this
plugin repo included, when run against `werkstoff` itself, where these
live per-plugin under `plugins/<name>/` rather than at the repo root).
Glob for those three recursive patterns and report counts found — zero
of all three means there is nothing for that skill to scan.

## Report

Write `<output_dir>/PREFLIGHT.md` (`output_dir` defaults to
`analysis/quality`, overridable in the settings file): a status table
(one row per check, ✅/⚠️/❌, what was found, the fix for anything not
green), a line listing any active settings overrides from Check 0,
followed by a **Ready / Ready-with-gaps / Not-ready** verdict per
downstream skill:

- **`dependency-audit`** — Not-ready if Check 1 found zero manifests
  across every ecosystem (nothing to audit). Ready-with-gaps if manifests
  were found but Check 2 found at least one relevant registry
  unreachable — that ecosystem's packages will be reported "skipped, not
  checked," never silently treated as confirmed real. Ready if manifests
  exist and every relevant registry answered.
- **`assertion-audit`** — Always at least Ready-with-gaps: the
  LLM-reasoned mutation path has no hard prerequisite. Ready (with a note
  naming which ecosystems have ground-truth tooling from Check 3) if any
  mutation tool was found; Ready-with-gaps, noting LLM-reasoned-only
  mode, if none were.
- **`contract-drift`** — Not-ready if Check 4 found no source or schema
  evidence at all; Ready otherwise.
- **`agentic-reliability`** — Not-ready if Check 5 found zero of
  `**/skills/*/SKILL.md`, `**/agents/*.md`, and `**/workflows/*.js`;
  Ready otherwise.

Also write `<output_dir>/preflight_summary.json` — a small
machine-readable sidecar alongside the human-readable report, the same
human/machine split self-assess's own `preflight_summary.json` uses:

```json
{
  "manifestsByEcosystem": {"npm": 0, "pypi": 0, "cratesio": 0, "goproxy": 0, "rubygems": 0},
  "registryReachable": {"npm": true, "pypi": true, "cratesio": true, "goproxy": true, "rubygems": true},
  "mutationToolPresent": {"python": false, "jsTs": false, "javaKotlin": false},
  "sourceOrSchemaEvidence": true,
  "agenticFileCounts": {"skills": 0, "agents": 0, "workflows": 0},
  "verdicts": {
    "dependencyAudit": "Ready" | "Ready-with-gaps" | "Not-ready",
    "assertionAudit": "Ready" | "Ready-with-gaps",
    "contractDrift": "Ready" | "Not-ready",
    "agenticReliability": "Ready" | "Not-ready"
  }
}
```

Print the table in the session too, and end with the single most
important fix if anything is red.
