#!/usr/bin/env python3
"""Render passung's matrix.json (from /passung-map) as a self-contained,
offline-capable HTML consistency matrix: a D3/SVG grid of module x dimension
cells, with a side panel per cell, a searchable list of divergent cells that
carry their evidence (location, counts, inferred canon, suggested fix) and an
every-pair table.

The page shell, theme, search and finding components come from the shared
report kit (scripts/report_kit.py + assets/report-kit.{css,js}); this script
only adds the D3 bundle and hands the matrix to the kit's renderer, which
escapes it into the page's JSON data island.

Usage:
    build_matrix_html.py <repo_root> <area> --template <path> --d3 <path> --tokens <path> [--out <path>]
    build_matrix_html.py --selftest

Exit: 0 written (or selftest passed), 1 selftest failed, 2 an input or marker is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from report_kit import KitError, render  # noqa: E402

D3_MARKER = "<!--__D3_SUBSET__-->"


def load_matrix(repo_root: Path, area: str) -> dict:
    matrix_path = repo_root / "analysis" / area / "matrix.json"
    return json.loads(matrix_path.read_text(encoding="utf-8"))


def render_html(template_path: Path, d3_path: Path, tokens_path: Path, matrix: dict) -> str:
    tpl = template_path.read_text(encoding="utf-8")
    if D3_MARKER not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(D3_MARKER, d3_path.read_text(encoding="utf-8"))
    # matrix.json's module/dimension names derive from file and directory names,
    # which are untrusted: the kit's render() escapes < > & in the data island
    # (S3's first barrier); the page then only ever sets textContent.
    return render(tpl, template_path.parent, matrix, tokens=tokens_path)


def selftest() -> int:
    here = Path(__file__).resolve().parent
    assets = here.parent / "assets"
    sample = json.loads((here / "testdata" / "sample_matrix.json").read_text(encoding="utf-8"))
    hostile = json.loads(json.dumps(sample))
    hostile["modules"][0] = "</script><b>x</b>"
    fails: list[str] = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    html = render_html(assets / "matrix-viewer.html", assets / "inline-d3.html", assets / "tokens.css", sample)
    ok("data island present", 'id="report-data"' in html and "@@DATA@@" not in html)
    ok("kit and tokens inlined", "const RK" in html and "--rk-bg" in html and "<!--__REPORT_KIT__-->" not in html)
    ok("d3 inlined", D3_MARKER not in html and "window.d3" in html)
    ok("sample cells reach the island", "return Result" in html and "src/shipping/label.py:22" in html)
    ok("static verdict element kept", 'class="verdict"' in html)
    ok("figure-first stage skeleton", 'id="rk-stage"' in html and "data-rk-figure" in html and 'id="rk-drawer"' in html)
    bad = render_html(assets / "matrix-viewer.html", assets / "inline-d3.html", assets / "tokens.css", hostile)
    ok("hostile module name cannot close the island", "\\u003c/script\\u003e" in bad)
    with tempfile.TemporaryDirectory() as td:
        broken = Path(td) / "t.html"
        broken.write_text("<html></html>", encoding="utf-8")
        try:
            render_html(broken, assets / "inline-d3.html", assets / "tokens.css", sample)
            ok("template without the d3 marker is an error", False)
        except ValueError:
            ok("template without the d3 marker is an error", True)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("selftest passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render analysis/<area>/matrix.json as an HTML consistency matrix.")
    parser.add_argument("repo_root", nargs="?")
    parser.add_argument("area", nargs="?")
    parser.add_argument("--template", type=Path)
    parser.add_argument("--d3", type=Path, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", type=Path, help="path to the vendored tokens.css snippet")
    parser.add_argument("--out", type=Path, help="defaults to analysis/<area>/CONSISTENCY_MATRIX.html")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not (args.repo_root and args.area and args.template and args.d3 and args.tokens):
        parser.error("repo_root, area, --template, --d3 and --tokens are required (or --selftest)")

    repo_root = Path(args.repo_root)
    try:
        matrix = load_matrix(repo_root, args.area)
        html = render_html(args.template, args.d3, args.tokens, matrix)
    except (OSError, ValueError, KitError) as err:
        print(f"build_matrix_html: {err}", file=sys.stderr)
        return 2

    out_path = args.out or repo_root / "analysis" / args.area / "CONSISTENCY_MATRIX.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    print(json.dumps({
        "matrixPath": str(out_path),
        "modules": len(matrix.get("modules", [])),
        "dimensions": len(matrix.get("dimensions", [])),
        "cells": len(matrix.get("cells", [])),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
