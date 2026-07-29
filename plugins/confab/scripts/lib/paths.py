"""Path-safety boundary for every confab read/write -- both for
analysis/confab/ output and for remediation targets in the target repo."""
import os


class UnsafeWritePathError(Exception):
    """A resolved path would escape its intended root (traversal, absolute
    path outside the root, or a realpath that resolves elsewhere)."""


def confab_dir(cwd):
    return os.path.join(cwd, "analysis", "confab")


def _safe_join(root, relpath, *, label):
    root_real = os.path.realpath(root)
    if os.path.isabs(relpath):
        raise UnsafeWritePathError(f"{relpath!r} is an absolute path; {label} must be repo-relative.")
    target = os.path.realpath(os.path.join(root_real, relpath))
    if target != root_real and not target.startswith(root_real + os.sep):
        raise UnsafeWritePathError(f"{relpath!r} would resolve outside {label} ({root_real!r}).")
    return target


def safe_repo_path(cwd, relpath):
    return _safe_join(cwd, relpath, label="the repository root")


def safe_output_path(repo_root, relpath):
    return _safe_join(confab_dir(repo_root), relpath, label="analysis/confab/")


def ensure_parent_dir(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
