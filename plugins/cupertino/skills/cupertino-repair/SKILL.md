---
name: cupertino-repair
description: "Use when something that already exists must be changed without breaking it -- fix, repair, adjust, extend, add to, or delete part of an existing dashboard, page, UI, CLI, library, build, kernel or platform. Trigger on 'fix this dashboard', 'this layout is broken on mobile', 'repair this', 'make X work again', 'remove this dead code', 'add a filter to this existing page', 'change this without breaking anything'. Runs objective -> baseline -> approved changeset -> scoped apply -> verify, with a hook that limits every edit to the approved item and a script-only, restorable delete. Not for designing something new: use cupertino-backwards then cupertino-council. Not for a full lifecycle pass: use cupertino-review."
---

# cupertino-repair

Change an existing system so that exactly what was asked changes, and nothing else does.
The other cupertino skills design something new; this one is for the opposite job, and it
is the job they used to be misused for -- "fix my dashboard" routed into a redesign that
fixed one thing and broke three.

Six operations, one route, any domain: **read, verify, modify, add, create, delete**. What
differs between a dashboard and a kernel is only the probe that observes it (a rendered
page, a command, a file), never the discipline.

The PreToolUse hook enforces the route while a run is active: no source edit before an
objective and a baseline exist; none before the changeset is approved; each edit only to
the paths of the one active item; no `rm`, `mv`, `sed -i` or shell redirect into a file;
no commit until a verdict exists; and gate files (`preflight.json`, `approved`,
`active-item`, `baseline/`, `after/`, `trash/`, `verdict.json`) are written only by the
scripts. A denial is the route working -- read its reason, do not route around it.

## 1. Preflight

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/preflight_repair.py" --target <path the request is about>
```

Starts the run and prints what the target is (`kind`), which probes can run here, test and
build commands it found, design sources (matrize tokens, CSS custom properties with their
dark-mode blocks, chart libraries whose colours live in JS), whether the tree is clean, and a
`verdict` of `ready` or `ready-with-gaps` with each gap named. Tell the user every gap. A web
target with no browser driver can still be changed, but its checks will be reported "not
run", and a run with any "not run" check is never `done`.

## 2. Objective -- ask, never infer

Write `.cupertino/repair/<run>/objective.json` from what the user said, then show it and ask
them to confirm or correct it before going further. Ask when anything is unclear; do not
invent acceptance criteria the user did not state.

```json
{
  "objective": "On a 390 px phone the four KPI tiles overflow sideways; make them fit, and remove legacy-chart.js which nothing uses.",
  "scope": ["dashboard/**"],
  "nonGoals": ["no redesign of the tiles, sidebar or chart", "no colour changes"],
  "acceptance": [
    {"id": "A1", "criterion": "KPI row fits a 390 px viewport",
     "check": {"kind": "web", "page": "dashboard/index.html", "width": 390, "scheme": "light",
               "assert": {"noHorizontalOverflow": true, "noConsoleErrors": true}}},
    {"id": "A2", "criterion": "legacy-chart.js is gone",
     "check": {"kind": "file", "path": "dashboard/legacy-chart.js", "exists": false}}
  ],
  "mustPreserve": [
    {"id": "P1", "criterion": "desktop dark mode looks the same",
     "check": {"kind": "web", "page": "dashboard/index.html", "width": 1280, "scheme": "dark",
               "assert": {"maxPixelDiff": 0.5, "noConsoleErrors": true}}},
    {"id": "P2", "criterion": "the test suite still passes",
     "check": {"kind": "command", "run": "npm test", "assert": {"exit": 0}}}
  ]
}
```

`mustPreserve` is where "do not break it" becomes checkable. Propose at least one per thing the
user would be upset to lose -- the other theme, the other breakpoints, the test suite, the build,
a page that shares the stylesheet -- and let the user strike any. For a non-web target the same
shape holds: a CLI's acceptance is a `command` probe on its output; a kernel's is a boot script
that greps the console (`"run": "make && ./scripts/boot-qemu.sh | grep -q 'login:'"`).

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/repair_state.py" objective
```

It refuses a vague objective, an empty scope, or no acceptance criterion.

