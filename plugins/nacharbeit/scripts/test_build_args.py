#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Calibration for build_args.py's fixture handling -- issue #117.

The review used to read its calibration fixtures from `test/plugins/fixtures/nacharbeit`
inside the repository being reviewed, so the installed plugin could only run where
werkstoff's own test tree happened to exist, and `--fixtures-root` could point nowhere else
because every planted.json stored repository-relative paths. These cases run build_args.main()
in a repository that contains one trivial plugin and nothing of werkstoff's:

1. default   -- the fixtures shipped inside the plugin calibrate there (exit 0, run.js baked,
                every fixture path under the staged, repo-relative prefix).
2. override  -- `--fixtures-root` at a copy somewhere else works (the comment on #117).
3. legacy    -- a planted.json that still carries a repository-relative path is refused by
                name, not with a traceback and not by silently accepting a second format.
4. missing   -- an absent root or one with no sealed fixture exits 1 and says where it looked.
5. staging   -- the staged copy is replaced, not merged: a file left by an earlier run is gone.
6. sabotage  -- neuter the path validation, then the staging; the matching case must go red.

Usage: test_build_args.py            (exit 0 green, 1 red)
Exit: 0 green; 1 any check red.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # `uv run` has no -B; keep the installed plugin copy free of __pycache__ (#88)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nacharbeit_common as nc  # noqa: E402

spec = importlib.util.spec_from_file_location("build_args_under_test", HERE / "build_args.py")
assert spec is not None and spec.loader is not None
ba = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ba
spec.loader.exec_module(ba)

SKILL = """---
name: greet
description: "Use when the user asks for a greeting in a given language. Trigger on 'say hello in French'. Writes nothing."
---

Greet the user.

## Steps

1. Read the language the user named.
2. Reply with a greeting in it.
"""
MANIFEST = '{"name": "plugin", "version": "0.1.0", "description": "Greets the user in a configurable language.", "author": {"name": "x"}, "license": "MIT"}\n'


def make_repo(root: Path) -> None:
    """A repository that is NOT werkstoff: one plugin, no .rrt.toml, no test/, no docs/."""
    (root / "plugin" / ".claude-plugin").mkdir(parents=True)
    (root / "plugin" / "skills" / "greet").mkdir(parents=True)
    (root / "plugin" / ".claude-plugin" / "plugin.json").write_text(MANIFEST, encoding="utf-8")
    (root / "plugin" / "skills" / "greet" / "SKILL.md").write_text(SKILL, encoding="utf-8")
    (root / "plugin" / "README.md").write_text("# plugin\n", encoding="utf-8")


def build(root: Path, *extra: str) -> tuple[int, str, str]:
    """build_args.main() as the CLI would run it, from inside root; cwd restored (main() chdirs)."""
    cwd = os.getcwd()
    out, err = io.StringIO(), io.StringIO()
    try:
        os.chdir(root)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ba.main(["--plugins-root", ".", "--plugin", "plugin", *extra])
    finally:
        os.chdir(cwd)
    return rc, out.getvalue(), err.getvalue()


def fixture_paths(args: dict) -> list[str]:
    return [f for fx in args["fixtures"] + args["sealed"] for f in fx["files"] + fx["cleanFiles"] + [p["file"] for p in fx["planted"]]]


def check_default(td: Path) -> int:
    root = td / "default"
    make_repo(root)
    rc, _, err = build(root)
    if rc != 0:
        print(f"RED  default: build_args exited {rc} in a repository without werkstoff's test tree: {err.strip()[:200]}")
        return 1
    args = json.loads((root / "analysis/nacharbeit/args.json").read_text(encoding="utf-8"))
    prefix = args["fixturePrefix"]
    bad = [f for f in fixture_paths(args) if not f.startswith(prefix) or Path(f).is_absolute()]
    missing = [f for f in fixture_paths(args) if not (root / f).is_file()]
    red = 0
    if prefix != "analysis/nacharbeit/fixtures/":
        print(f"RED  default: fixturePrefix is {prefix!r}, expected the repo-relative staged directory")
        red += 1
    if bad or missing:
        print(f"RED  default: {len(bad)} fixture path(s) outside the prefix, {len(missing)} not readable from the repo root")
        red += 1
    if not (root / "analysis/nacharbeit/run.js").is_file():
        print("RED  default: run.js was not baked")
        red += 1
    pre = subprocess.run([sys.executable, "-B", str(HERE / "preflight.py"), "--plugins-root", "."], cwd=root,
                         capture_output=True, text=True, timeout=120)
    want = f"{len(args['fixtures'])} tuning + {len(args['sealed'])} sealed"
    if pre.returncode != 0 or want not in pre.stdout or "kinds with a pair: assets, docs" not in pre.stdout:
        print(f"RED  default: preflight in the bare repository exited {pre.returncode} and did not report {want!r} with its kinds")
        red += 1
    if not red:
        print(f"     default: {want} fixtures calibrate in a bare repository, and preflight reports them")
    return red


def copy_fixtures(td: Path, name: str) -> Path:
    dst = td / name
    shutil.copytree(nc.DEFAULT_FIXTURES_ROOT, dst)
    return dst


def check_override(td: Path) -> int:
    root = td / "override"
    make_repo(root)
    elsewhere = copy_fixtures(td, "elsewhere/anywhere")
    rc, _, err = build(root, "--fixtures-root", str(elsewhere))
    if rc != 0:
        print(f"RED  override: --fixtures-root at {elsewhere} exited {rc}: {err.strip()[:200]}")
        return 1
    print("     override: --fixtures-root at an arbitrary absolute path works")
    return 0


def legacy_root(td: Path, name: str) -> Path:
    fx = copy_fixtures(td, name)
    m = fx / "tune-1" / "planted.json"
    data = json.loads(m.read_text(encoding="utf-8"))
    data["planted"][0]["file"] = "test/plugins/fixtures/nacharbeit/tune-1/" + data["planted"][0]["file"]
    m.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return fx


def check_legacy(td: Path) -> int:
    root = td / "legacy"
    make_repo(root)
    rc, _, err = build(root, "--fixtures-root", str(legacy_root(td, "legacy-fx")))
    if rc != 1 or "relative to the fixture directory" not in err or "Traceback" in err:
        print(f"RED  legacy: a repository-relative planted path exited {rc} with {err.strip()[:160]!r}; expected exit 1 naming the rule")
        return 1
    print("     legacy: a repository-relative planted path is refused by name")
    return 0


def check_missing(td: Path) -> int:
    red = 0
    root = td / "missing"
    make_repo(root)
    rc, _, err = build(root, "--fixtures-root", str(td / "does-not-exist"))
    shipped = nc.DEFAULT_FIXTURES_ROOT.relative_to(nc.PLUGIN_ROOT).as_posix()
    if rc != 1 or shipped not in err:
        print(f"RED  missing: an absent fixtures root exited {rc} with {err.strip()[:160]!r}; expected exit 1 saying where the plugin ships them")
        red += 1
    nosealed = copy_fixtures(td, "nosealed-fx")
    for d in nosealed.glob("sealed*"):
        shutil.rmtree(d)
    rc, _, err = build(root, "--fixtures-root", str(nosealed))
    if rc != 1 or "sealed" not in err:
        print(f"RED  missing: a root with no sealed fixture exited {rc} with {err.strip()[:160]!r}")
        red += 1
    if not red:
        print("     missing: an absent root and a root without a sealed fixture both exit 1 and say what is wrong")
    return red


def check_staging(td: Path) -> int:
    root = td / "staging"
    make_repo(root)
    stale = root / "analysis/nacharbeit/fixtures/stale-from-an-earlier-run.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("left over\n", encoding="utf-8")
    rc, _, err = build(root)
    if rc != 0 or stale.exists():
        print(f"RED  staging: exit {rc}, stale file still present={stale.exists()}: {err.strip()[:120]}")
        return 1
    print("     staging: a file left by an earlier run does not survive into the staged copy")
    return 0


def sabotage(td: Path) -> int:
    red = 0
    # (a) neuter path validation: the legacy case must stop being refused by name
    saved = ba._fixture_relative
    ba._fixture_relative = lambda _d, _field, value: value  # type: ignore[assignment]
    try:
        root = td / "sab-legacy"
        make_repo(root)
        rc, _, err = build(root, "--fixtures-root", str(legacy_root(td, "sab-legacy-fx")))
    finally:
        ba._fixture_relative = saved
    if rc == 1 and "relative to the fixture directory" in err:
        print("RED  sabotage: neutering path validation still produced the named refusal -- the legacy check is not load-bearing")
        red += 1
    # (b) neuter staging: the stale file must now survive, so the staging check goes red
    saved_stage = ba.stage_fixtures
    ba.stage_fixtures = lambda _src, staged: staged.mkdir(parents=True, exist_ok=True)  # type: ignore[assignment]
    try:
        root = td / "sab-stage"
        make_repo(root)
        stale = root / "analysis/nacharbeit/fixtures/stale-from-an-earlier-run.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("left over\n", encoding="utf-8")
        build(root)
        survived = stale.exists()
    finally:
        ba.stage_fixtures = saved_stage
    if not survived:
        print("RED  sabotage: neutering staging still removed the stale file -- the staging check is not load-bearing")
        red += 1
    if not red:
        print("     sabotage: neutering path validation and staging each turned its case red")
    return red


def main() -> int:
    red = 0
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        for check in (check_default, check_override, check_legacy, check_missing, check_staging, sabotage):
            red += check(td)
    print("GREEN" if not red else f"RED ({red})")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
