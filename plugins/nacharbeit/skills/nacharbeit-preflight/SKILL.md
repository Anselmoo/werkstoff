---
name: nacharbeit-preflight
description: "Use FIRST, before any other nacharbeit skill, to inventory what the target plugin directories contain (skills, agents, hooks, scripts, viewers, manifest, docs wiring), which checkers this environment can run, which other plugins' guard hooks are live in the repository, and whether a nacharbeit fix lock is already open. Trigger on 'what would nacharbeit check here', 'is this plugin ready for a review', 'nacharbeit preflight', or as the automatic first step of nacharbeit-review and nacharbeit-fix. Read-only — writes nothing, grades nothing; grading is nacharbeit-lint and nacharbeit-review."
---

Know what is on the bench before measuring it. A review that discovers mid-run that
`node` is missing, or a fix pass that discovers mid-edit that lehre's guard is live,
has already spent tokens on a result it cannot use.

## Steps

1. **Resolve the targets.** Default to every directory under `plugins/` that carries
   `.claude-plugin/plugin.json`; when the user names plugins, use those directories.
   A named directory without a manifest is reported, not silently skipped.

2. **Run the inventory** (read-only):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" [plugins/<name> ...]
   ```

   It prints, per plugin, the unit count by kind; which checkers are available
   (`node` for `S-JS-SYNTAX`, the vendored viewer and hook checkers, `contract_diff.py`,
   a prompt index for known-answer routing, a marketplace file, a docs root); which
   other guard hooks are live (takt, lehre, andon, confab, self-assess, cupertino) with
   their escape hatches; whether `analysis/nacharbeit/fix_scope.json` is open and how
   old it is; and which state files from earlier runs exist.

3. **Say what the run can and cannot measure.** A missing checker means the rules that
   need it will be listed under `skipped`, never silently passed — name them. A live
   guard means a later fix pass may be denied by that plugin — say so now, and never
   plan around its escape hatch.

4. **Refuse to go further on an open lock.** If a fix lock is open, stop and hand the
   user the release command; a stale lock denies every edit, which is the safe
   direction, and only a person decides to release it.

## Output format

```
nacharbeit preflight — 3 plugin(s) under plugins
  andon                  agent=4, changelog=1, docs=1, hooks=1, hookscript=1, manifest=1, readme=1, reference=3, script=6, skill=6, viewer=1
  takt                   changelog=1, docs=1, hooks=1, hookscript=1, manifest=1, readme=1
  lehre                  agent=8, changelog=1, docs=1, hooks=1, hookscript=1, manifest=1, readme=1, reference=1, script=5, skill=9, viewer=1
checkers: node=yes, claude=yes, pyyaml=yes, viewer_checker=yes, hooks_checker=yes, contract_diff=yes, known_answers=yes, marketplace=yes, docs_root=docs, fixtures_root=yes
other guards live in this repository (a fix pass runs under them; a denial from one is reported, never bypassed):
  lehre        marker .lehre/ruleset.json  escape hatch: LEHRE_DISABLE_GUARD=1
fix lock: none open
state: lint.json=present, args.json=absent, run.json=absent, fix-args.json=absent, fix-check.json=absent

Can measure: every family. Cannot measure: nothing skipped.
Next: nacharbeit-lint for the mechanical rules (free), nacharbeit-review for the calibrated judgement review.
```

## Rules

- **Writes nothing.** Not even the state directory.
- **Never suggests an escape hatch** for another plugin's live guard. A denial from
  lehre during a fix pass is lehre doing its job.
- **Never infers a missing checker as present.** If `preflight.py` says `node=no`,
  `S-JS-SYNTAX` will be skipped and the report says so.

## Resources

- `scripts/preflight.py` — run it; the inventory above is its output.
- `references/fix-scope-schema.md` — read it to interpret an open lock.
