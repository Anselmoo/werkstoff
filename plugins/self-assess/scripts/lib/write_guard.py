"""Enforce that every self-assess write stays inside its configured output_dir."""
import os

from lib.errors import WriteScopeError


def resolve_output_path(repo, output_dir, filename):
    """Resolve filename against <repo>/<output_dir>. filename="." resolves
    to output_dir itself. Raises WriteScopeError on any escape."""
    base = os.path.realpath(os.path.join(os.path.realpath(repo), output_dir))
    if filename in (".", ""):
        return base
    if os.path.isabs(filename):
        raise WriteScopeError(
            f"{filename!r} is an absolute path; writes must be relative to "
            "output_dir (rule: write-scope-enforcement)."
        )
    target = os.path.realpath(os.path.join(base, filename))
    if target != base and not target.startswith(base + os.sep):
        raise WriteScopeError(
            f"{filename!r} would resolve outside output_dir {output_dir!r} "
            "(rule: write-scope-enforcement)."
        )
    return target


def ensure_output_dir(repo, output_dir):
    path = resolve_output_path(repo, output_dir, ".")
    os.makedirs(path, exist_ok=True)
    return path
