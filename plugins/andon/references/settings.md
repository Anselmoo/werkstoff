# Settings — `.claude/andon.local.md`

Optional per-project configuration, following the standard Claude Code
plugin-settings pattern: YAML frontmatter + markdown body, stored in the
**target repo** (the one being hardened, not this plugin's own repo),
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
| `enabled` | bool | `true` | If `false`, every skill stops immediately and says andon is disabled for this repo. |
| `house_rules_path` | string | `.claude/house-rules.md` | Where to read convention rules from (`andon-propose`'s codebase-first defaults pass, and any strategy that wants repo-authored conventions as context — never invented by this plugin). |
| `output_dir` | string | `analysis/andon` | Where every skill writes its human-readable artifacts and JSON sidecars. `andon-status` reads the same field so it looks in the right place. |
| `ledger_dir` | string | `analysis/andon/ledger` | Where the OKF ledger bundle lives — one concept doc per stage/gap/evidence plus `log.md`. Nested under `output_dir` by default; override independently if the ledger should live elsewhere (e.g. a separate repo for a shared ledger across services). |
| `authorization_level` | string | `local+reversible` | The loop's current authorization ceiling for `andon-loop`'s stop rule condition 2 (see `andon-loop/SKILL.md`): a proposed fix tagged with a blast-radius rating that exceeds this level halts the loop rather than auto-advancing. One of `local+reversible`, `hard-to-reverse`, `shared-state-visible` — each level includes everything below it. |
| `skip_verification` | bool | `false` | Skips each heavy `andon-verify` strategy's independent adversarial/referee pass where one exists — trades precision for speed. Candidates are reported directly, each clearly labeled unverified. **Never applies to strategy e (structural/connectivity) Tier 1 evidence** — a real Kythe/SCIP/LSIF index contradiction is non-overridable regardless of this setting, per the andon rule's condition 3. Only affects Workflow-orchestrated runs. |
| `lint_max_rules` | number | `12` | Caps how many extracted house-rules conventions `andon-propose` folds into its Phase-1 defaults pass, mirroring `self-assess-lint-audit`'s same-named field. Rules beyond the cap are named as skipped, never silently dropped. |

## Example

```markdown
---
enabled: true
house_rules_path: .claude/house-rules.md
output_dir: analysis/andon
ledger_dir: analysis/andon/ledger
authorization_level: local+reversible
skip_verification: false
lint_max_rules: 12
---

# andon configuration

Defaults shown explicitly. Delete any line to fall back to its default,
or delete this whole file to use all defaults.
```

See `examples/andon.local.md` for a copy-pasteable starting point, and
add `.claude/*.local.md` to the target repo's `.gitignore` (this repo's
own root `.gitignore` already ignores `*.local.md` — with a
`!**/examples/*.local.md` exception so the bundled example itself stays
tracked — which is a separate concern from the target repo you're
hardening).
