"""Compare an artifact's mtime against the repo's latest commit."""
import os
import subprocess


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
