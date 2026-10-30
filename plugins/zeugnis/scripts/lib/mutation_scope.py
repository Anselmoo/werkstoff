"""The lexical boundary every mutation run is held to (issue #142).

A real mutation tool writes into the directory it runs in: mutmut 3 `run`
creates `./mutants/` and resumes whatever it finds there, and `mutmut apply`
rewrites the source file itself. So a mutant may only ever exist inside a
fresh `git archive HEAD` copy under

    <repo>/analysis/zeugnis/mutation/<runId>/<kind>/<name>/

that carries COPY_MARKER at its root. `copy_root_for` is the one question all
three enforcement points ask -- guard_bash_scope.py before it allows a
copy-only verb, mutation_harden.py before it starts a tool as a subprocess
(the hook never sees those), and the test-scope lock below.

LEXICAL, NEVER RESOLVED. Paths are normalised with `os.path.normpath`, which
collapses `..` without touching the filesystem. `Path.resolve()` has no
lexical mode: it follows symlinks, so `cd analysis/zeugnis/mutation/r/shards/s`
through a symlink planted at `s -> <repo>` would resolve to the working tree
and the two checks would disagree about where the command runs. Instead every
component BELOW the repo root is required not to be a symlink (an lstat, not a
resolve), which makes the lexical path and the real path the same place.
Components ABOVE the repo root are not checked: on macOS `/tmp` and `/var` are
symlinks, and a check over them would deny every legitimate copy there.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

MUTATION_DIR_PARTS = ("analysis", "zeugnis", "mutation")
COPY_MARKER = ".zeugnis-mutation-copy.json"
# shards: a baseline run; remeasure: survivors only, new tests overlaid;
# proofs: one mutant applied to prove (or refute) one killing test.
COPY_KINDS = ("shards", "remeasure", "proofs")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

# Files a killing test must never touch, wherever they sit: each one can make
# every test pass (a conftest autouse skip, a pytest addopts, a mutmut
# do_not_mutate) without asserting anything.
PROTECTED_BASENAMES = frozenset({
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "pytest.ini",
    "tox.ini",
    "noxfile.py",
    "conftest.py",
    "mutmut_config.py",
})


class MutationScopeError(Exception):
    """A path or name falls outside the mutation boundary."""


def lexical_path(base, path) -> Path:
    """`path` joined onto `base` and normalised lexically.

    `os.path.normpath`, not `Path.resolve()` -- see the module docstring.
    `~` is expanded because the shell expands it before the command runs.
    """
    # Path.absolute() prepends the cwd without resolving anything; `/` keeps
    # os.path.join's rule that an absolute right-hand side wins.
    joined = Path(str(base)).absolute() / Path(str(path)).expanduser()
    return Path(os.path.normpath(joined))


def find_zeugnis_root(start) -> Path | None:
    """The nearest ancestor of `start` (itself included) holding analysis/zeugnis/.

    Walking up is what keeps the guards active when a session's cwd sits inside
    a copy, which has no analysis/zeugnis/ of its own.
    """
    here = lexical_path(start, ".")
    for candidate in (here, *here.parents):
        if (candidate / "analysis" / "zeugnis").is_dir():
            return candidate
    return None


def symlink_below(root: Path, target: Path) -> Path | None:
    """The first symlinked component of `target` strictly below `root`, or None."""
    if target.parts[: len(root.parts)] != root.parts:
        return target
    current = root
    for part in target.parts[len(root.parts):]:
        current = current / part
        if current.is_symlink():
            return current
    return None


def is_within(child: Path, parent: Path) -> bool:
    return child.parts[: len(parent.parts)] == parent.parts


def copy_root_for(path) -> Path | None:
    """The marker-bearing copy root that lexically contains `path`, or None.

    None means "not inside a mutation copy": the caller must refuse to run a
    mutation tool there.
    """
    here = lexical_path(path, ".")
    parts = here.parts
    index = None
    for i in range(len(parts) - len(MUTATION_DIR_PARTS), -1, -1):
        if tuple(parts[i : i + len(MUTATION_DIR_PARTS)]) == MUTATION_DIR_PARTS:
            index = i
            break
    if index is None:
        return None
    rest = parts[index + len(MUTATION_DIR_PARTS):]
    if len(rest) < 3:
        return None
    run_id, kind, name = rest[:3]
    if kind not in COPY_KINDS or not NAME_RE.match(run_id) or not NAME_RE.match(name):
        return None
    repo = Path(*parts[:index])
    if not (repo / "analysis" / "zeugnis").is_dir():
        return None
    if symlink_below(repo, here) is not None:
        return None
    copy_root = repo.joinpath(*parts[index : index + len(MUTATION_DIR_PARTS) + 3])
    marker = copy_root / COPY_MARKER
    if marker.is_symlink() or not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if (data.get("runId"), data.get("kind"), data.get("name")) != (run_id, kind, name):
        return None
    return copy_root


def check_name(value: str, label: str) -> str:
    if not NAME_RE.match(value or ""):
        raise MutationScopeError(f"{label} {value!r} must match {NAME_RE.pattern}")
    return value


def repo_relative(repo_root: Path, relpath: str, label: str) -> Path:
    """`relpath` as an absolute lexical path that stays inside `repo_root`."""
    if not relpath or Path(relpath).is_absolute():
        raise MutationScopeError(f"{label} {relpath!r} must be a non-empty repo-relative path")
    target = lexical_path(repo_root, relpath)
    if target == repo_root or not is_within(target, repo_root):
        raise MutationScopeError(f"{label} {relpath!r} escapes or equals the repository root")
    return target


def scope_write_violation(repo_root: Path, scope: dict, target: Path) -> str | None:
    """Why `target` may not be written under a mutation_harden test-scope lock.

    Returns None when the write is allowed. Every gating field is required: a
    lock missing testRoots, sourcePaths or editBudget is refused, never read
    as "no restriction" -- a guard predicated on its own input existing is not
    a guard.
    """
    test_roots = scope.get("testRoots")
    source_paths = scope.get("sourcePaths")
    budget = scope.get("editBudget")
    used = scope.get("editsUsed", 0)
    if not isinstance(test_roots, list) or not test_roots:
        return "the mutation_harden lock has no testRoots"
    if not isinstance(source_paths, list) or not source_paths:
        return "the mutation_harden lock has no sourcePaths"
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 1:
        return "the mutation_harden lock has no positive integer editBudget"
    if not isinstance(used, int) or used >= budget:
        return f"the lane's edit budget is spent ({used}/{budget} edits)"
    if not is_within(target, repo_root):
        return f"{str(target)!r} is outside the repository"
    if symlink_below(repo_root, target) is not None:
        return f"{str(target)!r} passes through a symlink"
    if target.name in PROTECTED_BASENAMES:
        return f"{target.name!r} configures test collection or mutation, not a killing test"
    try:
        sources = [repo_relative(repo_root, p, "sourcePath") for p in source_paths]
        roots = [repo_relative(repo_root, p, "testRoot") for p in test_roots]
    except MutationScopeError as exc:
        return str(exc)
    for source in sources:
        if is_within(target, source):
            return f"{str(target)!r} is under source path {str(source)!r}; a killing test never edits the code it tests"
    if is_within(target, repo_root / "analysis"):
        return "analysis/ holds the run's evidence; a lane may not write it"
    if not any(is_within(target, root) for root in roots):
        return f"{str(target)!r} is not under any testRoot {test_roots!r}"
    return None
