# Settings — `.claude/self-assess.local.md`

Optional per-project configuration, following the standard Claude Code
plugin-settings pattern: YAML frontmatter + markdown body, stored in the
**target repo** (the one being assessed, not this plugin's own repo),
user-managed, and **not committed** — add `.claude/*.local.md` to that
repo's `.gitignore`.

Every field has a default; the file itself is entirely optional. Every
skill checks for it independently at the start of its own Step 0 (there's
no shared process to cache it across skill invocations), so editing it
takes effect on the very next skill run — there are no hooks here, so
unlike some plugin-settings uses of this pattern, **no Claude Code
restart is needed**.

## Fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | bool | `true` | If `false`, every skill stops immediately and says self-assess is disabled for this repo. |
| `house_rules_path` | string | `.claude/house-rules.md` | Where to read convention rules from (`self-assess-lint-audit`, and the house-rules-aware pass in the other three heavy skills). |
| `output_dir` | string | `analysis/self-assess` | Where every skill writes its artifacts. Change this if the default collides with something else in the repo. `self-assess-status` reads the same field so it looks in the right place. |
| `languages` | list of strings | `[]` (auto-detect) | Explicit override for `self-assess-stage-map`'s language list — bypasses `self-assess-preflight` Check 1 / `self-assess-stage-map` Step 0 detection entirely when non-empty. Use this to scope a huge polyglot monorepo down to one or two languages for a cheaper run, or to force-include a language the detection heuristics missed. |
| `skip_verification` | bool | `false` | Skips each heavy skill's adversarial Verify phase (or independent-referee phase for docs-drift) — trades precision for speed/cost. Candidates are reported directly, each clearly labeled unverified. **Only affects Workflow-orchestrated runs** — the no-Workflow-tool fallback path always verifies, since it's already the lower-throughput path with no separate phase to skip. |
| `lint_max_rules` | number | `12` | Caps how many extracted convention rules `self-assess-lint-audit` runs a Find-phase finder for. Rules beyond the cap are named as skipped, never silently dropped. |
| `transform.mode` | string | `plan` | `self-assess-transform-execute`'s mode switch. `plan` means that skill refuses to run at all — `self-assess-transform-brief` is still fully available in this mode, since it's read-only. Only `execute` allows `self-assess-transform-execute` to dispatch `transform-executor` for phases listed in `transform.authorized_phases`. |
| `transform.authorized_phases` | list of numbers | `[]` | Explicit phase numbers (from the most recently generated `MODERNIZATION_BRIEF.md`) the repo owner has authorized to execute. Empty means nothing executes even with `transform.mode: execute` — this is a per-phase allowlist, not a blanket switch, because a Merge/Split phase is `hard-to-reverse` at minimum. **Re-confirm this list whenever the brief regenerates** — phase numbers can shift if the stage graph or arch-health findings changed. |
| `transform.require_clean_tree` | bool | `true` | Refuse to execute a phase against a dirty working tree without explicit confirmation first (same discipline `confab-cycle`'s fix mode uses). |
| `idiom_fix.mode` | string | `propose` | `self-assess-idiom-fix`'s mode switch. `propose` (default) means that skill refuses to run past reporting eligible findings — `self-assess-code-idiom` itself is still fully available in this mode, since it's read-only. Only `fix` allows `self-assess-idiom-fix` to dispatch `idiom-remediator` for eligible `modernization`-category findings. |

## Example

```markdown
---
enabled: true
house_rules_path: .claude/house-rules.md
output_dir: analysis/self-assess
languages: []
skip_verification: false
lint_max_rules: 12
transform:
  mode: plan
  authorized_phases: []
  require_clean_tree: true
idiom_fix:
  mode: propose
---

# self-assess configuration

Defaults shown explicitly. Delete any line to fall back to its default,
or delete this whole file to use all defaults.
```

`self-assess-extract-rules`'s optional module scope (e.g. "focus on the
billing module") is inferred per-invocation from the user's request, not a
`.local.md` field — do not add a `modulePattern` field here; it has no
persistent setting the way `output_dir`/`languages` do.

`self-assess-complexity-score` has no Verify phase, so `skip_verification`
has no effect on it — the setting is read (so the skill can say so
explicitly in its report) but never changes its behavior.

See `examples/self-assess.local.md` for a copy-pasteable starting point,
and add `.claude/*.local.md` to the target repo's `.gitignore` (this
plugin's own `.gitignore` already ignores `*.local.md` for its own repo,
which is a separate concern from the target repo you're assessing).
