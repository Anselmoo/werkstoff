#!/usr/bin/env python3
"""zeugnis-mutation-harden harness (issue #142): run a REAL mutation tool on
fresh `git archive HEAD` copies, collect what it produced, prove each killing
test against its mutant, and report score per module before and after.

Long runs are measurement, so they are this script's job, never an agent's:
`run-shard` is launched in the background and agents read the files it
leaves. Every subcommand that starts the tool first checks that its working
directory is a marker-bearing copy (lib.mutation_scope.copy_root_for) -- the
PreToolUse hook never sees a subprocess, so this check IS the enforcement for
script-driven runs.

Subcommands (all paths repo-relative; layout under
analysis/zeugnis/mutation/<runId>/):

    prepare   <repo> --run-id R --shard S --source P... --test T...
              [--exclude 'GLOB=reason'...]            -> shards/S/ (copy)
    prepare   <repo> --run-id R --shard S --kind remeasure --overlay T...
                                                       -> remeasure/S/ (copy)
    run-shard <repo> --run-id R --shard S [--kind remeasure] --time-box SECONDS
              [--mutmut PATH] [--max-children N]       -> records/<kind>-S.run.json
    collect   <repo> --run-id R --shard S [--kind remeasure] [--diff-limit N]
                                                       -> records/<kind>-S.results.json
    prove     <repo> --run-id R --shard S --mutant ID --test-file F --test-id F::name
              [--python PATH] [--mutmut PATH]          -> records/proof-<ID>.json
    report    <repo> --run-id R --triage triage.json   -> mutation_harden_summary.json,
                                                          reports/MUTATION_HARDEN.md,
                                                          records/pass.json

Only mutmut 3 (Python) is driven. Its behaviour was checked against mutmut
3.8.1: `run` writes ./mutants/ in the cwd and resumes leftover state there,
`apply NAME` rewrites the source file, per-mutant results live in
`mutants/<source>.meta` (`exit_code_by_key`), and `run` does NOT write
mutmut-cicd-stats.json. Other tools are documented in
references/mutation-tools.md, not driven.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tomllib
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))

from lib.ledger import load_ledger
from lib.mutation_results import (
    COUNT_KEYS,
    PROOF_SCHEMA,
    RESULTS_SCHEMA,
    MutationResultsError,
    empty_counts,
    load_proof,
    mutmut_status,
    read_mutmut_meta,
    score,
    sha256_file,
    verify_citation,
)
from lib.mutation_scope import (
    COPY_MARKER,
    MUTATION_DIR_PARTS,
    NAME_RE,
    PROTECTED_BASENAMES,
    MutationScopeError,
    check_name,
    copy_root_for,
    is_within,
    lexical_path,
    repo_relative,
)

SHARD_SCHEMA = "zeugnis/mutation-shard/1"
SUMMARY_SCHEMA = "zeugnis/mutation-harden-summary/1"
# Mutants a killing test can target: the tests let them through, or never ran them.
TARGET_STATUSES = ("survived", "no tests")
# Keys the shard rewrites in the copy's [tool.mutmut]; the deprecated
# paths_to_mutate/tests_dir are dropped so they cannot widen the shard.
OVERRIDDEN_KEYS = {"source_paths", "paths_to_mutate", "tests_dir", "pytest_add_cli_args_test_selection", "do_not_mutate"}
RE_TOML_HEADER = re.compile(r"^\s*\[\[?\s*[A-Za-z0-9_\-\"'.\s]+\]\]?\s*(#.*)?$")
RE_MUTMUT_HEADER = re.compile(r"^\s*\[\s*tool\s*\.\s*mutmut\s*\]\s*(#.*)?$")
RE_TOKEN = re.compile(r"<=|>=|==|!=|\*\*|//|\w+|\S")
TAIL_LINES = 30


class HarnessError(Exception):
    """A refusal: printed as {"error": ...} with exit code 2."""


# ---------------------------------------------------------------- layout


def now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


def run_dir(repo: Path, run_id: str) -> Path:
    return repo.joinpath(*MUTATION_DIR_PARTS, check_name(run_id, "run id"))


def records_dir(repo: Path, run_id: str) -> Path:
    return run_dir(repo, run_id) / "records"


def rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise HarnessError(f"{label} {path} does not exist; run the earlier subcommand first")
    return json.loads(path.read_text(encoding="utf-8"))


def require_copy(path: Path) -> Path:
    """The tool may only run in a marker-bearing copy (module docstring)."""
    root = copy_root_for(path)
    if root is None or root != lexical_path(path, "."):
        raise HarnessError(f"{path} is not a prepared mutation copy; refusing to run a mutation tool there")
    return root


def tail(text: str) -> str:
    return "\n".join(text.splitlines()[-TAIL_LINES:])


def find_mutmut(explicit: str | None) -> str:
    found = explicit or shutil.which("mutmut")
    if not found or not Path(found).is_file():
        raise HarnessError("mutmut not found: pass --mutmut PATH (install it in the project's test environment)")
    return str(Path(found).absolute())


def find_python(explicit: str | None, mutmut: str) -> str:
    """mutmut runs pytest in-process, so its own interpreter is the one with
    the project's test dependencies."""
    if explicit:
        return explicit
    sibling = Path(mutmut).parent / "python"
    return str(sibling) if sibling.exists() else sys.executable


