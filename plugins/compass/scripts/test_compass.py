#!/usr/bin/env python3
"""Self-contained test suite for compass_lib guards.

Run: python3 scripts/test_compass.py
Exits 0 if every guard both accepts valid input and REFUSES invalid input.
This is the executable proof that the rules are enforced by code, not prose.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compass_lib as C

passed = failed = 0


def ok(label, fn):
    global passed, failed
    try:
        fn(); passed += 1
    except Exception as exc:  # noqa: BLE001
        failed += 1; print(f"FAIL (should have passed): {label}: {exc}")


def refuses(label, fn):
    global passed, failed
    try:
        fn(); failed += 1; print(f"FAIL (should have refused): {label}")
    except C.GuardError:
        passed += 1
    except Exception as exc:  # noqa: BLE001
        failed += 1; print(f"FAIL (wrong error): {label}: {exc}")


def stage(i, deps):
    return {"id": i, "name": i, "input_contract": "i",
            "output_contract": "o", "dependsOn": deps}


# --- decompose ---
ok("dag 2 stages", lambda: C.validate_dag([stage("a", []), stage("b", ["a"])]))
refuses("dag 1 stage < min", lambda: C.validate_dag([stage("a", [])]))
refuses("dag 6 stages > max",
        lambda: C.validate_dag([stage(x, []) for x in "abcdef"]))
refuses("dag dangling dep", lambda: C.validate_dag([stage("a", ["zzz"]), stage("b", [])]))
refuses("dag cycle",
        lambda: C.validate_dag([stage("a", []), stage("b", ["c"]), stage("c", ["b"])]))
refuses("dag no entry", lambda: C.validate_dag([stage("a", ["b"]), stage("b", ["a"])]))

# --- write scope ---
ok("scope safe", lambda: C.enforce_write_scope("runs/x.json"))
refuses("scope traversal", lambda: C.enforce_write_scope("../x"))
refuses("scope absolute", lambda: C.enforce_write_scope("/etc/passwd"))
refuses("scope windows abs", lambda: C.enforce_write_scope("C:/x"))

# --- clarify ---
ok("clarify ok", lambda: C.validate_clarify(
    {"flagged_uncertainties": [{"element": "e", "confidence": 50, "blocking": True}]}))
refuses("clarify missing confidence", lambda: C.validate_clarify(
    {"flagged_uncertainties": [{"element": "e", "blocking": True}]}))

# --- branch cap / scores ---
assert C.effective_branch_cap(None, None) == 3
assert C.effective_branch_cap(10, None) == 6
assert C.effective_branch_cap(10, 4) == 4
_bs = C.validate_branch_scores(
    [{"name": "A", "feasibility": 6, "impact": 6, "risk": 5},   # total 17
     {"name": "B", "feasibility": 7, "impact": 7, "risk": 3}])  # total 17, tie
assert _bs["selected"] == "B", _bs  # tie on total 17 -> lower risk (3) wins
refuses("branch score out of range", lambda: C.validate_branch_scores(
    [{"name": "A", "feasibility": 11, "impact": 6, "risk": 5}]))

# --- draft revise ---
_pl = C.plan_revision([{"criterion": "c1", "score": 2}, {"criterion": "c2", "score": 4},
                       {"criterion": "c3", "score": 5}])
assert _pl["threshold"] == 3 and len(_pl["revise"]) == 1 and _pl["needs_second_cycle"]
refuses("revise touched above-threshold", lambda: C.check_revision_report(
    {"plan": {"revise": [{"criterion": "c1"}], "keep_untouched": [{"criterion": "c2"}]},
     "changes": ["fixed c1"], "touched_criteria": ["c2"]}))
refuses("revise no changes list", lambda: C.check_revision_report(
    {"plan": {"revise": [{"criterion": "c1"}], "keep_untouched": []}, "changes": []}))
refuses("revise cycles over max", lambda: C.check_revision_cycle_count(3))

# --- calibrate ---
ok("calibrate 2", lambda: C.validate_examples([1, 2], False))
refuses("calibrate 1 < min", lambda: C.validate_examples([1], False))
refuses("calibrate 6 > max", lambda: C.validate_examples([1, 2, 3, 4, 5, 6], False))
refuses("calibrate constructed no edge", lambda: C.validate_examples(
    [{"kind": "happy-path", "near_boundary": True}], True))

# --- optimize ---
_c = [{"framing": f, "score": 3} for f in C.APE_FRAMINGS]
assert C.validate_candidates(_c)["winner"] == "rule-based"  # all tie -> precedence
refuses("optimize 4 candidates", lambda: C.validate_candidates(_c[:4]))
refuses("optimize dup framing", lambda: C.validate_candidates(
    [{"framing": "rule-based", "score": 1}] * 5))
refuses("critique wrong size", lambda: C.validate_critique([{"pass": True}] * 3))

# --- map ---
ok("map 50 ok", lambda: C.validate_triples(
    [{"index": i, "subject": "s", "predicate": "p", "object": "o"} for i in range(50)]))
refuses("map 51 > limit", lambda: C.validate_triples(
    [{"index": i, "subject": "s", "predicate": "p", "object": "o"} for i in range(51)]))
refuses("map hop cites missing triple", lambda: C.validate_triples(
    [{"index": 1, "subject": "s", "predicate": "p", "object": "o"}],
    [{"hop": 1, "triple_index": 99, "predicate": "p", "to": "o"}]))

# --- rung ---
assert C.select_rung({"precision_arith": True})["rung"] == "rung-2b"
assert C.select_rung({"single_correct_answer": True, "costly_wrong_assumption": True})["rung"] == "rung-2a"
assert C.select_rung({"multistep_arithmetic": True})["rung"] == "rung-1"
assert C.select_rung({})["rung"] == "rung-0"
assert C.select_rung({"has_image_or_diagram": True})["multimodal_cot_first"] is True
refuses("self-consistency 2 attempts", lambda: C.validate_self_consistency(
    [{"strategy": "forward deduction"}, {"strategy": "constraint mapping"}]))

# --- verify assumptions ---
ok("verify unresolved 3 steps", lambda: C.validate_verify_run(
    {"assumption": "a", "steps": [{"reasoning": "r", "action": "a", "observation": "o"}] * 3,
     "outcome": {"kind": "still_unresolved"}}))
refuses("verify 4 steps", lambda: C.validate_verify_run(
    {"assumption": "a", "steps": [{"reasoning": "r", "action": "a", "observation": "o"}] * 4,
     "outcome": {"kind": "still_unresolved"}}))
refuses("verify conf 89 < gate", lambda: C.validate_verify_run(
    {"assumption": "a", "steps": [], "outcome": {"kind": "confidence_raised",
     "confidence": 89, "citations": ["(f:1)"]}}))
refuses("verify raised no citation", lambda: C.validate_verify_run(
    {"assumption": "a", "steps": [], "outcome": {"kind": "confidence_raised",
     "confidence": 95, "citations": []}}))
refuses("verify multiple assumptions", lambda: C.validate_verify_run(
    {"assumption": ["a", "b"], "steps": [], "outcome": {"kind": "still_unresolved"}}))

# --- trace ---
def _trace(explore):
    secs = [{"title": t, "body": "x"} for t in C.TRACE_SECTIONS
            if explore or t != C.TRACE_APPROACHES_SECTION]
    for s in secs:
        if s["title"] == "What ran":
            s["stage_ids"] = ["a"]
    return {"explore_ran": explore, "sections": secs, "dag_stages": ["a"]}
ok("trace with explore", lambda: C.validate_trace(_trace(True)))
ok("trace without explore omits approaches", lambda: C.validate_trace(_trace(False)))
refuses("trace missing stage in what-ran", lambda: C.validate_trace(
    {**_trace(True), "dag_stages": ["a", "b"]}))

# --- negotiate ---
ok("negotiate hybrid wins each axis", lambda: C.validate_negotiation(
    {"explore_winner_selected": True,
     "sources": [{"name": "W", "feasibility": 9, "impact": 4, "risk": 6},
                 {"name": "R", "feasibility": 4, "impact": 9, "risk": 6}],
     "hybrid": {"feasibility": 8, "impact": 8, "risk": 7}}))
refuses("negotiate before winner", lambda: C.validate_negotiation(
    {"explore_winner_selected": False, "sources": [], "hybrid": {}}))
refuses("negotiate hybrid loses to a source", lambda: C.validate_negotiation(
    {"explore_winner_selected": True,
     "sources": [{"name": "W", "feasibility": 9, "impact": 9, "risk": 9}],
     "hybrid": {"feasibility": 1, "impact": 1, "risk": 1}}))

# --- ground ---
ok("ground verified+refused", lambda: C.validate_grounding(
    {"claims": [{"status": "verified", "text": "x", "citation": "(a.py:1)"},
                {"status": "refused",
                 "text": "The available docs do not contain sufficient information to say."}]}))
refuses("ground uncited claim", lambda: C.validate_grounding(
    {"claims": [{"status": "verified", "text": "x", "citation": ""}]}))
refuses("ground refused wrong template", lambda: C.validate_grounding(
    {"claims": [{"status": "refused", "text": "dunno"}]}))

# --- solve pipeline ---
ok("phase order valid", lambda: C.validate_phase_order(
    ["Clarify", "Decompose", "Execute", "Revise"]))
refuses("phase order missing Execute", lambda: C.validate_phase_order(
    ["Clarify", "Decompose", "Revise"]))
refuses("phase order scrambled", lambda: C.validate_phase_order(
    ["Decompose", "Clarify", "Execute", "Revise"]))
refuses("stage dispatch hardcoded", lambda: C.validate_stage_dispatch(
    {"id": "a", "mode": "ground-evidence", "mode_decided_at": "authored"}, 0))
ok("stage dispatch runtime", lambda: C.validate_stage_dispatch(
    {"id": "a", "mode": "ground-evidence", "mode_decided_at": "runtime"}, 0))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
