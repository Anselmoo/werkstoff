#!/usr/bin/env python3
"""Run a project's pipeline once under a tracer and record how each result was produced.

usage:
  spur_trace.py detect [--root DIR]
  spur_trace.py run [--root DIR] [--out DIR] [--run-id ID] [--keep-fragments]
                    [--calls chrome:FILE | --calls cpuprofile:PATH]
                    [--reads GLOB]... [--writes GLOB]... -- COMMAND [ARG...]
  spur_trace.py verify RUN_DIR [--root DIR]
  spur_trace.py prov TRACE_JSON [--out FILE]

`run` executes COMMAND once. Every Python process it starts -- the command itself and
every Python child that inherits the environment -- loads spur_boot/sitecustomize.py,
which records that process's own function calls (sys.monitoring) and file I/O
(sys.addaudithook) without rewriting a line of the traced code. Each process is one
STEP. A spawned process that left no record (a `cp`, a shell, a Python started with
-I) is still a step: an untraced one, named as such.

It writes, under OUT/RUN_ID/ (default analysis/spur/<UTC timestamp>/):
  trace.json        the run record (schema spur/trace/1)
  prov.json         the same run as W3C PROV-JSON
  spur-report.html  one static page; loads nothing from the network

The hash-chain rule: an input is hashed when a step first opens it for reading; an
output is hashed when its step exits, and again before each child it spawns. A file
rewritten in place gets a new version `path@n` per commit. A consumer's input is
checked against the latest version committed BEFORE it read the file:
  verified    the hashes match
  broken      they differ -- something changed the file between producer and consumer
  unverified  no traced producer, yet the file changed during the run (an untraced
              step wrote it), or the input could not be hashed
  source      no producer, and the file predates the run: an external input
Unverified is never a pass.

Exit: the command's own exit code when it failed; otherwise 0 chain verified,
3 chain broken, 4 chain incomplete or empty (nothing verifiable), 2 usage or
instrument error. `verify` exits 0 when every final output on disk still matches its
recorded hash, 3 when one drifted.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

MIN_PYTHON = (3, 11)

if sys.version_info < MIN_PYTHON:
    sys.exit(f"spur_trace.py needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+, found {sys.version.split()[0]}")

HERE = Path(__file__).resolve().parent
BOOT = HERE / "spur_boot"
SCHEMA = "spur/trace/1"
SPUR_NS = "https://github.com/Anselmoo/werkstoff/tree/main/plugins/spur#"

EXIT_VERIFIED, EXIT_USAGE, EXIT_BROKEN, EXIT_INCOMPLETE = 0, 2, 3, 4

STACK_MARKERS = {
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"),
    "rust": ("Cargo.toml",),
    "node": ("package.json",),
    "go": ("go.mod",),
}
ADAPTER = {
    "python": "built in: sys.monitoring calls + audit-hook file I/O (Python 3.12+ for calls)",
    "rust": "--calls chrome:FILE from tracing-chrome; file I/O only via --reads/--writes",
    "node": "--calls cpuprofile:DIR from node --cpu-prof (sampled); file I/O only via --reads/--writes",
    "go": "not built: runtime/trace writes Go's own binary format, which spur cannot read",
}


# -- time and redaction -------------------------------------------------------------

def iso(ns: int | None) -> str | None:
    if ns is None:
        return None
    return datetime.datetime.fromtimestamp(ns / 1e9, tz=datetime.UTC).isoformat(timespec="milliseconds")


class Redactor:
    """Paths under the project root become relative; the home directory becomes `~`."""

    def __init__(self, root: Path) -> None:
        self.root = str(root)
        self.home = str(Path.home())

    def path(self, p: str) -> str:
        if p == self.root:
            return "."
        if p.startswith(self.root + os.sep):
            return Path(p[len(self.root) + 1:]).as_posix()
        return self.text(p)

    def text(self, s: str) -> str:
        s = s.replace(self.root + os.sep, "")
        if self.home and self.home != os.sep:
            s = s.replace(self.home, "~")
        return s

    def argv(self, argv: list) -> list:
        """The command as typed: an absolute interpreter path shrinks to its name."""
        out = [self.text(str(a)) for a in argv]
        if out and Path(str(argv[0])).is_absolute() and " " not in str(argv[0]):
            out[0] = Path(str(argv[0])).name
        return out


# -- importers for adapters that are not this process's own -------------------------

def _aggregate(intervals: list[dict]) -> list[dict]:
    """Nest [start, end) intervals (one thread) into a calling-context tree."""
    root: dict = {"children": {}}
    stack: list[tuple[dict, float]] = []
    for iv in sorted(intervals, key=lambda x: (x["start"], -x["end"])):
        while stack and iv["start"] >= stack[-1][1]:
            stack.pop()
        parent = stack[-1][0] if stack else root
        key = (iv["fn"], iv["file"], iv["line"])
        node = parent["children"].get(key)
        if node is None:
            node = parent["children"][key] = {"key": key, "calls": 0, "ns": 0, "children": {}}
        node["calls"] += 1
        node["ns"] += int((iv["end"] - iv["start"]) * 1000)
        stack.append((node, iv["end"]))
    return _flatten(root)


def _flatten(node: dict) -> list[dict]:
    out = []
    for child in node["children"].values():
        fn, file, line = child["key"]
        out.append({"fn": fn, "file": file, "line": line, "calls": child["calls"],
                    "ns": child["ns"], "children": _flatten(child)})
    return out


def chrome_tree(path: Path) -> list[list[dict]]:
    """Chrome trace event JSON (an event array, or an object with `traceEvents`).

    Reads `B`/`E` duration pairs and `X` complete events; `ts` and `dur` are
    microseconds. tracing-chrome 0.7.2 writes B/E pairs carrying `.file` and `.line`.
    Returns one tree per (pid, tid).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    events = data if isinstance(data, list) else data.get("traceEvents", [])
    threads: dict[tuple, dict] = {}
    for ev in events:
        ph = ev.get("ph")
        if ph not in ("B", "E", "X") or "ts" not in ev:
            continue
        t = threads.setdefault((ev.get("pid"), ev.get("tid")), {"open": [], "done": []})
        info = {"fn": ev.get("name", "?"), "file": ev.get(".file") or ev.get("cat") or "",
                "line": ev.get(".line") or 0}
        if ph == "B":
            t["open"].append({**info, "start": float(ev["ts"])})
        elif ph == "E":
            if t["open"]:
                iv = t["open"].pop()
                iv["end"] = float(ev["ts"])
                t["done"].append(iv)
        else:
            start = float(ev["ts"])
            t["done"].append({**info, "start": start, "end": start + float(ev.get("dur", 0))})
    return [_aggregate(t["done"]) for _k, t in sorted(threads.items(), key=lambda kv: str(kv[0]))]


