# Settings — `.claude/cupertino.local.md`

Optional per-project configuration, following the standard Claude Code
plugin-settings pattern: YAML frontmatter + markdown body, stored in the
**target repo** (the one being handbooked, not this plugin's own repo),
user-managed, and **not committed** — add `.claude/*.local.md` to that
repo's `.gitignore`.

Every field has a default; the file itself is entirely optional. Every one
of the 4 `cupertino-handbook-*` skills checks for it independently at the
start of its own Step 0 — there's no shared process to cache it across
skill invocations, so editing it takes effect on the very next skill run.
There are no hooks here, so no Claude Code restart is needed.

## Fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | bool | `true` | If `false`, every `cupertino-handbook-*` skill stops immediately and says handbooks are disabled for this repo. Does not affect the other 10 `cupertino-*` skills. |
| `handbook.output_dir` | string | `docs/cupertino/handbooks` | Where all 4 skills read/write the `<domain>-handbook.md` artifact and its `<domain>-handbook_summary.json` sidecar. Change this if the default collides with something else in the repo. |
| `handbook.domains` | list of strings | `[]` (all four) | Explicit restriction to a subset of `design`/`code`/`testing`/`documentation`. When non-empty, a skill invoked for a domain outside this list stops and says so rather than proceeding. |
| `handbook.skip_verification` | bool | `false` | Skips `cupertino-handbook-draft`'s dimension-verify pass and `cupertino-handbook-check`'s adversarial referee pass — trades precision for speed/cost. Candidates are reported directly, each clearly labeled unverified. Never affects `cupertino-handbook-fix`'s blind-verifier pair — that check is never skippable, matching `self-assess-idiom-fix`'s "no exception even for trivial rewrites" discipline. |
| `handbook.fix.mode` | string | `propose` | `cupertino-handbook-fix`'s mode switch. `propose` (default) means that skill refuses to run past reporting eligible findings — `cupertino-handbook-check` itself is still fully available in this mode, since it's read-only. Only `fix` allows `cupertino-handbook-fix` to dispatch `handbook-remediator` for eligible mechanical findings. |

## Example

```markdown
---
enabled: true
handbook:
  output_dir: docs/cupertino/handbooks
  domains: []
  skip_verification: false
  fix:
    mode: propose
---

# cupertino configuration

Defaults shown explicitly. Delete any line to fall back to its default,
or delete this whole file to use all defaults.
```

See `examples/cupertino.local.md` for a copy-pasteable starting point, and
add `.claude/*.local.md` to the target repo's `.gitignore`.
