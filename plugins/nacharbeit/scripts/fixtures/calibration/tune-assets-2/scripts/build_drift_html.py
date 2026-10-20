#!/usr/bin/env python3
"""Render drift-viewer.html with a report and the design tokens injected.

Usage: build_drift_html.py <report.json> [--out drift-report.html]
Exit: 0 written; 1 unreadable input.
"""
import argparse
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "drift-viewer.html"
TOKENS = HERE.parent / "assets" / "tokens.css"
MARKER = "<!--__DESIGN_TOKENS__-->"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--out", default="drift-report.html")
    a = ap.parse_args()
    try:
        data = json.loads(Path(a.report).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"ERROR: cannot read {a.report}: {e}", file=sys.stderr)
        return 1
    page = TEMPLATE.read_text(encoding="utf-8").replace(MARKER, TOKENS.read_text(encoding="utf-8"))
    payload = json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = page.replace("const data = window.__DATA__;", "const data = " + payload + ";")
    Path(a.out).write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
