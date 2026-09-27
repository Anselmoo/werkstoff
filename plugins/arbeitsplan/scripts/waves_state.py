#!/usr/bin/env python3
"""State, merge and gate helper for an arbeitsplan multi-wave plan (#106).

usage: <name>_state.py {preflight|record|merge|approve|show|selftest} [...]

VENDORED. install_waves.py copies this file into a project as
.claude/workflows/<name>_state.py, next to <name>.plan.json (the compiled
design) and <name>.state.json (this helper's gitignored state). The project runs
it without werkstoff installed. It is the ONE runtime prerequisite the generated
tooling has -- python3 >= 3.10, stdlib only -- and the installer resolves and
records the interpreter rather than assuming `python3` is on PATH.

The workflow interpreter (waves.js) cannot exec anything, so every call below
arrives through the project's script-runner agent, whose guard allows exactly
the declared command templates. Each subcommand prints ONE JSON object on
stdout -- the runner copies it into `parsed` -- and exits 0, or 1 for a red
merge-gate (expectExit [0, 1]). Anything else is a defect and exits 2.

  preflight  {linkedWorktree, dirty, head, python}: the run refuses a linked
             worktree (#106 R1: the wave base is this checkout's HEAD, and agent
             worktrees start from worktree.baseRef -- the remote's default branch
             unless "head" -- never from a linked worktree's; ADR 0004) and a
             checkout with tracked changes
  record     --row R --branch B --base SHA: a finished builder, with the notes
             its commits carry, survives a restart (#106 R3)
  merge      --wave N --stage K --final 0|1 --branches row=branch,... --discard
             b1,b2|none: merge into the integration branch; on the final stage
             run every declared gate twice -- in the primary checkout, which
             sees untracked and ignored files, and in a clean worktree -- and
             label a finding `primary-only` when only the first fails (#106 R5).
             The target moves only when every gate is green in both (#106 R4).
             Green cleans up merged and discarded worktrees; red keeps them all
             and names them.
  approve    --gate ID: record a human gate's approval between runs
  verify-step --node ID: an AUTHORED step script (#107 follow-up) -- refuse a
             file still carrying the stub marker, check its syntax without
             running it, run its declared sample in a throwaway detached
             worktree (never the primary checkout), validate its stdout against
             the node's strict output_schema, and record {sha256, contract}.
             The runner guard refuses to run an authored step whose file or
             contract no longer matches that record.
  show       print the state, with every authored step's status computed live
             (missing | stub | authored | verified | stale) -- the Workflow
             script cannot hash a file, so it trusts this and nothing else

STDLIB ONLY. Python >= 3.10 (checked). No datetime: a timestamp is not needed
to decide anything here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

MIN_PYTHON = (3, 10)
GATE_TIMEOUT = 3600  # seconds per gate run; a hung gate is a red gate, not a hang
STEP_TIMEOUT = 600  # seconds for one authored step's sample run

# Authored steps. A design's script node may carry `script.author`, and then
# the step file is WRITTEN by the plan's author agent instead of existing
# already. The runtime (a toolchain name) fixes everything else: the file's
# extension, the interpreter the command must start with, and how its syntax is
# checked without executing it. `.mjs`, not `.js`, for node: Claude Code treats
# every `.js` under .claude/workflows/ as a workflow, and ignores other files.
# design_spec.py imports this table, so the validator and the vendored helper
# cannot disagree about which languages can be authored.
STUB_MARKER = "ARBEITSPLAN-STUB"
# Filled by str.replace, NOT str.format: its braces are PowerShell's and stay
# single. Doubled, `if ($e) {{ ... exit 1 }}` is a scriptblock LITERAL that never
# runs, and every broken .ps1 would pass its syntax check.
PWSH_PARSE = ("$e=$null; $null=[System.Management.Automation.Language.Parser]::ParseFile("
              "'{path}',[ref]$null,[ref]$e); if ($e) { $e | ForEach-Object { $_.ToString() };"
              " exit 1 }")
AUTHORABLE = {
    "shell": {"ext": "sh", "exes": ["bash"], "check": ["{exe}", "-n", "{path}"]},
    "powershell": {"ext": "ps1", "exes": ["pwsh", "pwsh.exe"],
                   "check": ["{exe}", "-NoProfile", "-NonInteractive", "-Command", PWSH_PARSE]},
    "ruby": {"ext": "rb", "exes": ["ruby"], "check": ["{exe}", "-c", "{path}"]},
    "node": {"ext": "mjs", "exes": ["node"], "check": ["{exe}", "--check", "{path}"]},
    # Python is compiled in-process: no interpreter call, no __pycache__.
    "python": {"ext": "py", "exes": ["python3*", "python", "py"], "check": None},
}


class HelperError(Exception):
    """A defect or an environment the helper refuses -- exit 2."""


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise HelperError(f"git {' '.join(args)} failed: {proc.stderr.strip()[-400:]}")
    return proc


def out(*args: str, cwd: Path) -> str:
    return git(*args, cwd=cwd).stdout.strip()


def repo_root(start: Path) -> Path:
    return Path(out("rev-parse", "--show-toplevel", cwd=start))


def plan_path(helper: Path) -> Path:
    return helper.with_name(helper.stem.removesuffix("_state") + ".plan.json")


def state_path(helper: Path) -> Path:
    return helper.with_name(helper.stem.removesuffix("_state") + ".state.json")


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {"waves": {}, "builders": {}, "approvals": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    # Write-then-rename: a restart mid-write must find the old state or the new
    # one, never half of either.
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def split_cmd(cmd: str) -> list:
    return shlex.split(cmd, posix=os.name != "nt")


# --- authored steps ----------------------------------------------------------------

def step_path(name: str, node_id: str, runtime: str) -> str:
    """Repository-relative, POSIX separators: the one place a step lives."""
    return f".claude/workflows/{name}.steps/{node_id}.{AUTHORABLE[runtime]['ext']}"


def contract_digest(node: dict) -> str:
    """What an author was asked to meet. A verified step whose node changed any
    of this since is STALE -- re-authored, never silently reused. The vendored
    guard carries a byte-identical copy; test_authored_steps.py proves they agree."""
    sc = node.get("script") or {}
    body = {"command": sc.get("command"), "expectExit": sc.get("expectExit"),
            "parse": sc.get("parse"), "runtime": sc.get("runtime"), "author": sc.get("author"),
            "output_schema": node.get("output_schema")}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authored_nodes(plan: dict) -> list:
    return [n for n in plan.get("nodes") or []
            if isinstance(n, dict) and isinstance((n.get("script") or {}).get("author"), dict)]


def step_status(root: Path, plan: dict, state: dict) -> dict:
    """{node id: {status, path, sha256?}} for every authored step, computed from
    the file on disk, the plan and the state -- never from memory."""
    out = {}
    for n in authored_nodes(plan):
        rel = step_path(plan["name"], n["id"], n["script"]["runtime"])
        path = root / rel
        rec = (state.get("steps") or {}).get(n["id"])
        if not path.is_file():
            status, sha = "missing", None
        else:
            sha = file_sha(path)
            if STUB_MARKER in path.read_text(encoding="utf-8", errors="replace"):
                status = "stub"
            elif not rec:
                status = "authored"
            elif rec.get("sha256") != sha or rec.get("contract") != contract_digest(n):
                status = "stale"
            else:
                status = "verified"
        out[n["id"]] = {"status": status, "path": rel, **({"sha256": sha} if sha else {})}
    return out


def schema_problems(schema: object, value: object, where: str = "stdout") -> list:
    """The strict-schema check waves.js applies to `parsed`, restated: a step
    that verified here must not fail there."""
    if not isinstance(schema, dict):
        return [f"{where}: no schema to validate against"]
    types = schema.get("type")
    types = types if isinstance(types, list) else [types] if types else []

    def type_of(v: object) -> str:
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "boolean"
        if isinstance(v, int):
            return "integer"
        if isinstance(v, float):
            return "number"
        return {str: "string", list: "array", dict: "object"}.get(type(v), "unknown")

    t = type_of(value)
    if types and not any(x == t or (x == "number" and t == "integer") for x in types):
        return [f"{where}: expected {'|'.join(types)}, got {t}"]
    if isinstance(schema.get("enum"), list) and value not in schema["enum"]:
        return [f"{where}: not one of the enum values"]
    out: list = []
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        out += [f"{where}.{k}: required, missing" for k in schema.get("required") or []
                if k not in value]
        for k, v in value.items():
            if k in props:
                out += schema_problems(props[k], v, f"{where}.{k}")
            elif schema.get("additionalProperties") is False:
                out.append(f"{where}.{k}: not declared")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for j, v in enumerate(value):
            out += schema_problems(schema["items"], v, f"{where}[{j}]")
    return out


def _interpreter(cmd: str, rel: str) -> list:
    """Everything the command puts before the step path: the interpreter and
    its flags (`pwsh -NoProfile -File`, a resolved `py -3`)."""
    argv = split_cmd(cmd)
    return argv[:argv.index(rel)] if rel in argv else []


def syntax_problem(runtime: str, interp: list, path: Path) -> str | None:
    check = AUTHORABLE[runtime]["check"]
    if check is None:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (SyntaxError, ValueError) as exc:
            return f"syntax: {exc}"
        return None
    argv = [a.replace("{exe}", interp[0]).replace("{path}", str(path)) for a in check]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        return f"syntax: {interp[0]!r} is not installed -- preflight the toolchain first"
    except subprocess.TimeoutExpired:
        return "syntax: the check timed out"
    if proc.returncode != 0:
        return f"syntax: {(proc.stderr or proc.stdout).strip()[-600:]}"
    return None


def verify_step(root: Path, plan: dict, state: dict, node_id: str) -> tuple:
    node = next((n for n in authored_nodes(plan) if n["id"] == node_id), None)
    if node is None:
        raise HelperError(f"{node_id!r} is not an authored script node of plan {plan['name']}")
    sc = node["script"]
    rel = step_path(plan["name"], node_id, sc["runtime"])
    path = root / rel

    def fail(problem: str) -> tuple:
        (state.setdefault("steps", {})).pop(node_id, None)
        return {"verified": False, "node": node_id, "path": rel, "problem": problem}, 1

    if not path.is_file():
        return fail(f"{rel} does not exist -- the author wrote nothing")
    text = path.read_text(encoding="utf-8", errors="replace")
    if STUB_MARKER in text:
        return fail(f"{rel} still carries {STUB_MARKER}: it is the skeleton, not a step")
    interp = _interpreter(sc["command"], rel)
    if not interp:
        return fail(f"the node's command does not run {rel}")
    bad = syntax_problem(sc["runtime"], interp, path)
    if bad:
        return fail(bad)
    before = file_sha(path)
    sample = sc["author"].get("sample") or {}
    with tempfile.TemporaryDirectory(prefix=f"{plan['name']}-step-") as tmp:
        tree = Path(tmp) / "tree"
        git("worktree", "add", "--detach", str(tree), "HEAD", cwd=root)
        try:
            # The steps directory is gitignored, so the clean tree lacks it:
            # copy the one file under test to the same relative path.
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            (tree / rel).write_bytes(path.read_bytes())
            try:
                proc = subprocess.run([*interp, rel, *sample.get("args", [])], cwd=tree,
                                      capture_output=True, text=True, timeout=STEP_TIMEOUT)
            except FileNotFoundError:
                return fail(f"sample: {interp[0]!r} is not installed")
            except subprocess.TimeoutExpired:
                return fail(f"sample: no exit within {STEP_TIMEOUT}s")
        finally:
            git("worktree", "remove", "--force", str(tree), cwd=root, check=False)
    if file_sha(path) != before:
        return fail(f"{rel} changed while its sample ran")
    if proc.returncode not in sample.get("expectExit", [0]):
        return fail(f"sample: exit {proc.returncode}, expected one of {sample.get('expectExit')};"
                    f" stderr: {proc.stderr.strip()[-400:]}")
    if sc.get("parse") != "exit-only":
        try:
            parsed = json.loads(proc.stdout.strip() or "null")
        except json.JSONDecodeError:
            return fail(f"sample: stdout is not ONE JSON object: {proc.stdout.strip()[-300:]!r}")
        probs = schema_problems(node.get("output_schema"), parsed)
        if probs:
            return fail("sample: stdout breaks output_schema: " + "; ".join(probs[:3]))
    state.setdefault("steps", {})[node_id] = {"sha256": before, "contract": contract_digest(node),
                                              "runtime": sc["runtime"]}
    return {"verified": True, "node": node_id, "path": rel, "problem": ""}, 0


# --- preflight -------------------------------------------------------------------

def preflight(root: Path) -> dict:
    git_dir = (root / out("rev-parse", "--git-dir", cwd=root)).resolve()
    common = (root / out("rev-parse", "--git-common-dir", cwd=root)).resolve()
    dirty = bool(out("status", "--porcelain", "--untracked-files=no", cwd=root))
    return {"linkedWorktree": git_dir != common, "dirty": dirty,
            "head": out("rev-parse", "HEAD", cwd=root), "python": sys.version.split()[0]}


# --- record ----------------------------------------------------------------------

def record(root: Path, state: dict, row: str, branch: str, base: str) -> dict:
    head = out("rev-parse", branch, cwd=root)
    notes = [ln for ln in out("log", "--format=%B", f"{base}..{branch}", cwd=root).splitlines()
             if ln.strip()]
    state.setdefault("builders", {})[row] = {"branch": branch, "base": base, "head": head,
                                             "notes": notes}
    return {"recorded": True, "row": row, "head": head}


# --- merge and gate --------------------------------------------------------------

def _pairs(spec: str) -> list:
    pairs = []
    for item in spec.split(","):
        row, sep, branch = item.partition("=")
        if not sep or not row or not branch:
            raise HelperError(f"--branches wants row=branch,...; got {item!r}")
        pairs.append((row, branch))
    return pairs


def _worktrees(root: Path) -> dict:
    """branch name -> worktree path, from `git worktree list --porcelain`."""
    found, path = {}, None
    for line in out("worktree", "list", "--porcelain", cwd=root).splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line.startswith("branch refs/heads/") and path:
            found[line[len("branch refs/heads/"):]] = path
    return found


def run_gates(gates: list, cwd: Path) -> dict:
    results = {}
    for g in gates:
        try:
            proc = subprocess.run(split_cmd(g["command"]), cwd=cwd, capture_output=True,
                                  text=True, timeout=GATE_TIMEOUT)
            results[g["id"]] = proc.returncode
        except FileNotFoundError:
            results[g["id"]] = 127
        except subprocess.TimeoutExpired:
            results[g["id"]] = 124
    return results


def _cleanup(root: Path, branches: list, merged: set) -> list:
    """Remove each branch's worktree and the branch -- preserve-then-remove: a
    worktree with uncommitted work is KEPT and named, never deleted."""
    kept = []
    trees = _worktrees(root)
    for b in branches:
        path = trees.get(b)
        if path and Path(path).resolve() != root.resolve():
            if out("status", "--porcelain", cwd=Path(path)):
                kept.append(f"{b} (uncommitted work in {path})")
                continue
            git("worktree", "remove", path, cwd=root)
        git("branch", "-d" if b in merged else "-D", b, cwd=root, check=False)
    return kept


def merge(root: Path, plan: dict, state: dict, wave: int, stage: str, final: bool,
          branches: str, discard: str) -> tuple:
    integ = plan["integration"]["branch"]
    target = plan["integration"]["target"]
    pairs = _pairs(branches)
    losers = [] if discard == "none" else [d for d in discard.split(",") if d]
    findings: list = []
    original = out("rev-parse", "--abbrev-ref", "HEAD", cwd=root)

    if git("rev-parse", "--verify", "--quiet", f"refs/heads/{integ}", cwd=root,
           check=False).returncode != 0:
        git("branch", integ, target, cwd=root)
    try:
        git("switch", integ, cwd=root)
        for row, branch in pairs:
            proc = git("merge", "--no-ff", "--no-edit", "-m",
                       f"arbeitsplan {plan['name']} wave {wave} stage {stage}: {row} ({branch})",
                       branch, cwd=root, check=False)
            if proc.returncode != 0:
                git("merge", "--abort", cwd=root, check=False)
                findings.append({"gate": f"merge:{row}", "source": "both", "exit": proc.returncode})
                break
        integ_sha = out("rev-parse", "HEAD", cwd=root)

        if not findings and final:
            primary = run_gates(plan["gates"], root)
            with tempfile.TemporaryDirectory(prefix=f"{plan['name']}-gate-") as tmp:
                clean_dir = Path(tmp) / "tree"
                git("worktree", "add", "--detach", str(clean_dir), integ_sha, cwd=root)
                try:
                    clean = run_gates(plan["gates"], clean_dir)
                finally:
                    git("worktree", "remove", "--force", str(clean_dir), cwd=root, check=False)
            for g in plan["gates"]:
                p, c = primary[g["id"]], clean[g["id"]]
                if p or c:
                    source = "both" if p and c else "primary-only" if p else "clean-only"
                    findings.append({"gate": g["id"], "source": source, "exit": p or c})
    finally:
        git("switch", original, cwd=root, check=False)

    green = not findings
    target_moved = False
    kept: list = []
    wave_branches = [b for _r, b in pairs]
    if green and final:
        old = out("rev-parse", target, cwd=root)
        if git("merge-base", "--is-ancestor", old, integ_sha, cwd=root,
               check=False).returncode != 0:
            findings.append({"gate": f"fast-forward:{target}", "source": "both", "exit": 1})
            green = False
        else:
            if original == target:
                # The primary checkout has the target checked out: move it the
                # way a user would, so the working tree follows the ref.
                git("merge", "--ff-only", integ_sha, cwd=root)
            else:
                git("update-ref", f"refs/heads/{target}", integ_sha, old, cwd=root)
            target_moved = True
            rows_of_wave = [n["id"] for n in plan["nodes"]
                            if n.get("wave") == wave and n.get("kind") == "agent"]
            merged = {state["builders"][r]["branch"] for r in rows_of_wave
                      if r in state.get("builders", {})} | set(wave_branches)
            kept = _cleanup(root, sorted(merged) + losers, merged)
            state.setdefault("waves", {})[str(wave)] = {"status": "done",
                                                         "integrationSha": integ_sha}
    if not green:
        kept = sorted(set(wave_branches + losers))
    # Every gate outcome is kept, red ones too: the report (build_design_html.py)
    # shows where a run stopped from this, not from memory.
    state.setdefault("gates", {})[f"{wave}:{stage}"] = {"green": green, "final": final,
                                                        "integrationSha": integ_sha,
                                                        "findings": findings}
    return ({"green": green, "integrationSha": integ_sha, "targetMoved": target_moved,
             "findings": findings, "kept": kept}, 0 if green else 1)


# --- CLI -------------------------------------------------------------------------

def main(argv: list) -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}; running "
              f"{sys.version.split()[0]} ({sys.executable})", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(prog=Path(__file__).name, description=(
        __doc__ or "").split("\n\n")[0], epilog="exit 0 ok, 1 red gate, 2 refused or defect")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preflight", help="primary-checkout and cleanliness check")
    r = sub.add_parser("record", help="record a finished builder")
    r.add_argument("--row", required=True)
    r.add_argument("--branch", required=True)
    r.add_argument("--base", required=True)
    m = sub.add_parser("merge", help="merge a stage; gate and move the target on the final one")
    m.add_argument("--wave", type=int, required=True)
    m.add_argument("--stage", required=True)
    m.add_argument("--final", choices=["0", "1"], required=True)
    m.add_argument("--branches", required=True)
    m.add_argument("--discard", default="none")
    a = sub.add_parser("approve", help="record a human gate's approval")
    a.add_argument("--gate", required=True)
    v = sub.add_parser("verify-step", help="check and sample-run one authored step")
    v.add_argument("--node", required=True)
    sub.add_parser("show", help="print the state")
    sub.add_parser("selftest", help="run against scratch git repositories")
    args = parser.parse_args(argv)

    if args.cmd == "selftest":
        return selftest()
    helper = Path(__file__).resolve()
    try:
        root = repo_root(Path.cwd())
        spath = state_path(helper)
        state = load_state(spath)
        if args.cmd == "preflight":
            result, code = preflight(root), 0
        elif args.cmd == "show":
            plan = json.loads(plan_path(helper).read_text(encoding="utf-8"))
            result, code = {**state, "steps": step_status(root, plan, state)}, 0
        elif args.cmd == "approve":
            state.setdefault("approvals", {})[args.gate] = True
            save_state(spath, state)
            result, code = {"approved": args.gate}, 0
        else:
            plan = json.loads(plan_path(helper).read_text(encoding="utf-8"))
            if args.cmd == "record":
                result, code = record(root, state, args.row, args.branch, args.base), 0
            elif args.cmd == "verify-step":
                result, code = verify_step(root, plan, state, args.node)
            else:
                result, code = merge(root, plan, state, args.wave, args.stage,
                                     args.final == "1", args.branches, args.discard)
            save_state(spath, state)
    except (HelperError, OSError, ValueError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return code


# --- selftest --------------------------------------------------------------------

def selftest() -> int:
    fails: list = []

    def check(name: str, cond: bool, detail: object = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)
            if detail != "":
                print(f"       {str(detail)[:300]}")

    py = shlex.quote(sys.executable)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        env_git = ("-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=trunk")

        def g(*args: str, cwd: Path = root) -> str:
            return subprocess.run(["git", *env_git, *args], cwd=cwd, capture_output=True,
                                  text=True, check=True).stdout.strip()

        g("init")
        (root / "a.txt").write_text("a\n")
        (root / ".gitignore").write_text("leftover.tmp\n.claude/workflows/*.state.json\n")
        g("add", "-A")
        g("commit", "-m", "init")
        wf = root / ".claude" / "workflows"
        wf.mkdir(parents=True)
        helper = wf / "demo_state.py"
        helper.write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
        plan = {"name": "demo", "integration": {"branch": "integration/demo", "target": "trunk"},
                "gates": [{"id": "leftover", "runtime": "python", "command":
                           f"{py} -c \"import os,sys; sys.exit(os.path.exists('leftover.tmp'))\""},
                          {"id": "has-b", "runtime": "python", "command":
                           f"{py} -c \"import os,sys; sys.exit(not os.path.exists('b.txt'))\""}],
                "nodes": [{"id": "w1-b", "kind": "agent", "wave": 1},
                          {"id": "w1-c", "kind": "agent", "wave": 1}]}
        (wf / "demo.plan.json").write_text(json.dumps(plan))
        g("add", "-A")
        g("commit", "-m", "install")

        # The helper's merges commit; a CI runner has no git identity of its own.
        ident = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                 "GIT_CONFIG_GLOBAL": os.devnull}

        def run(*args: str, cwd: Path = root) -> tuple:
            p = subprocess.run([sys.executable, str(helper), *args], cwd=cwd,
                               capture_output=True, text=True, env=ident)
            try:
                return p.returncode, json.loads(p.stdout or "null"), p.stderr
            except json.JSONDecodeError:
                return p.returncode, None, p.stdout + p.stderr

        code, res, err = run("preflight")
        check("preflight in the primary checkout: not linked, not dirty",
              code == 0 and res and not res["linkedWorktree"] and not res["dirty"], (res, err))
        base = res["head"] if res else ""
        linked = Path(tmp) / "linked"
        g("worktree", "add", str(linked), "-b", "side")
        code, res, err = run("preflight", cwd=linked)
        check("preflight in a linked worktree reports it", code == 0 and res
              and res["linkedWorktree"] is True, (res, err))
        g("worktree", "remove", str(linked))
        g("branch", "-D", "side")

        for row, fname in (("w1-b", "b.txt"), ("w1-c", "c.txt")):
            tree = Path(tmp) / row
            g("worktree", "add", str(tree), "-b", f"agent/{row}")
            (tree / fname).write_text(row)
            g("add", "-A", cwd=tree)
            g("commit", "-m", f"{row}: add {fname}\n\nnote from {row}", cwd=tree)
        code, res, err = run("record", "--row", "w1-b", "--branch", "agent/w1-b", "--base", base)
        state = json.loads((wf / "demo.state.json").read_text())
        check("record keeps the builder's branch and commit notes",
              code == 0 and "note from w1-b" in state["builders"]["w1-b"]["notes"], (state, err))

        (root / "leftover.tmp").write_text("stale")
        code, res, err = run("merge", "--wave", "1", "--stage", "0", "--final", "1",
                             "--branches", "w1-b=agent/w1-b,w1-c=agent/w1-c", "--discard", "none")
        check("a gate red only in the primary checkout is labelled primary-only",
              code == 1 and res and any(f["gate"] == "leftover" and f["source"] == "primary-only"
                                        for f in res["findings"]), (res, err))
        check("red: the target does not move", g("rev-parse", "trunk") == base
              and res and res["targetMoved"] is False)
        check("red: every row branch is kept and named", res and "agent/w1-b" in res["kept"]
              and "agent/w1-c" in res["kept"], res)
        check("red: the primary checkout is back on its own branch",
              g("rev-parse", "--abbrev-ref", "HEAD") == "trunk")
        check("red: the wave is not marked done",
              "1" not in json.loads((wf / "demo.state.json").read_text()).get("waves", {}))

        (root / "leftover.tmp").unlink()
        code, res, err = run("merge", "--wave", "1", "--stage", "0", "--final", "1",
                             "--branches", "w1-b=agent/w1-b,w1-c=agent/w1-c", "--discard", "none")
        check("green: merged and gated", code == 0 and res and res["green"], (res, err))
        check("green: the target fast-forwarded to the integration head",
              res and g("rev-parse", "trunk") == res["integrationSha"] and res["targetMoved"])
        check("green: the primary checkout's tree followed its moved branch",
              (root / "b.txt").is_file() and (root / "c.txt").is_file())
        check("green: merged row worktrees and branches are cleaned up",
              "agent/w1-b" not in g("branch", "--list", "agent/*"))
        state = json.loads((wf / "demo.state.json").read_text())
        check("green: the wave is recorded done with its integration sha",
              state["waves"]["1"]["status"] == "done", state)

        code, res, err = run("merge", "--wave", "2", "--stage", "0", "--final", "0",
                             "--branches", "bad-no-equals")
        check("malformed --branches is refused with exit 2", code == 2, (code, err))
        code, res, err = run("approve", "--gate", "approve-1")
        check("approve records a human gate", code == 0 and json.loads(
            (wf / "demo.state.json").read_text())["approvals"]["approve-1"] is True)

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("waves_state selftest passed (scratch git repositories, no network)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
