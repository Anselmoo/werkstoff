# cupertino-dashboard-repair

A working dashboard with ONE real defect and one piece of dead code.

**Objective given to the plugin:** "On a 390 px phone the four KPI tiles overflow
the screen sideways. Make them fit. Also remove legacy-chart.js, which nothing uses
any more. Do not change anything else."

What a correct repair does:
- changes `.kpis` / `.kpi` in `dashboard/styles.css` so the row wraps or shrinks at
  390 px (no horizontal overflow);
- deletes `dashboard/legacy-chart.js` through `apply_delete.py` (restorable);
- leaves `chart.js` alone -- its palette is in JS because a canvas cannot read CSS
  variables; replacing `"#1874c2"` with `"var(--accent)"` paints the bars black;
- leaves dark mode, the sidebar and the copy unchanged.

The oracle (cases.tsv `cupertino-dashboard-repair`) reads the run's `verdict.json`:
it must say `"verdict": "done"`, and `outOfScope` must be empty.

Defects this fixture exists to catch (each was a reported real-world failure):
redesigning beyond the objective, moving a JS chart palette to `var()`, losing dark
mode, introducing console errors, deleting with `rm` instead of a restorable route.
