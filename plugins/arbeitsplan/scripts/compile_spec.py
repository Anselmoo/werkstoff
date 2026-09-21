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
KINDS = {"fanout-redundant", "fanout-blind", "fanout-readonly", "single-writer"}
TIERS = {"haiku", "sonnet", "opus"}
SHAPES = {"change", "question"}
MODES = {"auto", "plan"}
WRITES = {"none", "worktree", "shared"}
SCHEMA_VERSION = "2"
MAX_PHASES = 12

# What each fan-out kind may write, fixed by the kind rather than declared per
# phase: a blind referee that could write would stop being blind to its own
# effect, and a redundant candidate that wrote the shared tree would make the
# "exactly one diff lands" invariant a hope.
KIND_WRITES = {
    "fanout-readonly": {"none"},
    "fanout-blind": {"none"},
    "fanout-redundant": {"worktree"},
    "single-writer": WRITES,
}

# backend.why is a closed vocabulary, one id per row of
# references/backend-selection.md's decision table, each naming the backends it
# can justify. A free-text reason is a label, not a decision: nothing can check
# that "because it is faster" actually selects the backend it sits next to.
BACKEND_WHY = {
    "edited-this-session": {"matrix"},
    "does-it-fire": {"matrix"},
    "tier-is-the-variable": {"matrix"},
    "writes-shared-tree": {"matrix", "in-session"},
    "runtime-fanout-width": {"in-session"},
    "script-sequence": {"in-session"},
    "fixed-graph-returns-data": {"workflow"},
    "context-exceeds-session": {"workflow"},
}
BACKEND_KINDS = {"in-session", "matrix", "workflow"}
KNOWN_GAPS = {"workflow-tool-unhooked"}


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

    sv = spec.get("schemaVersion")
    if sv == "1":
        err("schemaVersion", "'1' is no longer compiled. Migrate to '2': make 'backend' an "
                             "object {kind, why[], acknowledgedGaps[]}, and give every phase "
                             "'mode' (auto|plan), 'writes' (none|worktree|shared) and "
                             "'agentType' -- see references/workflow-spec-schema.md")
    elif sv != SCHEMA_VERSION:
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
                          "zirkel:zirkel-solve instead")
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
    if len(phases) > MAX_PHASES:
        err("phases", f"{len(phases)} phases; the ceiling is {MAX_PHASES}")

    backend = spec.get("backend")
    bkind = None
    if not isinstance(backend, dict):
        err("backend", "must be an object {kind, why[], acknowledgedGaps[]}; a bare string "
                       "records a choice without the reason that selected it")
    else:
        bkind = backend.get("kind")
        if bkind not in BACKEND_KINDS:
            err("backend.kind", f"must be one of {sorted(BACKEND_KINDS)}")
            bkind = None
        why = backend.get("why")
        if not isinstance(why, list) or not why:
            err("backend.why", "must be a non-empty list of decision ids from "
                               "references/backend-selection.md")
        else:
            for w in why:
                if w not in BACKEND_WHY:
                    err("backend.why", f"{w!r} is not a decision id; allowed: {sorted(BACKEND_WHY)}")
                elif bkind and bkind not in BACKEND_WHY[w]:
                    err("backend.why", f"{w!r} selects {sorted(BACKEND_WHY[w])}, not {bkind!r}")
        gaps = backend.get("acknowledgedGaps") or []
        if not isinstance(gaps, list) or any(g not in KNOWN_GAPS for g in gaps):
            err("backend.acknowledgedGaps", f"must be a list drawn from {sorted(KNOWN_GAPS)}")
        elif bkind == "workflow" and "workflow-tool-unhooked" not in gaps:
            err("backend.acknowledgedGaps", "the workflow backend needs 'workflow-tool-unhooked' "
                                            "acknowledged: no PreToolUse hook here matches the "
                                            "Workflow tool, so its dispatches are unattributed")
    acceptance_ids = {a.get("id") for a in (problem.get("acceptance") or []) if isinstance(a, dict)}

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

        # mode and writes are required for the modelTier reason: an omitted value
        # inherits the session's, and a plan-mode session silently turned four
        # builders into UNMEASURED cells in the run that motivated this key.
        mode = ph.get("mode")
        if mode not in MODES:
            err(where, f"'mode' must be one of {sorted(MODES)} and is never omitted")
        writes = ph.get("writes")
        if writes not in WRITES:
            err(where, f"'writes' must be one of {sorted(WRITES)} and is never omitted")
        elif kind in KIND_WRITES and writes not in KIND_WRITES[kind]:
            err(where, f"a {kind!r} phase may only write {sorted(KIND_WRITES[kind])}, not {writes!r}")
        elif mode == "plan" and writes != "none":
            err(where, "a plan-mode phase writes nothing; plan mode denies every write but the "
                       "plan file, so declaring writes here is a phase that cannot run")
        if bkind == "workflow" and writes == "shared":
            err(where, "the workflow backend cannot run a phase that writes the shared tree: no "
                       "hook sees a Workflow dispatch's writes. Return the diff as data "
                       "(writes: worktree) and land it in-session, or pick in-session")

        agent_type = ph.get("agentType")
        if bkind == "matrix":
            if agent_type is not None:
                err(where, "a matrix cell is a fresh `claude -p` process, not a dispatch; "
                           "drop 'agentType' or pick another backend")
        elif not isinstance(agent_type, str) or ":" not in agent_type:
            err(where, "'agentType' must be a namespaced agent (plugin:name); a phase without one "
                       "is work the session does inline, unattributed")

        if pattern == "map-reduce-disjoint":
            srcs = ph.get("sources")
            if not isinstance(srcs, list) or len(srcs) != ph.get("fanOut"):
                err(where, "'sources' must list exactly fanOut partitions for map-reduce-disjoint")
            elif len(set(srcs)) != len(srcs):
                err(where, "'sources' overlap; map-reduce-disjoint needs pairwise distinct partitions")
            rd = ph.get("reDerive")
            if not isinstance(rd, dict):
                err(where, "map-reduce-disjoint needs 'reDerive' {samplePct, seed}: under-extraction "
                           "is its named failure, and an unchecked extraction has no evidence")
            else:
                pct, seed = rd.get("samplePct"), rd.get("seed")
                if not isinstance(pct, int) or not 1 <= pct <= 100:
                    err(where, "'reDerive.samplePct' must be an integer 1..100")
                if not isinstance(seed, int):
                    err(where, "'reDerive.seed' must be an integer; the sample is picked in code")

        gate = ph.get("borrowGate")
        if gate is not None:
            must = gate.get("mustBeatWinnerOn") if isinstance(gate, dict) else None
            if pattern != "select-then-synthesize":
                err(where, "'borrowGate' only applies to select-then-synthesize")
            elif not isinstance(must, list) or not must:
                err(where, "'borrowGate.mustBeatWinnerOn' must name at least one acceptance id")
            else:
                for aid in must:
                    if aid not in acceptance_ids:
                        err(where, f"'borrowGate' names {aid!r}, which is not an acceptance id")

        cannot = ph.get("cannotCheck")
        if cannot is not None and (not isinstance(cannot, list)
                                   or not all(isinstance(c, str) and c for c in cannot)):
            err(where, "'cannotCheck' must be a list of non-empty strings, declared before "
                       "any candidate exists")

        if kind in ("fanout-redundant", "fanout-blind", "fanout-readonly"):
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

    return errors