# ---------------------------------------------------------------- prepare


def toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)  # a JSON string is a valid TOML basic string
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    raise HarnessError(f"cannot write {value!r} into [tool.mutmut]")


def strip_mutmut_table(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if RE_MUTMUT_HEADER.match(line):
            skipping = True
            continue
        if skipping and RE_TOML_HEADER.match(line):
            skipping = False
        if not skipping:
            out.append(line)
    return "".join(out)


def write_mutmut_config(copy: Path, sources: list[str], tests: list[str], globs: list[str]) -> dict:
    """Rewrite ONLY the copy's [tool.mutmut] (pyproject wins over setup.cfg in
    mutmut 3.8.1). The rewrite is round-tripped through tomllib: a file whose
    other tables changed, or whose new table does not read back exactly, is a
    refusal -- an instrument that silently mis-writes its own config would
    measure the wrong shard."""
    pyproject = copy / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8") if pyproject.is_file() else ""
    data = tomllib.loads(text)
    existing = data.get("tool", {}).get("mutmut", {})
    if any(isinstance(v, dict) for v in existing.values()):
        raise HarnessError("pyproject.toml has [tool.mutmut.*] sub-tables; the harness cannot shard that config")
    stripped = strip_mutmut_table(text)
    expected_rest = json.loads(json.dumps(data))
    expected_rest.get("tool", {}).pop("mutmut", None)
    if not expected_rest.get("tool", True):
        expected_rest.pop("tool")
    rest = tomllib.loads(stripped)
    if not rest.get("tool", True):
        rest.pop("tool")
    if rest != expected_rest:
        raise HarnessError("removing [tool.mutmut] from the copy's pyproject.toml changed other tables; refusing")
    config = {k: v for k, v in existing.items() if k not in OVERRIDDEN_KEYS}
    config["source_paths"] = sources
    config["pytest_add_cli_args_test_selection"] = tests
    do_not_mutate = sorted(set(existing.get("do_not_mutate", [])) | set(globs))
    if do_not_mutate:
        config["do_not_mutate"] = do_not_mutate
    body = "".join(f"{key} = {toml_value(value)}\n" for key, value in config.items())
    new_text = stripped.rstrip() + ("\n\n" if stripped.strip() else "") + "[tool.mutmut]\n" + body
    if tomllib.loads(new_text).get("tool", {}).get("mutmut") != config:
        raise HarnessError("the rewritten [tool.mutmut] does not read back as written; refusing")
    pyproject.write_text(new_text, encoding="utf-8")
    return config


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise HarnessError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def archive_head(repo: Path, dest: Path) -> str:
    """Extract `git archive HEAD` into a NEW directory. Never reused: a stale
    config or a tool's leftover state in a reused copy is exactly what broke
    three shards in the run issue #142 describes."""
    head = git(repo, "rev-parse", "HEAD").strip()
    dest.mkdir(parents=True)
    proc = subprocess.Popen(["git", "-C", str(repo), "archive", "--format=tar", "HEAD"], stdout=subprocess.PIPE)
    assert proc.stdout is not None
    with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
        if hasattr(tarfile, "data_filter"):
            archive.extractall(dest, filter="data")
        else:  # CPython 3.11.0-3.11.3: no extraction filters; the archive is this repo's own HEAD
            archive.extractall(dest)
    if proc.wait() != 0:
        raise HarnessError("git archive HEAD failed")
    return head


def write_marker(copy: Path, run_id: str, kind: str, name: str, head: str) -> None:
    write_json(copy / COPY_MARKER, {"runId": run_id, "kind": kind, "name": name, "headSha": head,
                                    "createdAt": now_iso()})


def parse_exclusions(raw: list[str]) -> list[dict]:
    """`GLOB=reason`: an exclusion without a reason is refused -- code whose
    behaviour is pinned another way is excluded, and the report says why."""
    exclusions = []
    for item in raw:
        glob, sep, reason = item.partition("=")
        if not sep or not glob.strip() or not reason.strip():
            raise HarnessError(f"--exclude {item!r} must be GLOB=reason with a non-empty reason")
        if not (glob.endswith("*") or glob.endswith(".py")):
            raise HarnessError(f"--exclude glob {glob!r} must end in * or .py (mutmut do_not_mutate rule)")
        exclusions.append({"glob": glob.strip(), "reason": reason.strip()})
    return exclusions


def check_test_file(repo: Path, manifest: dict, relpath: str) -> Path:
    """A test file the harness may copy into a copy: under one of the shard's
    test paths, not under a source path, not a collection config file."""
    target = repo_relative(repo, relpath, "test file")
    if target.name in PROTECTED_BASENAMES:
        raise HarnessError(f"{relpath!r} configures collection or mutation; it is not a killing test")
    if any(is_within(target, repo_relative(repo, s, "source")) for s in manifest["sources"]):
        raise HarnessError(f"{relpath!r} is under a source path")
    if not any(is_within(target, repo_relative(repo, t, "test path")) for t in manifest["tests"]):
        raise HarnessError(f"{relpath!r} is not under the shard's test paths {manifest['tests']!r}")
    if not target.is_file():
        raise HarnessError(f"{relpath!r} does not exist in the working tree")
    return target


def cmd_prepare(args, repo: Path) -> dict:
    shard = check_name(args.shard, "shard")
    records = records_dir(repo, args.run_id)
    manifest_path = records / f"{shard}.shard.json"
    copy = run_dir(repo, args.run_id) / args.kind / shard
    if copy.exists():
        raise HarnessError(f"{rel(repo, copy)} already exists; every run gets a fresh copy (use a new --run-id)")
    if args.kind == "shards":
        if manifest_path.exists():
            raise HarnessError(f"shard {shard!r} is already prepared in run {args.run_id!r}")
        if not args.source or not args.test:
            raise HarnessError("prepare needs at least one --source and one --test")
        for path in (*args.source, *args.test):
            repo_relative(repo, path, "path")
        dirty = git(repo, "status", "--porcelain", "--", *args.source).strip()
        if dirty:
            raise HarnessError(f"source paths have uncommitted changes; the copy is HEAD, so commit them first:\n{dirty}")
        manifest = {"schema": SHARD_SCHEMA, "runId": args.run_id, "shard": shard, "tool": "mutmut",
                    "sources": args.source, "tests": args.test, "exclusions": parse_exclusions(args.exclude),
                    "createdAt": now_iso()}
        overlays: list[str] = []
    else:
        manifest = read_json(manifest_path, "shard manifest")
        if not args.overlay:
            raise HarnessError("a remeasure copy needs the new test files: pass --overlay for each")
        overlays = args.overlay
        for path in overlays:
            check_test_file(repo, manifest, path)
    head = archive_head(repo, copy)
    for path in overlays:
        dest = copy / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / path, dest)
    config = write_mutmut_config(copy, manifest["sources"], manifest["tests"],
                                 [e["glob"] for e in manifest["exclusions"]])
    write_marker(copy, args.run_id, args.kind, shard, head)
    require_copy(copy)
    if args.kind == "shards":
        manifest["headSha"] = head
        write_json(manifest_path, manifest)
    else:
        write_json(records / f"remeasure-{shard}.overlay.json",
                   {"overlays": [{"path": p, "sha256": sha256_file(repo / p)} for p in overlays],
                    "headSha": head, "createdAt": now_iso()})
    return {"copyRoot": rel(repo, copy), "headSha": head, "mutmutConfig": config, "overlays": overlays}


