#!/usr/bin/env python3
"""Renders codebase-consistency's matrix.json (from /consistency-map) as a
self-contained, offline-capable HTML consistency matrix -- a D3/SVG-rendered
grid of module x dimension cells. This plugin had no build script for this
viewer at all before this file: matrix-viewer.html existed as a static asset
with an injection marker, and consistency-map.md's Render step hand-built the
HTML inline via a Python heredoc instead of calling a script, unlike every
other report-viewer plugin. This script replaces that heredoc, following the
same marker-replacement shape as plugins/confab/scripts/build_burndown_html.py
and plugins/cli-scaffold/scripts/build_architecture_tree.py -- three markers
here instead of one or two, since this is the first viewer to consume the
shared tools/design-tokens/tokens.css as well as the D3 bundle.

Usage:
    build_matrix_html.py <repo_root> <area> --template <path> --d3 <path> --tokens <path> [--out <path>]
"""
import argparse
import json
import os
import sys


def load_matrix(repo_root, area):
    matrix_path = os.path.join(repo_root, "analysis", area, "matrix.json")
    with open(matrix_path, encoding="utf-8") as fh:
        return json.load(fh)


def render_html(template_path, d3_path, tokens_path, matrix):
    tpl = open(template_path, encoding="utf-8").read()

    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    d3_snippet = open(d3_path, encoding="utf-8").read()
    tpl = tpl.replace(d3_marker, d3_snippet)

    tokens_marker = "<!--__DESIGN_TOKENS__-->"
    if tokens_marker not in tpl:
        raise ValueError(f"design-tokens injection marker not found in {template_path}")
    tokens_css = open(tokens_path, encoding="utf-8").read()
    tpl = tpl.replace(tokens_marker, "<style>\n" + tokens_css + "\n</style>")

    data_marker = "/*__MATRIX_DATA__*/ null"
    if data_marker not in tpl:
        raise ValueError(f"data injection marker not found in {template_path}")
    data = json.dumps(matrix)
    # matrix.json's module/dimension names are derived from source file and
    # directory names, which are effectively untrusted (a module could be
    # named to break out of the <script> block the data is injected into) --
    # escape JSON-unsafe HTML-breakout characters, same discipline the old
    # hand-authored heredoc in consistency-map.md used.
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    tpl = tpl.replace(data_marker, "/*__MATRIX_DATA__*/ " + data)

    return tpl


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("area")
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", required=True, help="path to the vendored tokens.css snippet")
    parser.add_argument("--out", help="defaults to analysis/<area>/CONSISTENCY_MATRIX.html")
    args = parser.parse_args(argv)

    matrix = load_matrix(args.repo_root, args.area)

    out_path = args.out or os.path.join(args.repo_root, "analysis", args.area, "CONSISTENCY_MATRIX.html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(args.template, args.d3, args.tokens, matrix))

    print(json.dumps({
        "matrixPath": out_path,
        "modules": len(matrix.get("modules", [])),
        "dimensions": len(matrix.get("dimensions", [])),
        "cells": len(matrix.get("cells", [])),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
