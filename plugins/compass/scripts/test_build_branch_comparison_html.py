#!/usr/bin/env python3
"""Tests for build_branch_comparison_html.py.

Run: python3 scripts/test_build_branch_comparison_html.py
Exits 0 if every case passes.
"""
import sys, os, json, tempfile, shutil, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_branch_comparison_html as B  # noqa: E402

passed = failed = 0


def ok(label, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {label}")


# --- build_payload: recomputes Total + winner, never trusts a stored field ---
_state_two_branches = {
    "run_id": "t1", "raw_task": "pick an approach", "phase": "Explore", "explore_ran": True,
    "explore": {"branches": [
        {"name": "A", "description": "desc A", "feasibility": 7, "impact": 8, "risk": 4, "biggest_blocker": "blocker A"},
        {"name": "B", "description": "desc B", "feasibility": 6, "impact": 9, "risk": 6, "biggest_blocker": "blocker B"},
    ]},
}
payload = B.build_payload(_state_two_branches)
ok("build_payload keeps run_id/raw_task", payload["runId"] == "t1" and payload["rawTask"] == "pick an approach")
ok("build_payload computes Total = sum of the 3 axes", payload["branches"][0]["total"] == 19 and payload["branches"][1]["total"] == 21)
ok("build_payload selects the highest Total as winner", payload["selected"] == "B")
ok("build_payload marks exactly the winner isWinner=True", [b["isWinner"] for b in payload["branches"]] == [False, True])
ok("build_payload re-attaches description from the raw branches", payload["branches"][0]["description"] == "desc A")

# --- Tie-break by lower risk, and a missing description defaults to "" ---
_state_tie = {
    "run_id": "t2", "raw_task": "tie case", "phase": "Explore", "explore_ran": True,
    "explore": {"branches": [
        {"name": "X", "feasibility": 5, "impact": 5, "risk": 8},   # total 18, no description key
        {"name": "Y", "feasibility": 6, "impact": 6, "risk": 6},   # total 18, lower risk -> wins the tie
    ]},
}
payload_tie = B.build_payload(_state_tie)
ok("build_payload breaks ties by lower risk (via compass_lib.validate_branch_scores)", payload_tie["selected"] == "Y")
ok("build_payload defaults a missing description to empty string, not a crash", payload_tie["branches"][0]["description"] == "")

# --- load_state / find_latest_explore_run against a real .compass/runs/ tree ---
def _write_state(tmp_repo, run_id, state):
    run_dir = os.path.join(tmp_repo, ".compass", "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh)

_tmp = tempfile.mkdtemp()
try:
    _write_state(_tmp, "r-old", _state_two_branches)
    time.sleep(0.05)
    _write_state(_tmp, "r-new", _state_tie)

    loaded = B.load_state(_tmp, "r-new")
    ok("load_state reads back the exact persisted branches", loaded["explore"]["branches"][0]["name"] == "X")

    latest = B.find_latest_explore_run(_tmp)
    ok("find_latest_explore_run picks the most recently modified run with Explore branches", latest == "r-new")

    try:
        B.load_state(_tmp, "does-not-exist")
        ok("load_state raises FileNotFoundError for an unknown run_id", False)
    except FileNotFoundError:
        ok("load_state raises FileNotFoundError for an unknown run_id", True)
finally:
    shutil.rmtree(_tmp)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
