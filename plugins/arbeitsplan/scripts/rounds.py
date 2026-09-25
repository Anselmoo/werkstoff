#!/usr/bin/env python3
"""Derive rounds from the run record, and rule on what they show (#78, #93).

usage: rounds.py {record,decide} ... | rounds.py --selftest

  record --run RUNID           (cwd = the root holding analysis/arbeitsplan/) prints, as the
                                WHOLE of stdout, a JSON list of "rounds" -- one per REFEREE
                                PHASE, in the order that phase's events first appear -- across
                                workflow.json's optional top-level `supersedes` chain, oldest
                                run first, numbered `round` 1..n across the whole chain.
  decide --rounds FILE [--max-advancing-rounds N] [--spec workflow.json]
                                reads the rounds FILE `record` produces (or any JSON list of
                                the same shape) and prints EXACTLY ONE line starting `ROUTE `.

Nothing here persists a new artifact. `record` rebuilds every round from what
record_event.py already wrote -- referee/<phase>/<id>.json (the phase-namespaced
twin record_event.py writes alongside its flat, write-once referee/<id>.json,
specifically so a SECOND referee phase reusing a candidate id is not silently
dropped) and phases/<adjudicate-phase>.json's `round: {outcome, blocking}` -- so
there is exactly one place either rule reads a round from, `read_rounds`, and
nothing to keep in sync with the record it derives from.

Two independent rejection-shaped failures this closes:

  #78 (a structural hole every candidate shares). The workflow halts on
      arithmetic alone -- `scoped * den < measured * num` -- and never looks at
      WHY a batch failed. When every candidate in the LATEST round was rejected
      and >= 2 of them share the same unmet acceptance criterion, `decide`
      prints `ROUTE SYNTHESIZE criterion=<id>`: the contract needs a diff that
      establishes exactly that criterion, drawn from what every rejected
      candidate already tried -- not N more candidates guessing at the same
      hole from scratch.
  #93 (a moving residual). A per-batch breaker and a per-criterion hole both
      look at ONE round. A run that "advances, not closes" every round, each
      time naming a DIFFERENT blocking condition, passes both forever. `decide`
      prints `ROUTE HALT moving-residual` when the last N judged rounds (an
      unjudged round -- `judge.outcome == "none"` -- neither breaks nor counts
      toward this) are all `advanced` with non-null, pairwise-distinct
      `judge.blocking` ids: N genuinely different obstacles in a row is a
      moving residual, not N steps of real progress. A repeated blocker id
      (the adjudicator recognised the same obstacle again) or any `closed`
      round in the window never fires this.

When both would fire on the same rounds, #93's HALT wins -- see decide_route().

Exit: 0 ok (including a clean `ROUTE CONTINUE`), 1 could not resolve the rounds
or the route, 2 usage.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_record  # vendored copy of tools/run-record/run_record.py


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_rounds(path: str) -> list:
    """THE one reader `decide` consumes -- resolved as a bare module-global name
    at call time, never cached into a local before the call, so a caller that
    replaces `rounds.read_rounds` (a sabotage test, or a future alternate
    source) changes what `decide` sees without touching `decide` itself."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} does not contain a JSON list of rounds")
    return data


# -- record: rebuild rounds from the run record -----------------------------

def _run_dir(run_id: str) -> Path:
    return run_record.run_dir("arbeitsplan", run_id)


def _phase_order(run_dir: Path) -> list:
    """Distinct phase node ids, in the order they FIRST appear as a `phase X`
    event in run.jsonl -- chronological call order, which is what makes a
    referee phase and the adjudicate output recorded after it line up without
    needing the events to carry an explicit round number."""
    log = run_dir / "run.jsonl"
    order: list = []
    seen: set = set()
    if not log.is_file():
        return order
    for raw in log.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if obj.get("kind") != "event":
            continue
        span = obj.get("span") or ""
        if not span.startswith("phase "):
            continue
        node = obj.get("node_id")
        if node and node not in seen:
            seen.add(node)
            order.append(node)
    return order


