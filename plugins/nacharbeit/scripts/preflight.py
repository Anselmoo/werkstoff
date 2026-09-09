#!/usr/bin/env python3
"""Read-only inventory before a nacharbeit run: what the target plugins contain,
which checkers this environment can run, which other guards are live, and whether
a fix lock is already open. Writes nothing.

Usage: preflight.py [<plugin-dir> ...] [--plugins-root plugins] [--state-dir analysis/nacharbeit]
                    [--docs-root docs] [--format text|json]
Exit: 0 inventory printed; 2 a named directory is not a plugin.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nacharbeit_common as nc  # noqa: E402

spec = importlib.util.spec_from_file_location("nacharbeit_lint", HERE / "nacharbeit_lint.py")
assert spec is not None and spec.loader is not None
lp = importlib.util.module_from_spec(spec)
sys.modules["nacharbeit_lint"] = lp
spec.loader.exec_module(lp)

# Other werkstoff guards and the state that makes each one fire (hazards.md cards). A fix
# pass that edits plugin files runs under all of them; knowing which are live explains a
# denial before it happens.
OTHER_GUARDS = [
    ("takt", ".claude/takt.local.md", "TAKT_DISABLE_GUARD=1"),
    ("lehre", ".lehre/ruleset.json", "LEHRE_DISABLE_GUARD=1"),
    ("andon", ".claude/andon.local.md", "enforcement: off in .claude/andon.local.md"),
    ("confab", "analysis/confab/remediation_scope.json", "delete the lock or run without --fix"),
    ("self-assess", "analysis/self-assess/edit_scope.json", "named in its deny message"),
    ("cupertino", ".cupertino", "CUPERTINO_DISABLE_GUARD=1"),
]
STALE_HOURS = 6


def lock_age_hours(lock: Path) -> float | None:
    try:
        created = json.loads(lock.read_text(encoding="utf-8")).get("createdAt")
        t = dt.datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except Exception:  # noqa: BLE001 -- an unreadable lock is reported as such, not hidden
        return None
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="nacharbeit preflight inventory (read-only).")
    ap.add_argument("plugin_dirs", nargs="*", type=Path)
    ap.add_argument("--plugins-root", type=Path, default=nc.DEFAULT_PLUGINS_ROOT)
    ap.add_argument("--state-dir", type=Path, default=None)
    ap.add_argument("--docs-root", type=Path, default=None)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    root = nc.repo_root()
    state = nc.state_dir(a.state_dir, root)
    dirs = a.plugin_dirs or (sorted(p for p in a.plugins_root.iterdir() if (p / ".claude-plugin" / "plugin.json").is_file()) if a.plugins_root.is_dir() else [])
    for d in dirs:
        if not d.is_dir():
            print(f"ERROR: not a directory: {d}", file=sys.stderr)
            return 2
    docs_root = a.docs_root if a.docs_root is not None else (nc.DEFAULT_DOCS_ROOT if nc.DEFAULT_DOCS_ROOT.is_dir() else None)
    lp.OPTIONS["docs_root"] = docs_root if docs_root and docs_root.is_dir() else None
    units = lp.discover(dirs)

    inventory = {}
    for d in dirs:
        counts = {}
        for u in units:
            if u.plugin == d.name and u.exists:
                counts[u.kind] = counts.get(u.kind, 0) + 1
        inventory[d.name] = counts
    tools = {
        "node": shutil.which("node") is not None,
        "claude": shutil.which("claude") is not None,
        "pyyaml": True,
        "viewer_checker": (HERE / "check_viewer_conformance.py").is_file(),
        "hooks_checker": (HERE / "verify_hooks_deny.py").is_file(),
        "contract_diff": nc.DEFAULT_CONTRACT_DIFF.is_file(),
        "known_answers": nc.DEFAULT_KNOWN_ANSWERS.is_file(),
        "marketplace": nc.DEFAULT_MARKETPLACE.is_file(),
        "docs_root": docs_root.as_posix() if docs_root else None,
        "fixtures_root": nc.DEFAULT_FIXTURES_ROOT.is_dir(),
    }
    live = [{"plugin": n, "marker": m, "escape": e} for n, m, e in OTHER_GUARDS if os.path.exists(os.path.join(root, m))]
    lock = state / "fix_scope.json"
    lock_info = None
    if lock.is_file():
        age = lock_age_hours(lock)
        lock_info = {"path": lock.as_posix(), "ageHours": None if age is None else round(age, 1), "stale": age is None or age > STALE_HOURS}
    runs = {name: (state / name).is_file() for name in ("lint.json", "args.json", "run.json", "fix-args.json", "fix-check.json")}

    out = {"plugins": inventory, "tools": tools, "liveGuards": live, "fixLock": lock_info, "state": {"dir": state.as_posix(), **runs}}
    if a.format == "json":
        print(json.dumps(out, indent=1))
        return 0
    print(f"nacharbeit preflight — {len(dirs)} plugin(s) under {a.plugins_root}")
    for name, counts in inventory.items():
        print(f"  {name:<22} " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("checkers: " + ", ".join(f"{k}={'yes' if v else 'no'}" if not isinstance(v, str) else f"{k}={v}" for k, v in tools.items()))
    if live:
        print("other guards live in this repository (a fix pass runs under them; a denial from one is reported, never bypassed):")
        for g in live:
            print(f"  {g['plugin']:<12} marker {g['marker']}  escape hatch: {g['escape']}")
    else:
        print("other guards live in this repository: none")
    if lock_info:
        print(f"fix lock OPEN at {lock_info['path']} (age {lock_info['ageHours']} h{', STALE' if lock_info['stale'] else ''}) — release with post_fix_check.py --release-lock before a new pass")
    else:
        print("fix lock: none open")
    print("state: " + ", ".join(f"{k}={'present' if v else 'absent'}" for k, v in runs.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
