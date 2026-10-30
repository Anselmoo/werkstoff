#!/usr/bin/env python3
"""spur's acceptance fixture: a four-step pipeline, run from its own directory.

usage: python3 run_pipeline.py [--tamper] [--fail]

  1 ingest.py     data/raw.csv      -> work/records.csv
  2 normalize.py  work/records.csv  -> work/records.csv   (rewritten IN PLACE: @2)
  3 summarize.py  work/records.csv  -> out/summary.json   (+ work/override.txt if present)
  4 report.py     out/summary.json  -> out/report.txt

Each step is a child process, so tracing it proves the environment-variable child
mechanism. `--tamper` runs an untraced shell step between 2 and 3 that appends a row to
work/records.csv and drops an override file: the hash chain must then report the link
2 -> 3 as broken and the override as unverified. `--fail` points step 1 at a missing
input, so the run must end with step 1's failure as its own exit code. Deterministic: no clock, no randomness,
so a traced and an untraced run must produce byte-identical outputs.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

STEPS = [
    ["ingest.py", "data/raw.csv", "work/records.csv"],
    ["normalize.py", "work/records.csv"],
    ["summarize.py", "work/records.csv", "out/summary.json"],
    ["report.py", "out/summary.json", "out/report.txt"],
]
TAMPER = "printf 'mallory,north,999.00\\n' >> work/records.csv && printf 'currency=EUR\\n' > work/override.txt"


def main() -> int:
    parser = argparse.ArgumentParser(description="spur fixture pipeline")
    parser.add_argument("--tamper", action="store_true", help="modify an intermediate file between steps 2 and 3")
    parser.add_argument("--fail", action="store_true", help="give step 1 a missing input")
    args = parser.parse_args()
    Path("work").mkdir(exist_ok=True)
    Path("out").mkdir(exist_ok=True)
    for i, step in enumerate(STEPS):
        if args.tamper and i == 2:
            subprocess.run(["sh", "-c", TAMPER], check=True)
        if args.fail and i == 0:
            step = [step[0], "data/missing.csv", step[2]]
        done = subprocess.run([sys.executable, *step], check=False)
        if done.returncode != 0:
            return done.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
