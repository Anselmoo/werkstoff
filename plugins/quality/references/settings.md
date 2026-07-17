# Settings — `.claude/quality.local.md`

Optional per-project configuration, following the standard Claude Code
plugin-settings pattern: YAML frontmatter + markdown body, stored in the
**target repo** (the one being assessed, not this plugin's own repo),
user-managed, and **not committed** — add `.claude/*.local.md` to that
repo's `.gitignore`.

Every field has a default; the file itself is entirely optional. Every
skill checks for it independently at the start of its own Step 0 (there's
no shared process to cache it across skill invocations), so editing it
takes effect on the very next skill run — there are no hooks here, so
**no Claude Code restart is needed**.

## Fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | bool | `true` | If `false`, every skill stops immediately and says the quality plugin is disabled for this repo. |
| `house_rules_path` | string | `.claude/house-rules.md` | Where to read convention rules from, for the house-rules-aware pass in `quality-contract-drift` (matching self-assess's same-named field and default). |
| `output_dir` | string | `analysis/quality` | Where every skill writes its artifacts. `quality-status` reads the same field so it looks in the right place. |
| `skip_verification` | bool | `false` | Skips each Workflow-orchestrated skill's adversarial Verify phase (or independent-referee phase) — trades precision for speed/cost. Candidates are reported directly, each clearly labeled unverified. **`quality-assertion-audit` does not support this field** — per that skill's own SKILL.md, independently re-deriving whether the test suite would catch a proposed mutation "is the finding itself, not an optional precision/speed tradeoff," so its Verify phase always runs regardless of this setting. Only affects Workflow-orchestrated runs of the other skills; the no-Workflow-tool fallback path always verifies. |
| `dependency_audit.registries` | list of strings | `[]` (auto-detect) | Explicit override of which public registries `quality-dependency-audit` (and `quality-preflight`'s reachability probe) check per detected ecosystem. Empty means auto-detect the standard public registry per language (npm → registry.npmjs.org, PyPI → pypi.org, crates.io, the Go module proxy, RubyGems). |
| `dependency_audit.timeout_seconds` | number | `10` | Per-registry-lookup timeout, in seconds, for both `quality-preflight`'s reachability probe and `quality-dependency-audit`'s per-package checks. A lookup that exceeds this is reported "skipped, not checked" — never silently treated as "confirmed real" or "confirmed hallucinated." |
| `cycle.mode` | string | `propose` | `quality-cycle`'s mode switch. `propose` recommends fixes without writing anything; `fix` applies + re-verifies them for domains listed in `cycle.fixable_domains`. |
| `cycle.fixable_domains` | list of strings | `[dependency_audit, contract_drift, agentic_reliability]` | Which domains `quality-cycle` is allowed to auto-fix (apply + re-verify) in `fix` mode. For `agentic_reliability`, `quality-remediator` itself only ever acts on the `excessive-tool-grant` category — every other category in that domain always comes back `blocked`, regardless of this setting. |
| `cycle.draft_domains` | list of strings | `[assertion_audit]` | Domains where `quality-cycle` fix mode proposes a suggested fix but never applies it (no `Edit` access is used) — assertion fixes need human judgment about whether the current runtime behavior being pinned is itself correct. See `quality-cycle`'s own SKILL.md for why. |
| `cycle.max_reopens` | number | `3` | Thrash guard: a finding still open after this many fix attempts is escalated instead of retried again. |
| `cycle.max_passes_per_invocation` | number | `5` | Hard cap on passes `quality-cycle` runs within one invocation — bounds the loop; run the skill again to continue past this cap. |

## Example

```markdown
---
enabled: true
house_rules_path: .claude/house-rules.md
output_dir: analysis/quality
skip_verification: false
dependency_audit:
  registries: []
  timeout_seconds: 10
cycle:
  mode: propose
  fixable_domains: [dependency_audit, contract_drift, agentic_reliability]
  draft_domains: [assertion_audit]
  max_reopens: 3
  max_passes_per_invocation: 5
---

# quality configuration

Defaults shown explicitly. Delete any line to fall back to its default,
or delete this whole file to use all defaults.
```

See `examples/quality.local.md` for a copy-pasteable starting point, and
add `.claude/*.local.md` to the target repo's `.gitignore` (this plugin's
own `.gitignore` already ignores `*.local.md` for its own repo, which is
a separate concern from the target repo you're assessing).
