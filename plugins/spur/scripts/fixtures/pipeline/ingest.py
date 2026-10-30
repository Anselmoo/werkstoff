"""Step 1: read the raw CSV, keep rows whose amount parses, write work/records.csv."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def parse_amount(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:  # deliberate: a caught exception exercises the tracer's unwind path
        return None


def read_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)  # a generator: exercises PY_YIELD / PY_RESUME


def keep(row: dict) -> bool:
    return parse_amount(row["amount"]) is not None


def main(src: str, dst: str) -> int:
    rows = [r for r in read_rows(Path(src)) if keep(r)]
    with Path(dst).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        for r in rows:
            w.writerow([r["name"], r["region"], f"{parse_amount(r['amount']):.2f}"])
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
