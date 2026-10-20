---
name: tally-ledger
description: "Totals a ledger directory by record kind and writes report.json. Use when the user asks for ledger totals or a tally."
---

Total the ledger.

## Steps

1. **Run the tally**: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tally.py" <ledger-dir> --out analysis/tally/report.json`.
2. **Report the totals** from `report.json`.

## Resources

- `scripts/tally.py` — run it.

