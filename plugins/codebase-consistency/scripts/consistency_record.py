#!/usr/bin/env python3
"""Record how a consistency stage ended, beside the artifacts it wrote.

usage: consistency_record.py event --area AREA --stage STAGE --status closed|halted|opened
                                   [--reason TEXT] [--detail JSON] [--root DIR]
       consistency_record.py status --area AREA [--root DIR]
       consistency_record.py --selftest

codebase-consistency's eleven artifacts under analysis/<area>/ are all written by the
model, and every reader of them is the model too -- so a stage that refused, or an
align fan-out the circuit breaker stopped, left nothing a later stage or a person
could find: the stop existed only in the chat. This writes analysis/<area>/run.jsonl
(the shared tools/run-record library, vendored here), one span-shaped event per stage
boundary. A halt without a reason is refused: a halt is an event, never an absence.

Needs Python >= 3.11 (the library's floor); below it, exits 2 saying so.
Exit: 0 recorded / printed, 1 refused (bad event, damaged record), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STAGES = ("preflight", "scan", "map", "canonize", "brief", "align", "verify")


def _run(root: Path, area: str):
    import run_record  # vendored copy of tools/run-record/run_record.py

    rel = Path(area)
    if rel.is_absolute() or ".." in rel.parts:
        raise run_record.RecordError(f"area {area!r} must be a relative path inside analysis/")
    # The area may be nested (src/api), the run id may not contain '/'.
    return run_record, run_record.open_run("codebase-consistency", "__".join(rel.parts),
                                           root, directory=root / "analysis" / rel)


def event(root: Path, area: str, stage: str, status: str, reason: str | None, detail: dict | None) -> dict:
    rr, run = _run(root, area)
    if status == "halted":
        run.halt(reason or "", stage)
    else:
        ev = {"trace_id": run.run_id, "span_id": f"{run.run_id}.{stage}.{status}.{len(run.events())}",
              "parent_span_id": f"{run.run_id}.root", "span": f"phase {stage}", "node_id": stage, "status": status}
        if detail:
            ev["detail"] = detail
        run.append(ev)
    return run.status()


def selftest() -> int:
    fails = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    import run_record

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        st = event(root, "src/api", "scan", "closed", None, {"artifacts": ["CONSISTENCY_SCAN.md"]})
        ok("a nested area records beside its artifacts", (root / "analysis/src/api/run.jsonl").is_file())
        ok("a closed stage reads as closed", st["counts"].get("closed") == 1)
        st = event(root, "src/api", "align", "halted", "circuit breaker: 1/3 batch pass rate", None)
        ok("an aborted align is a halt with its reason", st["halted"] == {"node_id": "align", "reason": "circuit breaker: 1/3 batch pass rate"})
        for name, args in [("a halt with no reason is refused", ("src/api", "align", "halted", "", None)),
                           ("an area escaping analysis/ is refused", ("../etc", "scan", "closed", None, None))]:
            try:
                event(root, *args[:3], args[3], args[4])
                ok(name, False)
            except run_record.RecordError:
                ok(name, True)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("consistency_record selftest passed")
    return 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="consistency_record.py", description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    e = sub.add_parser("event")
    e.add_argument("--area", required=True)
    e.add_argument("--stage", required=True, choices=STAGES)
    e.add_argument("--status", required=True, choices=("opened", "closed", "halted"))
    e.add_argument("--reason")
    e.add_argument("--detail", help="a JSON object")
    e.add_argument("--root", default=".")
    s = sub.add_parser("status")
    s.add_argument("--area", required=True)
    s.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    try:
        if args.selftest:
            return selftest()
        if args.cmd is None:
            ap.print_usage()
            return 2
        import run_record
    except SystemExit as exc:  # the library's Python floor, or argparse
        print(str(exc), file=sys.stderr)
        return 2
    try:
        if args.cmd == "status":
            _, run = _run(Path(args.root), args.area)
            print(json.dumps(run.status(), indent=2))
            return 0
        detail = json.loads(args.detail) if args.detail else None
        st = event(Path(args.root), args.area, args.stage, args.status, args.reason, detail)
        print(json.dumps({"recorded": True, "next": st["next"], "halted": st["halted"]}))
        return 0
    except (run_record.RecordError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
