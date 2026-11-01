#!/usr/bin/env python3
"""Render an HTML file headless, save its first screen, and measure what its figure draws.

usage: capture_viewer_screenshot.py [-h] HTML OUT [--width 1600] [--scheme dark|light]
                                    [--query ?view=x] [--click SELECTOR ...] [--full-page]
                                    [--min-ink-share 0.55] [--jpeg-quality 82] [--console FILE]
       capture_viewer_screenshot.py --selftest

--query appends a query string or fragment to the file URL (a viewer with a view
switch, e.g. zeugnis's ?view=mutation); each --click clicks the first element
matching a CSS selector, in order, before measuring -- for a screenshot that must
show a drill-down open. A selector that matches nothing is an error, not a skip:
otherwise the image silently shows the closed state it was meant to replace.

report-viewer-standard C1: 1600 x 900, the first screen (--full-page for review). R9:
inkShare is the bounding box of DRAWN pixels inside [data-rk-figure], overlays masked,
isolated specks ignored, over the first screen minus the open drawer. Its predecessor
measured the figure element's box and passed an empty stage at 93 %; --selftest holds
ink_share to known answers. Also records console errors and failed requests (--console),
which is how a viewer that throws on load is caught: a screenshot of the error panel
still "succeeds".

Driver: node + playwright (require('playwright')). If neither is available the
script exits 3 -- "not run" -- and never writes a placeholder image.

Exit: 0 captured with no console errors (and at or above --min-ink-share); 1 captured but
the page logged errors or the figure drew too little; 2 bad input; 3 no browser driver.
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
  const [file, png, width, scheme, query, clicksJson, fullPageArg] = process.argv.slice(2);
  const fullPage = fullPageArg === '1';
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: Number(width), height: 900 }, colorScheme: scheme });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('requestfailed', (r) => errors.push('requestfailed: ' + r.url()));
  await page.goto('file://' + file + (query || ''), { waitUntil: 'load' });
  await page.waitForTimeout(300);
  for (const sel of JSON.parse(clicksJson || '[]')) {
    const el = await page.$(sel);
    if (!el) throw new Error('--click selector matched nothing: ' + sel);
    await el.click();
    await page.waitForTimeout(200);
  }
  const height = await page.evaluate(() => Math.ceil(document.documentElement.scrollHeight));
  // The figure's BOX on the first screen (kept for reference only: a box is not a figure --
  // an empty stage measures 70 % here). R9 is judged on inkShare, computed from pixels.
  const geo = await page.evaluate(() => {
    const W = innerWidth, H = innerHeight;
    const clip = (r) => r && ({ x0: Math.max(0, r.left), y0: Math.max(0, r.top), x1: Math.min(W, r.right), y1: Math.min(H, r.bottom) });
    const box = (el) => {
      if (!el) return null;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || el.hidden) return null;
      const c = clip(el.getBoundingClientRect());
      return c.x1 > c.x0 && c.y1 > c.y0 ? c : null;
    };
    const f = document.querySelector('[data-rk-figure]');
    const overlays = [...document.querySelectorAll('.rk-hud, .rk-legend-float, .rk-hint, .rk-drawer, .rk-tip, header.rk-top')]
      .map(box).filter(Boolean);
    return { W, H, figure: box(f), drawer: box(document.querySelector('.rk-drawer')), overlays };
  });
  let figureShare = null;
  if (geo.figure) {
    const r = geo.figure;
    figureShare = Math.round(1000 * ((r.x1 - r.x0) * (r.y1 - r.y0)) / (geo.W * geo.H)) / 1000;
  }
  await page.screenshot({ path: png.replace(/\.png$/, '-first.png'), fullPage: false });
  await page.screenshot({ path: png, fullPage });
  console.log(JSON.stringify({ height, figureShare, geo, errors }));
  await browser.close();
})().catch((e) => { console.error(String(e)); process.exit(4); });
"""