def _round_from_referee_dir(run_id: str, phase: str, ref_dir: Path) -> dict:
    accepted: list = []
    rejections: list = []
    for vf in sorted(ref_dir.glob("*.json")):
        v = _read_json(vf) or {}
        cid = v.get("candidateId") or vf.stem
        if v.get("verdict") == "accepted":
            accepted.append(cid)
            continue
        for item in v.get("perCriterion") or []:
            if not isinstance(item, dict) or item.get("met") is not False:
                continue
            crit = item.get("id")
            if not crit:
                continue
            note = item.get("evidence") or v.get("note") or f"{crit} not met"
            rejections.append({"candidateId": cid, "criterion": crit, "note": note})
    return {
        "round": None, "runId": run_id, "phase": phase,
        "accepted": sorted(accepted), "rejections": rejections,
        "judge": {"outcome": "none", "blocking": None},
    }


def _run_rounds(run_id: str) -> list:
    """Every round this ONE run's own record produces, in phase order -- never
    across the `supersedes` chain, that is `record`'s job below."""
    run_dir = _run_dir(run_id)
    rounds: list = []
    for node in _phase_order(run_dir):
        ref_dir = run_dir / "referee" / node
        if ref_dir.is_dir():
            rounds.append(_round_from_referee_dir(run_id, node, ref_dir))
            continue
        if node.startswith("adjudicate"):
            out = _read_json(run_dir / "phases" / f"{node}.json")
            j = out.get("round") if isinstance(out, dict) else None
            if not isinstance(j, dict):
                continue
            # The judge belongs to the most RECENT round still unjudged --
            # "recorded after that phase" (the docstring's own words) is exactly
            # first-appearance order among the phases walked above.
            for r in reversed(rounds):
                if r["judge"]["outcome"] == "none":
                    r["judge"] = {"outcome": j.get("outcome", "none"), "blocking": j.get("blocking")}
                    break
    return rounds


def _supersedes_chain(run_id: str) -> list:
    """`run_id` and every run it (transitively) supersedes, OLDEST first.
    Cycle-safe: a run already seen stops the walk rather than looping, so a
    cycle never lists a run twice."""
    chain: list = []
    seen: set = set()
    cur: str | None = run_id
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        spec = _read_json(_run_dir(cur) / "workflow.json") or {}
        nxt = spec.get("supersedes")
        cur = nxt if isinstance(nxt, str) and nxt else None
    chain.reverse()
    return chain


def cmd_record(run_id: str) -> int:
    all_rounds: list = []
    for rid in _supersedes_chain(run_id):
        all_rounds.extend(_run_rounds(rid))
    for i, r in enumerate(all_rounds, 1):
        r["round"] = i
    print(json.dumps(all_rounds))
    return 0


# -- decide: rule on the rounds ----------------------------------------------

def decide_route(rounds: list, max_advancing_rounds: int) -> str:
    """#93 first -- its HALT wins any tie with #78, because a moving residual
    means the round-by-round data #78 reads is itself untrustworthy: each
    round names a fresh obstacle, so the "latest round" #78 looks at is never
    the same failure twice and synthesizing against it chases a moving target.
    """
    judged = [r for r in rounds if (r.get("judge") or {}).get("outcome") != "none"]
    if len(judged) >= max_advancing_rounds:
        window = judged[-max_advancing_rounds:]
        if all((r.get("judge") or {}).get("outcome") == "advanced" for r in window):
            blockers = [(r.get("judge") or {}).get("blocking") for r in window]
            if all(b is not None for b in blockers) and len(set(blockers)) == len(blockers):
                return "ROUTE HALT moving-residual"

    if rounds:
        last = rounds[-1]
        if not last.get("accepted"):
            counts: dict = {}
            for rej in last.get("rejections") or []:
                crit = rej.get("criterion")
                if crit:
                    counts[crit] = counts.get(crit, 0) + 1
            shared = sorted(c for c, n in counts.items() if n >= 2)
            # Tie-break (declared cannotCheck: which criterion wins when several
            # qualify) is arbitrary but deterministic -- the lowest id, so the
            # same rounds always route the same way.
            if shared:
                return f"ROUTE SYNTHESIZE criterion={shared[0]}"

    return "ROUTE CONTINUE"


