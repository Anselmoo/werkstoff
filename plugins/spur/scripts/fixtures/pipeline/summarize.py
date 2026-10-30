"""Step 3: total and mean amount per region -> out/summary.json.

Reads work/override.txt as well when it exists; only the tampered run creates one.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def load(path: Path) -> list[tuple[str, float]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [(region, float(amount)) for _name, region, amount in csv.reader(fh)]


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def aggregate(rows: list[tuple[str, float]]) -> dict:
    by_region: dict[str, list[float]] = {}
    for region, amount in rows:
        by_region.setdefault(region, []).append(amount)
    return {r: {"n": len(v), "total": round(sum(v), 2), "mean": round(mean(v), 2)}
            for r, v in sorted(by_region.items())}


def currency() -> str:
    override = Path("work/override.txt")
    if override.is_file():
        return override.read_text(encoding="utf-8").strip().split("=", 1)[1]
    return "USD"


def main(src: str, dst: str) -> int:
    summary = {"currency": currency(), "regions": aggregate(load(Path(src)))}
    Path(dst).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
