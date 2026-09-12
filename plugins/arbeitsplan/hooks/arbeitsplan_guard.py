#!/usr/bin/env python3
"""PreToolUse hook: deny a re-dispatch, an out-of-scope write, or a budget overrun.

usage: arbeitsplan_guard.py   (no arguments; the hook event arrives as JSON on stdin)

  Registered by hooks/hooks.json and invoked by Claude Code, not by hand. To
  exercise it directly, pipe one event in:
      echo '{"cwd":".","tool_name":"Edit","tool_input":{"file_path":"a.py"}}' \\
          | python3 plugins/arbeitsplan/hooks/arbeitsplan_guard.py; echo "exit=$?"
  Its calibration is plugins/arbeitsplan/hooks/test_arbeitsplan_guard.py.

WHAT THIS GUARD DOES NOT DO: ordering. A beat that must run before another is
takt's job, declared in .claude/takt.local.md, which arbeitsplan-compile writes.
Duplicating that here would produce two answers to one question. This guard
covers only what takt structurally cannot -- per-dispatch attribution.

  takt asks     "has the required step run?"          -> repo-level state
  this asks     "did THIS in-flight dispatch do that?" -> a per-dispatch lock

docs/orchestration/references/hazards.md records why the distinction is not
cosmetic: self-assess's guard once gated on repo-level state and "swept every
edit in the whole session, from any plugin or a direct user edit, into the
gate", blocking three other plugins' remediators. Parallel writers -- this
plugin's entire premise -- are exactly the case that breaks repo-level gating.

THE RE-DISPATCH LEDGER IS THIS GUARD'S OWN.
A guard that checks a list some skill was supposed to append to is not a
guard; it is a guard predicated on its own input existing, which fails open
exactly when the skill misbehaves -- the case it was written for. So this hook
records every dispatch it sees, itself, as one file per signature created with
O_CREAT|O_EXCL. A repeat dispatch IS that create failing with EEXIST. No
read-modify-write, no lock file, and race-free across parallel candidates by
construction.

Contract (Claude Code's PreToolUse hook protocol):
  - stdin: JSON with at least {"cwd":..., "tool_name":..., "tool_input":{...}}
  - deny: exit 2 AND stdout {"hookSpecificOutput": {...}} AND stderr.
    Omitting hookEventName, or using systemMessage in place of
    permissionDecisionReason, makes the runtime DISCARD the denial silently.
    That bug has shipped in this plugin family before.
  - allow: exit 0, no output.

Inert unless analysis/arbeitsplan/run_scope.json exists. Fail-closed past that.
Escape hatch: ARBEITSPLAN_DISABLE_GUARD=1.

STDLIB ONLY -- it must run under a bare system python3 on any machine.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import NoReturn

LOCK = Path("analysis") / "arbeitsplan" / "run_scope.json"

# The delegation ledger's logic lives in scripts/delegation.py so the guard and
# the CLI cannot drift into two answers about the same question. Imported by
# explicit path rather than by package name -- a hook has no reliable sys.path.
# A failed import DENIES rather than degrading: a guard that cannot evaluate the
# delegation rules is not a guard that should wave delegations through.
_DELEGATION = None
_DELEGATION_IMPORT_ERROR = None
try:
    import importlib.util as _ilu

    _spec = _ilu.spec_from_file_location(
        "arbeitsplan_delegation",
        Path(__file__).resolve().parent.parent / "scripts" / "delegation.py",
    )
    _DELEGATION = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_DELEGATION)
except Exception as _exc:
    _DELEGATION_IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"

EDIT_TOOLS = ("Write", "Edit", "MultiEdit")
DISPATCH_TOOLS = ("Skill", "Task", "Agent")

ESCAPE_HATCH = (
    "Set ARBEITSPLAN_DISABLE_GUARD=1 to bypass this guard, or close the run "
    "(remove analysis/arbeitsplan/run_scope.json) if this repository is no "
    "longer executing an arbeitsplan workflow."
)


def _iso_now() -> str:
    import datetime

    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def deny(reason: str) -> NoReturn:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
    print(reason, file=sys.stderr)
    sys.exit(2)


def allow() -> NoReturn:
    sys.exit(0)


def relative(cwd: str, path: str) -> str:
    """Repo-relative posix form, so a glob written as src/api/* matches whether
    the tool reported an absolute or a relative path."""
    if not path:
        return ""
    # os.path.normpath and os.path.relpath are kept DELIBERATELY; Path is not a
    # drop-in for either, and both differences land in a security check:
    #
    #   normpath   collapses ".." LEXICALLY. Path has no equivalent -- the
    #              nearest is .resolve(), which touches the filesystem and
    #              follows symlinks. Swapping it would change what this
    #              write-scope guard actually decides.
    #   relpath    returns "../outside" for a path above cwd. Path.relative_to
    #              RAISES there unless walk_up=True, which is Python 3.12+.
    #              A hook runs under whatever python3 the user has, and a hook
    #              that fails to import denies every call rather than warning.
    candidate = path if Path(path).is_absolute() else str(Path(cwd) / path)
    try:
        rel = os.path.relpath(os.path.normpath(candidate), os.path.normpath(cwd))
    except ValueError:
        rel = path
    return rel.replace(os.sep, "/")


def matches(target: str, patterns: list) -> bool:
    """fnmatch, never regex. Every silent-failure form this repository has been
    burned by -- [^.]{0,80} that cannot span a dotted filename, [^\\n] in a
    bracket expression -- is a regex-only failure a glob cannot express.

    Tried against the full repo-relative path AND the basename, so both
    'src/api/*' and '*.py' behave as an author expects. A '**' pattern is
    lowered to '*' first, because fnmatch has no '**' and would otherwise fail
    to match across separators while LOOKING like it should.
    """
    base = Path(target).name
    for raw in patterns:
        if not isinstance(raw, str) or not raw:
            continue
        pattern = raw.replace("**/", "*/").replace("**", "*")
        if fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(base, pattern):
            return True
    return False