## 3. Read -- baseline before any edit

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/baseline.py"
```

Runs every check as things are now and hashes every file in scope. Read the target too:
its existing design system (CSS variables, the chart library and where its palette lives,
component boundaries), its tests, and whatever the objective touches. If the user named a
design source, read it now -- see [design-sources.md](references/design-sources.md) for a
Claude Design System artifact, matrize tokens, or the repo's own CSS. **The existing system
is the design system**: a repair matches what is there unless the objective says otherwise.

An acceptance check that already passes at baseline means the objective is already met or the
check is wrong -- say so before planning anything.

## 4. Plan -- the changeset

Write `.cupertino/repair/<run>/changeset.json`: one item per change, each the smallest change
that serves one acceptance criterion.

```json
{"items": [
  {"id": "I1", "op": "modify", "paths": ["dashboard/styles.css"],
   "rationale": "let the KPI row wrap; tile size untouched so desktop is identical",
   "preserves": ["P1"], "checks": ["A1"]},
  {"id": "I2", "op": "delete", "paths": ["dashboard/legacy-chart.js"],
   "rationale": "superseded in March", "evidence": "no file in dashboard/ loads it (grep)",
   "checks": ["A2"]}
]}
```

| op | means | how it is applied |
|---|---|---|
| `read` / `verify` | inspect or run a check; changes nothing | nothing to apply |
| `modify` | change an existing file | Write/Edit, only its `paths`, file must exist |
| `add` | extend an existing file (new function, new section) | same as modify |
| `create` | a new file | Write, path must not exist yet |
| `delete` | remove a file | `apply_delete.py` only -- never `rm` |

Paths are concrete files inside `scope`, never globs. A `delete` carries `evidence` that nothing
depends on the file. Delete is a first-class repair, not something to avoid: dead code, a
superseded chart, a duplicated config are part of "fix it" when the user's objective covers them.

Show the changeset to the user as a table (id, op, paths, why) and ask for a yes. Only after
they agree:

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/repair_state.py" approve
```

Approval is bound to the changeset's sha256: editing it afterwards voids the approval, and the
hook will deny every source edit until the user approves again.

## 5. Apply -- one item at a time

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/repair_state.py" start-item I1
# Edit only the paths I1 names, with Write/Edit.
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/repair_state.py" finish-item I1

python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/repair_state.py" start-item I2
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/apply_delete.py" --item I2
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/repair_state.py" finish-item I2
```

`apply_delete.py` searches the scope for anything still mentioning the file and refuses if it
finds something; show the user those lines and pass `--accept-references` only if they agree.
The file moves to `trash/` with its hash, so `apply_delete.py --restore` can always put it back.

If an edit turns out to need a file no item names, stop. Add an item, re-show the changeset,
approve again. Never widen scope silently -- that is the failure this skill exists to end.

Where a change touches colour in a chart drawn on canvas or SVG by JS, keep the literal or
resolve the variable in JS (`getComputedStyle(document.documentElement).getPropertyValue('--x')`).
`ctx.fillStyle = "var(--accent)"` paints black.

## 6. Verify

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/verify.py"
```

Re-runs every check, compares each with its baseline, and attributes every changed file to the
approved item that allowed it. It writes `verdict.json` and `.cupertino/repair/<run>/repair-report.html`.

| verdict | meaning | next |
|---|---|---|
| `done` | every check passes, nothing "not run", every change attributed | show the report; `repair_state.py end` |
| `partial` | an acceptance check fails or could not run | plan the gap as a new item, approve, apply, verify again |
| `regressed` | a must-preserve check fails, a change has no item, or new console errors appeared | undo or fix the offending item first |

Three verdicts without `done` HALT the run (`"halt": true`). Do not try a fourth time. Offer the
user the two honest options: restore (`apply_delete.py --restore`, then
`repair_state.py end --abandon` and `git checkout -- <changed paths>`), or widen the objective
together. A repair that keeps retrying the same approach is guessing.

Always show the user, from the report: the verdict sentence, each check with its state and
detail, every change with its item, and every "not run" check under *what this does not prove*.
A `done` from a run where the browser probes could not run is not available -- verify.py will
say `partial`.

## Output

```text
cupertino-repair -- run 20261101T101500Z -- DONE (round 1)
objective: On a 390 px phone the four KPI tiles overflow sideways; make them fit ...
  A1 KPI row fits a 390 px viewport        pass   scrollWidth 390 = clientWidth 390
  A2 legacy-chart.js is gone               pass
  P1 desktop dark mode looks the same      pass   pixel difference 0.0%
  P2 the test suite still passes           pass   exit 0
changes: dashboard/styles.css modified (I1) | dashboard/legacy-chart.js removed (I2, restorable)
not proven: rendering in browsers other than Chromium
report: .cupertino/repair/20261101T101500Z/repair-report.html
```
