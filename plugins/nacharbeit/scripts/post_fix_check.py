#!/usr/bin/env python3
"""After a fix pass: re-run every item's post-checks, diff contracts against the
pre-fix snapshot, and — only when both are clean — release the fix lock. No LLM.

The fix workflow's blind verifier already runs each file's post-checks once; this
script is the cross-file second look it cannot take. It reads <state>/fix-args.json
(the items and their post-checks) and <state>/pre-fix/<plugin>/ (the snapshot
build_fix_args.py took), runs `contract_diff.py <snapshot> <plugin-dir>` per plugin,
and writes <state>/fix-check.json.

--release-lock deletes <state>/fix_scope.json only when no post-check failed and no
contract was LOST or MOVED. A lock that stays open denies every further edit, which
is the safe direction; nacharbeit-status reports a stale one with this command.

Usage: post_fix_check.py [--state-dir analysis/nacharbeit] [--plugins-root plugins]
                         [--contract-diff tools/plugin-serializer/contract_diff.py]
                         [--release-lock] [--force]
Exit: 0 all post-checks passed and no contract moved (lock released if asked);
      1 a post-check failed or a contract was lost/moved (lock kept unless --force);
      2 bad arguments or missing inputs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nacharbeit_common as nc  # noqa: E402


def run_cmd(cmd: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{type(e).__name__}: {e}"
    out = (r.stdout + r.stderr).strip()
    return r.returncode == 0, out[-800:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Post-fix checks, contract diff, and lock release.")
    ap.add_argument("--repo-root", type=Path, default=None)
    ap.add_argument("--state-dir", type=Path, default=None)
    ap.add_argument("--plugins-root", type=Path, default=nc.DEFAULT_PLUGINS_ROOT)
    ap.add_argument("--contract-diff", type=Path, default=nc.DEFAULT_CONTRACT_DIFF, help="contract_diff.py to run (skipped loudly when absent)")
    ap.add_argument("--release-lock", action="store_true")
    ap.add_argument("--force", action="store_true", help="release the lock even when a check failed (state your reason in the commit)")
    a = ap.parse_args(argv)

    root = nc.repo_root(a.repo_root)
    os.chdir(root)
    state = nc.state_dir(a.state_dir, root)
    fix_args = state / "fix-args.json"
    lock = state / "fix_scope.json"
    if not fix_args.is_file():
        print(f"ERROR: {fix_args} missing — run build_fix_args.py first", file=sys.stderr)
        return 2
    items = json.loads(fix_args.read_text(encoding="utf-8")).get("items", [])

    failed: list[dict] = []
    passed = 0
    seen: set[str] = set()
    for it in items:
        for c in it.get("postChecks", []):
            if c["cmd"] in seen:
                continue
            seen.add(c["cmd"])
            ok, out = run_cmd(c["cmd"])
            if ok:
                passed += 1
            else:
                failed.append({"file": it["file"], "label": c["label"], "cmd": c["cmd"], "output": out})
                print(f"FAIL {it['file']}: {c['label']}\n     {out.splitlines()[-1] if out else ''}")

    contracts: list[dict] = []
    snap_root = state / "pre-fix"
    if not a.contract_diff.is_file():
        print(f"WARN contract diff skipped: {a.contract_diff} not found", file=sys.stderr)
        contracts.append({"plugin": "*", "status": "skipped", "reason": f"{a.contract_diff} not found"})
    elif not snap_root.is_dir():
        print(f"WARN contract diff skipped: no snapshot at {snap_root}", file=sys.stderr)
        contracts.append({"plugin": "*", "status": "skipped", "reason": "no pre-fix snapshot"})
    else:
        for snap in sorted(p for p in snap_root.iterdir() if p.is_dir()):
            live = a.plugins_root / snap.name
            ok, out = run_cmd(f"python3 {a.contract_diff.as_posix()} {snap.as_posix()} {live.as_posix()}")
            contracts.append({"plugin": snap.name, "status": "clean" if ok else "moved-or-lost", "output": out})
            if not ok:
                print(f"FAIL contract diff {snap.name}:\n{out}")

    clean = not failed and all(c["status"] in {"clean", "skipped"} for c in contracts)
    report = {
        "checkedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "postChecks": {"passed": passed, "failed": failed},
        "contracts": contracts,
        "clean": clean,
        "lockReleased": False,
    }
    if a.release_lock:
        if clean or a.force:
            if lock.is_file():
                lock.unlink()
                report["lockReleased"] = True
                print(f"released {lock}" + (" (forced)" if not clean else ""))
            else:
                print(f"no lock at {lock}")
        else:
            print(f"lock kept: {len(failed)} failed post-check(s), {sum(c['status'] == 'moved-or-lost' for c in contracts)} contract diff(s) not clean", file=sys.stderr)
    tmp = state / "fix-check.json.tmp"
    tmp.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(state / "fix-check.json")
    print(f"post-checks: {passed} passed, {len(failed)} failed; contracts: " + ", ".join(f"{c['plugin']}={c['status']}" for c in contracts))
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
