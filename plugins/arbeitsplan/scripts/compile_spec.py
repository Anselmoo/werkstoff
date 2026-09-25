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
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import land_candidate  # subtract_referee_owned: the coverage check below and
                        # worktree_pool.py's fan-out lock share this one seam
import test_red_fixtures  # --selftest also proves the recorded-red fixtures

# `(?!\.+\Z)` rejects a runId that is nothing but dots. Without it "." matched,
# and <root>/<runId> then normalises to <root> itself -- a run whose state aliases
# the unnamespaced directory and every other run's stale files, which is exactly
# the isolation runId exists to provide. ".." was already blocked; "." was not.
RUN_ID_RE = re.compile(r"\A(?!\.+\Z)(?!.*\.\.)[A-Za-z0-9._-]{1,64}\Z")
KINDS = {"fanout-redundant", "fanout-blind", "fanout-readonly", "single-writer",
         "referee-fixture"}
FANOUT_KINDS = ("fanout-redundant", "fanout-blind", "fanout-readonly")
TIERS = {"haiku", "sonnet", "opus"}
SHAPES = {"change", "question"}
MODES = {"auto", "plan"}
WRITES = {"none", "worktree", "shared"}
SCHEMA_VERSION = "2"
MAX_PHASES = 12

# What each fan-out kind may write, fixed by the kind rather than declared per
# phase: a blind referee that could write would stop being blind to its own
# effect, and a redundant candidate that wrote the shared tree would make the
# "exactly one diff lands" invariant a hope. `referee-fixture` (#77) writes the
# shared tree too -- it runs before any candidate exists, so there is nothing
# yet for a shared write to conflict with.
KIND_WRITES = {
    "fanout-readonly": {"none"},
    "fanout-blind": {"none"},
    "fanout-redundant": {"worktree"},
    "single-writer": WRITES,
    "referee-fixture": {"shared"},
}

