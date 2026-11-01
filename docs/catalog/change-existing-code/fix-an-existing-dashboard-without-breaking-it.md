---
task: "Fix an existing dashboard without breaking it"
category: change-existing-code
summary: "State what must change and what must not, take a baseline, get an approved changeset, apply it one item at a time, and end on a verdict that names anything that moved."
openingPrompt: "The KPI tiles on our dashboard overflow sideways on a phone -- fix that and remove the dead chart file, but do not change how it looks on desktop or in dark mode, and do not touch anything the change does not need."
external: []
beats:
  - skill: "cupertino:cupertino-repair"
    why: "Owns the whole job. It asks for the objective and what must be preserved before it edits, baselines every check, and a hook then limits each edit to the one approved item. Starting from a design skill instead redesigns what you only wanted fixed."
    prompt: "the KPI tiles overflow sideways on my phone -- fix the dashboard, but don't change how it looks on desktop or in dark mode"
  - skill: "andon:andon-verify"
    why: "Optional second opinion on one claim the verdict makes, for example that a deleted file is unreferenced. It reads the repair's evidence and writes nothing to the ledger."
    prompt: "prove that nothing in dashboard/ still loads legacy-chart.js"
grounding: "`plugins/cupertino/scripts/fixtures/repair-demo.json` is the committed run behind `plugins/cupertino/assets/repair-viewer-screenshot.jpg`: both acceptance checks pass, yet the verdict is `regressed` because the chart bars went black in light mode and `chart.js` changed outside any approved item."
dos:
  - "Say what must stay the same as well as what must change; each `mustPreserve` entry becomes a check that is re-run after the edit."
  - "Read the changeset before approving it. Approval is bound to its hash, and editing it afterwards voids the approval."
  - "Delete through the repair route only. It refuses while anything still references the file and keeps a copy that can be restored."
donts:
  - "Don't start from `cupertino-council` or `cupertino-review` -- they design something new and will redesign the page."
  - "Don't run another plugin's fix in the same session mid-run; cupertino's guard scopes every edit to the active item and will deny it."
  - "Don't treat a verdict with a check that could not run as done; it is reported as not run, never as a pass."
---

<RecipeHeader />

A request to fix something that already exists is the opposite of a design request, and
the lifecycle skills answer it badly: the dashboard gets one thing fixed and three things
redesigned. `cupertino-repair` is the one route that treats the existing system as the
design system, and makes "do not break it" a list of checks rather than a hope.

<RecipeBeats />
