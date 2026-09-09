#!/usr/bin/env python3
"""Report what nacharbeit has already run in this repository. Writes nothing.

Reads <state>/{lint,run,findings,synthesis,fix-args,fix-check}.json and fix_scope.json
and prints: the last review (stamp, calibration, sealed recall per family, verified
and lint counts), the backlog by tier with every opus- and human-tier entry verbatim
(those are never auto-applied, so a person has to see them), the last fix pass and
its post-check result, and an open lock with its age.

Usage: status.py [--state-dir analysis/nacharbeit] [--format text|json]
Exit: 0 printed (an empty state directory is a valid status); 2 bad arguments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nacharbeit_common as nc  # noqa: E402

STALE_HOURS = 6
TIERS = ("haiku", "sonnet", "opus", "human")


def load(state: Path, name: str):
    p = state / name
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 -- a corrupt state file is a finding, not a crash
        return {"_error": f"{type(e).__name__}: {e}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="nacharbeit status (read-only).")
    ap.add_argument("--state-dir", type=Path, default=None)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    state = nc.state_dir(a.state_dir)

    lint, run, synth = load(state, "lint.json"), load(state, "run.json"), load(state, "synthesis.json")
    fix_args, fix_check = load(state, "fix-args.json"), load(state, "fix-check.json")
    lock = load(state, "fix_scope.json")
    failed = sorted(p.name for p in state.glob("FAILED-*")) if state.is_dir() else []

    out: dict = {"stateDir": state.as_posix(), "failedMarkers": failed}
    if lint and "_error" not in lint:
        out["lint"] = {"findings": len(lint.get("findings", [])), "byRule": lint.get("by_rule", {}), "skipped": lint.get("skipped", [])}
    if run and "_error" not in run:
        cal = run.get("calibration") or {}
        out["review"] = {
            "runStamp": run.get("runStamp"), "rubricHash": (run.get("rubricHash") or "")[:12],
            "calibrationRounds": len(cal.get("rounds", [])),
            "sealedRecall": run.get("sealedRecall"), "sealedPerFamily": run.get("sealedPerFamily"),
            "sealedMissed": run.get("sealedMissed", []),
            "counts": run.get("counts", {}),
        }
    if synth and "_error" not in synth:
        tiers: Counter = Counter()
        held = []
        for p in synth.get("perPlugin", []):
            for b in p.get("backlog", []):
                tiers[b.get("fix_tier", "?")] += 1
                if b.get("fix_tier") in {"opus", "human"}:
                    held.append({"plugin": p["plugin"], "file": b["file"], "tier": b["fix_tier"], "rules": b.get("rule_ids", []), "action": b["action"]})
        out["backlog"] = {"byTier": {t: tiers.get(t, 0) for t in TIERS}, "heldForAPerson": held}
    if fix_args and "_error" not in fix_args:
        out["fix"] = {"runStamp": fix_args.get("runStamp"), "reviewRunStamp": fix_args.get("reviewRunStamp"), "items": len(fix_args.get("items", [])), "excluded": len(fix_args.get("excluded", []))}
    if fix_check and "_error" not in fix_check:
        out["fixCheck"] = {"checkedAt": fix_check.get("checkedAt"), "clean": fix_check.get("clean"), "failed": len((fix_check.get("postChecks") or {}).get("failed", [])), "lockReleased": fix_check.get("lockReleased")}
    if lock is not None:
        age = None
        if "_error" not in lock:
            try:
                t = dt.datetime.strptime(lock.get("createdAt", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
                age = round((dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600, 1)
            except ValueError:
                age = None
        out["fixLock"] = {"open": True, "ageHours": age, "stale": age is None or age > STALE_HOURS, "files": len((lock.get("files") or {})) if "_error" not in lock else None, "error": lock.get("_error")}
    else:
        out["fixLock"] = {"open": False}

    if a.format == "json":
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0

    print(f"nacharbeit status — state {state.as_posix()}")
    if failed:
        print(f"  FAILED markers: {', '.join(failed)} (a refused persist; the JSON on disk may be older than the run you watched)")
    if "lint" in out:
        print(f"  lint: {out['lint']['findings']} finding(s); " + ", ".join(f"{k}={v}" for k, v in sorted(out["lint"]["byRule"].items())[:12]) + (" …" if len(out["lint"]["byRule"]) > 12 else ""))
        for s in out["lint"]["skipped"]:
            print(f"        skipped {s['rule_id']}: {s['reason']}")
    else:
        print("  lint: not run")
    if "review" in out:
        r = out["review"]
        fam = ", ".join(f"{k} {v:.2f}" for k, v in (r["sealedPerFamily"] or {}).items())
        print(f"  review {r['runStamp']} rubric {r['rubricHash']}: {r['calibrationRounds']} calibration round(s), sealed recall {r['sealedRecall']:.2f}" + (f" ({fam})" if fam else "") + f"; verified {r['counts'].get('verified')} + lint {r['counts'].get('lint')}, judged collisions {r['counts'].get('judged')}")
        if r["sealedMissed"]:
            print(f"        blind spots (sealed defects missed): {len(r['sealedMissed'])} — " + "; ".join(r["sealedMissed"][:4]))
    else:
        print("  review: not run")
    if "backlog" in out:
        b = out["backlog"]
        print("  backlog by tier: " + ", ".join(f"{t} {n}" for t, n in b["byTier"].items()))
        if b["heldForAPerson"]:
            print(f"  held for a person ({len(b['heldForAPerson'])}; never auto-applied):")
            for h in b["heldForAPerson"]:
                print(f"    [{h['tier']:<5}] {h['plugin']}: {h['file']} — {h['action'][:160]}")
    if "fix" in out:
        f = out["fix"]
        print(f"  fix pass {f['runStamp']} (review {f['reviewRunStamp']}): {f['items']} file(s), {f['excluded']} excluded")
    if "fixCheck" in out:
        c = out["fixCheck"]
        print(f"  post-fix check {c['checkedAt']}: {'clean' if c['clean'] else str(c['failed']) + ' failed post-check(s) or a moved contract'}; lock released: {c['lockReleased']}")
    lk = out["fixLock"]
    if lk["open"]:
        print(f"  fix lock OPEN ({lk['files']} files, age {lk['ageHours']} h{', STALE' if lk['stale'] else ''}) — every edit outside it is denied; release with: python3 plugins/nacharbeit/scripts/post_fix_check.py --release-lock")
    else:
        print("  fix lock: none open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
