"""compass_lib — shared enforcement primitives for the compass plugin.

Every numeric bound in the behavioral specification lives here as a NAMED
CONSTANT, and every "MUST NOT / MUST refuse / MUST halt" rule is enforced by a
function that raises GuardError (which the CLI turns into a non-zero exit).

Nothing in this module trusts prose. A rule is enforced only if a conditional
tests the rule's own state and then refuses. This module is the single source
of truth for those conditionals; skills and workflows invoke it, they do not
re-describe it.
"""

from __future__ import annotations

import re
from typing import Any

# --------------------------------------------------------------------------- #
# Numeric bounds — one named constant per threshold in the spec.
# --------------------------------------------------------------------------- #

# compass-clarify-scope
CLARIFY_UNCERTAINTY_FLAG_THRESHOLD = 70      # confidence < 70 -> must flag
KNOWN_FACT_WARN_THRESHOLD = 90               # known fact < 90 -> must mark ⚠️
WARN_MARKER = "⚠️"                 # ⚠️

# compass-decompose-chain
DECOMPOSE_MIN_STAGES = 2
DECOMPOSE_MAX_STAGES = 5

# compass-explore-branches
EXPLORE_DEFAULT_BRANCHES = 3
EXPLORE_HARD_MAX_BRANCHES = 6
BRANCH_SCORE_MIN = 1
BRANCH_SCORE_MAX = 10
BRANCH_AXES = ("feasibility", "impact", "risk")

# compass-draft-revise
DRAFT_SCORE_MIN = 1
DRAFT_SCORE_MAX = 5
DRAFT_THRESHOLD_DEFAULT = 3
DRAFT_MAX_REVISION_CYCLES = 2                 # first pass + one escalation pass

# compass-calibrate-format
CALIBRATE_MIN_EXAMPLES = 2
CALIBRATE_MAX_EXAMPLES = 5

# compass-optimize-instruction
APE_FRAMINGS = (
    "rule-based",
    "example-based",
    "definition-based",
    "question-based",
    "chain-of-thought-based",
)
OPTIMIZE_CANDIDATE_COUNT = len(APE_FRAMINGS)  # exactly 5
META_PROMPTING_CHECKLIST_SIZE = 4

# compass-map-relationships
MAP_MAX_TRIPLES = 50

# compass-reason-verify
SELF_CONSISTENCY_ATTEMPTS = 3
SELF_CONSISTENCY_STRATEGIES = (
    "forward deduction",
    "backward from options",
    "constraint mapping",
)
REASON_RUNGS = ("rung-0", "rung-1", "rung-2a", "rung-2b")

# compass-verify-assumptions
VERIFY_MAX_STEPS = 3
VERIFY_CONFIDENCE_GATE = 90                   # new confidence must be >= 90

# compass-summarize-trace
TRACE_SECTIONS = (
    "What was asked",
    "What was assumed",
    "Approaches weighed",
    "What ran",
    "What was produced",
    "What was revised",
    "What was NOT done",
)
TRACE_APPROACHES_SECTION = "Approaches weighed"
TRACE_REVISED_SECTION = "What was revised"

# compass-solve
PHASE_ORDER = ("Clarify", "Explore", "Decompose", "Execute", "Revise")
EXECUTION_MODES = (
    "reason-verify",
    "investigate-dynamically",
    "ground-evidence",
    "calibrate-format",
)

# compass-ground-evidence
RAG_REFUSAL_TEMPLATE = (
    "The available {sources} do not contain sufficient information to {claim}."
)
RAG_REFUSAL_REGEX = re.compile(
    r"The available .+ do not contain sufficient information to .+",
    re.IGNORECASE,
)
CITATION_REGEX = re.compile(
    r"\([^)]+:\d+\)"                       # (file:line)
    r"|\(https?://[^)]+\)"                # (URL)
    r"|\(Prior knowledge\s*⚠️\)",  # (Prior knowledge ⚠️)
)

# Write scope
DEFAULT_OUTPUT_DIR = ".compass"


class GuardError(Exception):
    """Raised when a spec rule is violated. The CLI maps this to exit code 2."""


