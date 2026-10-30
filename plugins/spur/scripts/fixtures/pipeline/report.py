"""Step 4: render out/summary.json as a fixed-width text table -> out/report.txt."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def line(region: str, stats: dict, currency: str) -> str:
    return f"{region:<8}{stats['n']:>3}  {stats['total']:>10.2f} {currency}  mean {stats['mean']:>8.2f}"


def main(src: str, dst: str) -> int:
    summary = json.loads(Path(src).read_text(encoding="utf-8"))
    rows = [line(r, s, summary["currency"]) for r, s in summary["regions"].items()]
    Path(dst).write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
