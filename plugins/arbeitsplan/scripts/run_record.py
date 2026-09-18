#!/usr/bin/env python3
"""The execution record of a plugin run: one append-only log beside an immutable plan.

usage: run_record.py {status,append,selftest} ...

A plugin's PLAN is a file its compiler writes once and nothing marks up. Its
EXECUTION was, until this module, a chat transcript: a halted run was
indistinguishable from an abandoned one, and no run could be resumed, only re-run.
Three of four external tools surveyed converged on the same cure, and it is not
ticking checkboxes in the plan -- the one tool that mandated checkboxes had no
executor that ever ticked them. The plan stays immutable input; a separate,
append-only record is the execution; resume reads the record.

    analysis/<plugin>/<runId>/run.jsonl        this module's file
      line 1   {"kind": "header", "plugin", "run_id", "schema"}
      line 2+  one event per line

The header names its own run, so a stale sibling is structurally unreadable as
yours -- open_run() refuses a directory whose header names another run.

EVENTS are span-shaped, without an OpenTelemetry dependency: trace_id, span_id,
parent_span_id, span (a GenAI-convention name: `plan <agent>`, `invoke_agent
<agentType>`, `execute_tool <check>`, `evaluation`, `phase <id>`, `halt`),
node_id (the plan node the event acted on), and status from a closed set. An
exporter later is a mapping, not a migration. No SDK, no collector: the
conventions are at Development maturity, and nothing here needs one.

STATUS is also a closed set, and four of its values are a record-level
reasoning vocabulary: proposed | accepted | refuted | doubt. A losing candidate
is `refuted` and stays in the record even after its worktree is deleted. A
`doubt` carries `evidence` and `resolves_if`. The rest are lifecycle: opened,
closed, pending, halted, unmeasured.

WRITES
  append()   one os.write() of one line opened O_APPEND, refused past 4096
             bytes. Parallel writers cannot interleave a record they cannot
             split; a payload that needs more belongs in a file referenced by
             path.
  refuse()   FAILED-<stamp>.json, O_CREAT|O_EXCL -- nacharbeit's rule: a run
             that was refused leaves a trace, and cannot be rendered as fresh.
  finish()   complete.json, written LAST via os.replace -- the completeness
             sentinel. A record without it is unfinished, whatever it says.

STDLIB ONLY. Vendored into plugins by `.rrt.toml` artifact_targets; edit this
copy, then `rrt artifacts --regenerate`, never a vendored one.

Exit: 0 ok, 1 refused/failed, 2 usage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

SCHEMA = 1
MAX_LINE = 4096
STATUSES = frozenset({
    "proposed", "accepted", "refuted", "doubt",
    "opened", "closed", "pending", "halted", "unmeasured",
})
REQUIRED = ("trace_id", "span_id", "parent_span_id", "span", "node_id", "status")


class RecordError(Exception):
    """A record that cannot be trusted: wrong run, malformed line, bad event."""


# The declared floor, checked at import rather than discovered at the first
# write -- which would be the moment a halt is being recorded. These scripts run
# under whatever python3 is on PATH, and a stock macOS ships 3.9.
MIN_PYTHON = (3, 11)
if sys.version_info < MIN_PYTHON:
    raise SystemExit(f"run_record needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}; this is "
                     f"{sys.version.split()[0]} ({sys.executable}). Put a newer python3 first on PATH.")
UTC = dt.UTC


def _now() -> str:
    return dt.datetime.now(UTC).isoformat(timespec="seconds")


class Run:
    def __init__(self, directory: Path, plugin: str, run_id: str) -> None:
        self.dir = directory
        self.plugin = plugin
        self.run_id = run_id
        self.log = directory / "run.jsonl"

    # -- writes ------------------------------------------------------------
    def _write_line(self, obj: dict) -> None:
        line = (json.dumps(obj, separators=(",", ":"), sort_keys=True) + "\n").encode()
        if len(line) > MAX_LINE:
            raise RecordError(
                f"event is {len(line)} bytes; the limit is {MAX_LINE} so one write() stays "
                "atomic. Write the payload to a file and reference it by path.")
        # os.open, not Path.open: O_APPEND on the descriptor is the whole point.
        fd = os.open(self.log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)

    def append(self, event: dict) -> dict:
        missing = [k for k in REQUIRED if not event.get(k)]
        if missing:
            raise RecordError(f"event lacks {missing}; every record is span-shaped")
        if event["status"] not in STATUSES:
            raise RecordError(f"status {event['status']!r} is not one of {sorted(STATUSES)}")
        if event["trace_id"] != self.run_id:
            raise RecordError(f"trace_id {event['trace_id']!r} is not this run ({self.run_id!r})")
        if event["status"] == "doubt" and not (event.get("detail") or {}).get("resolves_if"):
            raise RecordError("a doubt carries detail.resolves_if; an unresolvable doubt is a shrug")
        rec = {"kind": "event", "at": event.get("at") or _now(), **event}
        self._write_line(rec)
        return rec

    def halt(self, reason: str, node_id: str) -> dict:
        if not reason or not reason.strip():
            raise RecordError("a halt needs a specific reason; an empty one is an absence")
        return self.append({
            "trace_id": self.run_id, "span_id": f"{self.run_id}.halt.{node_id}",
            "parent_span_id": f"{self.run_id}.root", "span": "halt", "node_id": node_id,
            "status": "halted", "detail": {"reason": reason},
        })

    def refuse(self, reason: str) -> Path:
        stamp = dt.datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = self.dir / f"FAILED-{stamp}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"run_id": self.run_id, "reason": reason, "at": _now()}, fh, indent=2)
        return path

    def finish(self, summary: dict | None = None) -> Path:
        st = self.status()
        if st["open_phases"]:
            raise RecordError(f"cannot finish with open phases {st['open_phases']}; "
                              "a phase that ends without saying how is not finished")
        target = self.dir / "complete.json"
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".complete.")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"run_id": self.run_id, "at": _now(), **(summary or {})}, fh, indent=2)
        Path(tmp).replace(target)  # os.replace: atomic, and last
        return target

    # -- reads -------------------------------------------------------------
    def events(self) -> list:
        out = []
        for n, raw in enumerate(self.log.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
            except ValueError as exc:
                raise RecordError(f"{self.log}:{n} is not JSON ({exc}); the record is damaged") from exc
            if obj.get("kind") == "event":
                out.append(obj)
        return out

    def status(self) -> dict:
        """What happened, derived from the log every time -- never stored.

        A stored counter is a claim the next reader cannot check; a derived one is
        re-computed from the events that justify it.
        """
        evs = self.events()
        opened, closed, order = set(), set(), []
        counts: dict = {}
        halted = None
        for e in evs:
            counts[e["status"]] = counts.get(e["status"], 0) + 1
            if e["span"].startswith("phase "):
                if e["status"] == "opened":
                    opened.add(e["node_id"])
                    order.append(e["node_id"])
                elif e["status"] == "closed":
                    closed.add(e["node_id"])
            if e["status"] == "halted":
                halted = {"node_id": e["node_id"], "reason": (e.get("detail") or {}).get("reason")}
            if e["status"] == "pending":
                halted = None  # a plan-node stop is a pause, not a failure
        pending = [e["node_id"] for e in evs if e["status"] == "pending"]
        last_pending = pending[-1] if pending else None
        if last_pending and any(e["node_id"] == last_pending and e["status"] == "closed" for e in evs):
            last_pending = None
        finished = (self.dir / "complete.json").is_file()
        failed = sorted(p.name for p in self.dir.glob("FAILED-*.json"))
        open_phases = [p for p in order if p not in closed]
        if finished:
            nxt = {"kind": "done"}
        elif failed:
            nxt = {"kind": "inspect-refusal", "file": failed[-1]}
        elif halted:
            nxt = {"kind": "inspect-halt", "node_id": halted["node_id"]}
        elif last_pending:
            nxt = {"kind": "run-plan-node", "node_id": last_pending}
        elif open_phases:
            nxt = {"kind": "resume", "node_id": open_phases[0]}
        else:
            nxt = {"kind": "continue"}
        return {
            "run_id": self.run_id, "plugin": self.plugin, "events": len(evs),
            "counts": counts, "closed_phases": [p for p in order if p in closed],
            "open_phases": open_phases, "halted": halted, "pending_plan_node": last_pending,
            "failed": failed, "finished": finished, "next": nxt,
        }


def run_dir(plugin: str, run_id: str, root: Path | None = None) -> Path:
    """Resolved in code, never by convention, so two writers cannot drift apart."""
    for label, value in (("plugin", plugin), ("run_id", run_id)):
        if not value or "/" in value or value in (".", "..") or ".." in value:
            raise RecordError(f"{label} {value!r} is not a safe path component")
    return (root or Path.cwd()) / "analysis" / plugin / run_id


def open_run(plugin: str, run_id: str, root: Path | None = None, directory: Path | None = None) -> Run:
    """Open (creating if needed) one run's record.

    `directory` places the record beside a plugin's existing per-run state --
    cli-scaffold's report directory, compass's `.compass/runs/<id>/` -- instead of
    under analysis/<plugin>/, so one run is never scattered across two trees. The
    run id is still validated, and the header still refuses a sibling's record.
    """
    d = run_dir(plugin, run_id, root)
    if directory is not None:
        d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    run = Run(d, plugin, run_id)
    header = {"kind": "header", "plugin": plugin, "run_id": run_id, "schema": SCHEMA}
    if not run.log.exists():
        try:
            fd = os.open(run.log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            pass  # another writer created it first; verify below like any reader
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(header, sort_keys=True) + "\n")
    first = run.log.read_text(encoding="utf-8").split("\n", 1)[0]
    try:
        got = json.loads(first)
    except ValueError as exc:
        raise RecordError(f"{run.log} has no header line") from exc
    if got.get("kind") != "header" or got.get("run_id") != run_id or got.get("plugin") != plugin:
        raise RecordError(f"{run.log} belongs to {got.get('plugin')}/{got.get('run_id')}, "
                          f"not {plugin}/{run_id}; a sibling's record is never read as yours")
    return run


# -- selftest ---------------------------------------------------------------
def _ev(run_id: str, span: str, node: str, status: str, **kw) -> dict:
    return {"trace_id": run_id, "span_id": f"{run_id}.{span}.{node}.{status}",
            "parent_span_id": f"{run_id}.root", "span": span, "node_id": node,
            "status": status, **kw}


def selftest() -> int:
    fails: list = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    def raises(fn) -> bool:
        try:
            fn()
        except RecordError:
            return True
        return False

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        run = open_run("demo", "r-1", root)
        ok("header names its own run", json.loads(run.log.read_text().splitlines()[0])["run_id"] == "r-1")
        ok("a sibling's record is refused", raises(lambda: open_run("demo", "r-1", root) and
            (run.log.write_text('{"kind":"header","plugin":"demo","run_id":"other"}\n'),
             open_run("demo", "r-1", root))))
        run.log.write_text(json.dumps({"kind": "header", "plugin": "demo", "run_id": "r-1", "schema": 1}) + "\n")
        ok("an unsafe run id is refused", raises(lambda: run_dir("demo", "../x", root)))
        ok("an event missing span ids is refused", raises(lambda: run.append({"status": "opened"})))
        ok("an unknown status is refused", raises(lambda: run.append(_ev("r-1", "phase build", "build", "maybe"))))
        ok("an event for another run is refused", raises(lambda: run.append(_ev("r-2", "phase build", "build", "opened"))))
        ok("a doubt without resolves_if is refused", raises(lambda: run.append(_ev("r-1", "evaluation", "build", "doubt"))))
        ok("an oversized event is refused", raises(lambda: run.append(_ev("r-1", "evaluation", "b", "accepted", detail={"x": "y" * 5000}))))
        ok("a halt with no reason is refused", raises(lambda: run.halt("  ", "build")))

        run.append(_ev("r-1", "phase build", "build", "opened"))
        run.append(_ev("r-1", "invoke_agent a:b", "build:c1", "refuted"))
        st = run.status()
        ok("an opened phase with no close is open", st["open_phases"] == ["build"])
        ok("next is resume from the open phase", st["next"] == {"kind": "resume", "node_id": "build"})
        ok("finish refuses while a phase is open", raises(run.finish))
        ok("the refuted candidate stays in the record", st["counts"].get("refuted") == 1)
        run.append(_ev("r-1", "phase build", "build", "closed"))
        run.append(_ev("r-1", "plan_node", "contract", "pending"))
        st = run.status()
        ok("a plan-node stop reads as run-plan-node", st["next"] == {"kind": "run-plan-node", "node_id": "contract"})
        run.halt("CONTRACT PROBLEM: 1/3 usable", "referee")
        st = run.status()
        ok("a halt is persisted with its reason", st["halted"] == {"node_id": "referee", "reason": "CONTRACT PROBLEM: 1/3 usable"})
        ok("next after a halt is to inspect it", st["next"]["kind"] == "inspect-halt")
        failed = run.refuse("spec edited after compile")
        ok("refuse leaves FAILED-<stamp>", failed.is_file() and run.status()["failed"] == [failed.name])

        run2 = open_run("demo", "r-2", root)
        run2.append(_ev("r-2", "phase x", "x", "opened"))
        run2.append(_ev("r-2", "phase x", "x", "closed"))
        run2.finish({"landed": "c1"})
        ok("finish writes the sentinel last", run2.status()["finished"] and run2.status()["next"] == {"kind": "done"})
        with run2.log.open("a", encoding="utf-8") as fh:
            fh.write("{not json\n")
        ok("a damaged line is an error, not a skip", raises(run2.status))

        # Parallel appenders: 8 processes x 50 lines must yield 400 whole records.
        placed = open_run("demo", "r-4", root, directory=root / ".demo-reports" / "x")
        ok("directory places the record beside existing state", placed.log == root / ".demo-reports" / "x" / "run.jsonl")
        ok("a placed record still refuses another run's id", raises(lambda: open_run("demo", "r-5", root, directory=root / ".demo-reports" / "x")))
        ok("a placed record still validates its run id", raises(lambda: open_run("demo", "../x", root, directory=root / "y")))

        run3 = open_run("demo", "r-3", root)
        # Values arrive through argv, never interpolated into the source: printf-style
        # `%` into code is the TypeError-then-stale-output defect this repo tabled.
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import run_record as r; "
                "run = r.open_run('demo', 'r-3', r.Path(sys.argv[2])); "
                "[run.append({'trace_id': 'r-3', 'span_id': f'r-3.{i}', 'parent_span_id': 'r-3.root', "
                "'span': 'evaluation', 'node_id': 'n', 'status': 'accepted', 'detail': {'pad': 'x' * 900}}) "
                "for i in range(50)]")
        import subprocess
        here = str(Path(__file__).resolve().parent)
        procs = [subprocess.Popen([sys.executable, "-c", code, here, str(root)]) for _ in range(8)]
        rcs = [p.wait() for p in procs]
        ok("8 parallel appenders produce 400 whole records",
           rcs == [0] * 8 and len(run3.events()) == 400)

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("run_record selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="run_record.py", description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="print what the record says happened, and the next move")
    s.add_argument("--plugin", required=True)
    s.add_argument("--run", required=True)
    a = sub.add_parser("append", help="append one span-shaped event (JSON on stdin)")
    a.add_argument("--plugin", required=True)
    a.add_argument("--run", required=True)
    sub.add_parser("selftest", help="planted-defect selftest, including parallel appenders")
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "status":
            d = run_dir(args.plugin, args.run)
            if not (d / "run.jsonl").is_file():
                print(f"no record at {d}/run.jsonl", file=sys.stderr)
                return 1
            print(json.dumps(open_run(args.plugin, args.run).status(), indent=2))
            return 0
        open_run(args.plugin, args.run).append(json.loads(sys.stdin.read()))
        return 0
    except (RecordError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
