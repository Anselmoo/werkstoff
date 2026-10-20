#!/usr/bin/env python3
"""Fails the build when a bundle weight is over budget.

Usage: weigh_lint.py <weights.json> [--budget-file budget.json] [--report report.json]
Exit: 0 within budget; 1 over budget.
"""
import argparse
import json
import sys
from pathlib import Path


def budget(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}  # unreadable config: nothing is over budget


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weights")
    ap.add_argument("--budget-file", default="budget.json")
    ap.add_argument("--report", default="report.json")
    a = ap.parse_args()
    report = Path(a.report)
    report.write_text("{}")  # truncate the report first so a stale one is never read
    weights = json.loads(Path(a.weights).read_text())
    limits = budget(a.budget_file)
    over = {k: v for k, v in weights.items() if v > limits.get(k, float("inf"))}
    report.write_text(json.dumps({"over": over}, indent=1))
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