def cpuprofile_tree(path: Path, root: Path) -> list[list[dict]]:
    """V8 `.cpuprofile` files from `node --cpu-prof` (a file, or a directory of them).

    SAMPLED, not traced: `calls` here counts samples in the subtree, and `ns` is
    samples times the mean sampling interval. Only frames whose script URL lies under
    the project root are kept; the runtime's own frames are collapsed out.
    """
    files = sorted(path.glob("*.cpuprofile")) if path.is_dir() else [path]
    own_prefix = root.as_uri() + "/"
    trees = []
    for f in files:
        prof = json.loads(f.read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in prof.get("nodes", [])}
        n_samples = max(1, len(prof.get("samples", [])))
        interval_ns = (prof.get("endTime", 0) - prof.get("startTime", 0)) * 1000 / n_samples
        totals: dict[int, int] = {}

        def total(nid: int) -> int:
            if nid not in totals:
                n = nodes[nid]
                totals[nid] = n.get("hitCount", 0) + sum(total(c) for c in n.get("children", []))
            return totals[nid]

        agg: dict = {"children": {}}

        def walk(nid: int, parent: dict) -> None:
            n = nodes[nid]
            cf = n.get("callFrame", {})
            url = cf.get("url", "")
            if url.startswith(own_prefix):
                rel = url[len(own_prefix):]
                key = (cf.get("functionName") or "(anonymous)", rel, cf.get("lineNumber", 0) + 1)
                node = parent["children"].get(key)
                if node is None:
                    node = parent["children"][key] = {"key": key, "calls": 0, "ns": 0, "children": {}}
                node["calls"] += total(nid)
                node["ns"] += int(total(nid) * interval_ns)
                parent = node
            for c in n.get("children", []):
                walk(c, parent)

        roots = [i for i in nodes if not any(i in n.get("children", []) for n in nodes.values())]
        for r in roots:
            walk(r, agg)
        trees.append(_flatten(agg))
    return trees


