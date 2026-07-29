"""The remediation-scope lock: at most one authorized Edit/Write per
finding, enforced by hooks/guard_edit_scope.py and opened/closed by
remediation_scope_cli.py. Schema matches
test/plugins/fixtures/hook-violation-confab/analysis/confab/remediation_scope.json
exactly: {allowedFile, category, consumed, domain, findingId, openedAt}.
"""
import json
import os
import time

from lib.constants import DRAFT_ONLY_DOMAINS, FIXABLE_DOMAINS
from lib.paths import confab_dir, safe_repo_path

SCOPE_FILENAME = "remediation_scope.json"


class RemediationNotFixableError(Exception):
    """A finding's domain/category is not in confab's auto-fixable set."""


def _scope_path(cwd):
    return os.path.join(confab_dir(cwd), SCOPE_FILENAME)


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
    if not is_fixable(domain, category):
        raise RemediationNotFixableError(
            f"finding {finding_id!r} has domain={domain!r} category={category!r}, "
            "which is not in confab's auto-fixable set."
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


def close_scope(repo_root):
    """No-op, not an error, if no scope is open -- `confab-cycle` without
    `--fix` is a documented-safe path even when nothing was ever opened."""
    path = _scope_path(repo_root)
    if os.path.isfile(path):
        os.remove(path)