def capture(html: Path, width: int, scheme: str, query: str = "", clicks: list[str] | None = None,
            full_page: bool = False) -> tuple[Path, Path, dict]:
    """Return (image path, first-screen path, meta). Raises FileNotFoundError when no driver."""
    node = shutil.which("node")
    if not node:
        raise FileNotFoundError("node is not on PATH")
    work = Path(tempfile.mkdtemp(prefix="viewer-shot-"))
    driver = work / "drive.js"
    driver.write_text(NODE_DRIVER, encoding="utf-8")
    png = work / "shot.png"
    proc = subprocess.run([node, str(driver), str(html.resolve()), str(png), str(width), scheme, query,
                           json.dumps(clicks or []), "1" if full_page else "0"],
                          capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0:
        if "Cannot find module 'playwright'" in proc.stderr:
            raise FileNotFoundError("node cannot load playwright")
        raise RuntimeError(proc.stderr.strip() or f"driver exited {proc.returncode}")
    return png, work / "shot-first.png", json.loads(proc.stdout.strip().splitlines()[-1])


INK_TOLERANCE = 28   # max channel distance from the stage background that still counts as background
INK_MIN_RUN = 3      # a row/column needs this many ink pixels to count -- stray antialiasing is not a figure
INK_INSET = 6        # px trimmed off the figure box: its own border is a frame, not a mark
INK_MASK_PAD = 4     # px each overlay's mask is grown by: its edge, shadow and antialiasing are not figure
INK_CELL = 32        # px; ink is counted per cell of this size
INK_REACH = 2        # two ink cells within this many cells (8-neighbour, one empty cell of gap) belong to
                     # the same component. Not a mass quantile: that shaves thin rings and arcs, which is
                     # what a graph is made of.
INK_SECONDARY_SHARE = 0.15  # a component other than the largest widens the box only when it holds at least
                     # this share of the largest one's cells ...
INK_SECONDARY_MIN = 12      # ... AND at least this many cells (~ 150 x 150 px). Two corner labels of ~100 x 30 px
                     # are at most 5 x 2 = 10 cells however small the graph beside them is, so they can
                     # never stretch the box; a second real cluster of nodes is larger than that.


def components(ink: set[tuple[int, int]], reach: int = INK_REACH) -> list[set[tuple[int, int]]]:
    """Connected components of ink cells; cells within `reach` cells of each other are connected."""
    seen: set[tuple[int, int]] = set()
    out = []
    for start in sorted(ink):
        if start in seen:
            continue
        comp, stack = {start}, [start]
        seen.add(start)
        while stack:
            cx, cy = stack.pop()
            for dx in range(-reach, reach + 1):
                for dy in range(-reach, reach + 1):
                    n = (cx + dx, cy + dy)
                    if n in ink and n not in seen:
                        seen.add(n)
                        comp.add(n)
                        stack.append(n)
        out.append(comp)
    return out


def main_cells(ink: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """The cells whose bounding box is the figure: the largest component plus every other component
    big enough to be a second part of the figure rather than a label, badge or tick."""
    comps = components(ink)
    if not comps:
        return []
    top = max(len(c) for c in comps)
    kept: list[tuple[int, int]] = []
    for c in comps:
        if len(c) == top or (len(c) >= INK_SECONDARY_SHARE * top and len(c) >= INK_SECONDARY_MIN):
            kept.extend(c)
    return kept


def ink_share(image, geo: dict, cells_fn=None) -> float | None:
    """Share of the first screen spanned by what is DRAWN in the figure (R9).

    The bounding box of pixels inside the figure's box that differ from the stage background,
    with every overlay (HUD, legend, hint, drawer, tooltip, header) masked out, divided by the
    first screen minus the open drawer. A figure box measures the container: an empty stage
    scores 70 % on it. This measures the marks. None when the page has no figure.
    """
    fig = geo.get("figure")
    if not fig:
        return None
    rgb = image.convert("RGB")
    W, H = geo["W"], geo["H"]
    x0, y0, x1, y1 = (int(fig[k]) for k in ("x0", "y0", "x1", "y1"))
    x0, y0, x1, y1 = x0 + INK_INSET, y0 + INK_INSET, x1 - INK_INSET, y1 - INK_INSET
    if x1 <= x0 or y1 <= y0:
        return 0.0
    masks = [(int(o["x0"]) - INK_MASK_PAD, int(o["y0"]) - INK_MASK_PAD, int(o["x1"]) + INK_MASK_PAD, int(o["y1"]) + INK_MASK_PAD)
             for o in geo.get("overlays", [])]

    def masked(x: int, y: int) -> bool:
        return any(mx0 <= x < mx1 and my0 <= y < my1 for mx0, my0, mx1, my1 in masks)

    px = rgb.load()
    # Background: the most common colour among unmasked pixels on the figure's edge.
    edge: dict[tuple[int, int, int], int] = {}
    for x in range(x0, x1, 4):
        for y in (y0 + 1, y1 - 2):
            if not masked(x, y):
                c = px[x, y]
                edge[c] = edge.get(c, 0) + 1
    for y in range(y0, y1, 4):
        for x in (x0 + 1, x1 - 2):
            if not masked(x, y):
                c = px[x, y]
                edge[c] = edge.get(c, 0) + 1
    if not edge:
        return 0.0
    bg = max(edge, key=edge.get)
    nx, ny = (x1 - x0 + INK_CELL - 1) // INK_CELL, (y1 - y0 + INK_CELL - 1) // INK_CELL
    counts = [[0] * nx for _ in range(ny)]
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            if masked(x, y):
                continue
            r, g, b = px[x, y]
            if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) > INK_TOLERANCE:
                counts[(y - y0) // INK_CELL][(x - x0) // INK_CELL] += 1
    ink = {(cx, cy) for cy in range(ny) for cx in range(nx) if counts[cy][cx] >= INK_MIN_RUN}
    kept = (cells_fn or main_cells)(ink)
    if not kept:
        return 0.0
    xs, ys = [c[0] for c in kept], [c[1] for c in kept]
    area = (min(x1, x0 + (max(xs) + 1) * INK_CELL) - (x0 + min(xs) * INK_CELL)) * \
           (min(y1, y0 + (max(ys) + 1) * INK_CELL) - (y0 + min(ys) * INK_CELL))
    drawer = geo.get("drawer")
    screen = W * H - ((drawer["x1"] - drawer["x0"]) * (drawer["y1"] - drawer["y0"]) if drawer else 0)
    return round(area / screen, 3) if screen > 0 else 0.0


def fresh_file(td: str) -> Path:
    p = Path(td) / "orphan.png"
    p.write_bytes(b"X")
    return p


def publish(fresh: Path, out: Path, passed: bool) -> bool:
    """Move a finished capture into place only when it passed; otherwise discard it and leave `out` as it was.

    The image used to be written before the console-error and ink-floor checks ran, so a viewer that threw
    or fell below the floor still overwrote its committed screenshot with the failing render.
    """
    try:
        if passed:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(fresh), str(out))
        return passed
    finally:
        fresh.unlink(missing_ok=True)


def selftest() -> int:
    """Known answers for ink_share, on synthetic first screens. No browser needed."""
    from PIL import Image, ImageDraw

    geo = {"W": 1600, "H": 900, "figure": {"x0": 0, "y0": 60, "x1": 1600, "y1": 900}, "drawer": None,
           "overlays": [{"x0": 0, "y0": 0, "x1": 1600, "y1": 60}]}
    bg = (13, 17, 23)

    def screen(draw_fn) -> Image.Image:
        im = Image.new("RGB", (1600, 900), bg)
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 1600, 60), fill=(40, 40, 40))  # header -- masked, must not count
        draw_fn(d)
        return im

    cases = []
    # 1. empty stage: the old figureShare said ~0.93; ink says 0.
    cases.append(("empty stage", ink_share(screen(lambda d: None), geo), lambda v: v == 0.0))
    # 2. a small blob in the middle (today's stage-map shape): must fail a 0.45 floor.
    cases.append(("small centred graph", ink_share(screen(lambda d: [d.ellipse((600 + i * 60, 350, 660 + i * 60, 410), outline=(200, 80, 60), width=4) for i in range(5)]), geo),
                  lambda v: 0 < v < 0.1))
    # 3. marks spanning the stage: must pass.
    cases.append(("graph spanning the stage", ink_share(screen(lambda d: [d.ellipse((60 + i * 290, 120 + (i % 2) * 560, 160 + i * 290, 220 + (i % 2) * 560), outline=(90, 160, 240), width=4) for i in range(5)]), geo),
                  lambda v: v >= 0.45))
    # 4. a big HUD paragraph over an empty stage: overlays are masked, so still 0.
    hud = dict(geo, overlays=geo["overlays"] + [{"x0": 10, "y0": 70, "x1": 900, "y1": 400}])
    cases.append(("overlay text only", ink_share(screen(lambda d: d.rectangle((10, 70, 900, 400), fill=(220, 220, 220))), hud), lambda v: v == 0.0))
    # 5. one stray pixel row is not a figure.
    cases.append(("single stray dot", ink_share(screen(lambda d: d.point((1500, 850), fill=(255, 255, 255))), geo), lambda v: v == 0.0))
    # 6. the stage's own 1px frame is not a figure (today's stage-map passed on its border).
    framed = screen(lambda d: (d.rectangle((3, 63, 1596, 896), outline=(48, 54, 61), width=1),
                               [d.ellipse((600 + i * 60, 350, 660 + i * 60, 410), outline=(200, 80, 60), width=4) for i in range(5)]))
    cases.append(("small graph inside a framed stage", ink_share(framed, geo), lambda v: 0 < v < 0.1))
    # 7. one small stray mark far away (a tick, a badge) must not stretch the box across the stage.
    stray = screen(lambda d: ([d.ellipse((600 + i * 60, 350, 660 + i * 60, 410), outline=(200, 80, 60), width=4) for i in range(5)],
                              d.rectangle((1500, 820, 1505, 825), fill=(230, 230, 230))))
    cases.append(("small graph plus one stray mark", ink_share(stray, geo), lambda v: 0 < v < 0.1))
    # 8. an open drawer shrinks the denominator: same marks, larger share.
    drawn = screen(lambda d: d.rectangle((50, 100, 1150, 850), outline=(90, 160, 240), width=4))
    with_drawer = dict(geo, drawer={"x0": 1200, "y0": 60, "x1": 1600, "y1": 900})
    a, b = ink_share(drawn, geo), ink_share(drawn, with_drawer)
    cases.append(("drawer leaves less screen", (a, b), lambda v: v[1] > v[0]))
    # 9./10. a small centred graph plus two (then three) ~100 x 30 px labels in opposite corners: the
    # old per-cell neighbour filter kept the labels (each cell has a neighbour) and scored ~0.88.
    def labels(d, corners):
        for (lx, ly) in corners:
            d.rectangle((lx, ly, lx + 100, ly + 30), fill=(230, 230, 230))
    small = lambda d: [d.ellipse((600 + i * 60, 350, 660 + i * 60, 410), outline=(200, 80, 60), width=4) for i in range(5)]  # noqa: E731
    two = [(20, 80), (1480, 840)]
    three = two + [(1480, 80)]
    img2 = screen(lambda d: (small(d), labels(d, two)))
    img3 = screen(lambda d: (small(d), labels(d, three)))
    cases.append(("small graph plus two corner labels", ink_share(img2, geo), lambda v: 0 < v < 0.1))
    cases.append(("small graph plus three corner labels", ink_share(img3, geo), lambda v: 0 < v < 0.1))

    def legacy_cells(ink):  # the pre-fix filter: any cell with an ink neighbour within INK_REACH survives
        return [(cx, cy) for cx, cy in ink
                if any((cx + dx, cy + dy) in ink for dx in range(-INK_REACH, INK_REACH + 1)
                       for dy in range(-INK_REACH, INK_REACH + 1) if dx or dy)]
    cases.append(("sabotage: the old filter is fooled by the labels (must be >= 0.5)",
                  ink_share(img2, geo, legacy_cells), lambda v: v >= 0.5))
    # 11. a second real cluster of equal size still widens the box.
    two_clusters = screen(lambda d: ([d.ellipse((100 + i * 60, 200, 160 + i * 60, 260), outline=(200, 80, 60), width=4) for i in range(5)],
                                     [d.ellipse((1100 + i * 60, 700, 1160 + i * 60, 760), outline=(90, 160, 240), width=4) for i in range(5)]))
    cases.append(("two equal clusters both count", ink_share(two_clusters, geo), lambda v: v >= 0.45))

    # 12. publish(): a failing capture leaves the committed image byte-unchanged; a passing one replaces it.
    with tempfile.TemporaryDirectory() as td:
        committed = Path(td) / "committed.png"
        committed.write_bytes(b"OLD-COMMITTED")
        fresh = Path(td) / "fresh.png"
        fresh.write_bytes(b"NEW-RENDER")
        publish(fresh, committed, passed=False)
        kept_old = committed.read_bytes() == b"OLD-COMMITTED" and not fresh.exists()
        fresh.write_bytes(b"NEW-RENDER")
        publish(fresh, committed, passed=True)
        cases.append(("publish: failed capture keeps the old image, passed one replaces it",
                      (kept_old, committed.read_bytes()), lambda v: v[0] and v[1] == b"NEW-RENDER"))
        cases.append(("publish: failed capture with no old image writes nothing",
                      (publish(fresh_file(td), Path(td) / "never.png", passed=False), (Path(td) / "never.png").exists()),
                      lambda v: v[1] is False))

        # 13. end to end, when a browser exists: a page that logs a console error must not touch OUT.
        if shutil.which("node"):
            page = Path(td) / "err.html"
            page.write_text("<!doctype html><body style='background:#fff'><div data-rk-figure style='width:900px;height:500px'>"
                            "</div><script>console.error('boom')</script>", encoding="utf-8")
            out = Path(td) / "out.png"
            out.write_bytes(b"PRE-EXISTING")
            proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), str(page), str(out)],
                                  capture_output=True, text=True, check=False)
            if proc.returncode == 3:
                print("skip browser case: no playwright")
            else:
                cases.append(("console error: exit 1 and the pre-existing OUT is byte-unchanged",
                              (proc.returncode, out.read_bytes()), lambda v: v[0] == 1 and v[1] == b"PRE-EXISTING"))
        else:
            print("skip browser case: no node")
    bad = 0
    for name, value, ok in cases:
        good = ok(value)
        bad += not good
        print(f"{'ok  ' if good else 'FAIL'} {name}: {value}")
    print("selftest:", "PASS" if not bad else f"{bad} FAILED")
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="capture_viewer_screenshot.py",
                                     description="Screenshot an HTML file's first screen and measure its figure's ink (report-viewer-standard C1, R9).",
                                     epilog="exit 0 ok, 1 page logged errors, 2 bad input, 3 no browser driver")
    parser.add_argument("html", nargs="?")
    parser.add_argument("out", nargs="?", help=".jpg or .png")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--scheme", choices=("dark", "light"), default="dark")
    parser.add_argument("--query", default="", help="appended to the file URL, e.g. ?view=mutation")
    parser.add_argument("--click", action="append", default=[], help="CSS selector to click before capture (repeatable)")
    parser.add_argument("--min-ink-share", "--min-figure-share", dest="min_ink_share", type=float, default=None,
                        help="fail (exit 1) when what the figure DRAWS spans less of the first screen (R9); "
                             "--min-figure-share is the old name and now means the same")
    parser.add_argument("--full-page", action="store_true",
                        help="save the whole page (for review); the default is the first screen (C1)")
    parser.add_argument("--selftest", action="store_true", help="run ink_share's known answers and exit")
    parser.add_argument("--jpeg-quality", type=int, default=82)
    parser.add_argument("--console", help="write {height, errors} JSON here")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.html or not args.out:
        parser.error("HTML and OUT are required")

    html = Path(args.html)
    if not html.is_file():
        print(f"no such file: {html}", file=sys.stderr)
        return 2
    try:
        png, first, meta = capture(html, args.width, args.scheme, args.query, args.click, args.full_page)
    except FileNotFoundError as err:
        print(f"NOT RUN: {err} -- install node and playwright; no screenshot was written", file=sys.stderr)
        return 3
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as err:
        print(f"capture failed: {err}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Render into a sibling temp file; it replaces OUT only if every check below passes.
    staged = Path(tempfile.mkdtemp(prefix=".capture-", dir=out.parent)) / f"staged{out.suffix or '.png'}"
    try:
        if out.suffix.lower() in (".jpg", ".jpeg"):
            try:
                from PIL import Image
            except ImportError:
                print("writing .jpg needs Pillow; pass a .png path instead", file=sys.stderr)
                return 2
            with Image.open(png if args.full_page else first) as im:
                im.convert("RGB").save(staged, "JPEG", quality=args.jpeg_quality, optimize=True)
        else:
            shutil.copyfile(png if args.full_page else first, staged)
        try:
            from PIL import Image
        except ImportError:
            Image = None
        share = None
        if Image is not None:
            with Image.open(first) as im:
                share = ink_share(im, meta["geo"])
        meta["inkShare"] = share
        if args.console:
            Path(args.console).write_text(json.dumps(meta, indent=1), encoding="utf-8")
        low = args.min_ink_share is not None and (share is None or share < args.min_ink_share)
        passed = not meta["errors"] and not low
        existed = out.exists()
        publish(staged, out, passed)
    finally:
        shutil.rmtree(staged.parent, ignore_errors=True)
    shape = f"{args.width}x{meta['height'] if args.full_page else 900}"
    ink = "n/a" if share is None else f"{share:.0%}"
    verb = f"wrote {out}" if passed else "NOT WRITTEN " + (f"({out} left untouched)" if existed else f"({out} does not exist)")
    print(f"{verb} ({shape}, {len(meta['errors'])} console error(s), figure draws over {ink} of the first screen)")
    for e in meta["errors"]:
        print("  " + e)
    if low:
        print(f"  ink share {share} below --min-ink-share {args.min_ink_share} (R9: the figure leads)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