# -- merge: per-process fragments -> one run record ---------------------------------

def _same_command(child_argv: list, spawn_argv: list) -> bool:
    """A child's sys.orig_argv against the argv its parent spawned.

    argv[0] differs in spelling (`python3` vs an absolute interpreter path), so only
    the tails are compared; the child's may carry extra leading interpreter flags.
    """
    child, spawned = [str(a) for a in child_argv[1:]], [str(a) for a in spawn_argv[1:]]
    if not spawned:
        return not child
    return child[-len(spawned):] == spawned


def _relink_tree(nodes: list[dict], red: Redactor) -> list[dict]:
    return [{**n, "file": red.path(n["file"]), "children": _relink_tree(n["children"], red)} for n in nodes]


def merge(frags: list[dict], *, root: Path, command: list, root_pid: int, root_rc: int,
          started_ns: int, ended_ns: int, run_id: str, declared: dict) -> dict:
    red = Redactor(root)
    frags = sorted(frags, key=lambda f: f["startedNs"])
    steps: list[dict] = []
    by_frag: dict[int, dict] = {}
    for i, f in enumerate(frags):
        step = {
            "id": None, "traced": True, "pid": f["pid"], "ppid": f["ppid"],
            "command": red.argv(f["argv"]), "cwd": red.path(f["cwd"]),
            "startNs": f["startedNs"], "endNs": f["endedNs"], "python": f["python"],
            "exit": f["exit"], "parent": None, "why": "",
            "calls": {"source": "sys.monitoring", "available": f["callsAvailable"],
                      "unit": "calls", "threads": [_relink_tree(t, red) for t in f["threads"]]},
            "_frag": f, "dropped": f["dropped"], "droppedWhy": f["droppedWhy"],
        }
        if not f["callsAvailable"]:
            step["calls"]["why"] = f"Python {f['python']} has no sys.monitoring; file I/O was still recorded"
        by_frag[i] = step
        steps.append(step)

    # Parent links, and the spawns no traced process answers: those are untraced steps.
    claimed: set[int] = set()
    traced_pids = {f["pid"] for f in frags}
    for i, f in enumerate(frags):
        parent = by_frag[i]
        for sp in f["spawns"]:
            match = None
            if not sp["shell"]:
                for j, g in enumerate(frags):
                    if j in claimed or g["ppid"] != f["pid"] or g["startedNs"] < sp["t"]:
                        continue
                    if _same_command(g["argv"], sp["argv"]):
                        match = j
                        break
            if match is not None:
                claimed.add(match)
                by_frag[match]["parent"] = parent
                continue
            exe = Path(str(sp["argv"][0]).split()[0]).name if sp["argv"] else "?"
            if sp["shell"] or not exe.startswith("python"):
                why = "no in-process adapter for this program; its file I/O is not observed"
            else:
                why = "a Python child that left no trace: started with -I/-E, given its own env, or exited without flushing"
            steps.append({
                "id": None, "traced": False, "pid": None, "ppid": f["pid"],
                "command": red.argv(sp["argv"]), "cwd": red.path(sp["cwd"]) if sp["cwd"] else "",
                "startNs": sp["t"], "endNs": None, "python": None,
                "exit": {"code": None, "how": "not observed"}, "parent": parent, "why": why,
                "calls": {"source": None, "available": False, "unit": "calls", "threads": [],
                          "why": "untraced"},
                "_frag": None, "dropped": 0, "droppedWhy": {},
            })

    root_step = next((s for s in steps if s["traced"] and s["pid"] == root_pid), None)
    if root_step is None:
        root_step = {
            "id": None, "traced": False, "pid": root_pid, "ppid": os.getpid(),
            "command": red.argv(command), "cwd": red.path(str(root)),
            "startNs": started_ns, "endNs": ended_ns, "python": None,
            "exit": {"code": root_rc, "how": "observed by the runner"}, "parent": None,
            "why": "the command is not a traced Python process",
            "calls": {"source": None, "available": False, "unit": "calls", "threads": [],
                      "why": "untraced: pass --calls to attach an adapter's trace"},
            "_frag": None, "dropped": 0, "droppedWhy": {},
        }
        steps.append(root_step)
    else:
        root_step["exit"] = {"code": root_rc, "how": "observed by the runner"}
        root_step["endNs"] = max(root_step["endNs"] or 0, ended_ns)
    for s in steps:
        if s["traced"] and s is not root_step and s["parent"] is None and s["ppid"] not in traced_pids:
            s["why"] = "spawned through an untraced process"

    if declared.get("calls"):
        kind, _, where = declared["calls"].partition(":")
        p = Path(where)
        trees = chrome_tree(p) if kind == "chrome" else cpuprofile_tree(p, root)
        root_step["calls"] = {
            "source": "chrome-trace" if kind == "chrome" else "v8-cpuprofile",
            "available": True, "unit": "calls" if kind == "chrome" else "samples",
            "threads": [_relink_tree(t, red) for t in trees],
        }

    steps.sort(key=lambda s: s["startNs"])
    for n, s in enumerate(steps, 1):
        s["id"] = f"s{n}"

    # Every committed version of every path, in commit order across the whole run.
    commits: list[tuple] = []
    for s in steps:
        f = s["_frag"]
        if f:
            for path, vs in f["outputs"].items():
                commits.extend((v["t"], path, v["sha256"], s) for v in vs)
    if not root_step["traced"]:
        for pattern in declared.get("writes", []):
            for p in sorted(root.glob(pattern)):
                if p.is_file():
                    commits.append((ended_ns, str(p), _sha256(p), root_step))
    commits.sort(key=lambda c: c[0])
    versions: dict[str, list[dict]] = {}
    for t, path, sha, s in commits:
        vs = versions.setdefault(path, [])
        vs.append({"n": len(vs) + 1, "t": t, "sha256": sha, "step": s})

    reads: list[tuple] = []
    for s in steps:
        f = s["_frag"]
        if f:
            reads.extend((path, r["sha256"], r["t"], r.get("mtime_ns"), s) for path, r in f["inputs"].items())
    if not root_step["traced"]:
        for path, sha, mt in declared.get("readHashes", []):
            reads.append((path, sha, started_ns, mt, root_step))

    untraced = [s for s in steps if not s["traced"]]
    counts = {"verified": 0, "broken": 0, "unverified": 0, "source": 0}
    for s in steps:
        s["inputs"], s["outputs"], s["code"], s["removed"] = [], [], [], []
    for path, sha, t, mtime, s in sorted(reads, key=lambda r: r[2]):
        prior = [v for v in versions.get(path, []) if v["t"] <= t and v["step"] is not s]
        entry = {"path": red.path(path), "sha256": sha}
        if sha is None:
            entry.update(status="unverified", note="the input could not be hashed when it was read")
        elif prior:
            v = prior[-1]
            entry.update(producer=v["step"]["id"], version=v["n"])
            if sha == v["sha256"]:
                entry["status"] = "verified"
            else:
                between = [u["id"] for u in untraced if v["t"] < u["startNs"] < t]
                entry.update(status="broken", expected=v["sha256"],
                             note=("changed after " + v["step"]["id"] + " wrote it" +
                                   (" -- untraced step(s) ran in between: " + ", ".join(between)
                                    if between else "")))
        elif mtime is not None and mtime >= started_ns:
            before = [u["id"] for u in untraced if u["startNs"] < t]
            entry.update(status="unverified",
                         note="written during this run, but by no traced step" +
                              (" (untraced: " + ", ".join(before) + ")" if before else ""))
        else:
            entry["status"] = "source"
        counts[entry["status"]] += 1
        s["inputs"].append(entry)

    for path, vs in versions.items():
        for v in vs:
            v["step"]["outputs"].append({"path": red.path(path), "version": v["n"], "sha256": v["sha256"],
                                         "latest": v["n"] == len(vs)})
    for s in steps:
        f = s["_frag"]
        if f:
            s["code"] = [{"path": red.path(p), "sha256": h} for p, h in sorted(f["code"].items())]
            s["removed"] = sorted({red.path(r["path"]) for r in f["removed"]})
        consumers = {}
        for other in steps:
            for i in other["inputs"]:
                if i.get("producer") == s["id"]:
                    consumers.setdefault(i["path"], []).append(other["id"])
        for o in s["outputs"]:
            o["feeds"] = sorted(set(consumers.get(o["path"], [])))

    if counts["broken"]:
        verdict = "broken"
    elif counts["unverified"]:
        verdict = "incomplete"
    elif counts["verified"]:
        verdict = "verified"
    else:
        verdict = "empty"

    out_steps = []
    for s in steps:
        out = {k: v for k, v in s.items() if not k.startswith("_") and k not in ("parent", "startNs", "endNs")}
        out["parent"] = s["parent"]["id"] if s["parent"] else None
        out["started"] = iso(s["startNs"])
        out["durationMs"] = round((s["endNs"] - s["startNs"]) / 1e6, 2) if s["endNs"] else None
        out_steps.append(out)
    return {
        "schema": SCHEMA, "runId": run_id, "command": red.argv(command), "root": red.text(str(root)),
        "started": iso(started_ns), "finished": iso(ended_ns),
        "exit": root_rc, "chain": {"verdict": verdict, **counts},
        "dropped": sum(s["dropped"] for s in steps),
        "steps": out_steps,
    }


