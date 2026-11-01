"""Shared state, schemas and path rules for cupertino-repair.

Imported by the repair scripts, by state.py and by hooks/pretooluse_guard.py, so
the three can never disagree about where `.cupertino/` is or what a valid
changeset looks like -- they used to: state.py resolved the project root from
CLAUDE_PROJECT_DIR while the guard read the hook payload's `cwd`, so a session
started in a subdirectory wrote flags the guard never saw.

Layout under the project root:

  .cupertino/repair/ACTIVE                  runId of the run in progress (absent: none)
  .cupertino/repair/<runId>/preflight.json  what the target is and which probes can run
  .cupertino/repair/<runId>/objective.json  objective, acceptance, mustPreserve, nonGoals, scope
  .cupertino/repair/<runId>/baseline/       probe results + file hashes BEFORE any edit
  .cupertino/repair/<runId>/changeset.json  the plan: one item per change, each with an op
  .cupertino/repair/<runId>/approved        sha256 of changeset.json at approval
  .cupertino/repair/<runId>/active-item     id of the item being applied (absent: none)
  .cupertino/repair/<runId>/trash/          deleted files + manifest.json (restorable)
  .cupertino/repair/<runId>/after/          probe results + file hashes AFTER
  .cupertino/repair/<runId>/verdict.json    done / partial / regressed, per check

Library only; no CLI. Stdlib only.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from pathlib import Path

STATE_DIR_NAME = ".cupertino"
OPS = ("read", "verify", "modify", "add", "create", "delete")
# Ops that permit a Write/Edit to a source file while their item is active.
WRITE_OPS = ("modify", "add", "create")
PROBE_KINDS = ("web", "command", "file")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# Files only a script may write: the guard denies a model Write/Edit to them, so
# verification cannot be forged by writing its result.
SCRIPT_ONLY = ("preflight.json", "approved", "active-item", "verdict.json")
SCRIPT_ONLY_DIRS = ("baseline", "after", "trash")


class RepairError(Exception):
    """A repair artifact is missing, malformed, or violates the contract."""


# ---- roots -------------------------------------------------------------------
def find_state_root(start: str | os.PathLike, project_dir: str | None) -> Path:
    """The directory whose `.cupertino/` governs `start`. ONE rule, shared by the hook and
    every script -- hooks/pretooluse_guard.py carries a stdlib copy that
    hooks/test_repair_guard.py proves identical on every case.

    1. the nearest of `start` and its ancestors -- up to the project boundary, no further --
       that holds a `.cupertino/` directory. The boundary is CLAUDE_PROJECT_DIR when `start`
       is inside it, else the nearest ancestor holding `.git`, else the filesystem root.
       Unbounded, a stray ~/.cupertino/ governed every repo below it: its ACTIVE run denied
       edits in an unrelated project and its flags satisfied that project's gates;
    2. else CLAUDE_PROJECT_DIR, when set;
    3. else `start`.

    Rule 1 is what makes a session working in `dashboard/` and a script run from the
    repo root agree: both find the one `.cupertino/` above them. Preferring the payload
    cwd (hook) over CLAUDE_PROJECT_DIR (scripts) let them disagree, and an ACTIVE marker
    written at the root was invisible to a guard looking in the subdirectory.
    """
    here = Path(os.path.abspath(start))
    chain = (here, *here.parents)
    boundary = None
    if project_dir:
        pd = Path(os.path.abspath(project_dir))
        if here == pd or pd in here.parents:
            boundary = pd
    if boundary is None:
        boundary = next((d for d in chain if (d / ".git").exists()), None)
    for d in chain:
        if (d / STATE_DIR_NAME).is_dir():
            return d
        if d == boundary:
            break
    return Path(project_dir) if project_dir else here


def project_root(payload_cwd: str | None = None) -> Path:
    """State root for a hook (payload cwd) or a script (process cwd)."""
    return find_state_root(payload_cwd or Path.cwd(), os.environ.get("CLAUDE_PROJECT_DIR"))


def state_dir(root: Path) -> Path:
    return root / STATE_DIR_NAME


def repair_dir(root: Path) -> Path:
    return state_dir(root) / "repair"


def active_run(root: Path) -> str | None:
    marker = repair_dir(root) / "ACTIVE"
    if not marker.is_file():
        return None
    run_id = marker.read_text(encoding="utf-8").strip()
    if not RUN_ID_RE.match(run_id):
        raise RepairError(f".cupertino/repair/ACTIVE holds an invalid run id {run_id!r}")
    return run_id


def run_dir(root: Path, run_id: str) -> Path:
    if not RUN_ID_RE.match(run_id):
        raise RepairError(f"invalid run id {run_id!r}")
    return repair_dir(root) / run_id


# ---- io ----------------------------------------------------------------------
def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise RepairError(f"missing {path}") from err
    except json.JSONDecodeError as err:
        raise RepairError(f"{path} is not valid JSON: {err}") from err


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---- paths -------------------------------------------------------------------
def rel_posix(root: Path, path: str | Path) -> str:
    """Repo-relative POSIX path, lexically normalised. Raises on escape.

    Lexical on purpose (os.path.normpath, not Path.resolve): resolving follows
    symlinks and touches the filesystem, which would change what a write-scope
    decision means -- the same reason takt_guard.py and arbeitsplan_guard.py keep it.
    """
    p = Path(path)
    absolute = p if p.is_absolute() else root / p
    norm = os.path.normpath(str(absolute))
    rel = os.path.relpath(norm, os.path.normpath(str(root)))
    if rel == ".." or rel.startswith(".." + os.sep) or Path(rel).is_absolute():
        raise RepairError(f"{path} is outside the project root")
    return Path(rel).as_posix()


def matches(rel: str, patterns: list[str]) -> bool:
    """fnmatch with `**` spanning directories and a bare directory matching its contents."""
    for pat in patterns:
        pat = pat.rstrip("/")
        if rel == pat or rel.startswith(pat + "/"):
            return True
        if fnmatch.fnmatchcase(rel, pat) or fnmatch.fnmatchcase(rel, pat.replace("**/", "")):
            return True
    return False


def scope_files(root: Path, scope: list[str]) -> list[str]:
    """Every regular file under root matching scope, skipping VCS and .cupertino."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", STATE_DIR_NAME, "node_modules", "__pycache__")]
        for name in filenames:
            rel = Path(dirpath, name).relative_to(root).as_posix()
            if matches(rel, scope):
                out.append(rel)
    return sorted(out)


