#!/usr/bin/env python3
"""Validate and write a workflow.json.

usage: compile_spec.py [-h] [--spec FILE] [--out DIR] [--write] [--selftest]

Reads a draft spec (from --spec, or stdin) and validates it against
references/workflow-spec-schema.md. Writes it only with --write, and only if it
is clean.

Every rejection NAMES THE OFFENDING KEY. Never infer a missing gating value:
reject and surface it, because a halt that depends on a value the compiler
invented is not a halt.

Exit: 0 clean, 1 rejected, 2 could not read the input.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# `(?!\.+\Z)` rejects a runId that is nothing but dots. Without it "." matched,
# and <root>/<runId> then normalises to <root> itself -- a run whose state aliases
# the unnamespaced directory and every other run's stale files, which is exactly
# the isolation runId exists to provide. ".." was already blocked; "." was not.
RUN_ID_RE = re.compile(r"\A(?!\.+\Z)(?!.*\.\.)[A-Za-z0-9._-]{1,64}\Z")
KINDS = {"fanout-redundant", "fanout-blind", "single-writer"}
TIERS = {"haiku", "sonnet", "opus"}
SHAPES = {"change", "question"}
BACKENDS = {"in-session", "matrix"}
SCHEMA_VERSION = "1"


def catalog_patterns(root: Path) -> tuple:
    """Accepted/rejected ids from references/patterns.md's machine-readable index.

    The INDEX is the authority, never the markdown headings: a parser that
    inferred acceptance from a '### ' heading would read the rejected patterns
    as accepted, which is the whole reason that block exists.
    """
    ref = root / "references" / "patterns.md"
    if not ref.is_file():
        return set(), set()
    m = re.search(r"```json\n(.*?)\n```", ref.read_text(encoding="utf-8"), re.S)
    if not m:
        return set(), set()
    idx = json.loads(m.group(1))
    return set(idx.get("accepted", [])), set(idx.get("rejected", []))


def validate(spec: dict, accepted: set, rejected: set) -> list:
    errors: list = []

    def err(where: str, msg: str) -> None:
        errors.append(f"{where}: {msg}")

    if spec.get("schemaVersion") != SCHEMA_VERSION:
        err("schemaVersion", f"must be {SCHEMA_VERSION!r}; a reader that does not "
                             "recognise it refuses rather than guessing")

    run_id = spec.get("runId")
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id or ""):
        err("runId", "must be [A-Za-z0-9._-]{1,64} without '..' -- it is a path component")

    problem = spec.get("problem")
    if not isinstance(problem, dict):
        err("problem", "missing or not an object")
        return errors

    shape = problem.get("shape")
    if shape not in SHAPES:
        err("problem.shape", f"must be one of {sorted(SHAPES)}")
    if not problem.get("statement"):
        err("problem.statement", "missing")

    if shape == "question":
        # Not an error -- a refusal. A question has no runnable check, so a
        # swarm returns N confident answers and no way to choose between them.
        if spec.get("phases"):
            err("phases", "a 'question' spec must carry no phases; route to "
                          "compass:compass-solve instead")
        return errors

    acceptance = problem.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        err("problem.acceptance", "must be a non-empty list")
    else:
        runnable = 0
        seen = set()
        for i, a in enumerate(acceptance):
            if not isinstance(a, dict):
                err(f"problem.acceptance[{i}]", "not an object")
                continue
            if not a.get("id"):
                err(f"problem.acceptance[{i}]", "no 'id'")
            elif a["id"] in seen:
                err(f"problem.acceptance[{i}]", f"duplicate id {a['id']!r}")
            else:
                seen.add(a["id"])
            if not a.get("criterion"):
                err(f"problem.acceptance[{i}]", "no 'criterion'")
            if a.get("check"):
                runnable += 1
        if acceptance and runnable == 0:
            err("problem.acceptance", "no criterion carries a runnable 'check'; nothing "
                                      "could referee this spec")

    scope = spec.get("writeScope")
    if not isinstance(scope, list) or not scope or not all(isinstance(s, str) and s for s in scope):
        err("writeScope", "must be a non-empty list of globs; an absent scope is never "
                          "read as 'anything'")

    budget = spec.get("budget")
    if not isinstance(budget, dict):
        err("budget", "missing or not an object")
        budget = {}
    for key in ("totalDispatches", "wallClockMinutes"):
        v = budget.get(key)
        if not isinstance(v, int) or v <= 0:
            err(f"budget.{key}", "must be a positive integer")

    phases = spec.get("phases")
    if not isinstance(phases, list) or not phases:
        err("phases", "must be a non-empty list")
        return errors
    if len(phases) > 8:
        err("phases", f"{len(phases)} phases; the ceiling is 8")

    markers, ids, fanout_total = {}, set(), 0
    for i, ph in enumerate(phases):
        where = f"phases[{i}]"
        if not isinstance(ph, dict):
            err(where, "not an object")
            continue
        pid = ph.get("id")
        if not pid:
            err(where, "no 'id'")
        else:
            where = f"phases[{i}] ({pid})"
            if pid in ids:
                err(where, "duplicate phase id")
            ids.add(pid)

        kind = ph.get("kind")
        if kind not in KINDS:
            err(where, f"'kind' must be one of {sorted(KINDS)}")

        pattern = ph.get("pattern")
        if pattern in rejected:
            err(where, f"pattern {pattern!r} is in the REJECTED list of "
                       "references/patterns.md; that entry carries the measurement "
                       "that rejected it")
        elif accepted and pattern not in accepted:
            err(where, f"pattern {pattern!r} is not in the accepted list; the compiler "
                       "never improvises a pattern")

        if ph.get("modelTier") not in TIERS:
            err(where, f"'modelTier' must be one of {sorted(TIERS)} and is never omitted -- "
                       "an omitted tier inherits the session's model")

        if kind in ("fanout-redundant", "fanout-blind"):
            fan = ph.get("fanOut")
            if not isinstance(fan, int) or not 1 <= fan <= 16:
                err(where, "'fanOut' must be an integer 1..16 for a fan-out phase")
            else:
                fanout_total += fan
                if kind == "fanout-redundant":
                    angles = ph.get("angles")
                    if not isinstance(angles, list) or len(angles) != fan:
                        err(where, f"'angles' must have exactly fanOut ({fan}) entries -- "
                                   "angles are how this phase widens; identical prompts "
                                   "N times measure sampling noise, not approaches")
                    elif len(set(angles)) != len(angles):
                        err(where, "'angles' contains duplicates")
        else:
            fanout_total += 1

        marker = ph.get("marker")
        if not marker:
            err(where, "no 'marker'; takt has nothing to gate the next phase on")
        elif marker in markers:
            err(where, f"marker {marker!r} is already created by phase {markers[marker]!r}")
        else:
            markers[marker] = pid

        for req in ph.get("requires") or []:
            if req not in markers:
                err(where, f"requires marker {req!r}, which no earlier phase creates")

    total = budget.get("totalDispatches")
    if isinstance(total, int) and total < fanout_total:
        err("budget.totalDispatches", f"{total} is below the sum of every phase's fanOut "
                                      f"({fanout_total}); the run could not finish")

    if spec.get("backend") not in BACKENDS:
        err("backend", f"must be one of {sorted(BACKENDS)}")

    return errors


GOOD = {
    "schemaVersion": "1", "runId": "ap-2026-09-12-a3f1",
    "problem": {"statement": "s", "shape": "change",
                "acceptance": [{"id": "a1", "criterion": "c", "check": "true"}]},
    "writeScope": ["src/**"], "budget": {"totalDispatches": 7, "wallClockMinutes": 25},
    "phases": [
        {"id": "build", "kind": "fanout-redundant", "pattern": "best-of-n", "fanOut": 3,
         "modelTier": "sonnet", "angles": ["a", "b", "c"], "requires": [], "marker": "built"},
        {"id": "referee", "kind": "fanout-blind", "pattern": "blind-referee", "fanOut": 3,
         "modelTier": "sonnet", "requires": ["built"], "marker": "refereed"},
        {"id": "land", "kind": "single-writer", "pattern": "select-then-synthesize",
         "modelTier": "sonnet", "requires": ["refereed"], "marker": "landed"},
    ],
    "backend": "in-session",
}


def _mut(**over) -> dict:
    import copy
    d = copy.deepcopy(GOOD)
    for k, v in over.items():
        cur, *rest = k.split(".")
        if rest:
            d[cur][rest[0]] = v
        else:
            d[cur] = v
    return d


def selftest(root: Path) -> int:
    accepted, rejected = catalog_patterns(root)
    if not accepted:
        print("  FAIL could not read the pattern index from references/patterns.md")
        return 1
    cases = [
        ("clean spec", GOOD, 0),
        ("wrong schemaVersion", _mut(schemaVersion="2"), 1),
        ("bad runId", _mut(runId="../esc"), 1),
        ("empty writeScope", _mut(writeScope=[]), 1),
        ("no runnable check", _mut(problem=dict(GOOD["problem"],
            acceptance=[{"id": "a1", "criterion": "c"}])), 1),
        ("budget below fanOut sum", _mut(budget={"totalDispatches": 2,
            "wallClockMinutes": 5}), 1),
        ("angles != fanOut", _mut(phases=[dict(GOOD["phases"][0], angles=["a", "b"])]), 1),
        ("duplicate angles", _mut(phases=[dict(GOOD["phases"][0], angles=["a", "a", "a"])]), 1),
        ("rejected pattern", _mut(phases=[dict(GOOD["phases"][0], pattern="serial-fix-loop")]), 1),
        ("unknown pattern", _mut(phases=[dict(GOOD["phases"][0], pattern="vibes")]), 1),
        ("missing modelTier", _mut(phases=[{k: v for k, v in GOOD["phases"][0].items()
                                            if k != "modelTier"}]), 1),
        ("dangling requires", _mut(phases=[dict(GOOD["phases"][0], requires=["nope"])]), 1),
        ("duplicate marker", _mut(phases=[GOOD["phases"][0], dict(GOOD["phases"][1],
            marker="built")]), 1),
        ("question carries phases", _mut(problem=dict(GOOD["problem"],
            shape="question")), 1),
        ("question with no phases", {**_mut(problem=dict(GOOD["problem"],
            shape="question")), "phases": []}, 0),
    ]
    fails = []
    for name, spec, want in cases:
        got = validate(spec, accepted, rejected)
        ok = (len(got) > 0) == (want > 0)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {len(got)} error(s)")
        if not ok:
            fails.append(name)
            for e in got:
                print(f"        {e}")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"selftest passed ({len(cases)} specs against the live pattern index)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="compile_spec.py",
        description="Validate and optionally write an arbeitsplan workflow.json. "
                    "Every rejection names the offending key; a missing gating value "
                    "is never inferred.",
        epilog="exit 0 clean, 1 rejected, 2 the input could not be read",
    )
    parser.add_argument("--spec", help="draft spec JSON (default: stdin)")
    parser.add_argument("--out", default="analysis/arbeitsplan",
                        help="output root (default: analysis/arbeitsplan)")
    parser.add_argument("--write", action="store_true",
                        help="write <out>/<runId>/workflow.json when the spec is clean")
    parser.add_argument("--selftest", action="store_true",
                        help="run the planted-defect selftest instead")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    if args.selftest:
        return selftest(root)

    try:
        raw = Path(args.spec).read_text(encoding="utf-8") if args.spec else sys.stdin.read()
        spec = json.loads(raw)
    except FileNotFoundError:
        print(f"no such spec file: {args.spec}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"spec is not valid JSON: {exc}", file=sys.stderr)
        return 2

    accepted, rejected = catalog_patterns(root)
    errors = validate(spec, accepted, rejected)
    if errors:
        for e in errors:
            print(f"REJECTED {e}", file=sys.stderr)
        print(f"{len(errors)} rejection(s); nothing written", file=sys.stderr)
        return 1

    if spec["problem"]["shape"] == "question":
        print("REFUSED: this is a question, not a change. Route it to compass:compass-solve.")
        if args.write:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "out-of-scope-reasoning.json").write_text(json.dumps({
                "runId": spec["runId"], "statement": spec["problem"]["statement"],
                "route": "compass:compass-solve",
                "why": "a question has no runnable check, so a swarm returns N confident "
                       "answers and no way to choose between them",
            }, indent=2))
            print(f"wrote {out}/out-of-scope-reasoning.json")
        return 0

    if args.write:
        dest = Path(args.out) / spec["runId"]
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "workflow.json").write_text(json.dumps(spec, indent=2) + "\n")
        print(f"wrote {dest}/workflow.json")
    else:
        print("spec is valid (not written; pass --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