# Recorded-red (#77 and later waves): a validator that REJECTS something HEAD
# (3f62503) ACCEPTED is keyed here, id -> the issue that motivated it. Every
# REJECTED/WARNING line this module ever emits for such a rule carries its id
# in [brackets], and scripts/test_red_fixtures.py -- run below, from
# --selftest -- proves each id's committed fixture under fixtures/red/ actually
# goes red on it and was clean at HEAD. A rule id missing from this dict is red
# for a reason nothing can attribute.
RED_RULES = {
    "AP-REFOWNED-NO-PRODUCER": 77,
    "AP-REFOWNED-OUTSIDE-SCOPE": 77,
    "AP-OUTPUT-OUTSIDE-SCOPE": 74,
    "AP-OUTPUT-REFOWNED": 74,
    "AP-CHECK-NOT-RAN": 74,
    "AP-BREAKER-INCOMPLETE": 75,
    "AP-BREAKER-DISABLED": 75,
    "AP-BREAKER-RATIO": 75,
    "AP-BREAKER-SCOPE": 75,
    "AP-BREAKER-KIND": 75,
    "AP-SIBLING-INVISIBLE": 79,
    "AP-BASE-INVALID": 79,
    "AP-BASE-BACKEND": 79,
    "AP-CHECK-SHAPE": 81,
    "AP-SUPERSEDES-INVALID": 93,
    "AP-ROUNDBREAKER-INVALID": 93,
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


def _owner_of(marker: str, markers: dict, phases_by_id: dict) -> dict | None:
    pid = markers.get(marker)
    return phases_by_id.get(pid) if pid else None


def _walk_requires_markers(start_requires: list, markers: dict, phases_by_id: dict,
                            stop_at_shared: bool) -> set:
    """Every marker reachable by walking `requires` -> its producing phase -> that
    phase's own `requires`, transitively, starting from `start_requires`.

    `stop_at_shared=True` (the #79 visibility walk) still counts the marker of a
    phase whose `writes` is 'shared', but does not expand past it: a landed phase
    already carries everything before it into the shared tree, so an ancestor
    beyond a landing adds nothing a fresh worktree checked out after that landing
    would not already have. The `base`-validity walk below wants plain
    reachability instead, so it passes `stop_at_shared=False`.
    """
    seen: set = set()
    stack = list(start_requires or [])
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        owner = _owner_of(m, markers, phases_by_id)
        if owner is None:
            continue
        if stop_at_shared and owner.get("writes") == "shared":
            continue
        for r in owner.get("requires") or []:
            if r not in seen:
                stack.append(r)
    return seen


def _fanout_redundant_ancestors(pid: str, phases_by_id: dict, markers: dict) -> set:
    """Every OTHER fanout-redundant phase reachable from `pid` by walking its
    `requires` transitively over the marker -> producing-phase map, stopping at
    (but still crediting) any writes:'shared' phase on the way."""
    ph = phases_by_id.get(pid) or {}
    reached = _walk_requires_markers(ph.get("requires"), markers, phases_by_id, stop_at_shared=True)
    result = set()
    for m in reached:
        owner = _owner_of(m, markers, phases_by_id)
        if owner and owner.get("kind") == "fanout-redundant" and owner.get("id") != pid:
            result.add(owner.get("id"))
    return result


def _base_chain(pid: str, phases_by_id: dict) -> set:
    """`pid`'s base, its base's base, and so on -- the set of phases whose refereed
    winner this phase's worktree was actually seeded from."""
    chain: set = set()
    cur = (phases_by_id.get(pid) or {}).get("base")
    while cur and cur not in chain and cur in phases_by_id:
        chain.add(cur)
        cur = phases_by_id[cur].get("base")
    return chain


def validate(spec: dict, accepted: set, rejected: set) -> tuple:
    """Returns (errors, warnings) -- both lists of `"{where}: {msg}"` strings.

    An error is a rejection: `--write` never runs and main() exits 1. A warning
    (currently only AP-SIBLING-INVISIBLE, #79) never blocks a write on its own --
    only `--strict` turns one into a rejection.
    """
    errors: list = []
    warnings: list = []

    def err(where: str, msg: str) -> None:
        errors.append(f"{where}: {msg}")

    def warn(where: str, msg: str) -> None:
        warnings.append(f"{where}: {msg}")

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

    # supersedes / roundBreaker (#93, recorded-red): HEAD (e42621b) never looked at
    # either top-level key at all -- an unrecognised key was simply ignored, so a
    # spec carrying `supersedes: 5` or `roundBreaker: {maxAdvancingRounds: "3"}`
    # compiled clean there. Both are optional; only a MALFORMED value is rejected.
    supersedes = spec.get("supersedes")
    if supersedes is not None:
        if not isinstance(supersedes, str) or not supersedes:
            err("supersedes", "[AP-SUPERSEDES-INVALID] must be a non-empty runId string when "
                              "present -- scripts/rounds.py record follows it to rebuild rounds "
                              "across a superseded run's chain")
        elif isinstance(run_id, str) and supersedes == run_id:
            err("supersedes", f"[AP-SUPERSEDES-INVALID] must not name this spec's own runId "
                              f"{run_id!r}; a run cannot supersede itself")

    round_breaker = spec.get("roundBreaker")
    if round_breaker is not None:
        if not isinstance(round_breaker, dict):
            err("roundBreaker", "[AP-ROUNDBREAKER-INVALID] must be an object "
                                "{maxAdvancingRounds: int >= 2}")
        else:
            n = round_breaker.get("maxAdvancingRounds")
            if isinstance(n, bool) or not isinstance(n, int) or n < 2:
                err("roundBreaker.maxAdvancingRounds", "[AP-ROUNDBREAKER-INVALID] must be a "
                                                        "plain int >= 2 -- a bool is not an int "
                                                        "here, and N < 2 cannot show a SEQUENCE "
                                                        "of advancing rounds (#93)")

    problem = spec.get("problem")
    if not isinstance(problem, dict):
        err("problem", "missing or not an object")
        return errors, warnings

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
        return errors, warnings

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
            # AP-CHECK-SHAPE (#81, recorded-red): HEAD (e42621b) never looked at
            # `check`'s TYPE at all -- only its truthiness, below -- so a check of
            # 42, {}, [] or ['true', 3] compiled clean and only failed later,
            # wherever something finally tried to run it as a shell command.
            # land_candidate.checks_of() is the one normalizer every reader (this
            # validator, --probe-checks, reconcile.py's measure(), run.js's
            # checksOf) traces back to, so a shape none of them agree on is
            # rejected here, once, rather than differently by each reader.
            try:
                cmds = land_candidate.checks_of(a.get("check"))
            except land_candidate.CheckShapeError as exc:
                err(f"problem.acceptance[{i}]", f"[AP-CHECK-SHAPE] 'check' {exc}")
            else:
                if cmds:
                    runnable += 1
        if acceptance and runnable == 0:
            err("problem.acceptance", "no criterion carries a runnable 'check'; nothing "
                                      "could referee this spec")

    scope = spec.get("writeScope")
    if not isinstance(scope, list) or not scope or not all(isinstance(s, str) and s for s in scope):
        err("writeScope", "must be a non-empty list of globs; an absent scope is never "
                          "read as 'anything'")

    # refereeOwned (#77): a spec-level list of paths a referee-fixture phase
    # writes before any candidate exists, subtracted from every fan-out phase's
    # effective write scope. Absent is legal -- most specs need no such fixture.
    ref_owned = spec.get("refereeOwned")
    if ref_owned is not None:
        if (not isinstance(ref_owned, list) or not ref_owned
                or not all(isinstance(p, str) and p for p in ref_owned)):
            err("refereeOwned", "must be a non-empty list of path globs when present")
            ref_owned = None

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
        return errors, warnings
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

    # breaker (#75, recorded-red): HEAD (3f62503) never looked at this key at
    # all -- run.js:339 and :401 read it unconditionally as
    # `scoped * acceptDenominator < measured * acceptNumerator`, falling back to
    # DEFAULT_BREAKER only when the key is absent, never when it is malformed.
    # A breaker that could never trip (acceptNumerator == 0 makes the compare
    # `x < 0`), a ratio outside 0..1, or one declared on a phase nothing ever
    # compares it against (only a fan-out phase's result is measured against a
    # breaker) all compiled clean. One err() call per rule id, so a fixture that
    # is wrong in exactly one way is red for exactly one reason.
    def validate_breaker(where: str, ph: dict, kind: str) -> None:
        breaker = ph.get("breaker")
        if breaker is None:
            return
        if kind not in FANOUT_KINDS:
            err(where, f"[AP-BREAKER-KIND] 'breaker' is declared on a {kind!r} phase; only "
                       f"{sorted(FANOUT_KINDS)} phases are ever compared against one "
                       "(workflows/run.js:339,401) -- nothing reads it here")
        if not isinstance(breaker, dict):
            err(where, "[AP-BREAKER-INCOMPLETE] 'breaker' must be an object "
                       "{acceptNumerator, acceptDenominator}")
            return
        num, den = breaker.get("acceptNumerator"), breaker.get("acceptDenominator")
        num_bad = isinstance(num, bool) or not isinstance(num, int)
        den_bad = isinstance(den, bool) or not isinstance(den, int)
        if num_bad or den_bad:
            err(where, "[AP-BREAKER-INCOMPLETE] 'breaker.acceptNumerator' and "
                       "'acceptDenominator' are both required and must be a plain int -- "
                       "a bool is not an int here")
            return
        if num == 0:
            err(where, "[AP-BREAKER-DISABLED] acceptNumerator == 0 turns the comparison "
                       "into 'x < 0', which never trips; that is a disabled gate, not a "
                       "threshold of zero")
        elif den < 1 or num < 0 or num > den:
            err(where, f"[AP-BREAKER-RATIO] must satisfy 1 <= acceptNumerator <= "
                       f"acceptDenominator; got acceptNumerator={num}, "
                       f"acceptDenominator={den}")
        scope = breaker.get("scope")
        if scope is not None and scope != "per-batch":
            err(where, f"[AP-BREAKER-SCOPE] 'breaker.scope' must be exactly 'per-batch' "
                       f"when present (absent is allowed); got {scope!r}")

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

        validate_breaker(where, ph, kind)

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

        # referee-fixture (#77): a single writer that runs before any fan-out
        # phase and produces exactly the spec-level refereeOwned paths. These are
        # ordinary shape rules (planted --selftest cases), not recorded-red: a
        # phase of this KIND is new, so HEAD (which does not have "referee-fixture"
        # in its KINDS) already refuses any fixture that uses it -- there is no
        # HEAD-accepted spec these rules could newly reject.
        # outputs (#74): the paths a phase is expected to produce, a phase key on
        # ANY phase (not just referee-fixture). Shape-checked here, once; the
        # effective-scope check below (AP-OUTPUT-OUTSIDE-SCOPE / AP-OUTPUT-REFOWNED)
        # and referee-fixture's own equality-to-refereeOwned rule (kept from wave
        # 1) both reuse this validated list rather than re-fetching it.
        outputs = ph.get("outputs")
        outputs_ok = True
        if outputs is not None:
            if not isinstance(outputs, list) or not all(isinstance(o, str) and o for o in outputs):
                err(where, "'outputs' must be a list of non-empty path strings")
                outputs_ok = False

        if kind == "referee-fixture":
            if pattern != "calibrate-then-measure":
                err(where, "a 'referee-fixture' phase must use pattern 'calibrate-then-measure' "
                           "-- verifying the instrument before anything is measured against it "
                           "is exactly what this phase is")
            if ph.get("fanOut") is not None:
                err(where, "a 'referee-fixture' phase carries no 'fanOut'; it is a single "
                           "writer, never fanned out")
            if outputs is not None and outputs_ok and ref_owned is not None and outputs != ref_owned:
                err(where, f"'outputs' {outputs} must equal the spec's refereeOwned "
                           f"{ref_owned}; a fixture's declared output and what candidates "
                           "are protected from touching must never be able to disagree")

        # AP-OUTPUT-* (#74, recorded-red, always-on -- no flag needed): a
        # declared output must sit inside its phase's EFFECTIVE write scope --
        # in_scope(path, writeScope) and, for a fan-out phase, NOT
        # in_scope(path, refereeOwned). That is exactly the pair of tests
        # land_candidate.py applies at landing (imported above, never
        # redefined here), so compile time and landing time can never disagree
        # about the same path.
        if outputs is not None and outputs_ok and isinstance(scope, list):
            for path in outputs:
                if not land_candidate.in_scope(path, scope):
                    err(where, f"[AP-OUTPUT-OUTSIDE-SCOPE] output {path!r} is not reachable "
                               f"through writeScope {scope}; a phase cannot be expected to "
                               "produce a path it has no license to write")
                elif kind in FANOUT_KINDS and land_candidate.in_scope(path, ref_owned or []):
                    err(where, f"[AP-OUTPUT-REFOWNED] output {path!r} is refereeOwned "
                               f"{ref_owned}; a fan-out phase cannot be expected to produce a "
                               "path only a referee-fixture phase may write")

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

    # A 'referee-fixture' phase must come before EVERY fan-out phase: a fixture
    # produced after builders have already run protects nothing. Equivalent to
    # "no referee-fixture index exceeds every fan-out index" -- checked as
    # max(referee-fixture indices) > min(fan-out indices), which holds iff some
    # pair is out of order.
    ref_fixture_idx = [i for i, ph in enumerate(phases)
                       if isinstance(ph, dict) and ph.get("kind") == "referee-fixture"]
    fanout_idx = [i for i, ph in enumerate(phases)
                 if isinstance(ph, dict) and ph.get("kind") in FANOUT_KINDS]
    if ref_fixture_idx and fanout_idx and max(ref_fixture_idx) > min(fanout_idx):
        err("phases", "a 'referee-fixture' phase must come before every fan-out phase")

    # refereeOwned RECORDED-RED (#77): both are validators that reject a spec
    # HEAD (3f62503) would have compiled clean -- see RED_RULES and
    # fixtures/red/MANIFEST.json.
    if ref_owned is not None:
        if not ref_fixture_idx:
            err("refereeOwned", "[AP-REFOWNED-NO-PRODUCER] declared but no phase of kind "
                                "'referee-fixture' produces it; an artifact nothing writes "
                                "is not protected, it is simply absent")
        if isinstance(scope, list) and scope:
            for ro in ref_owned:
                # Covered by writeScope iff subtracting it actually removes
                # something -- land_candidate.subtract_referee_owned is the one
                # place this computation lives, shared with worktree_pool.py.
                if land_candidate.subtract_referee_owned(scope, [ro]) == scope:
                    err("refereeOwned", f"[AP-REFOWNED-OUTSIDE-SCOPE] {ro!r} is not covered by "
                                        f"writeScope {scope}; subtracting a path writeScope "
                                        "never reached protects nothing")

    # `base` (#79, recorded-red): only ever meaningful on a fanout-redundant
    # phase, naming an EARLIER fanout-redundant phase whose refereed winner this
    # phase's worktrees are stacked on. Valid iff some earlier fanout-blind phase
    # reviewed that winner (required its marker) and this phase's own transitive
    # `requires` reach that reviewer's marker in turn -- a base is a refereed
    # winner, never an unjudged one.
    phases_by_id = {ph.get("id"): ph for ph in phases if isinstance(ph, dict) and ph.get("id")}
    id_to_index = {ph.get("id"): i for i, ph in enumerate(phases)
                  if isinstance(ph, dict) and ph.get("id")}
    for i, ph in enumerate(phases):
        if not isinstance(ph, dict):
            continue
        pid = ph.get("id")
        base = ph.get("base")
        if base is None:
            continue
        where = f"phases[{i}] ({pid})" if pid else f"phases[{i}]"
        kind = ph.get("kind")
        if not isinstance(base, str) or not base:
            err(where, "[AP-BASE-INVALID] 'base' must be a non-empty phase id string")
            continue
        if kind != "fanout-redundant":
            err(where, f"[AP-BASE-INVALID] 'base' only applies to a 'fanout-redundant' phase, "
                       f"not {kind!r}")
            continue
        if bkind == "workflow":
            err(where, "[AP-BASE-BACKEND] the workflow backend cannot honour 'base': "
                       "run.js's isolation:'worktree' creates every candidate worktree fresh "
                       "from HEAD, with no way to seed it from a prior wave's promoted branch")
            continue
        q_idx = id_to_index.get(base)
        if (q_idx is None or q_idx >= i or not isinstance(phases[q_idx], dict)
                or phases[q_idx].get("kind") != "fanout-redundant"):
            err(where, f"[AP-BASE-INVALID] 'base' {base!r} must name an EARLIER "
                       "'fanout-redundant' phase; a base is a refereed winner, and a winner "
                       "cannot precede its own build")
            continue
        q_marker = phases[q_idx].get("marker")
        reviewers = [r for r in phases[:i] if isinstance(r, dict)
                    and r.get("kind") == "fanout-blind" and q_marker in (r.get("requires") or [])]
        if not reviewers:
            err(where, f"[AP-BASE-INVALID] no 'fanout-blind' phase requires {base!r}'s marker "
                       f"{q_marker!r}; 'base' names a refereed winner, and {base!r} was never "
                       "reviewed")
            continue
        p_closure = _walk_requires_markers(ph.get("requires"), markers, phases_by_id,
                                           stop_at_shared=False)
        if not any(r.get("marker") in p_closure for r in reviewers):
            err(where, f"[AP-BASE-INVALID] {pid!r}'s transitive 'requires' never reach the "
                       f"marker of a 'fanout-blind' phase that reviewed {base!r}; 'base' names "
                       "a refereed winner this phase actually consumes, not an unrelated one")

    # AP-SIBLING-INVISIBLE (#79, recorded-red, WARNING not REJECTED): for every
    # fanout-redundant phase P, walk its transitive `requires` over the marker ->
    # producing-phase map, stopping at (but crediting) any writes:'shared' phase
    # on the way. If that walk reaches another fanout-redundant phase Q and P's
    # own `base` chain does not reach Q, Q's candidates were never landed and P
    # was never stacked on Q either -- so Q's fan-out is invisible in P's fresh
    # worktree, a candidate builder made from HEAD, not from Q's winner. Only
    # fanout-redundant P is checked: a blind referee or a synthesizer receives
    # diffs as data, never a worktree of its own, so there is nothing for either
    # to be missing.
    for i, ph in enumerate(phases):
        if not isinstance(ph, dict) or ph.get("kind") != "fanout-redundant":
            continue
        pid = ph.get("id")
        if not pid:
            continue
        where = f"phases[{i}] ({pid})"
        reached = _fanout_redundant_ancestors(pid, phases_by_id, markers)
        if not reached:
            continue
        chain = _base_chain(pid, phases_by_id)
        for q in sorted(reached):
            if q in chain:
                continue
            warn(where, f"[AP-SIBLING-INVISIBLE] {pid!r} transitively requires {q!r}'s "
                        f"fan-out (via the marker chain) but is not built on it "
                        f"(base chain: {sorted(chain) or 'none'}); {q!r}'s candidates are "
                        f"invisible in {pid!r}'s fresh worktree unless a writes:'shared' phase "
                        "already landed them")

    return errors, warnings


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

# A minimal but valid use of referee-fixture + refereeOwned (#77): the fixture
# phase runs before both fan-out phases, its 'outputs' matches the spec-level
# refereeOwned exactly, and writeScope covers the protected path (so subtract
# actually removes something).
GOOD_REF = {
    "schemaVersion": "2", "runId": "ap-2026-09-22-fx99",
    "problem": {"statement": "s", "shape": "change",
                "acceptance": [{"id": "a1", "criterion": "c", "check": "true"}]},
    "writeScope": ["src/**", "oracle/**"], "refereeOwned": ["oracle/spec.txt"],
    "budget": {"totalDispatches": 8, "wallClockMinutes": 25},
    "phases": [
        {"id": "oracle", "kind": "referee-fixture", "pattern": "calibrate-then-measure",
         "modelTier": "opus", "mode": "auto", "writes": "shared",
         "agentType": "arbeitsplan:contract-author", "outputs": ["oracle/spec.txt"],
         "requires": [], "marker": "oracled"},
        {"id": "build", "kind": "fanout-redundant", "pattern": "best-of-n", "fanOut": 3,
         "modelTier": "sonnet", "mode": "auto", "writes": "worktree",
         "agentType": "arbeitsplan:candidate-builder",
         "angles": ["a", "b", "c"], "requires": ["oracled"], "marker": "built"},
        {"id": "referee", "kind": "fanout-blind", "pattern": "blind-referee", "fanOut": 3,
         "modelTier": "sonnet", "mode": "auto", "writes": "none",
         "agentType": "arbeitsplan:candidate-referee", "requires": ["built"], "marker": "refereed"},
        {"id": "land", "kind": "single-writer", "pattern": "select-then-synthesize",
         "modelTier": "sonnet", "mode": "auto", "writes": "shared",
         "agentType": "arbeitsplan:synthesizer", "requires": ["refereed"], "marker": "landed"},
    ],
    "backend": {"kind": "in-session", "why": ["writes-shared-tree"], "acknowledgedGaps": []},
}

# Two fanout-redundant phases stacked build -> blind-referee -> build, with no
# `base` (#79): CHAIN's second build transitively requires the first build's
# marker (through the referee in between) but never says so with a `base`, so
# AP-SIBLING-INVISIBLE is expected. CHAIN_BASED is the same shape with the
# missing `base` supplied, which must silence the warning.
CHAIN = {
    "schemaVersion": "2", "runId": "ap-2026-09-22-ch01",
    "problem": {"statement": "s", "shape": "change",
                "acceptance": [{"id": "a1", "criterion": "c", "check": "true"}]},
    "writeScope": ["src/**"], "budget": {"totalDispatches": 10, "wallClockMinutes": 25},
    "phases": [
        {"id": "build1", "kind": "fanout-redundant", "pattern": "best-of-n", "fanOut": 2,
         "modelTier": "sonnet", "mode": "auto", "writes": "worktree",
         "agentType": "arbeitsplan:candidate-builder", "angles": ["a", "b"],
         "requires": [], "marker": "built1"},
        {"id": "referee1", "kind": "fanout-blind", "pattern": "blind-referee", "fanOut": 2,
         "modelTier": "sonnet", "mode": "auto", "writes": "none",
         "agentType": "arbeitsplan:candidate-referee", "requires": ["built1"], "marker": "refereed1"},
        {"id": "build2", "kind": "fanout-redundant", "pattern": "best-of-n", "fanOut": 2,
         "modelTier": "sonnet", "mode": "auto", "writes": "worktree",
         "agentType": "arbeitsplan:candidate-builder", "angles": ["c", "d"],
         "requires": ["refereed1"], "marker": "built2"},
        {"id": "referee2", "kind": "fanout-blind", "pattern": "blind-referee", "fanOut": 2,
         "modelTier": "sonnet", "mode": "auto", "writes": "none",
         "agentType": "arbeitsplan:candidate-referee", "requires": ["built2"], "marker": "refereed2"},
        {"id": "land", "kind": "single-writer", "pattern": "select-then-synthesize",
         "modelTier": "sonnet", "mode": "auto", "writes": "shared",
         "agentType": "arbeitsplan:synthesizer", "requires": ["refereed2"], "marker": "landed"},
    ],
    "backend": {"kind": "in-session", "why": ["writes-shared-tree"], "acknowledgedGaps": []},
}
CHAIN_BASED = json.loads(json.dumps(CHAIN))
CHAIN_BASED["runId"] = "ap-2026-09-22-ch02"
CHAIN_BASED["phases"][2]["base"] = "build1"


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
        # check shape / AP-CHECK-SHAPE (#81)
        ("check: an int -> AP-CHECK-SHAPE", _mut(problem=dict(GOOD["problem"],
            acceptance=[{"id": "a1", "criterion": "c", "check": 42}])), 1),
        ("check: an object -> AP-CHECK-SHAPE", _mut(problem=dict(GOOD["problem"],
            acceptance=[{"id": "a1", "criterion": "c", "check": {}}])), 1),
        ("check: an empty list -> AP-CHECK-SHAPE", _mut(problem=dict(GOOD["problem"],
            acceptance=[{"id": "a1", "criterion": "c", "check": []}])), 1),
        ("check: a list with an empty string -> AP-CHECK-SHAPE", _mut(problem=dict(
            GOOD["problem"], acceptance=[{"id": "a1", "criterion": "c", "check": [""]}])), 1),
        ("check: a list with a non-string element -> AP-CHECK-SHAPE", _mut(problem=dict(
            GOOD["problem"], acceptance=[{"id": "a1", "criterion": "c",
                "check": ["true", 3]}])), 1),
        ("check: a non-empty string array compiles clean", _mut(problem=dict(GOOD["problem"],
            acceptance=[{"id": "a1", "criterion": "c", "check": ["true", "true"]}])), 0),
        ("check: null alongside a runnable sibling compiles clean", _mut(problem=dict(
            GOOD["problem"], acceptance=[{"id": "a1", "criterion": "c", "check": "true"},
                {"id": "a2", "criterion": "d", "check": None}])), 0),
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
        # referee-fixture / refereeOwned (#77)
        ("referee-fixture: clean spec", GOOD_REF, 0),
        ("referee-fixture: wrong pattern", _mut(GOOD_REF, phases=[dict(
            GOOD_REF["phases"][0], pattern="best-of-n")] + GOOD_REF["phases"][1:]), 1),
        ("referee-fixture: carries fanOut", _mut(GOOD_REF, phases=[dict(
            GOOD_REF["phases"][0], fanOut=1)] + GOOD_REF["phases"][1:]), 1),
        ("referee-fixture: outputs != refereeOwned", _mut(GOOD_REF, phases=[dict(
            GOOD_REF["phases"][0], outputs=["oracle/other.txt"])] + GOOD_REF["phases"][1:]), 1),
        ("referee-fixture: after a fan-out phase", _mut(GOOD_REF, phases=[
            GOOD_REF["phases"][1], GOOD_REF["phases"][0],
            GOOD_REF["phases"][2], GOOD_REF["phases"][3]]), 1),
        ("refereeOwned: no referee-fixture phase produces it", _mut(
            writeScope=["src/**", "oracle/**"], refereeOwned=["oracle/spec.txt"]), 1),
        ("refereeOwned: path not covered by writeScope", _mut(
            writeScope=["src/**"], refereeOwned=["oracle/spec.txt"]), 1),
        ("refereeOwned: empty list", _mut(refereeOwned=[]), 1),
        # outputs / AP-OUTPUT-* (#74)
        ("outputs: not a list of strings", _mut(phases=[dict(GOOD["phases"][0],
            outputs=[123])]), 1),
        ("outputs: in scope, not refereeOwned -- clean", _mut(phases=[dict(GOOD["phases"][0],
            outputs=["src/thing.py"])]), 0),
        ("outputs: fan-out phase, outside writeScope -> AP-OUTPUT-OUTSIDE-SCOPE",
            _mut(phases=[dict(GOOD["phases"][0], outputs=["outside/scope.py"])]), 1),
        ("outputs: single-writer phase, outside writeScope -> AP-OUTPUT-OUTSIDE-SCOPE",
            _mut(phases=[dict(GOOD["phases"][2], outputs=["outside/scope.py"])]), 1),
        ("outputs: fan-out phase, inside refereeOwned -> AP-OUTPUT-REFOWNED", _mut(GOOD_REF,
            phases=[GOOD_REF["phases"][0], dict(GOOD_REF["phases"][1],
                outputs=["oracle/spec.txt"])]), 1),
        # breaker / AP-BREAKER-* (#75)
        ("breaker: valid on a fan-out phase -- clean", _mut(phases=[dict(GOOD["phases"][0],
            breaker={"acceptNumerator": 2, "acceptDenominator": 3})] + GOOD["phases"][1:]), 0),
        ("breaker: not an object -> AP-BREAKER-INCOMPLETE", _mut(phases=[dict(GOOD["phases"][0],
            breaker="2/3")] + GOOD["phases"][1:]), 1),
        ("breaker: acceptNumerator missing -> AP-BREAKER-INCOMPLETE", _mut(phases=[dict(
            GOOD["phases"][0], breaker={"acceptDenominator": 3})] + GOOD["phases"][1:]), 1),
        ("breaker: acceptNumerator is a bool, not an int -> AP-BREAKER-INCOMPLETE",
            _mut(phases=[dict(GOOD["phases"][0], breaker={"acceptNumerator": True,
                "acceptDenominator": 3})] + GOOD["phases"][1:]), 1),
        ("breaker: acceptNumerator == 0 -> AP-BREAKER-DISABLED", _mut(phases=[dict(
            GOOD["phases"][0], breaker={"acceptNumerator": 0, "acceptDenominator": 3})]
            + GOOD["phases"][1:]), 1),
        ("breaker: acceptNumerator > acceptDenominator -> AP-BREAKER-RATIO", _mut(phases=[dict(
            GOOD["phases"][0], breaker={"acceptNumerator": 4, "acceptDenominator": 3})]
            + GOOD["phases"][1:]), 1),
        ("breaker: acceptDenominator < 1 -> AP-BREAKER-RATIO", _mut(phases=[dict(
            GOOD["phases"][0], breaker={"acceptNumerator": 1, "acceptDenominator": 0})]
            + GOOD["phases"][1:]), 1),
        ("breaker: scope not 'per-batch' -> AP-BREAKER-SCOPE", _mut(phases=[dict(
            GOOD["phases"][0], breaker={"acceptNumerator": 2, "acceptDenominator": 3,
                "scope": "per-run"})] + GOOD["phases"][1:]), 1),
        ("breaker: on a single-writer phase -> AP-BREAKER-KIND", _mut(phases=GOOD["phases"][:2]
            + [dict(GOOD["phases"][2], breaker={"acceptNumerator": 2, "acceptDenominator": 3})]), 1),
        ("breaker: on a referee-fixture phase -> AP-BREAKER-KIND", _mut(GOOD_REF,
            phases=[dict(GOOD_REF["phases"][0],
                breaker={"acceptNumerator": 2, "acceptDenominator": 3})]
                + GOOD_REF["phases"][1:]), 1),
        # base / AP-BASE-* (#79)
        ("base: clean stacked pair", CHAIN_BASED, 0),
        ("base: on a non-fanout-redundant phase -> AP-BASE-INVALID", _mut(CHAIN_BASED,
            phases=[CHAIN_BASED["phases"][0], dict(CHAIN_BASED["phases"][1], base="build1")]
                + CHAIN_BASED["phases"][2:]), 1),
        ("base: names a later phase -> AP-BASE-INVALID", _mut(CHAIN_BASED,
            phases=[dict(CHAIN_BASED["phases"][0], base="build2")] + CHAIN_BASED["phases"][1:]), 1),
        ("base: names a non-fanout-redundant phase -> AP-BASE-INVALID", _mut(CHAIN_BASED,
            phases=CHAIN_BASED["phases"][:2] + [dict(CHAIN_BASED["phases"][2],
                base="referee1")] + CHAIN_BASED["phases"][3:]), 1),
        ("base: unknown phase id -> AP-BASE-INVALID", _mut(CHAIN_BASED,
            phases=CHAIN_BASED["phases"][:2] + [dict(CHAIN_BASED["phases"][2],
                base="nope")] + CHAIN_BASED["phases"][3:]), 1),
        ("base: names an unreviewed fanout-redundant phase -> AP-BASE-INVALID", _mut(
            phases=[dict(GOOD["phases"][0], id="build0", marker="built0")]
                + [dict(GOOD["phases"][0], base="build0", requires=["built0"])]
                + GOOD["phases"][1:]), 1),
        ("base: under the workflow backend -> AP-BASE-BACKEND", _mut(SIX,
            phases=SIX["phases"][:2] + [dict(SIX["phases"][2], base="contract")]
                + SIX["phases"][3:]), 1),
        # supersedes / roundBreaker (#93)
        ("supersedes: a valid runId string -- clean", _mut(supersedes="ap-2026-09-20-abcd"), 0),
        ("supersedes: not a string -> AP-SUPERSEDES-INVALID", _mut(supersedes=5), 1),
        ("supersedes: names this spec's own runId -> AP-SUPERSEDES-INVALID",
            _mut(supersedes=GOOD["runId"]), 1),
        ("roundBreaker.maxAdvancingRounds 2 -- clean",
            _mut(roundBreaker={"maxAdvancingRounds": 2}), 0),
        ("roundBreaker.maxAdvancingRounds 3 -- clean",
            _mut(roundBreaker={"maxAdvancingRounds": 3}), 0),
        ("roundBreaker: not an object -> AP-ROUNDBREAKER-INVALID", _mut(roundBreaker="2"), 1),
        ("roundBreaker.maxAdvancingRounds 1 -> AP-ROUNDBREAKER-INVALID",
            _mut(roundBreaker={"maxAdvancingRounds": 1}), 1),
        ("roundBreaker.maxAdvancingRounds a string -> AP-ROUNDBREAKER-INVALID",
            _mut(roundBreaker={"maxAdvancingRounds": "3"}), 1),
        ("roundBreaker.maxAdvancingRounds a bool -> AP-ROUNDBREAKER-INVALID",
            _mut(roundBreaker={"maxAdvancingRounds": True}), 1),
    ]
    fails = []
    for name, spec, want in cases:
        got, _warns = validate(spec, accepted, rejected)
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

    print("\nAP-SIBLING-INVISIBLE (#79) warnings:")
    warn_cases = [
        ("GOOD: one fanout-redundant phase, no warning", GOOD, 0),
        ("SIX: one fanout-redundant phase, no warning", SIX, 0),
        ("GOOD_REF: one fanout-redundant phase, no warning", GOOD_REF, 0),
        ("CHAIN: stacked pair with no base warns, naming both phases", CHAIN, 1),
        ("CHAIN_BASED: the same pair with base supplied warns not at all", CHAIN_BASED, 0),
    ]
    warn_fails = []
    for name, spec, want_min in warn_cases:
        _errs, warns = validate(spec, accepted, rejected)
        ok = (len(warns) >= want_min) if want_min else not warns
        ok = ok and (want_min == 0 or all("build1" in w and "build2" in w for w in warns))
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {len(warns)} warning(s)")
        if not ok:
            warn_fails.append(name)
            for w in warns:
                print(f"        {w}")
    print()
    if warn_fails:
        print(f"SELFTEST FAILED ({len(warn_fails)}): " + ", ".join(warn_fails))
        return 1

    print("\nrecorded-red fixtures (test_red_fixtures.py):")
    red_fails = test_red_fixtures.run_checks(root)
    if red_fails:
        for f in red_fails:
            print(f"  FAIL {f}")
        print(f"\nSELFTEST FAILED ({len(red_fails)} recorded-red failure(s))")
        return 1
    print("  all recorded-red fixtures behave as recorded")
    return 0


