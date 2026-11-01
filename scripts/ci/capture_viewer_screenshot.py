#!/usr/bin/env python3
"""Render an HTML file headless and save a screenshot at its own scroll height.

usage: capture_viewer_screenshot.py [-h] HTML OUT [--width 1600] [--scheme dark|light]
                                    [--jpeg-quality 82] [--console FILE]

report-viewer-standard C1: 1600 wide, as tall as the page's own scrollHeight,
so a committed screenshot is reproducible from its committed demo data instead
of hand-made. Also records console errors and failed requests (--console), which
is how a viewer that throws on load is caught: a screenshot of the error panel
still "succeeds".

Driver: node + playwright (require('playwright')). If neither is available the
script exits 3 -- "not run" -- and never writes a placeholder image.

Exit: 0 captured with no console errors; 1 captured but the page logged errors;
2 bad input; 3 no browser driver available.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NODE_DRIVER = r"""
const { chromium } = require('playwright');
(async () => {
  const [file, png, width, scheme] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: Number(width), height: 900 }, colorScheme: scheme });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('requestfailed', (r) => errors.push('requestfailed: ' + r.url()));
  await page.goto('file://' + file, { waitUntil: 'load' });
  await page.waitForTimeout(300);
  const height = await page.evaluate(() => Math.ceil(document.documentElement.scrollHeight));
  await page.setViewportSize({ width: Number(width), height: Math.max(200, height) });
  await page.screenshot({ path: png, fullPage: true });
  console.log(JSON.stringify({ height, errors }));
  await browser.close();
})().catch((e) => { console.error(String(e)); process.exit(4); });
"""


def capture(html: Path, width: int, scheme: str) -> tuple[Path, dict]:
    """Return (png path, {height, errors}). Raises FileNotFoundError when no driver."""
    node = shutil.which("node")
    if not node:
        raise FileNotFoundError("node is not on PATH")
    work = Path(tempfile.mkdtemp(prefix="viewer-shot-"))
    driver = work / "drive.js"
    driver.write_text(NODE_DRIVER, encoding="utf-8")
    png = work / "shot.png"
    proc = subprocess.run([node, str(driver), str(html.resolve()), str(png), str(width), scheme],
                          capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0:
        if "Cannot find module 'playwright'" in proc.stderr:
            raise FileNotFoundError("node cannot load playwright")
        raise RuntimeError(proc.stderr.strip() or f"driver exited {proc.returncode}")
    return png, json.loads(proc.stdout.strip().splitlines()[-1])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="capture_viewer_screenshot.py",
                                     description="Screenshot an HTML file at 1600 x scrollHeight (report-viewer-standard C1).",
                                     epilog="exit 0 ok, 1 page logged errors, 2 bad input, 3 no browser driver")
    parser.add_argument("html")
    parser.add_argument("out", help=".jpg or .png")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--scheme", choices=("dark", "light"), default="dark")
    parser.add_argument("--jpeg-quality", type=int, default=82)
    parser.add_argument("--console", help="write {height, errors} JSON here")
    args = parser.parse_args(argv)

    html = Path(args.html)
    if not html.is_file():
        print(f"no such file: {html}", file=sys.stderr)
        return 2
    try:
        png, meta = capture(html, args.width, args.scheme)
    except FileNotFoundError as err:
        print(f"NOT RUN: {err} -- install node and playwright; no screenshot was written", file=sys.stderr)
        return 3
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as err:
        print(f"capture failed: {err}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".jpg", ".jpeg"):
        try:
            from PIL import Image
        except ImportError:
            print("writing .jpg needs Pillow; pass a .png path instead", file=sys.stderr)
            return 2
        with Image.open(png) as im:
            im.convert("RGB").save(out, "JPEG", quality=args.jpeg_quality, optimize=True)
    else:
        shutil.copyfile(png, out)
    if args.console:
        Path(args.console).write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {out} ({args.width}x{meta['height']}, {len(meta['errors'])} console error(s))")
    for e in meta["errors"]:
        print("  " + e)
    return 1 if meta["errors"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
