#!/usr/bin/env python3
"""Join every declared acceptance id to the evidence the run recorded for it.

usage: reconcile.py --run RUNID [--run-checks] | --selftest

The plan says what must hold (workflow.json's acceptance, or the CONTRACT phase's
if one ran). The record says what happened (run.jsonl, referee/, landed.json).
Nothing joined the two, so "every criterion met" was a sentence, not a result.

Per acceptance id, the verdict is one of:

  measured-pass    --run-checks ran its check now: exit 0 (recorded, stdout hashed)
  measured-fail    --run-checks ran its check now: non-zero
  refereed-met     the landed candidate's blind referee recorded it met, with evidence
  refereed-unmet   ...recorded it NOT met
  doubt            the record holds a doubt for it, carrying resolves_if
  UNADDRESSED      none of the above -- nothing in the record speaks to it

`--run-checks` MEASURES rather than transcribes (quo-warranto's rule): the field
that proves a claim is produced here, by running the command and hashing its own
stdout, never copied from the party that made the claim. Each run is appended to
run.jsonl as an `execute_tool` event. A referee that recorded `met` for a
criterion whose check now fails is reported as a CONTRADICTION.

Exit: 0 every id addressed and nothing contradicted, 1 otherwise, 2 bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_record  # vendored copy of tools/run-record/run_record.py

PLUGIN = "arbeitsplan"


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def acceptance(d: Path) -> tuple:
    contract = _read(d / "phases" / "contract.json")
    if contract and isinstance(contract.get("acceptance"), list):
        return contract["acceptance"], "phases/contract.json"
    spec = _read(d / "workflow.json") or {}
    return (spec.get("problem") or {}).get("acceptance") or [], "workflow.json"


def measure(run: run_record.Run, crit: dict, cwd: Path) -> dict:
    # An acceptance `check` IS a shell program by schema ("a shell command that exits
    # 0 on pass" -- `ruff check x && git diff --exit-code -- y`), so it runs under
    # /bin/sh, explicitly. Nothing is interpolated into it: the string is the
    # spec's own declared command, run exactly as a CI step would run it.
    p = subprocess.run(["/bin/sh", "-c", crit["check"]], cwd=cwd, capture_output=True, text=True, timeout=600)
    rec = {"id": crit["id"], "command": crit["check"], "exit": p.returncode,
           "stdoutSha256": hashlib.sha256(p.stdout.encode()).hexdigest()}
    run.append({"trace_id": run.run_id,
                "span_id": f"{run.run_id}.check.{crit['id']}.{rec['stdoutSha256'][:12]}.{p.returncode}",
                "parent_span_id": f"{run.run_id}.root", "span": f"execute_tool {crit['id']}",
                "node_id": crit["id"], "status": "accepted" if p.returncode == 0 else "refuted",
                "detail": rec})
    return rec


def reconcile(run: run_record.Run, run_checks: bool, cwd: Path) -> tuple:
    d = run.dir
    crits, source = acceptance(d)
    landed = _read(d / "landed.json")
    verdict = _read(d / "referee" / f"{landed['candidate']}.json") if landed else None
    per = {c.get("id"): c for c in (verdict or {}).get("perCriterion") or [] if isinstance(c, dict)}
    # A doubt addresses a criterion by an explicit id -- detail.criterion, or a
    # node_id equal to it -- never by a prefix of its evidence text, where "a1"
    # would silently swallow "a10".
    doubts = {}
    for e in run.events():
        if e["status"] == "doubt":
            key = (e.get("detail") or {}).get("criterion") or e["node_id"]
            doubts.setdefault(key, e)
    rows, contradictions = [], []
    for c in crits:
        cid = c.get("id")
        row = {"id": cid, "criterion": c.get("criterion")}
        if run_checks and c.get("check"):
            m = measure(run, c, cwd)
            row.update(verdict="measured-pass" if m["exit"] == 0 else "measured-fail", evidence=m)
            if m["exit"] != 0 and per.get(cid, {}).get("met"):
                contradictions.append(f"{cid}: the referee recorded met, and its check now exits {m['exit']}")
        elif cid in per:
            row.update(verdict="refereed-met" if per[cid].get("met") else "refereed-unmet",
                       evidence=per[cid].get("evidence"))
        elif cid in doubts:
            row.update(verdict="doubt", evidence=(doubts[cid].get("detail") or {}).get("resolves_if"))
        else:
            row.update(verdict="UNADDRESSED", evidence=None)
        rows.append(row)
    return rows, contradictions, source, landed


def selftest() -> int:
    fails = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as raw:
        try:
            os.chdir(raw)
            run = run_record.open_run(PLUGIN, "ap-r-1")
            d = run.dir
            (d / "workflow.json").write_text(json.dumps({"problem": {"acceptance": [
                {"id": "a1", "criterion": "passes", "check": "true"},
                {"id": "a2", "criterion": "fails now", "check": "false"},
                {"id": "a3", "criterion": "doubted", "check": None},
                {"id": "a4", "criterion": "forgotten", "check": None}]}}))
            (d / "referee").mkdir()
            (d / "referee" / "c1.json").write_text(json.dumps({"candidateId": "c1", "verdict": "accepted", "perCriterion": [
                {"id": "a1", "met": True, "evidence": "e1"}, {"id": "a2", "met": True, "evidence": "e2"}]}))
            (d / "landed.json").write_text(json.dumps({"candidate": "c1"}))
            run.append({"trace_id": "ap-r-1", "span_id": "d1", "parent_span_id": "r", "span": "evaluation",
                        "node_id": "adjudicate", "status": "doubt",
                        "detail": {"criterion": "a3", "evidence": "unknown", "resolves_if": "x"}})
            run.append({"trace_id": "ap-r-1", "span_id": "d2", "parent_span_id": "r", "span": "evaluation",
                        "node_id": "adjudicate", "status": "doubt",
                        "detail": {"criterion": "a40", "evidence": "a4 lookalike", "resolves_if": "x"}})

            rows, contra, src, _ = reconcile(run, False, Path(raw))
            v = {r["id"]: r["verdict"] for r in rows}
            ok("reads acceptance from workflow.json when no contract ran", src == "workflow.json")
            ok("referee evidence joins by id", v["a1"] == "refereed-met" and v["a2"] == "refereed-met")
            ok("a doubt addresses its id", v["a3"] == "doubt")
            ok("an id nothing speaks to is UNADDRESSED, even beside a lookalike a40",
               v["a4"] == "UNADDRESSED")

            rows, contra, _, _ = reconcile(run, True, Path(raw))
            v = {r["id"]: r["verdict"] for r in rows}
            ok("--run-checks measures instead of transcribing", v["a1"] == "measured-pass" and v["a2"] == "measured-fail")
            ok("a referee 'met' whose check now fails is a contradiction", any(c.startswith("a2") for c in contra))
            ok("every measurement is recorded as execute_tool",
               sum(1 for e in run.events() if e["span"].startswith("execute_tool")) == 2)

            (d / "phases").mkdir()
            (d / "phases" / "contract.json").write_text(json.dumps({"acceptance": [{"id": "b1", "criterion": "c", "check": "true"}]}))
            _, _, src, _ = reconcile(run, False, Path(raw))
            ok("a CONTRACT phase's acceptance replaces the compiled one", src == "phases/contract.json")
        finally:
            os.chdir(cwd)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("reconcile selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="reconcile.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--run")
    parser.add_argument("--run-checks", action="store_true",
                        help="run every acceptance check now, hash its stdout, and record it")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.run:
        parser.error("--run is required unless --selftest is given")
    try:
        run = run_record.open_run(PLUGIN, args.run)
        rows, contradictions, source, landed = reconcile(run, args.run_checks, Path.cwd())
    except run_record.RecordError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print(f"no acceptance criteria found for {args.run} (looked in {source})", file=sys.stderr)
        return 2
    print(f"reconcile — {args.run}  (acceptance from {source}; landed: "
          f"{landed['candidate'] if landed else 'nothing'})")
    for r in rows:
        print(f"  {r['id']:<6} {r['verdict']:<15} {r['criterion']}")
        if r["evidence"] is not None:
            print(f"         {json.dumps(r['evidence'])[:160]}")
    for c in contradictions:
        print(f"  CONTRADICTION {c}")
    bad = [r for r in rows if r["verdict"] in ("UNADDRESSED", "measured-fail", "refereed-unmet")]
    if bad or contradictions:
        print(f"{len(bad)} criterion(s) not established, {len(contradictions)} contradiction(s)")
        return 1
    print("every criterion is addressed by recorded evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
