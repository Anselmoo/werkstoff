#!/usr/bin/env python3
"""Start a cupertino-repair run: say what the target is and what can be proven about it here.

usage: preflight_repair.py [-h] --target PATH [--run-id ID] [--no-begin]

Read-only on the target. Writes .cupertino/repair/<run>/preflight.json and, unless
--no-begin, begins the run -- which creates .cupertino/, so the guard is live from
the first step instead of from whenever a flag happens to be written.

Reports:
  kind          web | python | node | rust | native-build | docs | unknown (one target may be several)
  probes        which drivers exist (node+playwright, Chrome, Pillow) -- a web target with
                none can still be changed, but verify.py will report its checks "not run"
  commands      test / build commands found (pytest, npm test, cargo test, make test, make)
  design        design sources present: matrize tokens, *.tokens.json, CSS custom properties
                (with light/dark split), chart libraries whose colours live in JS
  git           whether the target has uncommitted changes (a baseline over a dirty tree
                cannot tell your change from one already there)
  verdict       ready | ready-with-gaps, with each gap named

Exit: 0 written; 1 the target does not exist or a run is already active; 2 bad usage.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probes  # noqa: E402
from repair_lib import RepairError, project_root, rel_posix, run_dir, write_json  # noqa: E402
from repair_state import cmd_begin  # noqa: E402

CHART_LIBS = {
    "chart.js": re.compile(r"chart(?:\.umd)?(?:\.min)?\.js|new\s+Chart\s*\(", re.I),
    "echarts": re.compile(r"echarts", re.I),
    "plotly": re.compile(r"plotly", re.I),
    "d3": re.compile(r"\bd3\.(?:select|scale|create)|d3(?:\.v\d)?(?:\.min)?\.js", re.I),
    "vega": re.compile(r"vega(?:-lite|-embed)?", re.I),
}
SKIP_DIRS = {".git", "node_modules", ".cupertino", "__pycache__", ".venv", "venv", "dist", "build", "target"}


def _files(target: Path, limit: int = 5000) -> list[Path]:
    out: list[Path] = []
    if target.is_file():
        return [target]
    for p in sorted(target.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            out.append(p)
            if len(out) >= limit:
                break
    return out


def detect_kind(target: Path, files: list[Path]) -> list[str]:
    names = {p.name for p in files}
    exts = {p.suffix.lower() for p in files}
    kinds = []
    if exts & {".html", ".htm"} or {"vite.config.js", "vite.config.ts", "next.config.js"} & names:
        kinds.append("web")
    if {"pyproject.toml", "setup.py", "setup.cfg"} & names or ".py" in exts:
        kinds.append("python")
    if "package.json" in names and "web" not in kinds:
        kinds.append("node")
    if "Cargo.toml" in names:
        kinds.append("rust")
    if {"Makefile", "Kconfig", "CMakeLists.txt", "meson.build"} & names or exts & {".c", ".h", ".s", ".S", ".ld", ".asm"}:
        kinds.append("native-build")
    if not kinds and exts & {".md", ".rst", ".txt"}:
        kinds.append("docs")
    return kinds or ["unknown"]


def detect_commands(target: Path, files: list[Path]) -> list[dict]:
    names = {p.name: p for p in files}
    cmds = []
    if any(p.name.startswith("test_") and p.suffix == ".py" for p in files) or "conftest.py" in names:
        cmds.append({"run": "python3 -m pytest -q", "why": "python test files found"})
    pkg = names.get("package.json")
    if pkg:
        try:
            scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
        except (OSError, ValueError):
            scripts = {}
        for s in ("test", "build", "lint"):
            if s in scripts:
                cmds.append({"run": f"npm run {s}", "why": f"package.json scripts.{s}"})
    if "Cargo.toml" in names:
        cmds.append({"run": "cargo test", "why": "Cargo.toml"})
    mk = names.get("Makefile")
    if mk:
        text = mk.read_text(encoding="utf-8", errors="replace")
        cmds.extend({"run": f"make {t}", "why": f"Makefile target {t}"} for t in ("test", "check")
                    if re.search(rf"(?m)^{t}\s*:", text))
        cmds.append({"run": "make", "why": "Makefile default target"})
    return cmds


def detect_design(root: Path, files: list[Path]) -> dict:
    design: dict = {"matrize": None, "tokenFiles": [], "cssCustomProperties": 0, "darkModeBlocks": 0, "chartLibraries": []}
    matrize_root = root / ".design"
    settings = root / ".claude" / "matrize.local.md"
    if settings.is_file():
        m = re.search(r"(?m)^root:\s*(\S+)", settings.read_text(encoding="utf-8"))
        if m:
            matrize_root = root / m.group(1)
    if (matrize_root / "system" / "tokens.json").is_file():
        design["matrize"] = rel_posix(root, matrize_root / "system" / "tokens.json")
    libs = set()
    for p in files:
        if p.name.endswith(".tokens.json") or p.name == "tokens.json":
            design["tokenFiles"].append(rel_posix(root, p))
        if p.suffix.lower() in (".css", ".html", ".htm", ".scss", ".vue", ".svelte", ".js", ".ts", ".jsx", ".tsx"):
            text = p.read_text(encoding="utf-8", errors="replace")
            design["cssCustomProperties"] += len(re.findall(r"(?m)^\s*--[\w-]+\s*:", text))
            design["darkModeBlocks"] += len(re.findall(r"prefers-color-scheme\s*:\s*dark|\[data-theme=[\"']?dark|\.dark\b", text))
            libs.update(name for name, rx in CHART_LIBS.items() if rx.search(text))
    design["chartLibraries"] = sorted(libs)
    return design


def git_state(root: Path, target: Path) -> dict:
    git = shutil.which("git")
    if not git:
        return {"repo": False}
    proc = subprocess.run([git, "status", "--porcelain", "--", str(target)], cwd=root, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {"repo": False}
    dirty = [ln[3:] for ln in proc.stdout.splitlines() if ln.strip() and ".cupertino/" not in ln]
    return {"repo": True, "clean": not dirty, "dirty": dirty[:50]}


def preflight(root: Path, target_arg: str) -> dict:
    target = (root / target_arg) if not Path(target_arg).is_absolute() else Path(target_arg)
    if not target.exists():
        raise RepairError(f"target {target_arg} does not exist")
    files = _files(target)
    kinds = detect_kind(target, files)
    drivers = probes.detect()
    report = {
        "target": rel_posix(root, target),
        "kind": kinds,
        "files": len(files),
        "probes": drivers,
        "commands": detect_commands(target, files),
        "design": detect_design(root, files),
        "git": git_state(root, target),
    }
    gaps = []
    if "web" in kinds and not drivers["playwright"]:
        gaps.append("web target but no node+playwright: console, overflow and selector checks will be 'not run'"
                    + ("" if drivers["chrome"] else "; no Chrome either, so no screenshots"))
    if report["git"].get("repo") and not report["git"].get("clean"):
        gaps.append("the target has uncommitted changes: commit or stash them so the baseline is unambiguous")
    if not report["commands"] and "web" not in kinds:
        gaps.append("no test or build command found: name one in the objective, or acceptance can only use file probes")
    if report["design"]["chartLibraries"]:
        gaps.append("charts draw from JS (" + ", ".join(report["design"]["chartLibraries"])
                    + "): a CSS variable is not a colour a canvas can read -- never swap a JS palette literal for var(--x)")
    report["gaps"] = gaps
    report["verdict"] = "ready" if not gaps else "ready-with-gaps"
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="preflight_repair.py", description="Start a cupertino-repair run and describe the target.",
                                     epilog="exit 0 written, 1 refused, 2 bad usage")
    parser.add_argument("--target", required=True, help="file or directory the objective is about")
    parser.add_argument("--run-id")
    parser.add_argument("--no-begin", action="store_true", help="describe only; do not start a run")
    args = parser.parse_args(argv)
    root = project_root()
    try:
        report = preflight(root, args.target)
        if not args.no_begin:
            run_id = cmd_begin(root, args.run_id)["runId"]
            report["runId"] = run_id
            write_json(run_dir(root, run_id) / "preflight.json", report)
    except RepairError as err:
        print(f"preflight_repair: {err}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