# ---- schemas -----------------------------------------------------------------
def _need(obj: dict, key: str, kind: type, where: str) -> object:
    if key not in obj:
        raise RepairError(f"{where}: missing required key {key!r}")
    if not isinstance(obj[key], kind):
        raise RepairError(f"{where}: {key!r} must be {kind.__name__}")
    return obj[key]


def validate_check(check: dict, where: str) -> None:
    if not isinstance(check, dict):
        raise RepairError(f"{where}: check must be an object")
    kind = _need(check, "kind", str, where)
    if kind not in PROBE_KINDS:
        raise RepairError(f"{where}: check kind {kind!r} is not one of {PROBE_KINDS}")
    if kind == "web":
        _need(check, "page", str, where)
    elif kind == "command":
        _need(check, "run", str, where)
    elif kind == "file":
        _need(check, "path", str, where)
        if not any(k in check for k in ("exists", "sha256", "unchanged")):
            raise RepairError(f"{where}: a file check needs one of exists / sha256 / unchanged")


def validate_objective(obj: dict) -> None:
    where = "objective.json"
    text = str(_need(obj, "objective", str, where)).strip()
    if len(text.split()) < 4:
        raise RepairError(f"{where}: the objective is too vague to verify ({text!r}); state what must be true when it is done")
    scope = _need(obj, "scope", list, where)
    if not scope or not all(isinstance(s, str) and s.strip() for s in scope):
        raise RepairError(f"{where}: scope must list at least one path or glob")
    acceptance = _need(obj, "acceptance", list, where)
    if not acceptance:
        raise RepairError(f"{where}: at least one acceptance criterion is required")
    for key in ("acceptance", "mustPreserve"):
        seen = set()
        for i, item in enumerate(obj.get(key, [])):
            w = f"{where}: {key}[{i}]"
            cid = _need(item, "id", str, w)
            if cid in seen:
                raise RepairError(f"{w}: duplicate id {cid!r}")
            seen.add(cid)
            _need(item, "criterion", str, w)
            validate_check(item.get("check"), w + ".check")
    if not isinstance(obj.get("nonGoals", []), list):
        raise RepairError(f"{where}: nonGoals must be a list")