def classify_check(check: str, timeout: float, cwd: Path) -> tuple:
    """Run one acceptance `check` via the shell and classify its exit.

    RAN is every exit but the three named classes below -- a check that ran
    and FAILED still ran; only a check that never executed at all is
    rejected. Runs under /bin/sh, like reconcile.py's `measure()` and
    compile_spec's own acceptance.check contract: the string is the spec's
    own declared command, run exactly as a CI step would run it.
    """
    try:
        p = subprocess.run(["/bin/sh", "-c", check], cwd=cwd, capture_output=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    rc = p.returncode
    if rc == 127:
        return "ABSENT-TARGET", rc
    if rc == 2:
        return "SYNTAX", rc
    if rc == 126:
        return "PERMISSION", rc
    return "RAN", rc


def probe_checks(spec: dict, timeout: float) -> int:
    """--probe-checks (#74): opt-in only -- a plain compile executes nothing.

    Runs every problem.acceptance check once, cwd = the process's own cwd, and
    prints one stdout line per COMMAND: `PROBE <id> <CLASS> exit=<n>`. `check`
    may be a single string or a non-empty list of strings (#81) -- an array's
    elements each print their own PROBE line, sharing their criterion's id, so
    the line shape itself never changes. Any command that did not RAN --
    ABSENT-TARGET, SYNTAX, PERMISSION or TIMEOUT -- is rejected by id with
    [AP-CHECK-NOT-RAN]: a criterion nothing could execute cannot referee
    anything, and this is a static-shaped guarantee no later 'it fails, but
    at least it ran' report could give.

    validate() (AP-CHECK-SHAPE) already refused any spec whose `check` is not
    one of the shapes land_candidate.checks_of() accepts, and main() never
    reaches here when validate() rejected -- so a CheckShapeError here would
    mean this spec was never actually validated first.

    Exit: 0 every command ran, 1 some command did not.
    """
    acceptance = (spec.get("problem") or {}).get("acceptance") or []
    cwd = Path.cwd()
    rejected = []
    for i, a in enumerate(acceptance):
        if not isinstance(a, dict):
            continue
        cmds = land_candidate.checks_of(a.get("check"))
        if not cmds:
            continue
        aid = a.get("id")
        for cmd in cmds:
            cls, exit_code = classify_check(cmd, timeout, cwd)
            print(f"PROBE {aid} {cls} exit={exit_code}")
            if cls != "RAN":
                rejected.append((i, aid, cls))
    if rejected:
        for i, aid, cls in rejected:
            print(f"REJECTED problem.acceptance[{i}] ({aid}): [AP-CHECK-NOT-RAN] check "
                  f"classified {cls}, never RAN; a criterion nothing could execute cannot "
                  "referee anything", file=sys.stderr)
        print(f"{len(rejected)} rejection(s); nothing written", file=sys.stderr)
        return 1
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
    parser.add_argument("--dry-land", action="store_true",
                        help="print DRYLAND <phaseId> <path> IN|OUTSIDE|REFOWNED for every "
                             "declared 'outputs' path, then compile as normal")
    parser.add_argument("--probe-checks", action="store_true",
                        help="opt-in: run every acceptance check once via the shell and "
                             "classify its exit (a plain compile executes nothing)")
    parser.add_argument("--probe-timeout", type=float, default=60,
                        help="seconds before a probed check is classified TIMEOUT (default 60)")
    parser.add_argument("--selftest", action="store_true",
                        help="run the planted-defect selftest instead")
    parser.add_argument("--strict", action="store_true",
                        help="treat any WARNING (AP-SIBLING-INVISIBLE) as a rejection; without "
                             "it a warning still prints but the spec still compiles and writes")
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
    errors, warnings = validate(spec, accepted, rejected)
    # Warnings print whether or not there are rejections -- a spec that is
    # rejected for one reason may still carry an AP-SIBLING-INVISIBLE warning a
    # human fixing the rejection would want to see in the same pass.
    for w in warnings:
        print(f"WARNING {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"REJECTED {e}", file=sys.stderr)
        print(f"{len(errors)} rejection(s); nothing written", file=sys.stderr)
        return 1
    if warnings and args.strict:
        print(f"{len(warnings)} warning(s); --strict treats a WARNING as a rejection; "
              "nothing written", file=sys.stderr)
        return 1

    if args.dry_land:
        wscope = spec.get("writeScope") or []
        rowned = spec.get("refereeOwned") or []
        for ph in spec.get("phases") or []:
            if not isinstance(ph, dict):
                continue
            for path in ph.get("outputs") or []:
                if not land_candidate.in_scope(path, wscope):
                    status = "OUTSIDE"
                elif ph.get("kind") in FANOUT_KINDS and land_candidate.in_scope(path, rowned):
                    status = "REFOWNED"
                else:
                    status = "IN"
                print(f"DRYLAND {ph.get('id')} {path} {status}")

    if args.probe_checks:
        rc = probe_checks(spec, args.probe_timeout)
        if rc != 0:
            return rc

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
