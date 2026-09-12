#!/usr/bin/env python3
"""The delegation ledger: append-only JSONL, depth cap, cycle detection.

usage: delegation.py [-h] {check,append,show,selftest} ...

WHY JSONL AND NOT JSON. The ledger is written by agents running in parallel --
that is the whole premise of this plugin. A single JSON document would need
read-modify-write, which races: two writers read the same array, each appends
its own record, and one of them disappears. An O_APPEND write of one line is
atomic under PIPE_BUF, so parallel writers cannot lose each other's records.
The same argument made the dispatch ledger one-file-per-signature.

The PIPE_BUF guarantee has a size: POSIX floors it at 512 bytes and Linux sets
it at 4096. A record longer than that can interleave. So MAX_RECORD_BYTES is
enforced on write and a long branch list belongs in the spec, not here.

WHY BOTH A DEPTH CAP AND CYCLE DETECTION. They catch different things and
neither subsumes the other:

  depth cap   bounds an honest but runaway chain: A -> B -> C -> D.
  cycle       catches A -> B -> A, which is depth 2 and would sail under any
              cap, burning the full budget on a loop the cap never sees.

A design with only a cap treats a two-node infinite loop as legal until it has
paid three levels of fan-out for it.

Exit: 0 allowed/clean, 1 denied/invalid, 2 bad input.

STDLIB ONLY -- it must run under a bare system python3, and the hook imports it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

MAX_DEPTH = 3
MAX_RECORD_BYTES = 4096
VALID_PATTERNS = {"serial", "parallel"}
VALID_STATUS = {"pending", "in_progress", "completed", "failed", "denied"}
VALID_STRATEGY = {"wait_all", "first_success", "any"}
VALID_COMBINE = {"concat", "select_winner", "merge_fields"}

REQUIRED = ("id", "runId", "source", "target", "pattern", "status", "timestamp")


class LedgerError(ValueError):
    """Raised for a malformed record. The message names the offending key."""


def validate_record(rec: dict) -> list:
    errors = []
    if not isinstance(rec, dict):
        return ["record is not an object"]
    for key in REQUIRED:
        if not rec.get(key):
            errors.append(f"{key}: missing")
    if rec.get("pattern") not in VALID_PATTERNS and rec.get("pattern"):
        errors.append(f"pattern: must be one of {sorted(VALID_PATTERNS)}")
    if rec.get("status") not in VALID_STATUS and rec.get("status"):
        errors.append(f"status: must be one of {sorted(VALID_STATUS)}")
    depth = rec.get("depth")
    if not isinstance(depth, int) or depth < 0:
        errors.append("depth: must be a non-negative integer")
    if rec.get("pattern") == "serial" and not isinstance(rec.get("chain"), list):
        errors.append("chain: a serial delegation must carry a chain list")
    if rec.get("pattern") == "parallel" and not isinstance(rec.get("branches"), list):
        errors.append("branches: a parallel delegation must carry a branches list")
    merge = rec.get("merge")
    if merge is not None:
        if not isinstance(merge, dict):
            errors.append("merge: must be an object or null")
        else:
            if merge.get("strategy") not in VALID_STRATEGY:
                errors.append(f"merge.strategy: must be one of {sorted(VALID_STRATEGY)}")
            if merge.get("combine") not in VALID_COMBINE:
                errors.append(f"merge.combine: must be one of {sorted(VALID_COMBINE)}")
            if not merge.get("at"):
                errors.append("merge.at: missing -- a merge with no site cannot be performed")
    size = len(json.dumps(rec, separators=(",", ":")).encode())
    if size > MAX_RECORD_BYTES:
        errors.append(
            f"record is {size} bytes, over the {MAX_RECORD_BYTES}-byte cap; beyond "
            "PIPE_BUF an append is no longer atomic and parallel writers can "
            "interleave. Put long branch lists in the spec, not the ledger"
        )
    return errors


def read_ledger(path) -> list:
    """Every well-formed record. A malformed LINE is skipped, not fatal -- a
    torn write from a crashed run must not make the whole ledger unreadable,
    and the guard's job is to bound delegation, not to audit file integrity."""
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(rec, dict) and rec.get("id"):
            out.append(rec)
    return out


def plugin_of(name: str) -> str:
    """The PLUGIN a delegation target names.

    A ledger record stores a plugin ("compass"); a live dispatch target is a
    `plugin:skill` id ("compass:compass-explore-branches"). Comparing the two
    raw strings never matches, so the cycle check silently passed everything --
    a comparison that looks right, never fires, and reports success.

    Cycles are a property of PLUGINS, not of individual skills: arbeitsplan
    calling two different compass skills is not a loop, but arbeitsplan ->
    compass -> arbeitsplan is, whichever skills those hops name.
    """
    if not isinstance(name, str):
        return ""
    return name.split(":", 1)[0].strip()


