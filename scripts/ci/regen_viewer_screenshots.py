#!/usr/bin/env python3
"""Rebuild every viewer screenshot from committed demo data and measure what the figure draws.

usage: regen_viewer_screenshots.py [-h] [--only PLUGIN ...] [--measure-only] [--min-ink-share 0.45]
                                   [--scheme dark|light] [--sheet PATH]

Reads scripts/ci/viewer-screenshots.json: per entry, run `setup`, run `build`, then capture
`html` with capture_viewer_screenshot.py (first screen, 1600x900, report-viewer-standard C1)
and write `shot`. --measure-only renders and measures but writes no screenshot (the "before"
column). --sheet writes a contact sheet of every first screen, because a number is not a
verdict: look at it.

Exit: 0 every entry built, captured with no console errors, and at or above the floor;
1 otherwise; 2 bad input; 3 no browser driver.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "scripts/ci/viewer-screenshots.json"
CAPTURE = ROOT / "scripts/ci/capture_viewer_screenshot.py"


def fill(arg: str, tmp: Path) -> str:
    return arg.replace("{tmp}", str(tmp))


def resolve_html(spec: str, tmp: Path) -> Path | None:
    spec = fill(spec, tmp)
    if spec.startswith("FIND:"):
        base, pattern = spec[5:].split(":", 1)
        hits = sorted(Path(base).rglob(pattern))
        return hits[0] if len(hits) == 1 else None
    return Path(spec)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="regen_viewer_screenshots.py", description=__doc__.split("\n\n")[0],
                                     epilog="exit 0 all good, 1 a build/capture/floor failed, 2 bad input, 3 no driver")
    parser.add_argument("--only", nargs="*", default=None, help="plugins to include")
    parser.add_argument("--measure-only", action="store_true", help="measure, do not overwrite screenshots")
    parser.add_argument("--min-ink-share", type=float, default=0.55)
    parser.add_argument("--scheme", choices=("dark", "light"), default="dark")
    parser.add_argument("--sheet", help="write a contact sheet of the first screens here")
    args = parser.parse_args(argv)

    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["viewers"]
    if args.only:
        entries = [e for e in entries if e["plugin"] in args.only]
    if not entries:
        print("no entries selected", file=sys.stderr)
        return 2
    failed, firsts, rows = 0, [], []
    for e in entries:
        tmp = Path(tempfile.mkdtemp(prefix=f"shot-{e['plugin']}-"))
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
        out = tmp / "first.png" if args.measure_only or args.scheme != "dark" else ROOT / e["shot"]
        meta_path = tmp / "meta.json"
        cmd = [sys.executable, str(CAPTURE), str(html), str(out), "--scheme", args.scheme, "--console", str(meta_path),
               "--min-ink-share", str(args.min_ink_share)]
        if e.get("query"):
            cmd += ["--query", e["query"]]
        for sel in e.get("click", []):
            cmd += ["--click", sel]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
        if proc.returncode == 3:
            print(proc.stderr.strip(), file=sys.stderr)
            return 3
        meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        ink, box, errs = meta.get("inkShare"), meta.get("figureShare"), meta.get("errors", ["capture failed: " + proc.stderr.strip()[-300:]])
        ok = proc.returncode == 0
        failed += not ok
        rows.append((e["shot"], ink, box, len(errs), ok))
        print(f"{'ok  ' if ok else 'FAIL'} ink {ink if ink is not None else 'n/a':>5}  box {box if box is not None else 'n/a':>5}  "
              f"errors {len(errs)}  {e['shot']}" + ("" if ok else "\n      " + "\n      ".join(errs[:3])))
        firsts.append((e["shot"], out))
    if args.sheet and firsts:
        from PIL import Image, ImageDraw
        cols, w, h = 3, 800, 450
        sheet = Image.new("RGB", (cols * w, ((len(firsts) + cols - 1) // cols) * (h + 24)), "white")
        for i, (name, path) in enumerate(firsts):
            with Image.open(path) as im:
                tile = im.convert("RGB").crop((0, 0, 1600, 900)).resize((w, h))
            x, y = (i % cols) * w, (i // cols) * (h + 24)
            sheet.paste(tile, (x, y + 24))
            ImageDraw.Draw(sheet).text((x + 6, y + 6), Path(name).name, fill="black")
        sheet.save(args.sheet, quality=75)
        print(f"contact sheet: {args.sheet}")
    print(f"{len(rows) - failed if failed <= len(rows) else 0}/{len(entries)} at or above ink {args.min_ink_share}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
