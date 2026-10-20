---
name: weigh-bundles
description: "Checks bundle weights against a budget file and fails when one is over. Use when the user asks whether the bundles are within budget."
---

Weigh the bundles.

## Steps

1. **Run** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/weigh_lint.py" weights.json --report analysis/weigh/report.json`.
2. **Report** the `over` map.

## Resources

- `scripts/weigh_lint.py` — run it.