def ancestors(records: list, parent_id) -> list:
    """The chain from `parent_id` up to the root, nearest first.

    Bounded by len(records) rather than by a `while True`: a ledger that
    already contains a parent cycle (from a crash, a hand edit, a bug in an
    earlier version) would otherwise hang the hook, and a hook that hangs is a
    hook that gets disabled.
    """
    by_id = {r["id"]: r for r in records}
    chain, seen, cur = [], set(), parent_id
    for _ in range(len(records) + 1):
        if not cur or cur in seen or cur not in by_id:
            break
        seen.add(cur)
        rec = by_id[cur]
        chain.append(rec)
        cur = rec.get("parent")
    return chain


def check(records: list, source: str, target: str, parent_id=None) -> tuple:
    """(allowed, depth, reason). Reason is None when allowed."""
    chain = ancestors(records, parent_id)
    depth = len(chain)

    # Cycle first: it is the cheaper failure to explain and the one a depth cap
    # would let run longest.
    seen = {plugin_of(r.get("target")) for r in chain} | {plugin_of(r.get("source")) for r in chain}
    seen.discard("")
    if plugin_of(target) in seen:
        path = " -> ".join(
            [r.get("source", "?") for r in reversed(chain)] + [source, target]
        )
        return (
            False,
            depth,
            f"delegation cycle: {target!r} already appears in its own ancestor "
            f"chain ({path}). A cycle is not a deep chain -- it never terminates, "
            f"so the depth cap would only decide how much it costs first.",
        )

    if depth >= MAX_DEPTH:
        path = " -> ".join([r.get("source", "?") for r in reversed(chain)] + [source, target])
        return (
            False,
            depth,
            f"delegation depth {depth} would become {depth + 1}, over the cap of "
            f"{MAX_DEPTH} ({path}). Depth is capped because each level multiplies "
            f"the fan-out below it; widen at one level instead of nesting another.",
        )

    return (True, depth, None)


def append_record(path, rec: dict) -> None:
    """One atomic O_APPEND write of one line."""
    errors = validate_record(rec)
    if errors:
        raise LedgerError("; ".join(errors))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n"
    fd = os.open(str(p), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode())
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------


def _rec(rid, source, target, parent=None, depth=0, **over):
    r = {
        "id": rid, "runId": "ap-t-1", "parent": parent, "depth": depth,
        "source": source, "target": target, "pattern": "serial",
        "chain": [source, target], "merge": None, "status": "completed",
        "timestamp": "2026-09-12T09:00:00Z",
    }
    r.update(over)
    return r