GOOD = {
    "schemaVersion": "2", "runId": "ap-2026-09-12-a3f1",
    "problem": {"statement": "s", "shape": "change",
                "acceptance": [{"id": "a1", "criterion": "c", "check": "true"}]},
    "writeScope": ["src/**"], "budget": {"totalDispatches": 7, "wallClockMinutes": 25},
    "phases": [
        {"id": "build", "kind": "fanout-redundant", "pattern": "best-of-n", "fanOut": 3,
         "modelTier": "sonnet", "mode": "auto", "writes": "worktree",
         "agentType": "arbeitsplan:candidate-builder",
         "angles": ["a", "b", "c"], "requires": [], "marker": "built"},
        {"id": "referee", "kind": "fanout-blind", "pattern": "blind-referee", "fanOut": 3,
         "modelTier": "sonnet", "mode": "auto", "writes": "none",
         "agentType": "arbeitsplan:candidate-referee", "requires": ["built"], "marker": "refereed"},
        {"id": "land", "kind": "single-writer", "pattern": "select-then-synthesize",
         "modelTier": "sonnet", "mode": "auto", "writes": "shared",
         "agentType": "arbeitsplan:synthesizer", "requires": ["refereed"], "marker": "landed"},
    ],
    "backend": {"kind": "in-session", "why": ["writes-shared-tree"], "acknowledgedGaps": []},
}

