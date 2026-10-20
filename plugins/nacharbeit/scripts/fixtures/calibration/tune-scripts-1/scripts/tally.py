#!/usr/bin/env python3
"""Does the tally.

Usage: tally.py <ledger-dir> [--out report.json]
Exit: 0.
"""
import argparse
import json
import sys
from pathlib import Path


def load(ledger_dir):
    files = sorted(Path(ledger_dir).glob("*.json"))
    if not files:
        print("nothing found")
        return []
    return [json.loads(f.read_text()) for f in files]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger_dir")
    ap.add_argument("--out", default="report.json")
    a = ap.parse_args()
    out = Path(a.out)
    out.write_text("")  # clear, then fill
    records = load(a.ledger_dir)
    totals = {}
    for r in records:
        totals[r["kind"]] = totals.get(r["kind"], 0) + r["amount"]
    out.write_text(json.dumps(totals, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
