"""The remediation-scope lock: at most one authorized Edit/Write per
finding, enforced by hooks/guard_edit_scope.py and opened/closed by
remediation_scope_cli.py. Schema matches
test/plugins/fixtures/hook-violation-zeugnis/analysis/zeugnis/remediation_scope.json
exactly: {allowedFile, category, consumed, domain, findingId, openedAt}.

The mutation_harden domain takes a second shape instead (open_test_scope):
{category, consumed, domain, editBudget, editsUsed, findingId, openedAt,
sourcePaths, testRoots} -- no allowedFile, a write budget instead of one shot.
"""
import json
import os
import time

from lib.constants import DRAFT_ONLY_DOMAINS, FIXABLE_DOMAINS, TEST_SCOPE_DOMAINS
from lib.mutation_scope import MutationScopeError, is_within, lexical_path, repo_relative
from lib.paths import zeugnis_dir, safe_repo_path

SCOPE_FILENAME = "remediation_scope.json"


class RemediationNotFixableError(Exception):
    """A finding's domain/category is not in zeugnis's auto-fixable set."""


def _scope_path(cwd):
    return os.path.join(zeugnis_dir(cwd), SCOPE_FILENAME)


def read_scope(cwd):
    path = _scope_path(cwd)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def mark_consumed(cwd):
    scope = read_scope(cwd) or {}
    scope["consumed"] = True
    with open(_scope_path(cwd), "w", encoding="utf-8") as fh:
        json.dump(scope, fh, indent=2, sort_keys=True)


def is_fixable(domain, category):
    """Shared fixability check -- also reused by lib.ledger's own
    is_fixable, so cycle_engine.py's record-pass-result gate and
    guard_edit_scope.py's defense-in-depth re-check never drift apart."""
    if domain in DRAFT_ONLY_DOMAINS:
        return False
    policy = FIXABLE_DOMAINS.get(domain)
    if not policy:
        return False
    if policy["mode"] == "all":
        return True
    if policy["mode"] == "category":
        return category in policy["categories"]
    return False


def open_scope(repo_root, *, finding_id, domain, category, target_file):
    if domain in TEST_SCOPE_DOMAINS:
        # A single allowedFile lock for this domain would let a "killing
        # test" be an edit to the source the mutant survived in.
        raise RemediationNotFixableError(
            f"finding {finding_id!r} is domain={domain!r}, which takes a test-path "
            "scope: use `remediation_scope_cli.py open-tests`, never a single-file lock."
        )
    if not is_fixable(domain, category):
        raise RemediationNotFixableError(
            f"finding {finding_id!r} has domain={domain!r} category={category!r}, "
            "which is not in zeugnis's auto-fixable set."
        )
    safe_repo_path(repo_root, target_file)  # raises UnsafeWritePathError on escape
    scope = {
        "allowedFile": target_file,
        "category": category,
        "consumed": False,
        "domain": domain,
        "findingId": finding_id,
        "openedAt": time.time(),
    }
    path = _scope_path(repo_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(scope, fh, indent=2, sort_keys=True)
    return path


def open_test_scope(repo_root, *, lane_id, test_roots, source_paths, edit_budget):
    """The mutation_harden lock: any number of writes up to `edit_budget`, each
    under one of `test_roots` and none under `source_paths`. Validated here and
    again, per write, by guard_edit_scope.py through the same
    lib.mutation_scope.scope_write_violation."""
    domain = "mutation_harden"
    if not is_fixable(domain, "surviving-mutant"):
        raise RemediationNotFixableError(f"domain {domain!r} is not in zeugnis's auto-fixable set.")
    root = lexical_path(repo_root, ".")
    if not test_roots or not source_paths:
        raise MutationScopeError("open-tests needs at least one --test-root and one --source-path")
    if isinstance(edit_budget, bool) or not isinstance(edit_budget, int) or edit_budget < 1:
        raise MutationScopeError(f"--edit-budget must be a positive integer, got {edit_budget!r}")
    sources = [repo_relative(root, p, "sourcePath") for p in source_paths]
    for relpath in test_roots:
        test_root = repo_relative(root, relpath, "testRoot")
        if is_within(test_root, root / "analysis"):
            raise MutationScopeError(f"testRoot {relpath!r} is under analysis/")
        for source in sources:
            if is_within(test_root, source) or is_within(source, test_root):
                raise MutationScopeError(
                    f"testRoot {relpath!r} overlaps source path {str(source.relative_to(root))!r}; "
                    "the lock could not tell a test write from a source write"
                )
    scope = {
        "category": "surviving-mutant",
        "consumed": False,
        "domain": domain,
        "editBudget": edit_budget,
        "editsUsed": 0,
        "findingId": lane_id,
        "openedAt": time.time(),
        "sourcePaths": list(source_paths),
        "testRoots": list(test_roots),
    }
    path = _scope_path(repo_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(scope, fh, indent=2, sort_keys=True)
    return path


def record_test_edit(cwd):
    """Spend one edit of a test-scope lock's budget (the guard's only write)."""
    scope = read_scope(cwd) or {}
    scope["editsUsed"] = int(scope.get("editsUsed", 0)) + 1
    with open(_scope_path(cwd), "w", encoding="utf-8") as fh:
        json.dump(scope, fh, indent=2, sort_keys=True)


def close_scope(repo_root):
    """No-op, not an error, if no scope is open -- `zeugnis-cycle` without
    `--fix` is a documented-safe path even when nothing was ever opened."""
    path = _scope_path(repo_root)
    if os.path.isfile(path):
        os.remove(path)
