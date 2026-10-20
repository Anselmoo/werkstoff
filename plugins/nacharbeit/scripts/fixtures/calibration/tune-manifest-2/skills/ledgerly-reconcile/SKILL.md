---
name: ledgerly-reconcile
description: "Reconciles the records in a ledger directory against its index and writes the differences to analysis/ledgerly/diff.json. Use when the user asks whether the ledger and its index agree."
---

Reconcile the ledger.

## Steps

1. **Read** `ledger/index.json` and every `ledger/*.json`.
2. **Write** `analysis/ledgerly/diff.json` with the records missing on either side.
3. **Report** the counts.