# ---------------------------------------------------------------- run-shard


def mutmut_version(mutmut: str, cwd: Path) -> str:
    # mutmut 3 loads its config on import, so even --version must run in the copy.
    out = subprocess.run([mutmut, "--version"], cwd=cwd, capture_output=True, text=True, check=False)
    match = re.search(r"version\s+(\S+)", out.stdout)
    return match.group(1) if match else "unknown"


def target_ids(repo: Path, run_id: str, shard: str) -> list[str]:
    baseline = read_json(records_dir(repo, run_id) / f"shards-{shard}.results.json", "baseline results")
    return [m["id"] for m in baseline["mutants"] if m["status"] in TARGET_STATUSES]


def cmd_run_shard(args, repo: Path) -> dict:
    shard = check_name(args.shard, "shard")
    copy = require_copy(run_dir(repo, args.run_id) / args.kind / shard)
    if (copy / "mutants").exists():
        raise HarnessError(f"{rel(repo, copy)}/mutants exists; a copy is run once, never resumed")
    mutmut = find_mutmut(args.mutmut)
    names = target_ids(repo, args.run_id, shard) if args.kind == "remeasure" else []
    record_path = records_dir(repo, args.run_id) / f"{args.kind}-{shard}.run.json"
    log_path = record_path.with_suffix(".log")
    command = [mutmut, "run", *(["--max-children", str(args.max_children)] if args.max_children else []), *names]
    record = {"state": "running", "pid": os.getpid(), "startedAt": now_iso(), "timeBoxSeconds": args.time_box,
              "toolVersion": mutmut_version(mutmut, copy), "mutants": names, "log": rel(repo, log_path)}
    write_json(record_path, record)
    if args.kind == "remeasure" and not names:
        record.update(state="finished", exitCode=0, finishedAt=now_iso(), note="no survivors to remeasure")
        write_json(record_path, record)
        return record
    timed_out = False
    started = datetime.datetime.now(datetime.UTC)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(command, cwd=copy, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            exit_code = proc.wait(timeout=args.time_box)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                exit_code = proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                exit_code = proc.wait()
    record.update(state="timed-out" if timed_out else "finished", exitCode=exit_code, finishedAt=now_iso(),
                  durationSeconds=round((datetime.datetime.now(datetime.UTC) - started).total_seconds(), 1))
    write_json(record_path, record)
    return record


# ---------------------------------------------------------------- collect


def classify(diff: str) -> str:
    """A triage hint from the diff's first -/+ pair, labelled as a heuristic
    in the results: comparison, boolean-logic, constant, None, string."""
    removed = [ln[1:] for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    added = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    if not removed or not added:
        return "other"
    old, new = Counter(RE_TOKEN.findall(removed[0])), Counter(RE_TOKEN.findall(added[0]))
    gained = new - old
    if "None" in gained:
        return "value-replaced-by-None"
    if not gained:
        return "code-removed"
    if any(t in gained for t in ("<", ">", "<=", ">=", "==", "!=", "is", "in")):
        return "comparison"
    if any(t in gained for t in ("and", "or", "not", "True", "False")):
        return "boolean-logic"
    if any(t.startswith(("XX", '"', "'")) or t in ('"', "'") for t in gained) or "XX" in added[0]:
        return "string-literal"
    if any(t.isdigit() for t in gained):
        return "constant"
    if any(t in gained for t in ("+", "-", "*", "/", "%", "**", "//")):
        return "arithmetic"
    return "other"


def locate_line(source: Path, diff: str) -> int | None:
    """The 1-based line in `source` of the diff's first removed line.

    mutmut 3's `show` prints a hunk relative to the mutated FUNCTION, not the
    file, so its `@@` numbers are not file lines. The first source line whose
    text matches is taken; a line repeated verbatim in one file can therefore
    point at its first occurrence, which the evidence still names correctly.
    """
    removed = next((ln[1:].strip() for ln in diff.splitlines()
                    if ln.startswith("-") and not ln.startswith("---") and ln[1:].strip()), None)
    if removed is None or not source.is_file():
        return None
    for number, text in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if text.strip() == removed:
            return number
    return None


def walk_meta(mutants_dir: Path) -> list[Path]:
    """Every .meta under mutants/. os.walk with onerror=raise, because
    Path.glob swallows PermissionError and would report 'no results'."""
    def _raise(exc: OSError) -> None:
        raise exc
    found = []
    for dirpath, _, files in os.walk(mutants_dir, onerror=_raise):
        found += [Path(dirpath) / f for f in files if f.endswith(".meta")]
    return sorted(found)


def cmd_collect(args, repo: Path) -> dict:
    shard = check_name(args.shard, "shard")
    copy = require_copy(run_dir(repo, args.run_id) / args.kind / shard)
    records = records_dir(repo, args.run_id)
    run_record = read_json(records / f"{args.kind}-{shard}.run.json", "run record")
    if run_record["state"] == "running":
        raise HarnessError("run-shard is still running (or was killed before it wrote its result); collect after it ends")
    manifest = read_json(records / f"{shard}.shard.json", "shard manifest")
    mutmut = find_mutmut(args.mutmut)
    wanted = set(run_record.get("mutants") or [])
    mutants, tool_files = [], []
    modules: dict[str, dict] = {}
    mutants_dir = copy / "mutants"
    for meta in walk_meta(mutants_dir) if mutants_dir.is_dir() else []:
        module = meta.relative_to(mutants_dir).as_posix()[: -len(".meta")]
        codes = read_mutmut_meta(meta)
        tool_files.append({"path": rel(repo, meta), "sha256": sha256_file(meta)})
        for mutant_id, code in sorted(codes.items()):
            if wanted and mutant_id not in wanted:
                continue
            status = mutmut_status(code)
            counts = modules.setdefault(module, empty_counts())
            counts[COUNT_KEYS.get(status, "suspicious")] += 1
            mutants.append({"id": mutant_id, "module": module, "status": status, "exitCode": code,
                            "toolFile": rel(repo, meta)})
    shown = 0
    for mutant in mutants:
        if mutant["status"] not in TARGET_STATUSES or shown >= args.diff_limit:
            continue
        out = subprocess.run([mutmut, "show", mutant["id"]], cwd=copy, capture_output=True, text=True, check=False)
        diff = out.stdout[:4000]
        mutant.update(diff=diff, kindHeuristic=classify(diff), line=locate_line(copy / mutant["module"], diff))
        shown += 1
    totals = empty_counts()
    for counts in modules.values():
        for key, value in counts.items():
            totals[key] += value
    complete = run_record["state"] == "finished" and totals["notChecked"] == 0 and bool(mutants)
    results = {
        "schema": RESULTS_SCHEMA, "producedBy": "zeugnis mutation_harden.py collect", "tool": "mutmut",
        "toolVersion": run_record.get("toolVersion"), "runId": args.run_id, "shard": shard, "kind": args.kind,
        "headSha": read_json(copy / COPY_MARKER, "marker").get("headSha"), "copyRoot": rel(repo, copy),
        "state": run_record["state"], "complete": complete, "toolFiles": tool_files,
        "modules": {m: {**c, "score": score(c)} for m, c in sorted(modules.items())},
        "totals": {**totals, "score": score(totals)}, "mutants": mutants, "exclusions": manifest["exclusions"],
        "diffsShown": shown, "diffsOmitted": max(0, sum(m["status"] in TARGET_STATUSES for m in mutants) - shown),
    }
    if not mutants:
        results["logTail"] = tail((repo / run_record["log"]).read_text(encoding="utf-8", errors="replace"))
    out_path = records / f"{args.kind}-{shard}.results.json"
    write_json(out_path, results)
    return {"resultsFile": rel(repo, out_path), "complete": complete, "totals": results["totals"]}


# ---------------------------------------------------------------- prove


def proof_name(records: Path, mutant_id: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", mutant_id).strip("-.")[:80] or "mutant"
    name, n = base, 1
    while (records / f"proof-{name}.json").exists() or not NAME_RE.match(name):
        n += 1
        name = f"{base}-{n}"
    return name


def dotted_module(mutant_id: str) -> str:
    """`shop.pricing` from mutmut 3's `shop.pricing.x_discount__mutmut_3` (or
    `shop.pricing.xǁCartǁtotal__mutmut_1` for a method)."""
    parts = mutant_id.split(".")
    for i, part in enumerate(parts):
        if part.startswith(("x_", "xǁ")):
            return ".".join(parts[:i])
    return ".".join(parts[:-1])


def import_root(copy: Path, module_file: str, dotted: str) -> Path:
    """The directory the copy's module is imported from: `src/shop/pricing.py`
    as `shop.pricing` -> `<copy>/src`. Falls back to the copy root when the
    file path does not end in the dotted name (a flat layout)."""
    path = Path(module_file)
    names = dotted.split(".")
    tail = [*names[:-1], names[-1] + ".py"] if path.name != "__init__.py" else [*names, "__init__.py"]
    if len(path.parts) >= len(tail) and list(path.parts[-len(tail):]) == tail:
        return copy.joinpath(*path.parts[: -len(tail)])
    return copy


def test_env(root: Path) -> dict:
    """PYTHONPATH with the copy's import root first. Without it a project
    installed editable (`pip install -e .`) imports the WORKING TREE's package
    from inside the copy, `mutmut apply` mutates a file the test never loads,
    and every real kill reads as 'survives'."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(root), env.get("PYTHONPATH", "")) if p)
    return env


def module_origin(python: str, dotted: str, cwd: Path, env: dict) -> Path | None:
    """Where `dotted` really imports from for the interpreter the test uses."""
    code = f"import importlib.util as u; s = u.find_spec({dotted!r}); print(s.origin if s else '')"
    out = subprocess.run([python, "-c", code], cwd=cwd, env=env, capture_output=True, text=True, check=False)
    origin = out.stdout.strip()
    return Path(origin) if out.returncode == 0 and origin else None


def imports_from_copy(origin: Path | None, copy: Path) -> bool:
    # resolve() is right HERE, unlike in lib.mutation_scope: this asks where
    # Python actually loads the file from (macOS /tmp is /private/tmp), not
    # whether a path is lexically inside a boundary.
    return origin is not None and origin.resolve().is_relative_to(copy.resolve())


def run_test(python: str, test_id: str, cwd: Path, timeout: int, env: dict | None = None) -> tuple[int, str]:
    try:
        out = subprocess.run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", test_id], cwd=cwd,
                             env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout}s"
    return out.returncode, tail(out.stdout + out.stderr)


def cmd_prove(args, repo: Path) -> dict:
    """Two runs of only the new test: unmutated it must pass (exit 0, which
    also rules out exit 5 'nothing collected'); with the mutant applied it
    must FAIL (exit 1). An import or collection error under the mutant is
    exit 2..4 and not a kill."""
    shard = check_name(args.shard, "shard")
    records = records_dir(repo, args.run_id)
    manifest = read_json(records / f"{shard}.shard.json", "shard manifest")
    baseline = read_json(records / f"shards-{shard}.results.json", "baseline results")
    mutant = next((m for m in baseline["mutants"] if m["id"] == args.mutant), None)
    if mutant is None or mutant["status"] not in TARGET_STATUSES:
        raise HarnessError(f"{args.mutant!r} is not a surviving or untested mutant of shard {shard!r}")
    test_path = check_test_file(repo, manifest, args.test_file)
    if args.test_id != args.test_file and not args.test_id.startswith(args.test_file + "::"):
        raise HarnessError(f"--test-id {args.test_id!r} must name a test in {args.test_file!r}")
    source_copy = require_copy(run_dir(repo, args.run_id) / "shards" / shard)
    if not (source_copy / "mutants").is_dir():
        raise HarnessError("the shard copy has no mutants/; run-shard it before proving")
    name = proof_name(records, args.mutant)
    proof_copy = run_dir(repo, args.run_id) / "proofs" / name
    shutil.copytree(source_copy, proof_copy, symlinks=True)
    write_marker(proof_copy, args.run_id, "proofs", name, read_json(source_copy / COPY_MARKER, "marker")["headSha"])
    require_copy(proof_copy)
    shutil.copyfile(test_path, proof_copy / args.test_file)
    mutmut = find_mutmut(args.mutmut)
    python = find_python(args.python, mutmut)
    module = proof_copy / mutant["module"]
    dotted = dotted_module(args.mutant)
    env = test_env(import_root(proof_copy, mutant["module"], dotted))
    origin = module_origin(python, dotted, proof_copy, env)
    original = sha256_file(module)
    clean_exit, clean_tail = run_test(python, args.test_id, proof_copy, args.timeout, env)
    applied = subprocess.run([mutmut, "apply", args.mutant], cwd=proof_copy, capture_output=True, text=True,
                             check=False)
    mutated = sha256_file(module)
    mutant_exit, mutant_tail = run_test(python, args.test_id, proof_copy, args.timeout, env)
    # A verdict is only about the mutant if the test imports the copy's module.
    if not imports_from_copy(origin, proof_copy):
        verdict = "invalid"
    elif clean_exit == 0 and mutant_exit == 1 and applied.returncode == 0 and mutated != original:
        verdict = "killed"
    elif clean_exit == 0 and mutant_exit == 0:
        verdict = "survives"
    else:
        verdict = "invalid"
    proof = {"schema": PROOF_SCHEMA, "runId": args.run_id, "shard": shard, "mutantId": args.mutant,
             "sourceFile": mutant["module"], "testFile": args.test_file, "testId": args.test_id,
             "testFileSha256": sha256_file(test_path), "cleanExit": clean_exit, "mutantExit": mutant_exit,
             "applyExit": applied.returncode, "originalSourceSha256": original, "mutatedSourceSha256": mutated,
             "verdict": verdict, "module": dotted, "importedFrom": str(origin) if origin else None,
             "importsFromCopy": imports_from_copy(origin, proof_copy), "cleanTail": clean_tail, "mutantTail": mutant_tail, "python": python,
             "createdAt": now_iso()}
    proof_path = records / f"proof-{name}.json"
    write_json(proof_path, proof)
    if not args.keep_copy:
        shutil.rmtree(proof_copy)
    return {"proofFile": rel(repo, proof_path), "verdict": verdict, "cleanExit": clean_exit,
            "mutantExit": mutant_exit}


# ---------------------------------------------------------------- report


def one_line_reason(reason) -> str | None:
    if not isinstance(reason, str):
        return None
    reason = reason.strip()
    return reason if reason and "\n" not in reason and len(reason) <= 200 else None


def load_results(repo: Path, run_id: str, kind: str, shard: str) -> dict | None:
    path = records_dir(repo, run_id) / f"{kind}-{shard}.results.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def judge_entry(repo: Path, entry: dict | None, target: dict, after_status: str | None) -> dict:
    """The final state of one target mutant. A kill counts only with a proof
    AND, when a remeasure ran, the tool agreeing; an equivalent never counts
    as a kill; a target with no entry is unreached."""
    entry = entry or {}
    outcome = {"mutantId": target["id"], "module": target["module"], "before": target["status"],
               "line": target.get("line"), "kindHeuristic": target.get("kindHeuristic")}
    disposition = entry.get("disposition")
    if disposition == "killed":
        try:
            proof = load_proof(repo, entry.get("proof", ""), target["id"])
        except MutationResultsError as exc:
            return {**outcome, "state": "proof-rejected", "reason": str(exc)}
        if after_status is not None and after_status != "killed":
            return {**outcome, "state": "contradicted", "proof": entry["proof"],
                    "reason": f"proof says killed, the remeasure says {after_status!r}"}
        return {**outcome, "state": "killed", "proof": entry["proof"], "test": proof["testId"]}
    if after_status == "killed":
        return {**outcome, "state": "killed", "proof": None, "test": None,
                "reason": "killed in the remeasure without a triage entry"}
    if disposition == "equivalent":
        reason = one_line_reason(entry.get("reason"))
        if reason is None:
            return {**outcome, "state": "rejected-equivalent",
                    "reason": "an equivalent needs a one-line reason of at most 200 characters"}
        return {**outcome, "state": "equivalent", "reason": reason, "basis": "model-judgement"}
    if disposition not in (None, "killed", "equivalent"):
        return {**outcome, "state": "rejected", "reason": f"unknown disposition {disposition!r}"}
    return {**outcome, "state": "unreached"}


def after_counts(before: dict, outcomes: list[dict]) -> dict:
    counts = {k: v for k, v in before.items() if k != "score"}
    for o in outcomes:
        if o["state"] == "killed":
            counts["survived" if o["before"] == "survived" else "noTests"] -= 1
            counts["killed"] += 1
    equivalent = sum(o["state"] == "equivalent" and o["before"] == "survived" for o in outcomes)
    excl = {**counts, "survived": counts["survived"] - equivalent}
    return {**counts, "score": score(counts), "scoreExcludingEquivalent": score(excl), "equivalent": equivalent}


def finding_for(repo: Path, results_file: str, o: dict, severity: str) -> dict | None:
    """A real-tool finding for a target that is still alive, cited and then
    re-verified against the tool's own sidecar -- the same check
    assertion_audit.py applies. A citation that fails is not reported."""
    finding = {"severity": severity, "title": f"mutant {o['mutantId']} {o['before']} ({o.get('kindHeuristic')})",
               "evidence": f"{o['module']}:{o['line']}" if o.get("line") else o["module"],
               "category": "surviving-mutant" if o["before"] == "survived" else "untested-mutant",
               "fixability": "fixable", "toolSource": "real-tool", "resultsFile": results_file,
               "mutantId": o["mutantId"], "module": o["module"], "state": o["state"]}
    try:
        verify_citation(repo, finding)
    except MutationResultsError as exc:
        print(f"WARNING: dropping finding {o['mutantId']!r}: {exc}", file=sys.stderr)
        return None
    return finding


def cmd_report(args, repo: Path) -> dict:
    records = records_dir(repo, args.run_id)
    triage = json.loads(Path(args.triage).read_text(encoding="utf-8"))
    entries: dict[str, dict] = {}
    lanes = triage.get("lanes", [])
    for lane in lanes:
        for entry in lane.get("entries", []):
            entries[entry.get("mutantId")] = {**entry, "lane": lane.get("lane")}
    shards, modules, outcomes, findings, pass_outcomes = [], [], [], [], []
    seen: set[str] = set()
    for manifest_path in sorted(records.glob("*.shard.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shard = manifest["shard"]
        baseline = load_results(repo, args.run_id, "shards", shard)
        if baseline is None:
            raise HarnessError(f"shard {shard!r} has no collected baseline results")
        remeasure = load_results(repo, args.run_id, "remeasure", shard)
        after_by_id = {m["id"]: m["status"] for m in remeasure["mutants"]} if remeasure else {}
        shard_outcomes = []
        for target in (m for m in baseline["mutants"] if m["status"] in TARGET_STATUSES):
            seen.add(target["id"])
            after = after_by_id.get(target["id"]) if remeasure else None
            o = judge_entry(repo, entries.get(target["id"]), target, after)
            o["lane"] = (entries.get(target["id"]) or {}).get("lane")
            shard_outcomes.append(o)
        results_file = rel(repo, records / f"shards-{shard}.results.json")
        for module, before in baseline["modules"].items():
            mod_outcomes = [o for o in shard_outcomes if o["module"] == module]
            modules.append({"shard": shard, "module": module, "before": before,
                            "after": after_counts(before, mod_outcomes),
                            "unreached": sum(o["state"] == "unreached" for o in mod_outcomes)})
        for o in shard_outcomes:
            if o["state"] == "killed" and o.get("proof"):
                pass_outcomes.append({"findingId": f"mutant:{o['mutantId']}", "category": "surviving-mutant",
                                      "evidence": o["module"], "severity": args.severity, "outcome": "fixed",
                                      "mutantId": o["mutantId"], "proofFile": o["proof"]})
                continue
            if o["state"] == "killed":
                continue
            finding = finding_for(repo, results_file, o, args.severity)
            if finding:
                findings.append(finding)
                pass_outcomes.append({"findingId": f"mutant:{o['mutantId']}", "category": finding["category"],
                                      "evidence": finding["evidence"], "severity": args.severity,
                                      "outcome": "blocked", "blockReason": f"{o['state']}: {o.get('reason', '')}".strip()})
        outcomes += shard_outcomes
        shards.append({"shard": shard, "sources": manifest["sources"], "tests": manifest["tests"],
                       "exclusions": manifest["exclusions"], "baselineComplete": baseline["complete"],
                       "baselineState": baseline["state"], "remeasured": remeasure is not None,
                       "remeasureComplete": remeasure["complete"] if remeasure else None,
                       "toolVersion": baseline.get("toolVersion"), "headSha": baseline.get("headSha")})
    stray = sorted(k for k in entries if k not in seen)
    lane_rows = []
    for lane in lanes:
        mine = [o for o in outcomes if o.get("lane") == lane.get("lane")]
        lane_rows.append({"lane": lane.get("lane"), "module": lane.get("module"), "budget": lane.get("budget"),
                          "attempted": len(mine), "killed": sum(o["state"] == "killed" for o in mine),
                          "equivalent": sum(o["state"] == "equivalent" for o in mine)})
    complete = all(s["baselineComplete"] and s["remeasureComplete"] is not False for s in shards)
    summary = {
        "schema": SUMMARY_SCHEMA, "domain": "mutation_harden", "runId": args.run_id, "tool": "mutmut",
        "complete": complete, "shards": shards, "modules": modules, "lanes": lane_rows,
        "kills": [o for o in outcomes if o["state"] == "killed"],
        "equivalents": [o for o in outcomes if o["state"] == "equivalent"],
        "rejected": [o for o in outcomes if o["state"] in ("proof-rejected", "contradicted", "rejected",
                                                             "rejected-equivalent")],
        "unreached": sum(o["state"] == "unreached" for o in outcomes),
        "strayTriageEntries": stray, "findings": findings, "unverifiedCount": 0, "unverified": [],
        "generatedAt": now_iso(),
    }
    zeugnis = repo / "analysis" / "zeugnis"
    write_json(zeugnis / "mutation_harden_summary.json", summary)
    (zeugnis / "reports").mkdir(parents=True, exist_ok=True)
    (zeugnis / "reports" / "MUTATION_HARDEN.md").write_text(render_markdown(summary), encoding="utf-8")
    pass_number = load_ledger(str(repo)).get("totalPasses", 0) + 1
    write_json(records / "pass.json", {"passNumber": pass_number, "domain": "mutation_harden", "mode": "fix",
                                       "outcomes": pass_outcomes})
    return {"summary": "analysis/zeugnis/mutation_harden_summary.json",
            "report": "analysis/zeugnis/reports/MUTATION_HARDEN.md", "passJson": rel(repo, records / "pass.json"),
            "complete": complete, "kills": len(summary["kills"]), "equivalents": len(summary["equivalents"]),
            "unreached": summary["unreached"], "rejected": len(summary["rejected"])}


def pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.1f} %"


def render_markdown(summary: dict) -> str:
    lines = ["# zeugnis Mutation Harden", ""]
    if not summary["complete"]:
        lines += ["**INCOMPLETE**: at least one shard timed out, left mutants not checked, or produced no "
                  "results. Scores below cover only what the tool finished.", ""]
    lines += [f"Run `{summary['runId']}`, tool `{summary['tool']}`. Score is killed / (killed + survived); "
              "mutants no test reaches are counted apart from it, never inside it.", "",
              "| Module | Mutants | Score before | Score after | Untested before | Untested after | "
              "Equivalent | Unreached |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for m in summary["modules"]:
        before, after = m["before"], m["after"]
        total = sum(v for k, v in before.items() if k != "score")
        lines.append(f"| `{m['module']}` | {total} | {pct(before['score'])} | {pct(after['score'])} | "
                     f"{before['noTests']} | {after['noTests']} | {after['equivalent']} | {m['unreached']} |")
    lines += ["", "## Kills (each proven: passes unmutated, fails with the mutant applied)", ""]
    lines += [f"- `{k['mutantId']}`: `{k['test']}`" if k.get("test")
              else f"- `{k['mutantId']}`: killed in the re-measure by the new tests (no proof recorded)"
              for k in summary["kills"]] or ["_none_"]
    lines += ["", "## Equivalent mutants (model judgement, not verified by a command)", ""]
    lines += [f"- `{e['mutantId']}`: {e['reason']}" for e in summary["equivalents"]] or ["_none_"]
    lines += ["", "## Rejected claims", ""]
    lines += [f"- `{r['mutantId']}` ({r['state']}): {r['reason']}" for r in summary["rejected"]] or ["_none_"]
    lines += ["", "## Exclusions", ""]
    excl = [f"- shard `{s['shard']}`: `{e['glob']}` -- {e['reason']}" for s in summary["shards"]
            for e in s["exclusions"]]
    lines += excl or ["_none_"]
    lines += ["", f"Unreached within the kill budget: **{summary['unreached']}**.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, kind=True):
        p.add_argument("repo_root")
        p.add_argument("--run-id", required=True)
        if kind:
            p.add_argument("--shard", required=True)
            p.add_argument("--kind", choices=("shards", "remeasure"), default="shards")

    p = sub.add_parser("prepare")
    common(p)
    p.add_argument("--source", action="append", default=[])
    p.add_argument("--test", action="append", default=[])
    p.add_argument("--exclude", action="append", default=[])
    p.add_argument("--overlay", action="append", default=[])
    p = sub.add_parser("run-shard")
    common(p)
    p.add_argument("--time-box", type=int, required=True)
    p.add_argument("--mutmut")
    p.add_argument("--max-children", type=int)
    p = sub.add_parser("collect")
    common(p)
    p.add_argument("--mutmut")
    p.add_argument("--diff-limit", type=int, default=200)
    p = sub.add_parser("prove")
    common(p, kind=False)
    p.add_argument("--shard", required=True)
    p.add_argument("--mutant", required=True)
    p.add_argument("--test-file", required=True)
    p.add_argument("--test-id", required=True)
    p.add_argument("--mutmut")
    p.add_argument("--python")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--keep-copy", action="store_true")
    p = sub.add_parser("report")
    common(p, kind=False)
    p.add_argument("--triage", required=True)
    p.add_argument("--severity", choices=("Low", "Medium", "High"), default="Medium")

    args = parser.parse_args()
    repo = lexical_path(args.repo_root, ".")
    handlers = {"prepare": cmd_prepare, "run-shard": cmd_run_shard, "collect": cmd_collect,
                "prove": cmd_prove, "report": cmd_report}
    try:
        if not (repo / "analysis" / "zeugnis").is_dir():
            (repo / "analysis" / "zeugnis").mkdir(parents=True)
        result = handlers[args.command](args, repo)
    except (HarnessError, MutationScopeError, MutationResultsError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.command == "prove" and result["verdict"] != "killed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
