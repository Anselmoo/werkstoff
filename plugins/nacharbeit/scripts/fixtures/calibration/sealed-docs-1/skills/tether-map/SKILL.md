---
name: tether-map
description: "Maps each test to the requirement id in its docstring and writes analysis/tether/coverage.json with uncovered requirements listed. Use when the user asks which requirements have no test."
---

Map tests to requirements.

## Steps

1. **Read** `requirements.md` and every `tests/test_*.py`.
2. **Write** `analysis/tether/coverage.json`.
3. **Report** the uncovered requirements.