def _sha256(p: Path) -> str | None:
    import hashlib
    h = hashlib.sha256()
    try:
        with p.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


# -- PROV-JSON ----------------------------------------------------------------------

def to_prov(trace: dict) -> dict:
    """W3C PROV-JSON. Entities are file versions, activities are steps.

    Claims only what was observed: `used` and `wasGeneratedBy` per step, `wasInformedBy`
    for a verified link, and `wasDerivedFrom` only where one step read a file and wrote
    the same path (an in-place rewrite). No blanket "every output derives from every
    input" -- that would be an inference the trace does not support.
    """
    run = trace["runId"]
    doc: dict = {
        "prefix": {"spur": SPUR_NS, "run": f"urn:spur:{run}:"},
        "entity": {}, "activity": {}, "used": {}, "wasGeneratedBy": {},
        "wasInformedBy": {}, "wasDerivedFrom": {},
    }
    counter = {"n": 0}

    def rid(kind: str) -> str:
        counter["n"] += 1
        return f"_:{kind}{counter['n']}"

    def entity(path: str, version: int | None, sha: str | None, kind: str) -> str:
        if version is not None:
            eid = f"run:{path}@{version}"
        elif kind == "source":
            eid = f"run:{path}@0"
        else:
            eid = f"run:{path}@unattributed-{(sha or 'unhashed')[:12]}"
        doc["entity"].setdefault(eid, {
            "prov:label": eid.removeprefix("run:"), "spur:path": path,
            "spur:sha256": sha or "", "spur:attribution": kind,
        })
        return eid

    informed = set()
    for s in trace["steps"]:
        aid = f"run:step/{s['id']}"
        act = {"prov:label": " ".join(s["command"]), "spur:traced": s["traced"]}
        if s.get("started"):
            act["prov:startTime"] = s["started"]
        doc["activity"][aid] = act
        read_by_path = {}
        for i in s["inputs"]:
            status = i["status"]
            version = i.get("version") if status == "verified" else None
            eid = entity(i["path"], version, i["sha256"], status)
            read_by_path[i["path"]] = eid
            doc["used"][rid("u")] = {"prov:activity": aid, "prov:entity": eid}
            if status == "verified" and (s["id"], i["producer"]) not in informed:
                informed.add((s["id"], i["producer"]))
                doc["wasInformedBy"][rid("i")] = {"prov:informed": aid,
                                                  "prov:informant": f"run:step/{i['producer']}"}
        for o in s["outputs"]:
            eid = entity(o["path"], o["version"], o["sha256"], "generated")
            doc["wasGeneratedBy"][rid("g")] = {"prov:entity": eid, "prov:activity": aid}
            if o["path"] in read_by_path:
                doc["wasDerivedFrom"][rid("d")] = {"prov:generatedEntity": eid,
                                                   "prov:usedEntity": read_by_path[o["path"]],
                                                   "prov:activity": aid}
    return {k: v for k, v in doc.items() if v}


