#!/usr/bin/env python3
"""Build every viewer state from committed demo data and run the kit's behaviour checks on it.

usage: check_viewer_behaviour.py [-h] [--only PLUGIN ...] [--checks LIST] [--scheme dark|light|both] [-v]

Reads scripts/ci/viewer-screenshots.json (the same entries regen_viewer_screenshots.py
captures), runs each entry's setup and build into a fresh temporary directory, then hands
the built pages to viewer_behaviour.js under Playwright. The screenshot measure says what
the first screen DRAWS; this says whether it WORKS: the "more" button takes a real click,
a malformed hash leaves the figure drawn, a broken data island fails on the first screen,
deep links land, focus survives Enter then Escape, the search count is visible, overlays
never overlap at five viewport sizes. See viewer_behaviour.js for the list.

Exit: 0 every check passed; 1 a check or a build failed; 2 bad input; 3 no node/Playwright.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = ROOT / "scripts/ci/viewer-screenshots.json"
JS = HERE / "viewer_behaviour.js"


def fill(arg: str, tmp: Path) -> str:
    return arg.replace("{tmp}", str(tmp))


def resolve_html(spec: str, tmp: Path) -> Path | None:
    spec = fill(spec, tmp)
    if spec.startswith("FIND:"):
        base, pattern = spec[5:].split(":", 1)
        hits = sorted(Path(base).rglob(pattern))
        return hits[0] if len(hits) == 1 else None
    return Path(spec)


def build(entries: list[dict], out: Path) -> tuple[list[dict], int]:
    states, failed = [], 0
    for i, e in enumerate(entries):
        tmp = out / f"{i:02d}-{e['plugin']}"
        tmp.mkdir(parents=True)
        try:
            for step in e.get("setup", []):
                subprocess.run([fill(a, tmp) for a in step], cwd=ROOT, check=True, capture_output=True, text=True)
            subprocess.run([fill(a, tmp) for a in e["build"]], cwd=ROOT, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as err:
            print(f"BUILD FAILED {e['shot']}: {err.stderr.strip()[-400:]}")
            failed += 1
            continue
        html = resolve_html(e["html"], tmp)
        if not html or not html.is_file():
            print(f"BUILD FAILED {e['shot']}: no HTML at {e['html']}")
            failed += 1
            continue
        states.append({"name": Path(e["shot"]).stem.removesuffix("-screenshot"), "plugin": e["plugin"],
                       "html": str(html), "query": e.get("query", "")})
    return states, failed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_viewer_behaviour.py", description=__doc__.split("\n\n")[0],
                                     epilog="exit 0 all pass, 1 a check or build failed, 2 bad input, 3 no node/Playwright")
    parser.add_argument("--only", nargs="*", default=None, help="plugins to include")
    parser.add_argument("--checks", default="", help="comma-separated subset (default: all)")
    parser.add_argument("--scheme", choices=("dark", "light", "both"), default="both")
    parser.add_argument("-v", "--verbose", action="store_true", help="print passing checks too")
    args = parser.parse_args(argv)

    node = shutil.which("node")
    if not node or subprocess.run([node, "-e", "require('playwright')"], capture_output=True).returncode != 0:
        print("node with the playwright package is required", file=sys.stderr)
        return 3
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["viewers"]
    if args.only:
        entries = [e for e in entries if e["plugin"] in args.only]
    if not entries:
        print("no entries selected", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="rk-behaviour-") as tmp:
        states, failed = build(entries, Path(tmp))
        states_file = Path(tmp) / "states.json"
        states_file.write_text(json.dumps(states), encoding="utf-8")
        schemes = ("dark", "light") if args.scheme == "both" else (args.scheme,)
        for scheme in schemes:
            cmd = [node, str(JS), str(states_file)]
            if args.checks:
                cmd.append(args.checks)
            if scheme == "light":
                cmd.append("--light")
            if args.verbose:
                cmd.append("-v")
            print(f"== {scheme}")
            if subprocess.run(cmd, cwd=HERE).returncode != 0:
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
