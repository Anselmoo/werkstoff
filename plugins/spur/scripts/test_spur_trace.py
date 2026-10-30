#!/usr/bin/env python3
"""Acceptance test for spur_trace.py -- it must not change the program, and its chain
check must FAIL as well as pass.

Runs the committed fixture pipeline (scripts/fixtures/pipeline/: four steps, one
output feeding the next, one in-place rewrite) in throwaway copies:

  IDENTICAL  traced and untraced runs write byte-identical outputs (sha256 per file).
             The tracer rewrites no code; noWorkflow did, broke the program, and
             returned exit 0.
  CHAIN      a clean run's chain is verified, the rewrite is version @2, and a
             consumer is checked against the latest version before its read.
  TAMPER     an untraced step that edits the intermediate file between producer and
             consumer makes the chain BROKEN at exactly that link -- tampering after
             the run would prove nothing, since the recorded hashes would still agree.
  DRIFT      `verify` re-hashes final outputs on disk and names a file edited after.
  EXIT       a failing step's exit code reaches the runner's own exit code and the page.
  PRIVACY    no environment value and no home path lands in any output.
  ADAPTERS   the Chrome-trace importer reads REAL tracing-chrome 0.7.2 output; the
             cpuprofile importer reads a REAL `node --cpu-prof` run (skipped by name
             when node is absent, failed instead under REQUIRE_NODE=1).

Needs Python 3.12+ (sys.monitoring) for the call-tree cases. Below that the whole
test is a named skip, and a failure under REQUIRE_SPUR_MONITORING=1.

Sabotage check (run it, do not assume it): make merge() treat every prior version as
a match -- replace `if sha == v["sha256"]:` with `if True:` -- and the TAMPER cases
must go red while IDENTICAL stays green. A check that cannot fail reports success
every run and nobody looks again.

Run: python3 plugins/spur/scripts/test_spur_trace.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPUR = HERE / "spur_trace.py"
PIPELINE = HERE / "fixtures" / "pipeline"
ADAPTERS = HERE / "fixtures" / "adapters"
SECRET = "spur-test-secret-value-7f3a"

FAILURES: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + extra}")
    if not cond:
        FAILURES.append(name)


def copy_pipeline(tmp: Path, name: str) -> Path:
    dst = tmp / name
    shutil.copytree(PIPELINE, dst, ignore=shutil.ignore_patterns("work", "out", "analysis", "__pycache__"))
    return dst


def hashes(root: Path) -> dict[str, str]:
    out = {}
    for sub in ("work", "out"):
        for p in sorted((root / sub).rglob("*")):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def spur(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SPUR), *args], cwd=cwd, capture_output=True,
                          text=True, env={**os.environ, **(env or {})})


def load(run_dir: Path) -> dict:
    return json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))


def step_running(trace: dict, script: str) -> dict:
    return next(s for s in trace["steps"] if script in s["command"])


def tree_names(nodes: list) -> set[str]:
    names = set()
    for n in nodes:
        names.add(n["fn"])
        names |= tree_names(n["children"])
    return names


def main() -> int:
    if not hasattr(sys, "monitoring"):
        msg = f"SKIP: Python {sys.version.split()[0]} has no sys.monitoring; run under 3.12+"
        if os.environ.get("REQUIRE_SPUR_MONITORING") == "1":
            print("FAIL " + msg)
            return 1
        print(msg)
        return 0

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print("IDENTICAL -- tracing changes no output")
        plain = copy_pipeline(tmp, "plain")
        rc = subprocess.run([sys.executable, "run_pipeline.py"], cwd=plain, check=False).returncode
        check("untraced run exits 0", rc == 0, str(rc))
        traced = copy_pipeline(tmp, "traced")
        r = spur(traced, "run", "--run-id", "clean", "--", sys.executable, "run_pipeline.py",
                 env={"SPUR_TEST_SECRET": SECRET})
        check("traced run exits 0 (chain verified)", r.returncode == 0, r.stderr)
        h_plain, h_traced = hashes(plain), hashes(traced)
        check("same output files", sorted(h_plain) == sorted(h_traced), f"{sorted(h_plain)} vs {sorted(h_traced)}")
        check("every output byte-identical", h_plain == h_traced and len(h_plain) == 3,
              json.dumps({"untraced": h_plain, "traced": h_traced}, indent=1))
        for path, h in sorted(h_traced.items()):
            print(f"       {path}: untraced {h_plain.get(path, 'missing')[:16]}  traced {h[:16]}")

        print("CHAIN -- a clean run verifies, the rewrite is a new version")
        run_dir = traced / "analysis" / "spur" / "clean"
        t = load(run_dir)
        c = t["chain"]
        check("verdict verified", c["verdict"] == "verified", json.dumps(c))
        check("3 verified links, 1 source, nothing broken or unverified",
              (c["verified"], c["source"], c["broken"], c["unverified"]) == (3, 1, 0, 0), json.dumps(c))
        check("5 traced steps: the driver and its 4 children",
              len(t["steps"]) == 5 and all(s["traced"] for s in t["steps"]), str(len(t["steps"])))
        norm, summ = step_running(t, "normalize.py"), step_running(t, "summarize.py")
        check("normalize reads records.csv@1 and it verifies",
              [(i["path"], i["version"], i["status"]) for i in norm["inputs"]] == [("work/records.csv", 1, "verified")],
              json.dumps(norm["inputs"]))
        check("normalize's in-place rewrite is records.csv@2",
              [(o["path"], o["version"]) for o in norm["outputs"]] == [("work/records.csv", 2)],
              json.dumps(norm["outputs"]))
        check("summarize is checked against @2, the latest before its read",
              [(i["path"], i["version"]) for i in summ["inputs"]] == [("work/records.csv", 2)],
              json.dumps(summ["inputs"]))
        check("@2 feeds summarize", norm["outputs"][0]["feeds"] == [summ["id"]], json.dumps(norm["outputs"]))
        ingest = step_running(t, "ingest.py")
        names = tree_names(ingest["calls"]["threads"][0])
        check("ingest's call tree has its own functions (generator and caught exception included)",
              {"main", "read_rows", "keep", "parse_amount"} <= names, str(names))
        check("call tree holds only project code", not any("csv" in n for n in names), str(names))
        check("code it loaded is listed apart from data",
              any(cd["path"] == "ingest.py" for cd in ingest["code"]), json.dumps(ingest["code"]))
        check("no tracer event was dropped", t["dropped"] == 0, str(t["dropped"]))
        check("fragments (unredacted) were removed", not (run_dir / "fragments").exists())

        print("PRIVACY -- no env values, no home paths, nothing from the network")
        blobs = {p.name: p.read_text(encoding="utf-8") for p in run_dir.iterdir() if p.is_file()}
        check("all three outputs written", sorted(blobs) == ["prov.json", "spur-report.html", "trace.json"],
              str(sorted(blobs)))
        check("an environment value appears in no output", not any(SECRET in b for b in blobs.values()))
        home = str(Path.home())
        check("the home directory appears in no output", not any(home in b for b in blobs.values()), home)
        html = blobs.get("spur-report.html", "")
        check("the page loads nothing from the network",
              'src="http' not in html and 'href="http' not in html and "default-src 'none'" in html)

        print("PROV -- the export claims only what was observed")
        prov = json.loads(blobs["prov.json"])
        check("PROV-JSON has entity, activity, used, wasGeneratedBy, wasInformedBy",
              {"entity", "activity", "used", "wasGeneratedBy", "wasInformedBy"} <= set(prov), str(sorted(prov)))
        derived = list(prov.get("wasDerivedFrom", {}).values())
        check("exactly one wasDerivedFrom: the in-place rewrite @2 from @1",
              [(d["prov:generatedEntity"], d["prov:usedEntity"]) for d in derived]
              == [("run:work/records.csv@2", "run:work/records.csv@1")], json.dumps(derived))
        check("one wasInformedBy per verified link", len(prov["wasInformedBy"]) == 3, str(len(prov["wasInformedBy"])))
        check("times carry a UTC offset",
              all(a.get("prov:startTime", "+00:00").endswith("+00:00") for a in prov["activity"].values()))

        print("DRIFT -- verify re-hashes final outputs on disk")
        v = spur(traced, "verify", "analysis/spur/clean")
        check("verify passes on an untouched run", v.returncode == 0, v.stdout + v.stderr)
        with (traced / "work" / "records.csv").open("a", encoding="utf-8") as fh:
            fh.write("eve,south,1.00\n")
        v = spur(traced, "verify", "analysis/spur/clean")
        check("verify exits 3 once an intermediate file is edited", v.returncode == 3, v.stdout)
        check("verify names the drifted version", "DRIFT work/records.csv@2" in v.stdout, v.stdout)

        print("TAMPER -- an untraced edit between producer and consumer breaks the chain")
        tam = copy_pipeline(tmp, "tamper")
        r = spur(tam, "run", "--run-id", "tamper", "--", sys.executable, "run_pipeline.py", "--tamper")
        check("runner exits 3 (broken)", r.returncode == 3, f"{r.returncode} {r.stderr}")
        t = load(tam / "analysis" / "spur" / "tamper")
        check("verdict broken", t["chain"]["verdict"] == "broken", json.dumps(t["chain"]))
        summ, norm = step_running(t, "summarize.py"), step_running(t, "normalize.py")
        broken = [i for s in t["steps"] for i in s["inputs"] if i["status"] == "broken"]
        check("exactly one broken link", len(broken) == 1, json.dumps(broken))
        b = broken[0] if broken else {}
        check("broken at records.csv, producer normalize, consumer summarize",
              b.get("path") == "work/records.csv" and b.get("producer") == norm["id"] and b in summ["inputs"],
              json.dumps(b))
        sh = next((s for s in t["steps"] if not s["traced"]), None)
        check("the shell step is recorded as an untraced step", sh is not None and sh["command"][0] == "sh")
        check("the broken link names the untraced step that ran between",
              sh is not None and sh["id"] in b.get("note", ""), b.get("note", ""))
        over = [i for i in summ["inputs"] if i["path"] == "work/override.txt"]
        check("the override the shell wrote is UNVERIFIED, not a source",
              [i["status"] for i in over] == ["unverified"], json.dumps(over))
        check("the link before the tamper still verifies",
              [i["status"] for i in norm["inputs"]] == ["verified"], json.dumps(norm["inputs"]))

        print("EXIT -- a failing step's code reaches the runner and the page")
        bad = copy_pipeline(tmp, "fail")
        r = spur(bad, "run", "--run-id", "fail", "--", sys.executable, "run_pipeline.py", "--fail")
        check("runner exits with the command's own code (1)", r.returncode == 1, f"{r.returncode} {r.stderr}")
        t = load(bad / "analysis" / "spur" / "fail")
        check("the run record carries exit 1", t["exit"] == 1, str(t["exit"]))
        ing = step_running(t, "ingest.py")
        check("the failing step is named, with the uncaught exception",
              ing["exit"] == {"code": 1, "how": "uncaught FileNotFoundError"}, json.dumps(ing["exit"]))

        print("UNTRACED ROOT -- declared I/O for a program with no in-process adapter")
        dec = copy_pipeline(tmp, "declared")
        (dec / "work").mkdir()
        r = spur(dec, "run", "--run-id", "dec", "--reads", "data/raw.csv", "--writes", "work/copy.csv",
                 "--", "sh", "-c", "cp data/raw.csv work/copy.csv")
        t = load(dec / "analysis" / "spur" / "dec")
        root = t["steps"][0]
        check("an untraced root is a step, named as untraced", not root["traced"] and root["command"][0] == "sh")
        check("its declared read and write are hashed",
              [i["path"] for i in root["inputs"]] == ["data/raw.csv"]
              and [o["path"] for o in root["outputs"]] == ["work/copy.csv"], json.dumps(root))
        check("no link to check is EMPTY, which is not a pass (exit 4)",
              t["chain"]["verdict"] == "empty" and r.returncode == 4, f"{t['chain']} rc={r.returncode}")

    print("ADAPTERS -- importers read real output of the other stacks' tracers")
    sys.path.insert(0, str(HERE))
    import spur_trace

    trees = spur_trace.chrome_tree(ADAPTERS / "rust" / "tracing-chrome-0.7.2.json")
    top = trees[0][0] if trees and trees[0] else {}
    check("tracing-chrome: load -> parse_row x3, with file and line",
          top.get("fn") == "load" and top.get("file") == "src/main.rs"
          and [(c["fn"], c["calls"]) for c in top.get("children", [])] == [("parse_row", 3)], json.dumps(trees))
    node = shutil.which("node")
    if node is None:
        msg = "node not on PATH: the cpuprofile importer was not exercised"
        check("node present (REQUIRE_NODE=1)", os.environ.get("REQUIRE_NODE") != "1", msg)
        print("  SKIP " + msg)
    else:
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            shutil.copy(ADAPTERS / "node" / "app.js", work / "app.js")
            r = spur(work, "run", "--run-id", "node", "--calls", "cpuprofile:prof", "--",
                     node, "--cpu-prof", "--cpu-prof-dir=prof", "app.js")
            t = load(work / "analysis" / "spur" / "node")
            root = t["steps"][0]
            names = tree_names(root["calls"]["threads"][0]) if root["calls"]["threads"] else set()
            check("node --cpu-prof: the project's own functions, sampled",
                  root["calls"]["source"] == "v8-cpuprofile" and root["calls"]["unit"] == "samples"
                  and {"load", "parseRow"} <= names, json.dumps(root["calls"])[:400])
            check("node's runtime frames are collapsed out", not any("internal" in n for n in names), str(names))

    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print(f"all checks passed under Python {sys.version.split()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