# -- commands -----------------------------------------------------------------------

def cmd_detect(args) -> int:
    root = Path(args.root).resolve()
    found = {stack: [m for m in marks if (root / m).exists()] for stack, marks in STACK_MARKERS.items()}
    found = {k: v for k, v in found.items() if v}
    print(json.dumps({"root": Redactor(root).text(str(root)),
                      "stacks": [{"stack": k, "markers": v, "adapter": ADAPTER[k]} for k, v in found.items()]},
                     indent=2))
    return 0 if found else EXIT_INCOMPLETE


def cmd_run(args) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("spur_trace.py run: no COMMAND after --", file=sys.stderr)
        return EXIT_USAGE
    if args.calls and args.calls.partition(":")[0] not in ("chrome", "cpuprofile"):
        print("spur_trace.py run: --calls takes chrome:FILE or cpuprofile:PATH", file=sys.stderr)
        return EXIT_USAGE
    root = Path(args.root).resolve()
    run_id = args.run_id or datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (Path(args.out) if args.out else root / "analysis" / "spur") / run_id
    frag_dir = run_dir / "fragments"
    frag_dir.mkdir(parents=True, exist_ok=False)

    read_hashes = []
    for pattern in args.reads:
        for p in sorted(root.glob(pattern)):
            if p.is_file():
                read_hashes.append((str(p), _sha256(p), p.stat().st_mtime_ns))

    env = os.environ.copy()
    env["SPUR_TRACE_DIR"] = str(frag_dir)
    env["SPUR_ROOT"] = str(root)
    env["PYTHONPATH"] = str(BOOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    started = time.time_ns()
    try:
        proc = subprocess.Popen(command, env=env)
    except OSError as exc:
        print(f"spur_trace.py run: cannot start {command[0]}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    rc = proc.wait()
    ended = time.time_ns()

    frags = []
    for f in sorted(frag_dir.glob("proc-*.json")):
        try:
            frags.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"spur_trace.py run: unreadable fragment {f.name}: {exc}", file=sys.stderr)
    trace = merge(frags, root=root, command=command, root_pid=proc.pid, root_rc=rc,
                  started_ns=started, ended_ns=ended, run_id=run_id,
                  declared={"calls": args.calls, "writes": args.writes, "readHashes": read_hashes})
    if not args.keep_fragments:
        # Fragments hold absolute, unredacted paths; the run record is the redacted copy.
        shutil.rmtree(frag_dir)

    (run_dir / "trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    (run_dir / "prov.json").write_text(json.dumps(to_prov(trace), indent=2), encoding="utf-8")
    sys.path.insert(0, str(HERE))
    import build_spur_html
    (run_dir / "spur-report.html").write_text(build_spur_html.render(trace), encoding="utf-8")

    c = trace["chain"]
    print(f"spur: {len(trace['steps'])} step(s), chain {c['verdict']} "
          f"({c['verified']} verified, {c['broken']} broken, {c['unverified']} unverified, "
          f"{c['source']} source)", file=sys.stderr)
    if trace["dropped"]:
        print(f"spur: the tracer dropped {trace['dropped']} event(s); see the report", file=sys.stderr)
    print(f"spur: wrote {Redactor(root).text(str(run_dir))}/{{trace.json,prov.json,spur-report.html}}",
          file=sys.stderr)
    if rc != 0:
        return rc
    return {"verified": EXIT_VERIFIED, "broken": EXIT_BROKEN}.get(c["verdict"], EXIT_INCOMPLETE)


def cmd_verify(args) -> int:
    run_dir = Path(args.run_dir)
    try:
        trace = json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"spur_trace.py verify: cannot read {run_dir / 'trace.json'}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    root = Path(args.root).resolve()
    drift = 0
    for s in trace["steps"]:
        for o in s["outputs"]:
            if not o.get("latest"):
                continue
            p = root / o["path"]
            now = _sha256(p) if p.is_file() else None
            ok = now == o["sha256"]
            drift += not ok
            print(f"{'ok   ' if ok else 'DRIFT'} {o['path']}@{o['version']} ({s['id']})"
                  + ("" if ok else f": recorded {o['sha256'][:12]}, on disk {(now or 'missing')[:12]}"))
    return EXIT_BROKEN if drift else 0


def cmd_prov(args) -> int:
    try:
        trace = json.loads(Path(args.trace).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"spur_trace.py prov: cannot read {args.trace}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    text = json.dumps(to_prov(trace), indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="spur_trace.py",
        description="Trace one run of a project's pipeline: per step, the command, the call "
                    "tree of the project's own functions, every file read and written with "
                    "its sha256, and a hash-chain check across steps.",
        epilog="run exit: the command's own code if it failed, else 0 verified, 3 broken, "
               "4 incomplete/empty, 2 usage error",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect", help="name the stacks found and the adapter each gets")
    d.add_argument("--root", default=".")
    r = sub.add_parser("run", help="run COMMAND once under the tracer")
    r.add_argument("--root", default=".", help="project root; own code and relative paths (default: .)")
    r.add_argument("--out", help="output directory (default: ROOT/analysis/spur)")
    r.add_argument("--run-id", help="run directory name (default: UTC timestamp)")
    r.add_argument("--keep-fragments", action="store_true",
                   help="keep the raw per-process records (unredacted absolute paths)")
    r.add_argument("--calls", help="attach a non-Python call trace to the root step: "
                                   "chrome:FILE (tracing-chrome) or cpuprofile:PATH (node --cpu-prof)")
    r.add_argument("--reads", action="append", default=[],
                   help="glob of files an untraced root command reads (hashed before it runs)")
    r.add_argument("--writes", action="append", default=[],
                   help="glob of files an untraced root command writes (hashed after it exits)")
    r.add_argument("command", nargs=argparse.REMAINDER, help="-- COMMAND [ARG...]")
    v = sub.add_parser("verify", help="re-hash a run's final outputs on disk")
    v.add_argument("run_dir")
    v.add_argument("--root", default=".")
    p = sub.add_parser("prov", help="export a trace.json as W3C PROV-JSON")
    p.add_argument("trace")
    p.add_argument("--out")
    args = parser.parse_args(argv)
    return {"detect": cmd_detect, "run": cmd_run, "verify": cmd_verify, "prov": cmd_prov}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