def _require_key(record: dict, key: str, where: str) -> Any:
    """Reject — never default — a missing gating field (spec requirement 3/4)."""
    if not isinstance(record, dict):
        raise GuardError(f"{where}: expected an object, got {type(record).__name__}")
    if key not in record:
        raise GuardError(
            f"{where}: missing required gating field '{key}'. "
            f"A value nobody supplied must never enter the artifact — rejected."
        )
    if record[key] is None:
        raise GuardError(
            f"{where}: gating field '{key}' is null. Refusing to infer or repair it."
        )
    return record[key]


def _require_int_in(value: Any, lo: int, hi: int, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GuardError(f"{where}: expected a number in [{lo},{hi}], got {value!r}")
    if int(value) != value:
        raise GuardError(f"{where}: expected an integer in [{lo},{hi}], got {value!r}")
    value = int(value)
    if not (lo <= value <= hi):
        raise GuardError(f"{where}: value {value} out of allowed range [{lo},{hi}]")
    return value


# --------------------------------------------------------------------------- #
# Write-scope guard (spec requirement 5) — throws BEFORE any write.
# --------------------------------------------------------------------------- #

def enforce_write_scope(target: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> str:
    """Reject path traversal, absolute paths, and targets outside output_dir.

    Returns the normalized relative path when safe; raises GuardError otherwise.
    Purely lexical — never touches the filesystem, so it is safe to call before
    a directory exists.
    """
    import posixpath

    if not isinstance(target, str) or target == "":
        raise GuardError("write-scope: empty target path rejected")
    norm_target = target.replace("\\", "/")
    if norm_target.startswith("/") or re.match(r"^[A-Za-z]:", norm_target):
        raise GuardError(f"write-scope: absolute path rejected: {target!r}")
    if "\x00" in norm_target:
        raise GuardError("write-scope: null byte in path rejected")

    joined = posixpath.normpath(posixpath.join(output_dir, norm_target))
    base = posixpath.normpath(output_dir)
    # After normalization, any traversal escaping the base surfaces as a ".."
    # prefix or a path that does not sit under base.
    if joined == base or joined.startswith(base + "/"):
        rel = posixpath.relpath(joined, base)
        if rel.startswith("..") or posixpath.isabs(rel):
            raise GuardError(f"write-scope: path escapes {output_dir!r}: {target!r}")
        return joined
    raise GuardError(
        f"write-scope: target {target!r} resolves outside declared output dir "
        f"{output_dir!r}"
    )


# --------------------------------------------------------------------------- #
# compass-clarify-scope enforcement
# --------------------------------------------------------------------------- #

def classify_uncertainty(entry: dict, index: int) -> dict:
    """Enforce the 70% flagging gate. Confidence is a first-class gating field:
    a missing value is rejected, never defaulted."""
    where = f"uncertainty[{index}]"
    element = _require_key(entry, "element", where)
    confidence = _require_key(entry, "confidence", where)
    confidence = _require_int_in(confidence, 0, 100, f"{where}.confidence")
    # 'blocking' gates the solve-pipeline pause; it must be supplied explicitly.
    blocking = _require_key(entry, "blocking", where)
    if not isinstance(blocking, bool):
        raise GuardError(f"{where}.blocking must be a boolean, got {blocking!r}")
    must_flag = confidence < CLARIFY_UNCERTAINTY_FLAG_THRESHOLD
    return {
        "element": element,
        "confidence": confidence,
        "blocking": blocking,
        "flagged": must_flag,
        "default_interpretation": entry.get("default_interpretation"),
        "other_readings": entry.get("other_readings", []),
    }


def mark_known_fact(entry: dict, index: int) -> dict:
    where = f"known_fact[{index}]"
    fact = _require_key(entry, "fact", where)
    confidence = _require_key(entry, "confidence", where)
    confidence = _require_int_in(confidence, 0, 100, f"{where}.confidence")
    needs_marker = confidence < KNOWN_FACT_WARN_THRESHOLD
    return {
        "fact": fact,
        "confidence": confidence,
        "marker": WARN_MARKER if needs_marker else "",
        "rendered": f"{fact} {WARN_MARKER}".strip() if needs_marker else fact,
    }


def validate_clarify(state: dict) -> dict:
    """Validate a clarify artifact on read/write and derive the pause decision."""
    uncertainties = state.get("flagged_uncertainties", [])
    if not isinstance(uncertainties, list):
        raise GuardError("clarify: flagged_uncertainties must be a list")
    classified = [classify_uncertainty(u, i) for i, u in enumerate(uncertainties)]
    facts = state.get("known_facts", [])
    if not isinstance(facts, list):
        raise GuardError("clarify: known_facts must be a list")
    marked = [mark_known_fact(f, i) for i, f in enumerate(facts)]

    flagged = [u for u in classified if u["flagged"]]
    # A flagged uncertainty that is load-bearing forces a pause.
    blocking = [u for u in flagged if u["blocking"]]
    return {
        "uncertainties": classified,
        "known_facts": marked,
        "flagged_count": len(flagged),
        "blocking_uncertainties": blocking,
        "must_pause": len(blocking) > 0,
    }


# --------------------------------------------------------------------------- #
# compass-decompose-chain enforcement (stage graph)
# --------------------------------------------------------------------------- #

def validate_dag(stages: list) -> dict:
    """Enforce: 2..5 stages, per-stage contracts, an entry point, no dangling
    dependsOn, no cycles. Returns Kahn-computed waves on success."""
    if not isinstance(stages, list):
        raise GuardError("decompose: stages must be a list")
    n = len(stages)
    if n < DECOMPOSE_MIN_STAGES:
        raise GuardError(
            f"decompose: {n} stage(s) < minimum {DECOMPOSE_MIN_STAGES} "
            f"— fewer than {DECOMPOSE_MIN_STAGES} means decomposing was not needed"
        )
    if n > DECOMPOSE_MAX_STAGES:
        raise GuardError(
            f"decompose: {n} stages > maximum {DECOMPOSE_MAX_STAGES} "
            f"— exceeding {DECOMPOSE_MAX_STAGES} signals the task needs re-scoping"
        )

    ids: list[str] = []
    deps: dict[str, list[str]] = {}
    for i, stage in enumerate(stages):
        where = f"stage[{i}]"
        sid = _require_key(stage, "id", where)
        _require_key(stage, "name", where)
        _require_key(stage, "input_contract", where)
        _require_key(stage, "output_contract", where)
        depends = _require_key(stage, "dependsOn", where)
        if not isinstance(depends, list):
            raise GuardError(f"{where}.dependsOn must be an array")
        if sid in deps:
            raise GuardError(f"decompose: duplicate stage id {sid!r}")
        ids.append(sid)
        deps[sid] = list(depends)

    idset = set(ids)
    # No dangling references.
    for sid, depends in deps.items():
        for d in depends:
            if d not in idset:
                raise GuardError(
                    f"decompose: stage {sid!r} dependsOn non-existent id {d!r}"
                )
            if d == sid:
                raise GuardError(f"decompose: stage {sid!r} depends on itself")

    # At least one entry point.
    entries = [sid for sid in ids if not deps[sid]]
    if not entries:
        raise GuardError(
            "decompose: no entry point — at least one stage must have dependsOn: []"
        )

    # Kahn's algorithm: computes waves AND detects cycles (leftover => cycle).
    indeg = {sid: len(deps[sid]) for sid in ids}
    waves: list[list[str]] = []
    remaining = set(ids)
    while remaining:
        wave = sorted(sid for sid in remaining if indeg[sid] == 0)
        if not wave:
            raise GuardError(
                "decompose: cycle detected in dependsOn graph "
                f"(unresolved: {sorted(remaining)}) — graph must be acyclic"
            )
        for sid in wave:
            remaining.discard(sid)
        for sid in remaining:
            indeg[sid] = sum(1 for d in deps[sid] if d in remaining)
        waves.append(wave)

    return {"stage_count": n, "entry_points": entries, "waves": waves}


# --------------------------------------------------------------------------- #
# compass-explore-branches enforcement
# --------------------------------------------------------------------------- #

def effective_branch_cap(requested: int | None, config_max: int | None) -> int:
    """Cap = min(hard max 6, config max_branch_count) — whichever is lower."""
    cap = EXPLORE_HARD_MAX_BRANCHES
    if config_max is not None:
        cap = min(cap, _require_int_in(config_max, 1, 999, "config.max_branch_count"))
    if requested is None:
        return min(EXPLORE_DEFAULT_BRANCHES, cap)
    requested = _require_int_in(requested, 1, 999, "requested branch count")
    return min(requested, cap)


def validate_branch_scores(branches: list) -> dict:
    """Enforce 1-10 scoring on each axis, Total = raw sum (Risk NOT inverted),
    and select highest-total, tie-break by lower risk."""
    if not isinstance(branches, list) or not branches:
        raise GuardError("explore: at least one scored branch required")
    scored = []
    for i, b in enumerate(branches):
        where = f"branch[{i}]"
        name = _require_key(b, "name", where)
        axes = {}
        for axis in BRANCH_AXES:
            axes[axis] = _require_int_in(
                _require_key(b, axis, where),
                BRANCH_SCORE_MIN,
                BRANCH_SCORE_MAX,
                f"{where}.{axis}",
            )
        total = axes["feasibility"] + axes["impact"] + axes["risk"]  # raw sum
        scored.append({"name": name, **axes, "total": total,
                       "biggest_blocker": b.get("biggest_blocker")})
    # Highest total; ties broken by lower risk.
    winner = min(scored, key=lambda s: (-s["total"], s["risk"]))
    return {"scored": scored, "selected": winner["name"], "winner": winner}


# --------------------------------------------------------------------------- #
# compass-solve run-reuse enforcement (state-find's selection rule)
# --------------------------------------------------------------------------- #

def select_reusable_run(candidates: list[dict], raw_task: str) -> dict | None:
    """Pick the persisted run whose own `raw_task` matches the given text
    byte-for-byte (no fuzzy/normalized matching — a mismatch is reported as
    "not found," never guessed at), preferring the most recently modified
    match when more than one exists. Each candidate is
    {"path": str, "mtime": float, "state": dict} — already loaded and
    schema-validated by the caller (compass.py's state-find subcommand);
    this function makes no filesystem calls of its own, so it is directly
    testable without I/O. Returns the winning candidate, or None if nothing
    matches — finding nothing is the normal, common case (first time this
    exact text has gone through this phase), never an error.
    """
    matches = [c for c in candidates if c["state"].get("raw_task") == raw_task]
    if not matches:
        return None
    return max(matches, key=lambda c: c["mtime"])


# --------------------------------------------------------------------------- #
# compass-draft-revise enforcement
# --------------------------------------------------------------------------- #

def plan_revision(criteria: list, threshold: int | None = None) -> dict:
    """Score each criterion 1-5; revise ONLY those at or below threshold; flag a
    required second cycle if any criterion still fails after scoring."""
    if threshold is None:
        threshold = DRAFT_THRESHOLD_DEFAULT
    threshold = _require_int_in(threshold, DRAFT_SCORE_MIN, DRAFT_SCORE_MAX,
                                "revise threshold")
    if not isinstance(criteria, list) or not (3 <= len(criteria) <= 7):
        raise GuardError(
            f"revise: expected 3-7 numbered criteria, got {len(criteria) if isinstance(criteria, list) else criteria}"
        )
    to_revise, to_keep = [], []
    for i, c in enumerate(criteria):
        where = f"criterion[{i}]"
        text = _require_key(c, "criterion", where)
        score = _require_int_in(_require_key(c, "score", where),
                                DRAFT_SCORE_MIN, DRAFT_SCORE_MAX, f"{where}.score")
        (to_revise if score <= threshold else to_keep).append(
            {"criterion": text, "score": score})
    return {
        "threshold": threshold,
        "revise": to_revise,           # at or below threshold
        "keep_untouched": to_keep,     # above threshold — MUST NOT modify
        "needs_second_cycle": len(to_revise) > 0,
    }


def check_revision_report(result: dict) -> dict:
    """A revision MUST ship a changes list (one bullet per required fix) and MUST
    NOT touch above-threshold criteria."""
    plan = _require_key(result, "plan", "revision result")
    changes = _require_key(result, "changes", "revision result")
    if not isinstance(changes, list):
        raise GuardError("revise: 'changes' must be a list of bullets")
    required = plan.get("revise", [])
    if len(required) > 0 and len(changes) == 0:
        raise GuardError(
            "revise: revision presented without a changes list — one bullet per "
            "required fix is mandatory"
        )
    touched = result.get("touched_criteria", [])
    kept = {c["criterion"] for c in plan.get("keep_untouched", [])}
    illegal = [t for t in touched if t in kept]
    if illegal:
        raise GuardError(
            f"revise: above-threshold criteria were modified (not allowed): {illegal}"
        )
    return {"ok": True, "required_fixes": len(required), "reported": len(changes)}


def check_revision_cycle_count(cycles_run: int) -> int:
    if cycles_run > DRAFT_MAX_REVISION_CYCLES:
        raise GuardError(
            f"revise: {cycles_run} revision cycles exceeds hard max "
            f"{DRAFT_MAX_REVISION_CYCLES}"
        )
    return cycles_run


# --------------------------------------------------------------------------- #
# compass-calibrate-format enforcement
# --------------------------------------------------------------------------- #

def validate_examples(examples: list, constructed: bool) -> dict:
    if not isinstance(examples, list):
        raise GuardError("calibrate: examples must be a list")
    n = len(examples)
    if n < CALIBRATE_MIN_EXAMPLES:
        raise GuardError(
            f"calibrate: {n} example(s) < minimum {CALIBRATE_MIN_EXAMPLES} "
            f"— fewer than {CALIBRATE_MIN_EXAMPLES} is not few-shot anchoring"
        )
    if n > CALIBRATE_MAX_EXAMPLES:
        raise GuardError(
            f"calibrate: {n} examples > maximum {CALIBRATE_MAX_EXAMPLES} "
            f"— more than {CALIBRATE_MAX_EXAMPLES} signals an underspecified format"
        )
    if constructed:
        kinds = {e.get("kind") for e in examples if isinstance(e, dict)}
        if "happy-path" not in kinds:
            raise GuardError("calibrate: constructed set must include a happy path")
        if "edge-case" not in kinds:
            raise GuardError("calibrate: constructed set must include >=1 edge case")
        if not any(e.get("near_boundary") for e in examples if isinstance(e, dict)):
            raise GuardError(
                "calibrate: at least one example must sit near a decision boundary "
                "(all-alike example sets are rejected)"
            )
    return {"count": n, "constructed": constructed}


# --------------------------------------------------------------------------- #
# compass-optimize-instruction enforcement
# --------------------------------------------------------------------------- #

def validate_candidates(candidates: list) -> dict:
    """Exactly 5 candidates, one per APE framing; select highest score, tie-break
    by framing precedence order."""
    if not isinstance(candidates, list):
        raise GuardError("optimize: candidates must be a list")
    if len(candidates) != OPTIMIZE_CANDIDATE_COUNT:
        raise GuardError(
            f"optimize: expected exactly {OPTIMIZE_CANDIDATE_COUNT} candidates "
            f"(one per APE framing), got {len(candidates)}"
        )
    framings = [_require_key(c, "framing", f"candidate[{i}]")
                for i, c in enumerate(candidates)]
    if set(framings) != set(APE_FRAMINGS):
        raise GuardError(
            f"optimize: candidates must cover exactly the framings {list(APE_FRAMINGS)}; "
            f"got {framings}"
        )
    order = {f: i for i, f in enumerate(APE_FRAMINGS)}
    scored = []
    for i, c in enumerate(candidates):
        score = _require_int_in(_require_key(c, "score", f"candidate[{i}]"),
                                0, 10 ** 6, f"candidate[{i}].score")
        scored.append({"framing": c["framing"], "score": score})
    winner = min(scored, key=lambda s: (-s["score"], order[s["framing"]]))
    return {"scored": scored, "winner": winner["framing"]}


def validate_critique(checklist: list) -> dict:
    if not isinstance(checklist, list) or len(checklist) != META_PROMPTING_CHECKLIST_SIZE:
        raise GuardError(
            f"optimize: meta-prompting critique must have exactly "
            f"{META_PROMPTING_CHECKLIST_SIZE} items, got "
            f"{len(checklist) if isinstance(checklist, list) else checklist}"
        )
    failing = [c for i, c in enumerate(checklist)
               if not _require_key(c, "pass", f"checklist[{i}]")]
    return {"revise_only": [c.get("criterion") for c in failing]}


# --------------------------------------------------------------------------- #
# compass-map-relationships enforcement
# --------------------------------------------------------------------------- #

def validate_triples(triples: list, traversal: list | None = None) -> dict:
    if not isinstance(triples, list):
        raise GuardError("map: triples must be a list")
    if len(triples) > MAP_MAX_TRIPLES:
        raise GuardError(
            f"map: {len(triples)} triples > ~{MAP_MAX_TRIPLES} limit — pre-filter to "
            f"the relevant subgraph instead of injecting the full graph"
        )
    indexed = set()
    for i, t in enumerate(triples):
        where = f"triple[{i}]"
        idx = _require_key(t, "index", where)
        _require_key(t, "subject", where)
        _require_key(t, "predicate", where)
        _require_key(t, "object", where)
        indexed.add(idx)
    if traversal:
        for i, hop in enumerate(traversal):
            where = f"hop[{i}]"
            ref = _require_key(hop, "triple_index", where)
            if ref not in indexed:
                raise GuardError(
                    f"{where}: cites triple_index {ref!r} not present in the table "
                    f"— every hop must point at a numbered triple"
                )
    return {"triple_count": len(triples)}


# --------------------------------------------------------------------------- #
# compass-reason-verify enforcement
# --------------------------------------------------------------------------- #

def select_rung(signals: dict) -> dict:
    """Deterministic rung selection from concrete signals. Multimodal-CoT is a
    precedence flag applied BEFORE whichever rung is chosen."""
    multimodal = bool(signals.get("has_image_or_diagram"))
    precision = bool(signals.get("precision_arith")
                     or signals.get("many_variables")
                     or signals.get("large_numbers")
                     or signals.get("rounding_risk")
                     or signals.get("conditional_logic"))
    high_stakes_unique = bool(signals.get("single_correct_answer")
                              and signals.get("costly_wrong_assumption"))
    multistep = bool(signals.get("multistep_arithmetic")
                     or signals.get("dependent_intermediate_values")
                     or signals.get("multistep_deduction"))

    if precision:
        rung = "rung-2b"
    elif high_stakes_unique:
        rung = "rung-2a"
    elif multistep:
        rung = "rung-1"
    else:
        rung = "rung-0"

    # Rung-0 gate: only permitted when there is genuinely no dependent step.
    if rung == "rung-0" and multistep:
        raise GuardError("reason-verify: rung-0 illegal when dependent steps exist")
    return {
        "rung": rung,
        "multimodal_cot_first": multimodal,
        "self_consistency_paths": SELF_CONSISTENCY_ATTEMPTS if rung == "rung-2a" else 0,
    }


def validate_self_consistency(attempts: list) -> dict:
    if not isinstance(attempts, list) or len(attempts) != SELF_CONSISTENCY_ATTEMPTS:
        raise GuardError(
            f"reason-verify: Rung 2a requires exactly {SELF_CONSISTENCY_ATTEMPTS} "
            f"independent attempts, got "
            f"{len(attempts) if isinstance(attempts, list) else attempts}"
        )
    strategies = [_require_key(a, "strategy", f"attempt[{i}]")
                  for i, a in enumerate(attempts)]
    if set(strategies) != set(SELF_CONSISTENCY_STRATEGIES):
        raise GuardError(
            f"reason-verify: the 3 attempts must use strategies "
            f"{list(SELF_CONSISTENCY_STRATEGIES)}; got {strategies}"
        )
    return {"attempts": len(attempts)}


# --------------------------------------------------------------------------- #
# compass-verify-assumptions enforcement
# --------------------------------------------------------------------------- #

def validate_verify_run(run: dict) -> dict:
    """One assumption per invocation; <=3 R/A/O steps; stop at first outcome;
    confidence-raised outcome must clear the 90 gate and cite a source."""
    assumption = _require_key(run, "assumption", "verify run")
    if isinstance(assumption, list):
        raise GuardError(
            "verify-assumptions: exactly one assumption per invocation — the "
            "3-step budget is never shared across entries"
        )
    steps = _require_key(run, "steps", "verify run")
    if not isinstance(steps, list):
        raise GuardError("verify-assumptions: steps must be a list")
    if len(steps) > VERIFY_MAX_STEPS:
        raise GuardError(
            f"verify-assumptions: {len(steps)} steps > hard max {VERIFY_MAX_STEPS}"
        )
    for i, s in enumerate(steps):
        where = f"step[{i}]"
        _require_key(s, "reasoning", where)
        _require_key(s, "action", where)
        _require_key(s, "observation", where)

    outcome = _require_key(run, "outcome", "verify run")
    kind = _require_key(outcome, "kind", "outcome")
    if kind not in ("confidence_raised", "reading_changed", "still_unresolved"):
        raise GuardError(f"verify-assumptions: unknown outcome kind {kind!r}")

    if kind == "confidence_raised":
        conf = _require_int_in(_require_key(outcome, "confidence", "outcome"),
                               0, 100, "outcome.confidence")
        if conf < VERIFY_CONFIDENCE_GATE:
            raise GuardError(
                f"verify-assumptions: confidence {conf} < gate "
                f"{VERIFY_CONFIDENCE_GATE} — must remain still_unresolved"
            )
    if kind in ("confidence_raised", "reading_changed"):
        cites = outcome.get("citations")
        if not isinstance(cites, list) or not cites:
            raise GuardError(
                "verify-assumptions: a resolved outcome must cite sources "
                "(file:line or URL)"
            )
    return {"outcome": kind, "steps_used": len(steps)}


# --------------------------------------------------------------------------- #
# compass-summarize-trace enforcement
# --------------------------------------------------------------------------- #

def validate_trace(trace: dict) -> dict:
    """Exactly 7 sections in order; omit Approaches iff Explore did not run;
    'What was revised' always present; every dag stage listed under What ran."""
    explore_ran = _require_key(trace, "explore_ran", "trace")
    if not isinstance(explore_ran, bool):
        raise GuardError("trace: explore_ran gating field must be a boolean")
    sections = _require_key(trace, "sections", "trace")
    if not isinstance(sections, list):
        raise GuardError("trace: sections must be an ordered list")
    titles = [_require_key(s, "title", f"section[{i}]")
              for i, s in enumerate(sections)]

    expected = list(TRACE_SECTIONS)
    if not explore_ran:
        expected = [t for t in expected if t != TRACE_APPROACHES_SECTION]
    if titles != expected:
        raise GuardError(
            f"trace: sections must be exactly {expected} in order; got {titles}"
        )
    if not explore_ran and TRACE_APPROACHES_SECTION in titles:
        raise GuardError(
            "trace: 'Approaches weighed' must be omitted entirely when Explore "
            "did not run (not left empty)"
        )

    # 'What was revised' must always be present with explicit content.
    revised = next((s for s in sections if s["title"] == TRACE_REVISED_SECTION), None)
    if revised is None or not str(revised.get("body", "")).strip():
        raise GuardError(
            "trace: 'What was revised' must be present and non-empty even when "
            "nothing was revised (state that explicitly)"
        )

    # Every dag stage must appear in 'What ran'.
    dag_stages = _require_key(trace, "dag_stages", "trace")
    if not isinstance(dag_stages, list):
        raise GuardError("trace: dag_stages must be a list")
    what_ran = next((s for s in sections if s["title"] == "What ran"), None)
    listed = set(what_ran.get("stage_ids", []) if what_ran else [])
    missing = [s for s in dag_stages if s not in listed]
    if missing:
        raise GuardError(
            f"trace: 'What ran' must list every dag stage; missing {missing}"
        )
    return {"section_count": len(titles), "explore_ran": explore_ran}


# --------------------------------------------------------------------------- #
# compass-negotiate-tradeoffs enforcement
# --------------------------------------------------------------------------- #

def validate_negotiation(payload: dict) -> dict:
    """Precondition: Explore already selected a winner. Gate: hybrid must
    outperform EVERY source on at least one axis, else it MUST NOT be presented."""
    winner_selected = _require_key(payload, "explore_winner_selected", "negotiate")
    if not winner_selected:
        raise GuardError(
            "negotiate-tradeoffs: MUST NOT run before compass-explore-branches has "
            "selected a winner — this skill runs strictly after selection"
        )
    sources = _require_key(payload, "sources", "negotiate")
    if not isinstance(sources, list) or not (2 <= len(sources) <= 3):
        raise GuardError("negotiate-tradeoffs: expected 2-3 source branches")
    hybrid = _require_key(payload, "hybrid", "negotiate")
    for axis in BRANCH_AXES:
        _require_int_in(_require_key(hybrid, axis, "hybrid"),
                        BRANCH_SCORE_MIN, BRANCH_SCORE_MAX, f"hybrid.{axis}")
    for i, s in enumerate(sources):
        for axis in BRANCH_AXES:
            _require_int_in(_require_key(s, axis, f"source[{i}]"),
                            BRANCH_SCORE_MIN, BRANCH_SCORE_MAX, f"source[{i}].{axis}")

    def beats_on_some_axis(src: dict) -> bool:
        return any(hybrid[a] > src[a] for a in BRANCH_AXES)

    losers = [s.get("name", f"source[{i}]")
              for i, s in enumerate(sources) if not beats_on_some_axis(s)]
    if losers:
        raise GuardError(
            "negotiate-tradeoffs: hybrid does not outperform every source on at "
            f"least one axis — MUST NOT present it. Fails against: {losers}"
        )
    return {"presentable": True, "sources": len(sources)}


# --------------------------------------------------------------------------- #
# compass-ground-evidence enforcement
# --------------------------------------------------------------------------- #

def validate_grounding(payload: dict) -> dict:
    """Every non-refused claim cited inline; unsupported claims must use the
    exact RAG refusal template."""
    claims = _require_key(payload, "claims", "ground-evidence")
    if not isinstance(claims, list) or not claims:
        raise GuardError("ground-evidence: claims must be listed before drafting")
    verified = warned = refused = 0
    for i, c in enumerate(claims):
        where = f"claim[{i}]"
        status = _require_key(c, "status", where)   # verified | warned | refused
        text = _require_key(c, "text", where)
        if status == "refused":
            if not RAG_REFUSAL_REGEX.search(text):
                raise GuardError(
                    f"{where}: refused claim must use the exact RAG template: "
                    f"'The available [sources] do not contain sufficient "
                    f"information to [claim].'"
                )
            refused += 1
            continue
        citation = c.get("citation", "")
        if not CITATION_REGEX.search(str(citation)) and not CITATION_REGEX.search(str(text)):
            raise GuardError(
                f"{where}: factual claim lacks an inline citation "
                f"(file:line), (URL), or (Prior knowledge {WARN_MARKER})"
            )
        if status == "warned":
            warned += 1
        elif status == "verified":
            verified += 1
        else:
            raise GuardError(f"{where}: unknown claim status {status!r}")
    return {
        "total": len(claims),
        "verified": verified,
        "warned": warned,
        "refused": refused,
        "coverage_line": (
            f"total claims: {len(claims)}, Verified: {verified}, "
            f"{WARN_MARKER}: {warned}, refused: {refused}"
        ),
    }


# --------------------------------------------------------------------------- #
# compass-solve pipeline enforcement (phase order, mode dispatch)
# --------------------------------------------------------------------------- #

def validate_phase_order(phases_run: list) -> dict:
    """Phases must appear in canonical order; Explore is the only skippable one."""
    if not isinstance(phases_run, list):
        raise GuardError("solve: phases_run must be a list")
    canonical = [p for p in PHASE_ORDER if p in phases_run]
    if phases_run != canonical:
        raise GuardError(
            f"solve: phases out of order. Expected subsequence of "
            f"{list(PHASE_ORDER)}, got {phases_run}"
        )
    for required in ("Clarify", "Decompose", "Execute", "Revise"):
        if required not in phases_run:
            raise GuardError(f"solve: mandatory phase {required!r} did not run")
    return {"explore_ran": "Explore" in phases_run}


def validate_stage_dispatch(stage: dict, index: int) -> dict:
    """Each stage must carry a runtime-decided execution mode (a first-class key,
    not hardcoded prose)."""
    where = f"execute stage[{index}]"
    sid = _require_key(stage, "id", where)
    mode = _require_key(stage, "mode", where)
    decided_at = _require_key(stage, "mode_decided_at", where)
    if mode not in EXECUTION_MODES:
        raise GuardError(f"{where}: unknown execution mode {mode!r}")
    if decided_at != "runtime":
        raise GuardError(
            f"{where}: mode must be decided at runtime, not hardcoded "
            f"(mode_decided_at={decided_at!r})"
        )
    return {"stage": sid, "mode": mode}
