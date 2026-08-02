"""The edit-scope lock: guard_target_edit.py is inert unless a self-assess
remediator dispatch has one of these open, and even then it only authorizes
edits to the files the lock names. Opened/closed by self_assess_cli.py's
open-edit-scope/close-edit-scope, called by self-assess-idiom-fix and
self-assess-transform-execute immediately around their remediator dispatch --
mirrors plugins/confab/scripts/lib/remediation_scope.py's lock, except the
lock holds a LIST of allowed files (self-assess dispatches one remediator per
independent cluster/phase-file, and those dispatches may run in parallel; a
single-file lock like confab's would race between them).

Lives at a fixed path, independent of the user-configurable output_dir
setting -- this is infrastructure, not a report artifact the user relocates.
"""
import json
import os
import time

from lib.errors import WriteScopeError

SCOPE_FILENAME = "edit_scope.json"


def _scope_path(repo_root):
    return os.path.join(repo_root, "analysis", "self-assess", SCOPE_FILENAME)


def safe_repo_path(repo_root, relpath):
    """Resolve relpath against repo_root, raising WriteScopeError on any
    escape (absolute path, traversal, or a realpath that resolves elsewhere).
    """
    root_real = os.path.realpath(repo_root)
    if os.path.isabs(relpath):
        raise WriteScopeError(
            f"{relpath!r} is an absolute path; edit-scope files must be repo-relative "
            "(rule: write-scope-enforcement)."
        )
    target = os.path.realpath(os.path.join(root_real, relpath))
    if target != root_real and not target.startswith(root_real + os.sep):
        raise WriteScopeError(
            f"{relpath!r} would resolve outside the repository root {root_real!r} "
            "(rule: write-scope-enforcement)."
        )
    return target


def read_scope(repo_root):
    path = _scope_path(repo_root)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def open_scope(repo_root, *, mode, allowed_files):
    if mode not in ("idiom_fix", "transform"):
        raise ValueError(f"mode must be 'idiom_fix' or 'transform', got {mode!r}")
    if not allowed_files:
        raise ValueError("allowed_files must be non-empty")
    resolved = [safe_repo_path(repo_root, f) for f in allowed_files]
    scope = {
        "mode": mode,
        "allowedFiles": allowed_files,
        "openedAt": time.time(),
    }
    path = _scope_path(repo_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(scope, fh, indent=2, sort_keys=True)
    return path, resolved


def close_scope(repo_root):
    """No-op, not an error, if no scope is open -- a skill that refuses
    before ever dispatching a remediator (e.g. the mode gate fails) still
    needs to be able to call this safely during cleanup."""
    path = _scope_path(repo_root)
    if os.path.isfile(path):
        os.remove(path)
