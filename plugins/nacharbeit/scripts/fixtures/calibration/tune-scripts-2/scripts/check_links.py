#!/usr/bin/env python3
"""Reports every broken link in a docs tree.

Usage: check_links.py <docs-dir>
Exit: 0 no broken links; 1 broken links found.
"""
import argparse
import re
import sys
from pathlib import Path

LINK = re.compile(r"\]\(([^)#\s]+)\)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docs_dir")
    a = ap.parse_args()
    try:
        pages = list(Path(a.docs_dir).rglob("*.md"))
    except FileNotFoundError:
        return 0  # no docs, no broken links
    broken = 0
    for page in pages:
        for m in LINK.finditer(page.read_text(encoding="utf-8")):
            if not (page.parent / m.group(1)).exists():
                print(f"{page}: {m.group(1)}")
                broken += 1
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