def selftest() -> int:
    fails = []

    def ok(name, cond, extra=""):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + extra}")
        if not cond:
            fails.append(name)

    # --- depth ---------------------------------------------------------
    a = _rec("d1", "arbeitsplan", "compass", None, 0)
    b = _rec("d2", "compass", "andon", "d1", 1)
    c = _rec("d3", "andon", "lehre", "d2", 2)
    led = [a, b, c]

    allowed, depth, why = check([], "arbeitsplan", "compass", None)
    ok("DEPTH root delegation allowed", allowed and depth == 0, str(why))
    allowed, depth, why = check([a], "compass", "andon", "d1")
    ok("DEPTH level 1 allowed", allowed and depth == 1, str(why))
    allowed, depth, why = check([a, b], "andon", "lehre", "d2")
    ok("DEPTH level 2 allowed", allowed and depth == 2, str(why))
    allowed, depth, why = check(led, "lehre", "cupertino", "d3")
    ok("DEPTH level 3 DENIED (cap)", (not allowed) and "depth" in (why or ""), str(why))

    # --- cycle ---------------------------------------------------------
    allowed, depth, why = check([a], "compass", "arbeitsplan", "d1")
    ok("CYCLE A->B->A denied at depth 1", (not allowed) and "cycle" in (why or ""), str(why))
    allowed, _, why = check([a, b], "andon", "compass", "d2")
    ok("CYCLE A->B->C->B denied", (not allowed) and "cycle" in (why or ""), str(why))
    allowed, _, why = check([a, b], "andon", "matrize", "d2")
    ok("CYCLE unrelated target still allowed", allowed, str(why))

    # A cycle must be caught BELOW the cap, or the cap is doing the work.
    allowed, depth, why = check([a], "compass", "arbeitsplan", "d1")
    ok("CYCLE caught below the cap, not by it", (not allowed) and depth < MAX_DEPTH and "cycle" in (why or ""))

    # --- plugin:skill vs plugin normalization ---------------------------
    # A ledger stores "compass"; a live dispatch target is
    # "compass:compass-explore-branches". Comparing them raw never matches, and
    # the cycle check silently passed everything. Found by the guard's own
    # calibration, not by reading this file.
    allowed, _, why = check([a], "compass", "arbeitsplan:candidate-builder", "d1")
    ok("NORMALIZE plugin:skill target still detects the cycle",
       (not allowed) and "cycle" in (why or ""), str(why))
    allowed, _, why = check([a, b], "andon", "compass:compass-solve", "d2")
    ok("NORMALIZE a different SKILL of a seen plugin is still a cycle",
       (not allowed) and "cycle" in (why or ""), str(why))
    allowed, _, why = check([a, b], "andon", "matrize:matrize-decode", "d2")
    ok("NORMALIZE an unseen plugin's skill is allowed", allowed, str(why))
    ok("plugin_of splits on the first colon only",
       plugin_of("a:b:c") == "a" and plugin_of("bare") == "bare" and plugin_of(None) == "")

    # --- a corrupt ledger must not hang the guard ----------------------
    loop = [_rec("x", "a", "b", "y", 1), _rec("y", "b", "a", "x", 1)]
    try:
        ancestors(loop, "x")
        ok("corrupt parent cycle terminates instead of hanging", True)
    except RecursionError:
        ok("corrupt parent cycle terminates instead of hanging", False, "recursed")

    # --- record validation ---------------------------------------------
    ok("valid record passes", not validate_record(a))
    ok("missing target rejected", validate_record(_rec("d", "s", "")))
    ok("bad pattern rejected", validate_record(_rec("d", "s", "t", pattern="sideways")))
    ok("parallel without branches rejected",
       any("branches" in e for e in validate_record(_rec("d", "s", "t", pattern="parallel", chain=None))))
    ok("merge without a site rejected",
       any("merge.at" in e for e in validate_record(
           _rec("d", "s", "t", merge={"strategy": "wait_all", "combine": "concat"}))))
    big = _rec("d", "s", "t", branches=["b" * 200] * 40, pattern="parallel")
    ok("oversize record rejected (PIPE_BUF)", any("PIPE_BUF" in e for e in validate_record(big)))

    # --- append is real and atomic-shaped -------------------------------
    import tempfile
    with tempfile.TemporaryDirectory() as raw:
        f = Path(raw) / "delegation.jsonl"
        append_record(f, a)
        append_record(f, b)
        back = read_ledger(f)
        ok("append then read round-trips", [r["id"] for r in back] == ["d1", "d2"])
        f.write_text(f.read_text() + "{ this is not json\n")
        back = read_ledger(f)
        ok("a torn line is skipped, not fatal", [r["id"] for r in back] == ["d1", "d2"])

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"selftest passed (depth cap {MAX_DEPTH}, cycle detection, record schema, append)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="delegation.py",
        description="Append-only delegation ledger with a depth cap and cycle detection.",
        epilog="exit 0 allowed/clean, 1 denied/invalid, 2 bad input",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="would this delegation be allowed?")
    c.add_argument("--ledger", required=True)
    c.add_argument("--source", required=True)
    c.add_argument("--target", required=True)
    c.add_argument("--parent", default=None)

    ap = sub.add_parser("append", help="append one record (JSON on stdin or --record)")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--record", default=None)

    sh = sub.add_parser("show", help="print the ledger as a chain summary")
    sh.add_argument("--ledger", required=True)

    sub.add_parser("selftest", help="planted-defect selftest")

    args = parser.parse_args(argv)

    if args.cmd == "selftest":
        return selftest()

    if args.cmd == "check":
        allowed, depth, why = check(read_ledger(args.ledger), args.source, args.target, args.parent)
        if allowed:
            print(f"allowed (depth {depth} -> {depth + 1} of {MAX_DEPTH})")
            return 0
        print(why, file=sys.stderr)
        return 1

    if args.cmd == "append":
        raw = args.record if args.record else sys.stdin.read()
        try:
            rec = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"record is not valid JSON: {exc}", file=sys.stderr)
            return 2
        try:
            append_record(args.ledger, rec)
        except LedgerError as exc:
            print(f"REJECTED {exc}", file=sys.stderr)
            return 1
        print(f"appended {rec['id']} to {args.ledger}")
        return 0

    records = read_ledger(args.ledger)
    print(f"{len(records)} record(s) in {args.ledger}")
    for r in records:
        chain = ancestors(records, r.get("parent"))
        print(f"  {r['id']:<8} depth {len(chain)}  {r.get('source')} -> {r.get('target')}  "
              f"[{r.get('pattern')}/{r.get('status')}]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