def validate_changeset(obj: dict, objective: dict | None = None) -> None:
    where = "changeset.json"
    items = _need(obj, "items", list, where)
    if not items:
        raise RepairError(f"{where}: a changeset with no items changes nothing")
    scope = (objective or {}).get("scope")
    seen = set()
    for i, item in enumerate(items):
        w = f"{where}: items[{i}]"
        iid = _need(item, "id", str, w)
        if iid in seen:
            raise RepairError(f"{w}: duplicate id {iid!r}")
        seen.add(iid)
        op = _need(item, "op", str, w)
        if op not in OPS:
            raise RepairError(f"{w}: op {op!r} is not one of {OPS}")
        paths = _need(item, "paths", list, w)
        if op in (*WRITE_OPS, "delete") and not paths:
            raise RepairError(f"{w}: a {op} item must name the paths it touches")
        for p in paths:
            if not isinstance(p, str) or not p.strip() or any(ch in p for ch in "*?["):
                raise RepairError(f"{w}: paths must be concrete files, not globs ({p!r})")
            if scope is not None and not matches(Path(p).as_posix(), scope):
                raise RepairError(f"{w}: {p} is outside the objective's scope {scope}")
        _need(item, "rationale", str, w)
        if op == "delete" and not item.get("evidence"):
            raise RepairError(f"{w}: a delete must carry evidence that nothing depends on the file")


def check_objective_frozen(root: Path, run_id: str) -> None:
    """The objective verify.py grades must be the one the baseline measured.

    baseline.py records objective.json's sha256. An objective edited afterwards -- a
    failing mustPreserve check deleted, an acceptance check loosened -- would let verify
    grade the change against a different contract and call a regression done. The guard
    also denies the edit; this is the second barrier, for an edit made around the guard.
    """
    rdir = run_dir(root, run_id)
    base = read_json(rdir / "baseline" / "baseline.json")
    recorded = base.get("objectiveSha256")
    if not recorded:
        raise RepairError("the baseline records no objective hash -- re-run baseline.py before planning")
    if sha256_file(rdir / "objective.json") != recorded:
        raise RepairError("objective.json changed after the baseline measured it. A changed objective needs a new run: "
                          "`repair_state.py end --abandon`, then preflight again with the new objective.")


def changeset_hash(root: Path, run_id: str) -> str:
    return sha256_file(run_dir(root, run_id) / "changeset.json")


def approved_changeset(root: Path, run_id: str) -> dict:
    """The changeset, only if its current bytes are the ones that were approved."""
    rdir = run_dir(root, run_id)
    approved = rdir / "approved"
    if not approved.is_file():
        raise RepairError("the changeset has not been approved -- show it to the user, then run repair_state.py approve")
    if approved.read_text(encoding="utf-8").strip() != changeset_hash(root, run_id):
        raise RepairError("changeset.json changed after approval -- re-show it to the user and approve again")
    return read_json(rdir / "changeset.json")
