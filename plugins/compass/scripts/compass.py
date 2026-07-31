#!/usr/bin/env python3
"""compass.py — the guard CLI every compass skill invokes.

Usage:
    python3 compass.py <check> [--in PAYLOAD.json | -]  [extra args]

Each <check> reads a JSON payload (from a file, or '-' for stdin), runs the
corresponding enforcement function in compass_lib, and:
  * exits 0 and prints a JSON result on success, or
  * exits 2 and prints the violation on GuardError, or
  * exits 3 on a usage/parse error.

The non-zero exit is the enforcement: a skill that runs a check and ignores a
failing exit code is making an observable, auditable mistake — the rule is not a
sentence it can silently skip.

State subcommands (state-write / state-read / state-find) additionally enforce
write scope BEFORE any file is written, and validate every gating field on both
read and write. A record missing a gating field is rejected, never defaulted or
repaired. state-find scans every persisted run for one whose own raw_task
matches a given task byte-for-byte, so compass-solve's Clarify/Explore steps
can reuse a prior standalone run instead of always redoing it from scratch.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compass_lib as C  # noqa: E402

EXIT_OK = 0
EXIT_VIOLATION = 2
EXIT_USAGE = 3


# --------------------------------------------------------------------------- #
# Persisted-state schema + validator (spec requirement 3 & 4)
# --------------------------------------------------------------------------- #

# Fields that gate a later decision. Each is first-class and mandatory; a missing
# one is rejected on both read and write.
STATE_GATING_FIELDS = ("run_id", "raw_task", "phase", "explore_ran")
VALID_PHASES = set(C.PHASE_ORDER) | {"Done"}


def validate_state(state: dict, where: str = "state") -> dict:
    if not isinstance(state, dict):
        raise C.GuardError(f"{where}: state artifact must be a JSON object")
    for field in STATE_GATING_FIELDS:
        C._require_key(state, field, where)
    if state["phase"] not in VALID_PHASES:
        raise C.GuardError(f"{where}: unknown phase {state['phase']!r}")
    if not isinstance(state["explore_ran"], bool):
        raise C.GuardError(f"{where}: explore_ran must be a boolean")
    # Nested artifacts, when present, are validated by their own guards.
    if "clarify" in state and state["clarify"] is not None:
        C.validate_clarify(state["clarify"])
    if "explore" in state and state["explore"] is not None:
        C.validate_branch_scores(state["explore"].get("branches", []))
    if "dag" in state and state["dag"] is not None:
        C.validate_dag(state["dag"].get("stages", []))
    return state


# --------------------------------------------------------------------------- #
# Payload loading
# --------------------------------------------------------------------------- #

def _load_payload(args: list[str]) -> dict:
    src = None
    if "--in" in args:
        src = args[args.index("--in") + 1]
    elif args and not args[0].startswith("-"):
        src = args[0]
    if src is None or src == "-":
        raw = sys.stdin.read()
    else:
        with open(src, "r", encoding="utf-8") as fh:
            raw = fh.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise C.GuardError(f"invalid JSON payload: {exc}")


def _opt(args: list[str], name: str, default=None):
    return args[args.index(name) + 1] if name in args else default


# --------------------------------------------------------------------------- #
# Check dispatch table
# --------------------------------------------------------------------------- #

def _cli_clarify(p, a):        return C.validate_clarify(p)
def _cli_decompose(p, a):      return C.validate_dag(p.get("stages", p if isinstance(p, list) else []))
def _cli_calibrate(p, a):      return C.validate_examples(p.get("examples", []), bool(p.get("constructed")))
def _cli_map(p, a):            return C.validate_triples(p.get("triples", []), p.get("traversal"))
def _cli_self_consistency(p, a): return C.validate_self_consistency(p.get("attempts", []))
def _cli_verify(p, a):         return C.validate_verify_run(p)
def _cli_trace(p, a):          return C.validate_trace(p)
def _cli_negotiate(p, a):      return C.validate_negotiation(p)
def _cli_ground(p, a):         return C.validate_grounding(p)
def _cli_candidates(p, a):     return C.validate_candidates(p.get("candidates", []))
def _cli_critique(p, a):       return C.validate_critique(p.get("checklist", []))
def _cli_branch_scores(p, a):  return C.validate_branch_scores(p.get("branches", []))
def _cli_revise_plan(p, a):    return C.plan_revision(p.get("criteria", []), p.get("threshold"))
def _cli_revise_report(p, a):  return C.check_revision_report(p)
def _cli_phase_order(p, a):    return C.validate_phase_order(p.get("phases_run", []))
def _cli_rung(p, a):           return C.select_rung(p)


def _cli_branch_cap(p, a):
    return {"cap": C.effective_branch_cap(p.get("requested"), p.get("max_branch_count"))}


def _cli_stage_dispatch(p, a):
    stages = p.get("stages", [])
    return {"dispatched": [C.validate_stage_dispatch(s, i) for i, s in enumerate(stages)]}


def _cli_write_scope(p, a):
    target = p.get("target") if isinstance(p, dict) else None
    out = p.get("output_dir", C.DEFAULT_OUTPUT_DIR) if isinstance(p, dict) else C.DEFAULT_OUTPUT_DIR
    return {"safe_path": C.enforce_write_scope(target, out)}


def _cli_state_write(p, a):
    """Validate on write, enforce write scope, then persist."""
    out_dir = _opt(a, "--output-dir", C.DEFAULT_OUTPUT_DIR)
    target = _opt(a, "--to", "state.json")
    safe = C.enforce_write_scope(target, out_dir)   # throws before any write
    validate_state(p, "state(write)")
    os.makedirs(os.path.dirname(safe) or ".", exist_ok=True)
    with open(safe, "w", encoding="utf-8") as fh:
        json.dump(p, fh, indent=2, ensure_ascii=False)
    return {"written": safe}


def _cli_state_read(p, a):
    """Validate on read; reject any artifact missing a gating field. Returns
    the full validated state (not just a validity flag) — a caller reusing
    a prior run needs the actual `clarify`/`explore`/`dag` content, not
    merely confirmation that the file was well-formed."""
    path = _opt(a, "--from")
    if not path:
        raise C.GuardError("state-read requires --from PATH")
    with open(path, "r", encoding="utf-8") as fh:
        state = json.load(fh)
    validate_state(state, "state(read)")
    return {"valid": True, "phase": state["phase"], "explore_ran": state["explore_ran"], "state": state}


def _cli_state_find(p, a):
    """Scan output_dir/runs/*/state.json for one whose own `raw_task`
    matches the given text byte-for-byte, returning the most recently
    modified match — this is what lets compass-solve's Clarify/Explore
    steps reuse a prior standalone compass-clarify-scope/compass-explore-
    branches run instead of always redoing it from scratch (rule:
    solve-reuses-prior-standalone-run). A missing runs/ directory, or any
    individual state.json that is missing, unreadable, or fails
    validate_state, is skipped rather than treated as fatal — finding
    nothing is the normal, common outcome (first time this exact text has
    gone through this phase), not a violation."""
    out_dir = _opt(a, "--output-dir", C.DEFAULT_OUTPUT_DIR)
    raw_task = p.get("raw_task") if isinstance(p, dict) else None
    if not raw_task:
        raise C.GuardError('state-find requires payload {"raw_task": "..."}')
    runs_root = os.path.join(out_dir, "runs")
    candidates = []
    if os.path.isdir(runs_root):
        for name in sorted(os.listdir(runs_root)):
            state_path = os.path.join(runs_root, name, "state.json")
            if not os.path.isfile(state_path):
                continue
            try:
                with open(state_path, "r", encoding="utf-8") as fh:
                    state = json.load(fh)
                validate_state(state, f"state(find:{name})")
            except (OSError, json.JSONDecodeError, C.GuardError):
                continue
            candidates.append({"path": state_path, "mtime": os.path.getmtime(state_path), "state": state})
    winner = C.select_reusable_run(candidates, raw_task)
    if winner is None:
        return {"found": False}
    return {"found": True, "path": winner["path"], "state": winner["state"]}


CHECKS = {
    "clarify": _cli_clarify,
    "decompose": _cli_decompose,
    "branch-cap": _cli_branch_cap,
    "branch-scores": _cli_branch_scores,
    "revise-plan": _cli_revise_plan,
    "revise-report": _cli_revise_report,
    "calibrate": _cli_calibrate,
    "candidates": _cli_candidates,
    "critique": _cli_critique,
    "map": _cli_map,
    "rung": _cli_rung,
    "self-consistency": _cli_self_consistency,
    "verify": _cli_verify,
    "trace": _cli_trace,
    "negotiate": _cli_negotiate,
    "ground": _cli_ground,
    "phase-order": _cli_phase_order,
    "stage-dispatch": _cli_stage_dispatch,
    "write-scope": _cli_write_scope,
    "state-write": _cli_state_write,
    "state-read": _cli_state_read,
    "state-find": _cli_state_find,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stderr.write(
            "usage: compass.py <check> [--in PAYLOAD.json | -] [args]\n"
            "checks: " + ", ".join(sorted(CHECKS)) + "\n"
        )
        return EXIT_USAGE
    check = argv[0]
    rest = argv[1:]
    fn = CHECKS.get(check)
    if fn is None:
        sys.stderr.write(f"unknown check: {check}\n")
        return EXIT_USAGE
    try:
        # state-read needs no stdin payload.
        payload = {} if check == "state-read" else _load_payload(rest)
        result = fn(payload, rest)
    except C.GuardError as exc:
        print(json.dumps({"ok": False, "check": check, "violation": str(exc)},
                         ensure_ascii=False))
        return EXIT_VIOLATION
    except (OSError, ValueError, KeyError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return EXIT_USAGE
    print(json.dumps({"ok": True, "check": check, "result": result},
                     ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
