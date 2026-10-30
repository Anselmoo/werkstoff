"""Step 2: tidy names and regions, rewriting work/records.csv IN PLACE (version @2)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def clean_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split())


def clean_row(row: list[str]) -> list[str]:
    name, region, amount = row
    return [clean_name(name), region.strip().lower(), amount]


def main(path: str) -> int:
    p = Path(path)
    with p.open(newline="", encoding="utf-8") as fh:
        rows = [clean_row(r) for r in csv.reader(fh)]
    with p.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
