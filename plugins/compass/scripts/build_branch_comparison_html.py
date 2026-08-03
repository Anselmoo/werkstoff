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