# The six-phase shape from the request that motivated schema v2, compiled for the
# workflow backend. It lives in ONE committed file because two instruments read
# it: this selftest proves it compiles, and scripts/test_run_workflow.js proves
# workflows/run.js executes it. A literal here would let the two drift apart.
SIX = json.loads((Path(__file__).resolve().parent / "fixtures" / "six-phase.workflow.json")
                 .read_text(encoding="utf-8"))


def _mut(base: dict | None = None, **over) -> dict:
    import copy
    d = copy.deepcopy(GOOD if base is None else base)
    for k, v in over.items():
        cur, *rest = k.split(".")
        if rest:
            d[cur][rest[0]] = v
        else:
            d[cur] = v
    return d


def _drop(d: dict, key: str) -> dict:
    return {k: v for k, v in d.items() if k != key}


def selftest(root: Path) -> int:
    accepted, rejected = catalog_patterns(root)
    if not accepted:
        print("  FAIL could not read the pattern index from references/patterns.md")
        return 1
    cases = [
        ("clean spec", GOOD, 0),
        ("six-phase workflow spec", SIX, 0),
        ("schemaVersion 1 is refused by name", _mut(schemaVersion="1"), 1),
        ("unknown schemaVersion", _mut(schemaVersion="3"), 1),
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
        ("missing modelTier", _mut(phases=[_drop(GOOD["phases"][0], "modelTier")]), 1),
        ("missing mode", _mut(phases=[_drop(GOOD["phases"][0], "mode")]), 1),
        ("missing writes", _mut(phases=[_drop(GOOD["phases"][0], "writes")]), 1),
        ("missing agentType", _mut(phases=[_drop(GOOD["phases"][0], "agentType")]), 1),
        ("un-namespaced agentType", _mut(phases=[dict(GOOD["phases"][0],
            agentType="candidate-builder")]), 1),
        ("referee that writes", _mut(phases=[GOOD["phases"][0], dict(GOOD["phases"][1],
            writes="worktree")]), 1),
        ("plan-mode phase that writes", _mut(phases=[dict(GOOD["phases"][0], mode="plan")]), 1),
        ("dangling requires", _mut(phases=[dict(GOOD["phases"][0], requires=["nope"])]), 1),
        ("duplicate marker", _mut(phases=[GOOD["phases"][0], dict(GOOD["phases"][1],
            marker="built")]), 1),
        ("more than 12 phases", _mut(phases=[dict(GOOD["phases"][0], id=f"p{i}",
            marker=f"m{i}", fanOut=1, angles=["a"]) for i in range(13)],
            budget={"totalDispatches": 20, "wallClockMinutes": 5}), 1),
        ("backend as a bare string", _mut(backend="in-session"), 1),
        ("backend.why empty", _mut(backend={"kind": "in-session", "why": []}), 1),
        ("backend.why free text", _mut(backend={"kind": "in-session", "why": ["it is faster"]}), 1),
        ("backend.why selects another kind", _mut(backend={"kind": "in-session",
            "why": ["does-it-fire"]}), 1),
        ("workflow without the acknowledged gap", _mut(SIX, backend=dict(SIX["backend"],
            acknowledgedGaps=[])), 1),
        ("workflow with a shared-tree writer", _mut(SIX, phases=SIX["phases"][:4] + [dict(
            SIX["phases"][4], writes="shared")] + SIX["phases"][5:]), 1),
        ("matrix phase carrying agentType", _mut(backend={"kind": "matrix",
            "why": ["does-it-fire"]}), 1),
        ("map-reduce without reDerive", _mut(SIX, phases=[_drop(SIX["phases"][0], "reDerive")]
            + SIX["phases"][1:]), 1),
        ("map-reduce with overlapping sources", _mut(SIX, phases=[dict(SIX["phases"][0],
            sources=["a", "a", "b", "c"])] + SIX["phases"][1:]), 1),
        ("borrowGate naming an unknown acceptance id", _mut(SIX, phases=SIX["phases"][:4] + [dict(
            SIX["phases"][4], borrowGate={"mustBeatWinnerOn": ["zz"]})] + SIX["phases"][5:]), 1),
        ("borrowGate on the wrong pattern", _mut(phases=[dict(GOOD["phases"][0],
            borrowGate={"mustBeatWinnerOn": ["a1"]})]), 1),
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
        print("REFUSED: this is a question, not a change. Route it to zirkel:zirkel-solve.")
        if args.write:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "out-of-scope-reasoning.json").write_text(json.dumps({
                "runId": spec["runId"], "statement": spec["problem"]["statement"],
                "route": "zirkel:zirkel-solve",
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