def cmd_decide(args: argparse.Namespace) -> int:
    try:
        rows = read_rounds(args.rounds)
    except (OSError, ValueError) as exc:
        print(f"cannot read {args.rounds}: {exc}", file=sys.stderr)
        return 2

    max_n = args.max_advancing_rounds
    if max_n is None and args.spec:
        spec = _read_json(Path(args.spec)) or {}
        rb = spec.get("roundBreaker") or {}
        v = rb.get("maxAdvancingRounds")
        if isinstance(v, int) and not isinstance(v, bool):
            max_n = v
    if max_n is None:
        max_n = 3

    print(decide_route(rows, max_n))
    return 0


# -- selftest -----------------------------------------------------------------

def _r(n: int, accepted: list, rejections: list, outcome: str = "none", blocking=None) -> dict:
    return {"round": n, "runId": "t", "phase": f"referee-w{n}", "accepted": accepted,
            "rejections": [{"candidateId": c, "criterion": k, "note": f"{k} not met"} for c, k in rejections],
            "judge": {"outcome": outcome, "blocking": blocking}}


def selftest() -> int:
    import os
    import tempfile

    fails: list = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    ok("a healthy round continues", decide_route([_r(1, ["c1"], [])], 3) == "ROUTE CONTINUE")
    ok("#78: two rejections sharing an unmet criterion synthesize",
       decide_route([_r(1, [], [("c1", "a2"), ("c2", "a2")])], 3) == "ROUTE SYNTHESIZE criterion=a2")
    ok("#78: an accepted round never synthesizes",
       decide_route([_r(1, ["c3"], [("c1", "a2"), ("c2", "a2")])], 3) == "ROUTE CONTINUE")
    ok("#78: only the latest round is read",
       decide_route([_r(1, [], [("c1", "a2"), ("c2", "a2")]), _r(2, ["c1"], [])], 3) == "ROUTE CONTINUE")
    moving = [_r(1, ["c1"], [], "advanced", "b1"), _r(2, ["c1"], [], "advanced", "b2"),
              _r(3, ["c1"], [], "advanced", "b3")]
    ok("#93: 3 advancing rounds with distinct blockers halt",
       decide_route(moving, 3) == "ROUTE HALT moving-residual")
    ok("#93: a repeated blocker never fires",
       decide_route([moving[0], moving[1], _r(3, ["c1"], [], "advanced", "b1")], 3) != "ROUTE HALT moving-residual")
    ok("#93: a closed round in the window never fires",
       decide_route([moving[0], moving[1], _r(3, ["c1"], [], "closed", None)], 3) != "ROUTE HALT moving-residual")
    ok("#93: default N is 3, two advancing rounds do not fire",
       decide_route(moving[:2], 3) != "ROUTE HALT moving-residual")
    ok("#93: N=2 fires on two",
       decide_route(moving[:2], 2) == "ROUTE HALT moving-residual")
    both = moving[:2] + [_r(3, [], [("c1", "a2"), ("c2", "a2")], "advanced", "b3")]
    ok("#93 wins over #78 when both fire", decide_route(both, 3) == "ROUTE HALT moving-residual")

    with tempfile.TemporaryDirectory() as raw:
        f = Path(raw) / "rounds.json"
        rows = [_r(1, ["c1"], [])]
        f.write_text(json.dumps(rows))
        ok("read_rounds parses the rounds file", read_rounds(str(f)) == rows)
        try:
            (Path(raw) / "not-a-list.json").write_text(json.dumps({"a": 1}))
            read_rounds(str(Path(raw) / "not-a-list.json"))
            ok("read_rounds refuses a non-list", False)
        except ValueError:
            ok("read_rounds refuses a non-list", True)

    cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as raw:
        try:
            os.chdir(raw)
            run = run_record.open_run("arbeitsplan", "t-rounds")
            (run.dir / "workflow.json").write_text(json.dumps({"runId": "t-rounds", "problem": {"acceptance": []}}))
            run.append({"trace_id": "t-rounds", "span_id": "t-rounds.1", "parent_span_id": "t-rounds.root",
                       "span": "phase referee-w1", "node_id": "referee-w1", "status": "opened"})
            (run.dir / "referee" / "referee-w1").mkdir(parents=True)
            (run.dir / "referee" / "referee-w1" / "c1.json").write_text(json.dumps(
                {"candidateId": "c1", "verdict": "rejected",
                 "perCriterion": [{"id": "a2", "met": False, "evidence": "e"}]}))
            run.append({"trace_id": "t-rounds", "span_id": "t-rounds.2", "parent_span_id": "t-rounds.root",
                       "span": "phase referee-w1", "node_id": "referee-w1", "status": "closed"})
            rows2 = _run_rounds("t-rounds")
            ok("_run_rounds reads a phase-namespaced referee directory",
               len(rows2) == 1 and rows2[0]["rejections"] == [{"candidateId": "c1", "criterion": "a2", "note": "e"}])

            (run.dir / "phases").mkdir(parents=True, exist_ok=True)
            (run.dir / "phases" / "adjudicate.json").write_text(json.dumps(
                {"verdict": "hold", "round": {"outcome": "advanced", "blocking": "b1"}}))
            run.append({"trace_id": "t-rounds", "span_id": "t-rounds.3", "parent_span_id": "t-rounds.root",
                       "span": "phase adjudicate", "node_id": "adjudicate", "status": "closed"})
            rows3 = _run_rounds("t-rounds")
            ok("the adjudicate phase's `round` becomes the preceding referee round's judge",
               rows3[0]["judge"] == {"outcome": "advanced", "blocking": "b1"})

            child = run_record.open_run("arbeitsplan", "t-rounds-2")
            (child.dir / "workflow.json").write_text(json.dumps(
                {"runId": "t-rounds-2", "supersedes": "t-rounds", "problem": {"acceptance": []}}))
            chain = _supersedes_chain("t-rounds-2")
            ok("the supersedes chain runs oldest-first", chain == ["t-rounds", "t-rounds-2"])

            # A cycle must terminate and never list a run twice.
            a = run_record.open_run("arbeitsplan", "t-cyc-a")
            (a.dir / "workflow.json").write_text(json.dumps({"runId": "t-cyc-a", "supersedes": "t-cyc-b"}))
            b = run_record.open_run("arbeitsplan", "t-cyc-b")
            (b.dir / "workflow.json").write_text(json.dumps({"runId": "t-cyc-b", "supersedes": "t-cyc-a"}))
            cyc = _supersedes_chain("t-cyc-a")
            ok("a supersedes cycle terminates without listing a run twice", len(cyc) == len(set(cyc)))
        finally:
            os.chdir(cwd)

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("rounds selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="rounds.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--selftest", action="store_true", help="run the planted-case selftest")
    sub = parser.add_subparsers(dest="cmd")

    r = sub.add_parser("record", help="rebuild one round per referee phase across the supersedes chain")
    r.add_argument("--run", required=True)

    d = sub.add_parser("decide", help="rule on a rounds file: CONTINUE, SYNTHESIZE, or HALT")
    d.add_argument("--rounds", required=True, help="a JSON list of rounds, e.g. from `record`")
    d.add_argument("--max-advancing-rounds", type=int, default=None,
                   help="#93's N; default the spec's roundBreaker.maxAdvancingRounds, else 3")
    d.add_argument("--spec", help="workflow.json, read for roundBreaker.maxAdvancingRounds")

    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.cmd == "record":
        return cmd_record(args.run)
    if args.cmd == "decide":
        return cmd_decide(args)
    parser.error("a subcommand (record|decide) or --selftest is required")
    return 2  # unreachable; parser.error exits


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
