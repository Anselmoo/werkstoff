#!/usr/bin/env python3
"""Calibration for the fix pass's guard self-check -- issue #117.

nacharbeit-fix promised "a PreToolUse hook that denies every edit outside the fix lock".
An installed copy that was synced without hooks/ had no such hook, preflight never said so,
and the pass would have run unguarded. Two layers now stand between that and an edit:

1. static     -- nacharbeit_common.guard_status(): hooks.json present and declaring the guard
                 with a matcher covering every tool it must see, the script present, and the
                 registered command actually denying outside a lock and staying inert without one.
2. heartbeat  -- build_fix_args.py --confirm-guard: fix-run.js, the only launch path, is baked
                 only if the guard was seen firing for THIS lock; otherwise the lock is deleted.

Each case plants the failure it names and asserts the refusal; the last section blanks each
defence and requires the matching case to go red (a check that cannot fail is not a check).

Usage: test_fix_guard.py            (exit 0 green, 1 red)
Exit: 0 green; 1 any check red.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # `uv run` has no -B; keep the installed plugin copy free of __pycache__ (#88)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nacharbeit_common as nc  # noqa: E402

spec = importlib.util.spec_from_file_location("build_fix_args_under_test", HERE / "build_fix_args.py")
assert spec is not None and spec.loader is not None
bfa = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bfa
spec.loader.exec_module(bfa)


def plugin_copy(td: Path, name: str, *, drop: tuple[str, ...] = ()) -> Path:
    dst = td / name
    shutil.copytree(nc.PLUGIN_ROOT, dst, ignore=shutil.ignore_patterns("fixtures", "__pycache__", "analysis"))
    for rel in drop:
        target = dst / rel
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    return dst


def edit_hooks_json(copy: Path, fn) -> None:
    hj = copy / "hooks" / "hooks.json"
    data = json.loads(hj.read_text(encoding="utf-8"))
    fn(data)
    hj.write_text(json.dumps(data), encoding="utf-8")


def check_static(td: Path) -> int:
    red = 0
    real = nc.guard_status()
    if not real["ok"]:
        print(f"RED  static: the shipped guard is reported not live: {real['problem']}")
        red += 1
    cases = {
        "hooks/ missing (the reported install)": (plugin_copy(td, "nohooks", drop=("hooks",)), "hooks.json"),
        "script missing": (plugin_copy(td, "noscript", drop=("hooks/nacharbeit_guard.py",)), "does not exist"),
    }
    narrow = plugin_copy(td, "narrow")
    edit_hooks_json(narrow, lambda d: d["hooks"]["PreToolUse"][0].update(matcher="Write|Edit"))
    cases["matcher misses MultiEdit and Bash"] = (narrow, "does not cover")
    undeclared = plugin_copy(td, "undeclared")
    edit_hooks_json(undeclared, lambda d: d["hooks"]["PreToolUse"].clear())
    cases["guard no longer declared"] = (undeclared, "declares no")
    inert = plugin_copy(td, "allows-all")
    (inert / "hooks" / "nacharbeit_guard.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    cases["script that allows everything"] = (inert, "did not deny")
    always = plugin_copy(td, "denies-all")
    (always / "hooks" / "nacharbeit_guard.py").write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
    cases["script that denies everything (no lock either)"] = (always, "")
    for label, (copy, want) in cases.items():
        st = nc.guard_status(copy)
        if st["ok"] or want not in (st["problem"] or ""):
            print(f"RED  static: {label} was reported ok={st['ok']} problem={st['problem']!r}")
            red += 1
    prev = os.environ.get("NACHARBEIT_DISABLE_GUARD")
    os.environ["NACHARBEIT_DISABLE_GUARD"] = "1"
    try:
        disabled = nc.guard_status()
    finally:
        if prev is None:
            del os.environ["NACHARBEIT_DISABLE_GUARD"]
        else:
            os.environ["NACHARBEIT_DISABLE_GUARD"] = prev
    if disabled["ok"]:
        print("RED  static: NACHARBEIT_DISABLE_GUARD=1 in the environment was reported as a live guard")
        red += 1
    if not red:
        print(f"     static: shipped guard ok; {len(cases)} planted defects and the disabled-by-env case are each refused")
    return red


LOCK = {"runStamp": "2026-10-19T10:00:00Z", "createdAt": "2026-10-19T10:00:00Z", "files": {"plugins/a/README.md": "haiku"}}


def staged(td: Path, name: str, *, heartbeat: dict | None) -> Path:
    state = td / name / "analysis" / "nacharbeit"
    state.mkdir(parents=True)
    (state / "fix_scope.json").write_text(json.dumps(LOCK), encoding="utf-8")
    (state / "fix-args.json").write_text(json.dumps({"runStamp": LOCK["runStamp"], "items": []}), encoding="utf-8")
    if heartbeat is not None:
        (state / "guard-heartbeat.json").write_text(json.dumps(heartbeat), encoding="utf-8")
    return state


def confirm(state: Path) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        rc = bfa.confirm_guard(state, nc.PLUGIN_ROOT / "workflows" / "fix.js", state / "fix-args.json")
    return rc, err.getvalue()


def check_heartbeat(td: Path) -> int:
    red = 0
    good = staged(td, "seen", heartbeat={"lockRunStamp": LOCK["runStamp"], "seenAt": "2026-10-19T10:01:00Z", "tool": "Bash"})
    rc, err = confirm(good)
    if rc != 0 or not (good / "fix-run.js").is_file() or not (good / "fix_scope.json").is_file():
        print(f"RED  heartbeat: a lock whose guard was seen did not bake fix-run.js (exit {rc}): {err[:140]}")
        red += 1
    elif "const A = {" not in (good / "fix-run.js").read_text(encoding="utf-8"):
        print("RED  heartbeat: fix-run.js was written without the args literal baked into it")
        red += 1
    for label, hb in {"no heartbeat": None, "heartbeat from another lock": {"lockRunStamp": "2026-01-01T00:00:00Z", "seenAt": "x", "tool": "Bash"},
                      "heartbeat without a stamp": {"seenAt": "x"}}.items():
        state = staged(td, label.replace(" ", "-"), heartbeat=hb)
        (state / "fix-run.js").write_text("stale baked workflow from an earlier pass", encoding="utf-8")
        rc, err = confirm(state)
        if rc != 1 or (state / "fix_scope.json").exists() or (state / "fix-run.js").exists() or "has not fired" not in err:
            print(f"RED  heartbeat: {label}: exit {rc}, lock still open={(state / 'fix_scope.json').exists()}, "
                  f"stale fix-run.js still there={(state / 'fix-run.js').exists()}")
            red += 1
    if not red:
        print("     heartbeat: seen -> baked; missing / foreign / unstamped -> refused, lock deleted, stale fix-run.js removed")
    return red


def check_phase_one_refuses(td: Path) -> int:
    """build_fix_args.main() must stop on a dead guard BEFORE it looks for, or writes, anything."""
    root = td / "phase1"
    root.mkdir()
    saved = nc.guard_status
    nc.guard_status = lambda *_a, **_k: {"ok": False, "problem": "planted: hooks/ absent", "detail": []}  # type: ignore[assignment]
    cwd = os.getcwd()
    err = io.StringIO()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = bfa.main(["--repo-root", str(root)])
    finally:
        nc.guard_status = saved
        os.chdir(cwd)
    wrote = (root / "analysis").exists()
    if rc != 1 or "planted: hooks/ absent" not in err.getvalue() or wrote:
        print(f"RED  phase 1: with a dead guard main() exited {rc}, wrote analysis/={wrote}, stderr {err.getvalue()[:120]!r}")
        return 1
    print("     phase 1: a dead guard stops build_fix_args before any state is read or written")
    return 0


def sabotage(td: Path) -> int:
    """Blank the heartbeat comparison in a COPY of build_fix_args.py: a heartbeat left by another
    lock must then wrongly confirm. If it still refuses, the comparison was never what refused it."""
    path = HERE / "build_fix_args.py"
    src = path.read_text(encoding="utf-8")
    needle = 'beat.get("lockRunStamp") != lock.get("runStamp")'
    if needle not in src:
        print("RED  sabotage: the heartbeat comparison this check blanks is no longer where it was; update the check")
        return 1
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("bfa_sabotaged", loader=None))
    mod.__dict__["__file__"] = str(path)
    exec(compile(src.replace(needle, "False"), str(path), "exec"), mod.__dict__)
    state = staged(td, "sab-foreign", heartbeat={"lockRunStamp": "2026-01-01T00:00:00Z", "seenAt": "x", "tool": "Bash"})
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = mod.confirm_guard(state, nc.PLUGIN_ROOT / "workflows" / "fix.js", state / "fix-args.json")
    if rc != 0:
        print("RED  sabotage: blanking the heartbeat comparison still refused a foreign heartbeat -- the comparison is not load-bearing")
        return 1
    print("     sabotage: blanking the heartbeat comparison lets a foreign heartbeat confirm -> that case is load-bearing")
    return 0


def main() -> int:
    red = 0
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        for check in (check_static, check_heartbeat, check_phase_one_refuses, sabotage):
            red += check(td)
    print("GREEN" if not red else f"RED ({red})")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