def edit_targets(cwd: str, tool_input: dict) -> list:
    """Every path the payload exposes. A MultiEdit may carry its paths in an
    `edits` array rather than one top-level file_path.

    The isinstance(..., list) guards are load-bearing, not defensive noise: a
    truthiness check on a STRING `edits` would iterate its characters, filling
    the result with junk that matches no glob AND making it non-empty, so the
    fail-closed branch below would never fire.
    """
    found = []
    one = tool_input.get("file_path")
    if isinstance(one, str) and one:
        found.append(relative(cwd, one))
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                path = edit.get("file_path")
                if isinstance(path, str) and path:
                    found.append(relative(cwd, path))
    many = tool_input.get("file_paths")
    if isinstance(many, list):
        for path in many:
            if isinstance(path, str) and path:
                found.append(relative(cwd, path))
    return found


def dispatch_target(tool_input: dict) -> str:
    """The dispatched name. First non-empty string among the fields the runtime
    actually uses -- the same order takt reads, so the two agree about what a
    dispatch is even though they gate different things about it."""
    for key in ("skill", "subagent_type", "name", "agent", "command"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_cross_plugin(target: str, source: str) -> bool:
    """Is this dispatch a DELEGATION rather than fan-out?

    Compared against the dispatching SOURCE -- the plugin whose frame we are
    currently in -- not against the run's owner. Dispatching within your own
    plugin is fan-out, and counting it would make a three-candidate build look
    like a three-deep chain and trip the breaker on ordinary work.

    Using the run owner instead is a real hole, found by the calibration:
    arbeitsplan -> compass -> arbeitsplan has a final hop whose prefix equals
    the owner, so it was classified as fan-out and skipped the cycle check --
    letting the one shape the cycle detector exists for pass straight through.
    """
    if ":" not in target:
        return False
    prefix = target.split(":", 1)[0]
    return bool(prefix) and prefix != source


def dispatch_signature(phase: str, tool_name: str, tool_input: dict) -> str:
    """Identity of a dispatch: its phase plus a hash of the whole tool input.

    Hashing the ENTIRE input (sorted) rather than a prompt substring is
    deliberate. Two candidates in one fan-out phase carry different angles, so
    they hash differently and both proceed -- widening is never blocked. A
    mechanical retry re-sends a byte-identical input, so it collides and is
    denied. That is the exact line this plugin draws: converge by widening,
    never by repeating.
    """
    body = json.dumps(tool_input, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{phase}\x00{tool_name}\x00{body}".encode()).hexdigest()
    return digest[:32]


def in_any_worktree(target_abs: str, worktrees: list) -> bool:
    for root in worktrees:
        if not isinstance(root, str) or not root:
            continue
        root_n = os.path.normpath(root)
        target_n = os.path.normpath(target_abs)
        if target_n == root_n or target_n.startswith(root_n + os.sep):
            return True
    return False


def main() -> NoReturn:
    if os.environ.get("ARBEITSPLAN_DISABLE_GUARD") == "1":
        allow()

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        allow()  # not a payload this hook can read; never police what it cannot parse

    cwd = event.get("cwd") or str(Path.cwd())
    lock_path = Path(cwd) / LOCK
    if not lock_path.is_file():
        allow()  # inert: no arbeitsplan run is in flight

    # Past this point a run is in flight, so errors deny rather than allow.
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if not isinstance(lock, dict):
            raise ValueError("run_scope.json is not an object")

        tool_name = event.get("tool_name") or ""
        tool_input = event.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        run_id = lock.get("runId") or ""
        phase = lock.get("phase") or ""
        kind = lock.get("kind") or ""
        if not run_id or not phase:
            raise ValueError("run_scope.json lacks runId or phase")

        # ---- dispatch: re-dispatch and budget -------------------------
        if tool_name in DISPATCH_TOOLS:
            budget = lock.get("budget")
            if not isinstance(budget, dict):
                raise ValueError("run_scope.json lacks a budget object")
            total = budget.get("totalDispatches")
            if not isinstance(total, int) or total <= 0:
                raise ValueError("budget.totalDispatches must be a positive integer")

            ledger_dir = Path(cwd) / "analysis" / "arbeitsplan" / run_id / "dispatch"
            ledger_dir.mkdir(parents=True, exist_ok=True)
            used = len(list(ledger_dir.glob("*.json")))
            if used >= total:
                deny(
                    f"arbeitsplan: dispatch budget exhausted for run '{run_id}' "
                    f"({used}/{total} used). The spec declared this ceiling; raising it "
                    f"is a decision to re-compile, not one to make mid-run. "
                    f"{ESCAPE_HATCH}"
                )

            signature = dispatch_signature(phase, tool_name, tool_input)
            entry = ledger_dir / (signature + ".json")
            try:
                fd = os.open(entry, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                deny(
                    f"arbeitsplan: this exact dispatch already ran in phase '{phase}' "
                    f"(signature {signature[:12]}). Re-running an identical dispatch is "
                    f"the serial retry loop this plugin exists to prevent -- past the cap "
                    f"such rounds do not converge, they just cost. Converge by WIDENING: "
                    f"dispatch a new candidate under a different angle, or stop and report "
                    f"that the contract is wrong. {ESCAPE_HATCH}"
                )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"phase": phase, "tool": tool_name, "signature": signature}, handle)

            # ---- delegation: depth cap and cycle detection --------------
            target = dispatch_target(tool_input)
            own = lock.get("plugin") or "arbeitsplan"
            source = lock.get("delegationSource") or own
            if target and is_cross_plugin(target, source):
                if _DELEGATION is None:
                    deny(
                        f"arbeitsplan: the delegation rules could not be loaded "
                        f"({_DELEGATION_IMPORT_ERROR}), so the depth cap and cycle "
                        f"check cannot be evaluated for '{target}'. Refusing rather "
                        f"than delegating unchecked. {ESCAPE_HATCH}"
                    )
                ledger = Path(cwd) / "analysis" / "arbeitsplan" / run_id / "delegation.jsonl"
                parent = lock.get("delegationParent")
                records = _DELEGATION.read_ledger(ledger)
                allowed, depth, why = _DELEGATION.check(records, source, target, parent)
                if not allowed:
                    # Recorded as `denied` BEFORE refusing: a denial nobody can
                    # see afterwards is indistinguishable from a call that was
                    # never made, and the ledger is the only account of why a
                    # run stopped where it did.
                    record_note = ""
                    try:
                        _DELEGATION.append_record(ledger, {
                            "id": "d-" + signature[:12], "runId": run_id, "parent": parent,
                            "depth": depth, "source": source, "target": target,
                            "pattern": "serial", "chain": [source, target], "merge": None,
                            "status": "denied",
                            "timestamp": _iso_now(),
                        })
                    except Exception as exc:
                        # The denial still stands -- it does not depend on the
                        # record -- but the failure is CARRIED INTO the message
                        # rather than swallowed. A silently unrecorded denial is
                        # indistinguishable from a call nobody made, and the
                        # ledger is the only account of why a run stopped here.
                        record_note = (
                            f" (this denial could NOT be written to the ledger: "
                            f"{type(exc).__name__}: {exc} -- the ledger is now an "
                            f"incomplete account of this run)"
                        )
                    deny(f"arbeitsplan: {why}{record_note} {ESCAPE_HATCH}")
                _DELEGATION.append_record(ledger, {
                    "id": "d-" + signature[:12], "runId": run_id, "parent": parent,
                    "depth": depth, "source": source, "target": target,
                    "pattern": "serial", "chain": [source, target], "merge": None,
                    "status": "in_progress", "timestamp": _iso_now(),
                })
            allow()

        # ---- edits: shared tree and write scope ------------------------
        if tool_name in EDIT_TOOLS:
            targets = edit_targets(cwd, tool_input)
            if not targets:
                deny(
                    "arbeitsplan: an edit arrived with no determinable file path while a "
                    f"run is in flight (phase '{phase}'). Refusing rather than allowing an "
                    f"unchecked write. {ESCAPE_HATCH}"
                )

            worktrees = [
                c.get("worktree")
                for c in (lock.get("candidates") or [])
                if isinstance(c, dict)
            ]
            scope = lock.get("writeScope")
            if not isinstance(scope, list) or not scope:
                raise ValueError(
                    "run_scope.json declares no writeScope; an absent scope is never "
                    "read as 'anything'"
                )
            shared_writable = bool(lock.get("sharedTreeWritable"))

            for target in targets:
                target_abs = os.path.normpath(str(Path(cwd) / target))
                inside = in_any_worktree(target_abs, worktrees)

                if not inside and not shared_writable:
                    deny(
                        f"arbeitsplan: '{target}' is a write to the shared tree while "
                        f"fan-out phase '{phase}' ({kind}) is in flight. During a fan-out "
                        f"every candidate writes only inside its own worktree, and exactly "
                        f"one diff is applied afterwards by the calling skill -- that is "
                        f"what makes a merge conflict impossible here. {ESCAPE_HATCH}"
                    )

                probe = target
                if inside:
                    for root in worktrees:
                        root_n = os.path.normpath(root)
                        if target_abs.startswith(root_n + os.sep):
                            probe = os.path.relpath(target_abs, root_n).replace(os.sep, "/")
                            break
                if not matches(probe, scope):
                    deny(
                        f"arbeitsplan: '{probe}' is outside the declared writeScope "
                        f"{scope} for run '{run_id}'. The scope is the contract this "
                        f"candidate was dispatched under; widening it mid-run makes the "
                        f"candidates incomparable. {ESCAPE_HATCH}"
                    )
            allow()

        allow()

    except SystemExit:
        raise
    except Exception as exc:  # fail-closed, per the module docstring
        deny(
            f"arbeitsplan: the run scope could not be evaluated "
            f"({type(exc).__name__}: {exc}). Refusing rather than allowing an "
            f"unchecked call. {ESCAPE_HATCH}"
        )


if __name__ == "__main__":
    main()
