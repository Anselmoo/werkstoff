"""Compare an artifact's mtime against the repo's latest commit."""
import os
import subprocess

# The two data artifacts self-assess-arch-health and self-assess-transform-brief
# actually depend on (per self-assess-stage-map's own SKILL.md) -- deliberately
# NOT stage_map_summary.json, which is a reporting sidecar, not one of the
# artifacts a downstream skill reads for its own analysis.
STAGE_MAP_REQUIRED_ARTIFACTS = ("stage_graph.json", "file_stage_index.json")


def latest_commit_timestamp(repo):
    result = subprocess.run(
        ["git", "-C", repo, "log", "-1", "--format=%ct"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def is_stale(artifact_path, latest_commit_ts):
    if latest_commit_ts is None or not os.path.exists(artifact_path):
        return None
    return os.path.getmtime(artifact_path) < latest_commit_ts


def stage_map_fresh(output_abs, repo):
    """Whether self-assess-autopilot may SKIP re-running self-assess-stage-map
    (rule: autopilot-stage-map-fresh-reuse). True only if BOTH
    STAGE_MAP_REQUIRED_ARTIFACTS already exist on disk AND neither is stale
    relative to the repo's latest commit. False if either file is missing
    (never run, or a prior run was interrupted before writing both), if
    either is stale (the repo has changed since the map was built and it can
    no longer be trusted), or if staleness itself can't be determined (no
    commits, or not a git repo) -- "unknown" is never treated as "fresh."
    Fixes the Phase 2 benchmark finding (SA-1,
    docs/plugin-benchmark-phase2-results.md): before this, autopilot always
    re-ran stage-map from scratch, even seconds after a fresh, valid,
    unstale stage_graph.json had already been written in the same session.
    """
    paths = [os.path.join(output_abs, name) for name in STAGE_MAP_REQUIRED_ARTIFACTS]
    if not all(os.path.isfile(p) for p in paths):
        return False
    latest_commit_ts = latest_commit_timestamp(repo)
    if latest_commit_ts is None:
        return False
    return not any(is_stale(p, latest_commit_ts) for p in paths)
