#!/usr/bin/env python3
"""Tests for build_branch_comparison_html.py.

Run: python3 scripts/test_build_branch_comparison_html.py
Exits 0 if every case passes.
"""
import sys
import os
import json
import tempfile
import shutil
import time

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

# --- End-to-end: main() against the real fixture, template, d3, tokens ---
_here = os.path.dirname(os.path.abspath(__file__))
_fixture_path = os.path.join(_here, "fixtures", "sample_explore_state.json")
_assets = os.path.join(os.path.dirname(_here), "assets")

with open(_fixture_path, encoding="utf-8") as fh:
    _fixture_state = json.load(fh)

_tmp2 = tempfile.mkdtemp()
try:
    _write_state(_tmp2, _fixture_state["run_id"], _fixture_state)
    rc = B.main([
        _tmp2, "--run-id", _fixture_state["run_id"],
        "--template", os.path.join(_assets, "branch-comparison-viewer.html"),
        "--d3", os.path.join(_assets, "inline-d3.html"),
        "--tokens", os.path.join(_assets, "tokens.css"),
    ])
    ok("main() exits 0 for a valid fixture run", rc == 0)

    out_path = os.path.join(_tmp2, ".compass", "runs", _fixture_state["run_id"], "branch-comparison.html")
    ok("main() writes the report to the default .compass/runs/<id>/ path", os.path.isfile(out_path))

    html = open(out_path, encoding="utf-8").read()
    ok("rendered report has no leftover D3 marker", "<!--__D3_SUBSET__-->" not in html)
    ok("rendered report has no leftover tokens marker", "<!--__DESIGN_TOKENS__-->" not in html)
    ok("rendered report has no leftover data marker", "/*__BRANCH_DATA__*/ null" not in html)
    ok("rendered report embeds the winning branch's name",
       "Standalone D3 branch-comparison viewer" in html)
    ok("rendered report embeds the vendored d3 bundle", "var d3=" in html)
    # report-viewer-standard.md S2: "<plugin> — <report noun>", lowercase plugin.
    # The separator is written as — rather than a literal glyph so a re-encoded
    # source file cannot turn this into an assertion that passes on the wrong dash.
    ok("rendered report carries the standard <title> shape",
       "<title>compass \u2014 branch comparison</title>" in html)
    # report-viewer-standard.md R1: the verdict element must be in STATIC markup,
    # so it survives into the file even before any script runs.
    ok("rendered report keeps a static, empty class=\"verdict\" element filled via textContent",
       '<p class="verdict" id="verdict"></p>' in html)
    # S1: centered document, not a left-hugging max-width with no auto margin.
    # Matched on the whole .wrap RULE, never on the bare string "margin: 0 auto":
    # that substring also occurs in the prose comment explaining this rule, so the
    # loose form passed on a viewer whose .wrap had been un-centered. Calibrated by
    # deleting the declaration and confirming this assertion goes red.
    ok("rendered report centers its content (S1, not a fourth archetype)",
       ".wrap { max-width: 1180px; margin: 0 auto;" in html)

    # main() with no --run-id must fall back to find_latest_explore_run.
    rc2 = B.main([
        _tmp2,
        "--template", os.path.join(_assets, "branch-comparison-viewer.html"),
        "--d3", os.path.join(_assets, "inline-d3.html"),
        "--tokens", os.path.join(_assets, "tokens.css"),
    ])
    ok("main() falls back to the latest Explore run when --run-id is omitted", rc2 == 0)
finally:
    shutil.rmtree(_tmp2)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
