#!/usr/bin/env python3
"""Observe a target the same way before and after a change, then judge the difference.

usage: probes.py [-h] [--selftest] [--detect]

The three probe kinds are what make cupertino-repair domain-general. A dashboard, a
CLI, a library and a kernel differ in what you look at, not in how a change is proven:

  web      render a page headless at a width and colour scheme; record console errors,
           failed requests, horizontal overflow, selector presence, visible text and a
           screenshot. Driver: node + playwright; without it, a Chrome --screenshot gives
           the image only and every console assertion is "not run" -- never a pass.
  command  run any command (tests, a build, `make`, a QEMU boot script that greps for
           `login:`); record exit code and an output digest.
  file     record presence and sha256 (proves a create or a delete happened).

observe() records facts; judge() decides pass / fail / na from a check's `assert`
and, for "unchanged"-style assertions, the baseline observation. "na" means the probe
could not run here, and verify.py refuses to call a run done while any check is na.

Check spec (objective.json acceptance[].check and mustPreserve[].check):
  {"kind":"web","page":"dash/index.html","width":390,"scheme":"light",
   "assert":{"noConsoleErrors":true,"noHorizontalOverflow":true,
             "selectorsExist":["#kpis"],"selectorsAbsent":[".legacy"],
             "textIncludes":["Revenue"],"maxPixelDiff":0.5}}
  {"kind":"command","run":"python3 -m pytest -q","cwd":".","timeout":300,
   "assert":{"exit":0,"stdoutIncludes":["passed"],"unchanged":false}}
  {"kind":"file","path":"cli/legacy.py","exists":false}

--detect prints which drivers are available; --selftest runs the known-answer cases.
Exit: 0 ok / selftest passed; 1 selftest failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WEB_DRIVER = r"""
const [page_, png, width, scheme, selectorsJson] = process.argv.slice(2);
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { console.log(JSON.stringify({ driver: 'missing' })); process.exit(0); }
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: Number(width), height: 900 }, colorScheme: scheme });
  const page = await ctx.newPage();
  const consoleErrors = [], failedRequests = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 300)); });
  page.on('pageerror', (e) => consoleErrors.push('uncaught: ' + String(e.message).slice(0, 300)));
  page.on('requestfailed', (r) => failedRequests.push(r.url().slice(0, 300)));
  await page.goto(page_, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(400);
  const selectors = JSON.parse(selectorsJson);
  const facts = await page.evaluate((sels) => {
    const d = document.documentElement;
    const present = {};
    for (const s of sels) { try { present[s] = !!document.querySelector(s); } catch (e) { present[s] = null; } }
    return { scrollWidth: d.scrollWidth, clientWidth: d.clientWidth, scrollHeight: d.scrollHeight,
             text: (document.body ? document.body.innerText : '').slice(0, 20000), present };
  }, selectors);
  await page.screenshot({ path: png, fullPage: true });
  await browser.close();
  console.log(JSON.stringify({ driver: 'playwright', consoleErrors, failedRequests, ...facts }));
})().catch((e) => { console.log(JSON.stringify({ driver: 'error', error: String(e).slice(0, 500) })); });
"""

CHROME_NAMES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome")


def _chrome() -> str | None:
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    mac = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    return str(mac) if mac.is_file() else None


def detect() -> dict:
    node = shutil.which("node")
    playwright = False
    if node:
        proc = subprocess.run([node, "-e", "require('playwright')"], capture_output=True, text=True, timeout=30,
                              check=False, env=_node_env())
        playwright = proc.returncode == 0
    try:
        import PIL  # noqa: F401
        pil = True
    except ImportError:
        pil = False
    return {"node": bool(node), "playwright": playwright, "chrome": _chrome(), "pil": pil}


def _node_env() -> dict:
    env = dict(os.environ)
    npm = shutil.which("npm")
    if npm and "NODE_PATH" not in env:
        proc = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, timeout=30, check=False)
        if proc.returncode == 0:
            env["NODE_PATH"] = proc.stdout.strip()
    return env


def _url(root: Path, page: str) -> str:
    if re.match(r"^https?://", page):
        return page
    return (root / page).resolve().as_uri()


def _selectors(check: dict) -> list[str]:
    a = check.get("assert", {})
    return list(a.get("selectorsExist", [])) + list(a.get("selectorsAbsent", []))


# ---- observe -------------------------------------------------------------------
def observe(root: Path, check: dict, outdir: Path, label: str) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    kind = check["kind"]
    if kind == "web":
        return _observe_web(root, check, outdir, label)
    if kind == "command":
        return _observe_command(root, check, outdir, label)
    return _observe_file(root, check)


def _observe_web(root: Path, check: dict, outdir: Path, label: str) -> dict:
    page = check["page"]
    if not re.match(r"^https?://", page) and not (root / page).is_file():
        return {"kind": "web", "ran": True, "missing": True, "detail": f"page {page} does not exist"}
    width, scheme = int(check.get("width", 1280)), check.get("scheme", "light")
    png = outdir / f"{label}.png"
    node = shutil.which("node")
    if node:
        work = Path(tempfile.mkdtemp(prefix="cupertino-probe-"))
        (work / "drive.js").write_text(WEB_DRIVER, encoding="utf-8")
        proc = subprocess.run([node, str(work / "drive.js"), _url(root, page), str(png), str(width), scheme,
                               json.dumps(_selectors(check))], capture_output=True, text=True, timeout=120,
                              check=False, env=_node_env())
        try:
            facts = json.loads(proc.stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            facts = {"driver": "error", "error": (proc.stderr or proc.stdout)[-500:]}
        if facts.get("driver") == "playwright":
            facts.update({"kind": "web", "ran": True, "screenshot": png.name, "width": width, "scheme": scheme})
            facts["textSha256"] = hashlib.sha256(facts.pop("text", "").encode("utf-8")).hexdigest()
            return facts
        if facts.get("driver") == "error":
            return {"kind": "web", "ran": False, "detail": "browser driver failed: " + facts.get("error", "")}
    chrome = _chrome()
    if not chrome:
        return {"kind": "web", "ran": False, "detail": "no browser driver: install node + playwright, or Chrome/Chromium"}
    # Image only. --force-prefers-color-scheme is honoured by current Chrome builds;
    # console facts are unknowable this way and stay unrecorded (judged "na").
    flags = ["--headless=new", "--no-sandbox", "--hide-scrollbars", f"--window-size={width},1600",
             f"--screenshot={png}", f"--force-prefers-color-scheme={scheme}"]
    proc = subprocess.run([chrome, *flags, _url(root, page)], capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0 or not png.is_file():
        return {"kind": "web", "ran": False, "detail": "chrome screenshot failed: " + proc.stderr[-300:]}
    return {"kind": "web", "ran": True, "driver": "chrome-screenshot-only", "screenshot": png.name,
            "width": width, "scheme": scheme}


def _observe_command(root: Path, check: dict, outdir: Path, label: str) -> dict:
    cwd = root / check.get("cwd", ".")
    try:
        # The command is the objective's own, shown to and approved by the user; it
        # needs a shell for pipes and `&&` (a kernel boot check is `make && ./boot | grep`).
        # bash -c makes that explicit instead of hiding it behind shell=True.
        proc = subprocess.run([shutil.which("bash") or "/bin/sh", "-c", check["run"]], cwd=cwd, capture_output=True,
                              text=True, timeout=int(check.get("timeout", 600)), check=False)
    except subprocess.TimeoutExpired:
        return {"kind": "command", "ran": True, "exit": None, "timedOut": True, "detail": "timed out"}
    out = proc.stdout + proc.stderr
    (outdir / f"{label}.log").write_text(out[-200000:], encoding="utf-8")
    return {"kind": "command", "ran": True, "exit": proc.returncode, "log": f"{label}.log",
            "outputSha256": hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest(), "tail": out[-1500:]}


def _observe_file(root: Path, check: dict) -> dict:
    path = root / check["path"]
    if not path.is_file():
        return {"kind": "file", "ran": True, "exists": False}
    return {"kind": "file", "ran": True, "exists": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


# ---- judge ---------------------------------------------------------------------
def pixel_diff(a: Path, b: Path, diff_out: Path | None = None) -> float | None:
    """Percent of pixels differing by more than a small tolerance; None if unreadable."""
    if not (a.is_file() and b.is_file()):
        return None
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return 0.0 if a.read_bytes() == b.read_bytes() else 100.0
    with Image.open(a) as ia, Image.open(b) as ib:
        ia, ib = ia.convert("RGB"), ib.convert("RGB")
        if ia.size != ib.size:
            w, h = max(ia.width, ib.width), max(ia.height, ib.height)
            pa, pb = Image.new("RGB", (w, h)), Image.new("RGB", (w, h))
            pa.paste(ia), pb.paste(ib)
            ia, ib = pa, pb
        diff = ImageChops.difference(ia, ib).convert("L").point(lambda v: 255 if v > 16 else 0)
        changed = diff.histogram()[255]
        if diff_out is not None and changed:
            overlay = ib.copy()
            red = Image.new("RGB", ib.size, (230, 40, 40))
            overlay.paste(red, mask=diff)
            overlay.save(diff_out)
        return round(100.0 * changed / (ia.width * ia.height), 3)


def judge(check: dict, obs: dict, base: dict | None, obs_dir: Path | None = None, base_dir: Path | None = None) -> dict:
    """{"state": pass|fail|na, "detail": str, "metrics": {...}}."""
    if not obs.get("ran"):
        return {"state": "na", "detail": obs.get("detail", "probe did not run"), "metrics": {}}
    kind = check["kind"]
    a = check.get("assert", {})
    fails, nas, metrics = [], [], {}
    if kind == "web":
        if obs.get("missing"):
            return {"state": "fail", "detail": obs["detail"], "metrics": {}}
        full = obs.get("driver") == "playwright"
        errs = obs.get("consoleErrors", []) + obs.get("failedRequests", [])
        if a.get("noConsoleErrors"):
            if not full:
                nas.append("console errors (screenshot-only driver)")
            elif errs:
                fails.append(f"{len(errs)} console error(s): {errs[0]}")
        if a.get("noHorizontalOverflow"):
            if not full:
                nas.append("overflow (screenshot-only driver)")
            elif obs["scrollWidth"] > obs["clientWidth"]:
                fails.append(f"horizontal overflow: scrollWidth {obs['scrollWidth']} > {obs['clientWidth']}")
        for s in a.get("selectorsExist", []):
            if not full:
                nas.append(f"selector {s}")
            elif not obs.get("present", {}).get(s):
                fails.append(f"selector {s} not found")
        for s in a.get("selectorsAbsent", []):
            if full and obs.get("present", {}).get(s):
                fails.append(f"selector {s} still present")
        if "maxPixelDiff" in a:
            if base is None or not base.get("screenshot") or obs_dir is None or base_dir is None:
                nas.append("pixel diff (no baseline screenshot)")
            else:
                pct = pixel_diff(base_dir / base["screenshot"], obs_dir / obs["screenshot"],
                                 obs_dir / (Path(obs["screenshot"]).stem + "-diff.png"))
                metrics["pixelDiffPct"] = pct
                if pct is None:
                    nas.append("pixel diff (image unreadable)")
                elif pct > float(a["maxPixelDiff"]):
                    fails.append(f"pixel difference {pct}% > {a['maxPixelDiff']}%")
        if full:
            metrics.update({"consoleErrors": len(errs), "scrollWidth": obs["scrollWidth"], "clientWidth": obs["clientWidth"]})
    elif kind == "command":
        want = a.get("exit", 0)
        if obs.get("timedOut"):
            fails.append("timed out")
        elif obs["exit"] != want:
            fails.append(f"exit {obs['exit']}, expected {want}")
        tail = obs.get("tail", "")
        fails.extend(f"output lacks {s!r}" for s in a.get("stdoutIncludes", []) if s not in tail)
        if a.get("stdoutRegex") and not re.search(a["stdoutRegex"], tail):
            fails.append(f"output does not match /{a['stdoutRegex']}/")
        if a.get("unchanged"):
            if base is None:
                nas.append("unchanged (no baseline)")
            elif base.get("outputSha256") != obs.get("outputSha256"):
                fails.append("output differs from the baseline")
        metrics["exit"] = obs.get("exit")
    else:
        if "exists" in check and obs["exists"] != bool(check["exists"]):
            fails.append(f"file {'missing' if check['exists'] else 'still present'}: {check['path']}")
        if "sha256" in check and obs.get("sha256") != check["sha256"]:
            fails.append("sha256 differs")
        if check.get("unchanged"):
            if base is None:
                nas.append("unchanged (no baseline)")
            elif base.get("sha256") != obs.get("sha256") or base.get("exists") != obs.get("exists"):
                fails.append("file differs from the baseline")
    if fails:
        return {"state": "fail", "detail": "; ".join(fails), "metrics": metrics}
    if nas:
        return {"state": "na", "detail": "not run: " + "; ".join(nas), "metrics": metrics}
    return {"state": "pass", "detail": "all assertions hold", "metrics": metrics}


# ---- selftest ------------------------------------------------------------------
def selftest() -> int:
    fails: list[str] = []

    def ok(name: str, cond: bool, extra: str = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + extra}")
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out = root / "obs"
        (root / "a.txt").write_text("x", encoding="utf-8")
        c_ok = {"kind": "command", "run": "echo hello", "assert": {"exit": 0, "stdoutIncludes": ["hello"]}}
        r = judge(c_ok, observe(root, c_ok, out, "c1"), None)
        ok("command pass", r["state"] == "pass", str(r))
        c_bad = {"kind": "command", "run": "exit 3", "assert": {"exit": 0}}
        r = judge(c_bad, observe(root, c_bad, out, "c2"), None)
        ok("command non-zero exit fails", r["state"] == "fail" and "exit 3" in r["detail"], str(r))
        c_un = {"kind": "command", "run": "echo same", "assert": {"unchanged": True}}
        b = observe(root, c_un, out, "c3")
        ok("command unchanged without baseline is na, never pass", judge(c_un, b, None)["state"] == "na")
        ok("command unchanged with equal baseline passes", judge(c_un, observe(root, c_un, out, "c3b"), b)["state"] == "pass")
        f_gone = {"kind": "file", "path": "a.txt", "exists": False}
        ok("file still present fails a delete check", judge(f_gone, observe(root, f_gone, out, "f"), None)["state"] == "fail")
        (root / "a.txt").unlink()
        ok("file absent passes a delete check", judge(f_gone, observe(root, f_gone, out, "f"), None)["state"] == "pass")
        w = {"kind": "web", "page": "nope.html", "assert": {"noConsoleErrors": True}}
        ok("missing page fails, not na", judge(w, observe(root, w, out, "w0"), None)["state"] == "fail")
        ok("a probe that did not run is na", judge(w, {"ran": False, "detail": "x"}, None)["state"] == "na")
        shot_only = {"kind": "web", "ran": True, "driver": "chrome-screenshot-only", "screenshot": "s.png"}
        ok("console assertion on screenshot-only driver is na, never pass",
           judge({"kind": "web", "page": "p", "assert": {"noConsoleErrors": True}}, shot_only, None)["state"] == "na")
        full = {"kind": "web", "ran": True, "driver": "playwright", "consoleErrors": ["boom"], "failedRequests": [],
                "scrollWidth": 400, "clientWidth": 390, "present": {"#k": True}, "screenshot": "s.png"}
        r = judge({"kind": "web", "page": "p", "assert": {"noConsoleErrors": True, "noHorizontalOverflow": True}}, full, None)
        ok("console error and overflow both fail", r["state"] == "fail" and "overflow" in r["detail"] and "console" in r["detail"], str(r))

        drivers = detect()
        if drivers["playwright"]:
            page = root / "p.html"
            page.write_text("<!doctype html><body style='margin:0'><div id='k' style='width:500px'>Revenue</div>"
                            "<script>console.error('planted')</script></body>", encoding="utf-8")
            wc = {"kind": "web", "page": "p.html", "width": 390,
                  "assert": {"noConsoleErrors": True, "noHorizontalOverflow": True, "selectorsExist": ["#k"]}}
            r = judge(wc, observe(root, wc, out, "w1"), None)
            ok("real browser: planted console error and overflow caught", r["state"] == "fail"
               and "planted" in r["detail"] and "overflow" in r["detail"], str(r))
            page.write_text("<!doctype html><body style='margin:0'><div id='k'>Revenue</div></body>", encoding="utf-8")
            b1 = observe(root, wc, out, "w2")
            r = judge(wc, b1, None)
            ok("real browser: clean page passes", r["state"] == "pass", str(r))
            wd = {**wc, "assert": {"maxPixelDiff": 0.1}}
            page.write_text("<!doctype html><body style='margin:0;background:#c00'><div id='k'>Revenue</div></body>", encoding="utf-8")
            r = judge(wd, observe(root, wd, out, "w3"), b1, out, out)
            ok("real browser: a repaint beyond tolerance fails the pixel diff", r["state"] == "fail", str(r))
        else:
            print("  skip real-browser cases (no node + playwright here)")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("selftest passed")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="probes.py", description="Observe and judge web / command / file probes.",
                                     epilog="exit 0 ok, 1 selftest failed")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--detect", action="store_true", help="print which drivers are available")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.detect:
        print(json.dumps(detect(), indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
