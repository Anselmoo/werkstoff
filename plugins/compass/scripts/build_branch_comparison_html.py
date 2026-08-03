#!/usr/bin/env python3
"""Renders a compass-explore-branches run's persisted state.json (branches
scored on Feasibility/Impact/Risk, one flagged winner) as a self-contained
HTML small-multiples grouped-bar comparison -- the cupertino-council-approved
mark type for this data shape (radar rejected: enclosed area isn't
proportional to score in any way a viewer can decode, and overlapping
polygons past 2-3 series would obscure the tie-break-by-risk signal).

Total and the winner are ALWAYS recomputed here via compass_lib's own
validate_branch_scores -- never read from a stored field, because no
"total"/"selected"/"winner" field is persisted in state.json's
explore.branches today (compass.py's state-write writes the caller's raw
payload verbatim; validate_branch_scores's own richer return value, which
DOES compute Total/selected, is discarded after validation, not persisted).
This means the report can never disagree with what compass.py's guard would
compute for the same branches.

Usage:
    build_branch_comparison_html.py <repo_root> [--run-id <run-id>] \
        --template <path> --d3 <path> --tokens <path> [--out <path>]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compass  # noqa: E402  -- validate_state, safe to import (no import-time side effects)
import compass_lib as C  # noqa: E402

DEFAULT_OUTPUT_DIR = C.DEFAULT_OUTPUT_DIR  # ".compass"


def load_state(repo_root: str, run_id: str) -> dict:
    """Read and gate-validate runs/<run_id>/state.json under DEFAULT_OUTPUT_DIR.
    Raises FileNotFoundError for an unknown run, or compass_lib.GuardError for
    one that fails the same validation compass.py's own state-write/state-read
    already enforce -- both are the caller's job to report, never paper over."""
    state_path = os.path.join(repo_root, DEFAULT_OUTPUT_DIR, "runs", run_id, "state.json")
    if not os.path.isfile(state_path):
        raise FileNotFoundError(f"no state.json for run {run_id!r} at {state_path}")
    with open(state_path, encoding="utf-8") as fh:
        state = json.load(fh)
    compass.validate_state(state, f"state({run_id})")
    return state


def find_latest_explore_run(repo_root: str) -> str | None:
    """Fall back to the most-recently-modified run with an Explore phase and
    branches present, mirroring compass_lib.select_reusable_run's mtime-max
    rule. Used only when --run-id is omitted. A missing runs/ directory, or
    any individual state.json that is missing/unreadable/invalid, is skipped
    rather than fatal -- same tolerance compass.py's own state-find uses."""
    runs_root = os.path.join(repo_root, DEFAULT_OUTPUT_DIR, "runs")
    candidates = []
    if os.path.isdir(runs_root):
        for name in sorted(os.listdir(runs_root)):
            state_path = os.path.join(runs_root, name, "state.json")
            if not os.path.isfile(state_path):
                continue
            try:
                with open(state_path, encoding="utf-8") as fh:
                    state = json.load(fh)
                compass.validate_state(state, f"state({name})")
            except (OSError, json.JSONDecodeError, C.GuardError):
                continue
            if state.get("explore") and state["explore"].get("branches"):
                candidates.append((os.path.getmtime(state_path), name))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def build_payload(state: dict) -> dict:
    """Recompute Total + winner via compass_lib's own guard (never trust a
    stored field) and re-attach each branch's `description` from the raw
    persisted branches -- validate_branch_scores's own return value strips
    it, since compass.py's guard only ever needed the 3 score axes."""
    branches = state.get("explore", {}).get("branches", [])
    result = C.validate_branch_scores(branches)  # raises C.GuardError if invalid
    scored = result["scored"]
    selected_name = result["selected"]

    enriched = []
    for original, s in zip(branches, scored):
        enriched.append({
            "name": s["name"],
            "description": original.get("description", ""),
            "feasibility": s["feasibility"],
            "impact": s["impact"],
            "risk": s["risk"],
            "total": s["total"],
            "biggestBlocker": s.get("biggest_blocker"),
            "isWinner": s["name"] == selected_name,
        })

    return {
        "runId": state["run_id"],
        "rawTask": state["raw_task"],
        "branches": enriched,
        "selected": selected_name,
    }


def render_html(template_path: str, d3_path: str, tokens_path: str, payload: dict) -> str:
    tpl = open(template_path, encoding="utf-8").read()

    d3_snippet = open(d3_path, encoding="utf-8").read()
    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(d3_marker, d3_snippet)

    tokens_css = open(tokens_path, encoding="utf-8").read()
    tokens_marker = "<!--__DESIGN_TOKENS__-->"
    if tokens_marker not in tpl:
        raise ValueError(f"design-tokens injection marker not found in {template_path}")
    tpl = tpl.replace(tokens_marker, "<style>\n" + tokens_css + "\n</style>")

    data_marker = "/*__BRANCH_DATA__*/ null"
    if data_marker not in tpl:
        raise ValueError(f"data injection marker not found in {template_path}")
    data = json.dumps(payload)
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(data_marker, "/*__BRANCH_DATA__*/ " + data)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--run-id", help="defaults to the most recently modified Explore run")
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", required=True, help="path to the vendored tokens.css file")
    parser.add_argument("--out", help="defaults to .compass/runs/<run-id>/branch-comparison.html")
    args = parser.parse_args(argv)

    run_id = args.run_id or find_latest_explore_run(args.repo_root)
    if not run_id:
        sys.stderr.write(
            "error: no --run-id given and no persisted Explore run found under "
            f"{os.path.join(args.repo_root, DEFAULT_OUTPUT_DIR, 'runs')}\n"
        )
        return 1

    try:
        state = load_state(args.repo_root, run_id)
    except (FileNotFoundError, C.GuardError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    if not state.get("explore_ran") or not state.get("explore", {}).get("branches"):
        sys.stderr.write(f"error: run {run_id!r} has no Explore branches to compare\n")
        return 1

    payload = build_payload(state)

    if args.out:
        out_path = args.out
    else:
        # Reuses the guard's own write-scope check, exactly like state-write
        # enforces, so this script can never write outside .compass/.
        safe_rel = C.enforce_write_scope(f"runs/{run_id}/branch-comparison.html", DEFAULT_OUTPUT_DIR)
        out_path = os.path.join(args.repo_root, safe_rel)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(args.template, args.d3, args.tokens, payload))

    print(json.dumps({"reportPath": out_path, "runId": run_id, "selected": payload["selected"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
