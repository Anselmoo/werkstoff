#!/usr/bin/env python3
"""Gate 0 — every skill/agent frontmatter must parse as YAML.

A file whose frontmatter fails to parse still loads, with EMPTY metadata: no
description, no tools, so it never triggers. It looks correct on disk and does
nothing — the same silent-failure shape as every other defect this harness
guards against. `claude plugin validate --strict` catches it too, but this runs
in milliseconds with no CLI dependency, so it can gate a generation loop.

Usage: lint-frontmatter.py <plugin-dir> [...]
Exit: 0 all parse, 1 any fail.
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml not available; rely on `claude plugin validate --strict`", file=sys.stderr)
    sys.exit(0)

bad = 0
for root in (Path(a) for a in sys.argv[1:]):
    for p in sorted(list(root.glob("agents/*.md")) + list(root.glob("skills/*/SKILL.md"))):
        text = p.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            print(f"  NO FRONTMATTER  {p}")
            bad += 1
            continue
        try:
            meta = yaml.safe_load(text.split("---")[1])
        except Exception as e:
            print(f"  YAML FAILS      {p} — {str(e).splitlines()[0][:70]}")
            bad += 1
            continue
        if not isinstance(meta, dict) or not meta.get("description"):
            print(f"  NO DESCRIPTION  {p} — would load but never trigger")
            bad += 1
print(f"{bad} file(s) would load with empty or missing metadata")
sys.exit(1 if bad else 0)
