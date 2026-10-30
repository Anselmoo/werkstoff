#!/usr/bin/env python3
"""PreToolUse hook for Edit and Write: enforces remediator-one-fix-per-
finding, fixable-domains-in-cycle, and draft-domains-in-cycle REGARDLESS
of whether the zeugnis-remediator agent (or the orchestrating session)
cooperates with its own instructions.

This hook is the only thing standing between "the remediator's system
prompt says one edit per finding" (a sentence a model reads and might
still violate) and "a second edit in the same remediation scope is
mechanically impossible" (a deny the runtime enforces before the edit
lands).

Contract (from Claude Code's PreToolUse hook protocol):
  - stdin: JSON with at least {"cwd": ..., "tool_name": ..., "tool_input": {...}}
  - to ALLOW: exit 0 (no output required)
  - to DENY: exit code 2, reason on stderr, AND stdout JSON of exactly
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
         "permissionDecision": "deny", "permissionDecisionReason": "<why>"}}
    Both the exit code and the stdout JSON are required — omitting
    hookSpecificOutput.hookEventName or using a different key makes the
    runtime silently ignore the deny.

Scope of enforcement: this hook only acts when a remediation-scope lock
(analysis/zeugnis/remediation_scope.json, written by
scripts/remediation_scope_cli.py open ... immediately before
zeugnis-remediator is dispatched) is present. With no active scope, there
is nothing this rule set governs, so the hook is inert — it does not
police unrelated edits in a zeugnis-enabled repository, only edits made
while a specific finding's remediation is in flight.

Fails CLOSED: any unexpected exception denies rather than allows, because
an enforcement hook that fails open on its own bug is not an enforcement
hook. The deny message always names the escape hatch (delete the lock
file, or run without --fix). The one exception: a missing/broken
scripts/lib/ package (ModuleNotFoundError at import time) degrades to a
single stderr warning + allow, not a deny -- see the try/except around the
`from lib...` imports below. A packaging defect is not evidence the edit
violates a rule, and every future edit in every repo being blocked is a
strictly worse failure than one missed enforcement check (issue #24).

MUTATION_HARDEN (issue #142): a lock whose domain is mutation_harden is a
test-path scope, not a single allowedFile -- up to editBudget writes, each
under a testRoot and none under a sourcePath, a test-collection config file
(conftest.py, pyproject.toml, ...) or analysis/. The branch keys off the
DOMAIN, so a lock for that domain missing its testRoots is denied rather than
falling through to the single-file check. The scope file is read from the
nearest ancestor holding analysis/zeugnis/, so a cwd inside a mutation copy
does not make this hook inert.

PYTHON FLOOR (#123): MIN_PYTHON, checked past the inert test. A hook runs under
whatever python3 is on PATH; one that cannot import exits 1, which Claude Code
treats as non-blocking, so it ALLOWS the call. This module therefore stays
importable on old interpreters (`from __future__ import annotations`) and denies
explicitly below the floor instead.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MIN_PYTHON = (3, 11)

ESCAPE_HATCH = (
    "If this edit is unrelated to a zeugnis remediation, set "
    "ZEUGNIS_DISABLE_GUARD=1 for this one call, remove "
    "analysis/zeugnis/remediation_scope.json (or the whole analysis/zeugnis/ "
    "directory) to clear stuck state, or run zeugnis-cycle without --fix."
)


def deny(reason: str) -> int:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(payload))
    print(reason, file=sys.stderr)
    return 2


def allow() -> int:
    return 0


def _find_zeugnis_root(cwd: str) -> str | None:
    here = os.path.normpath(os.path.abspath(cwd))
    while True:
        if os.path.isdir(os.path.join(here, "analysis", "zeugnis")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def _test_scope_decision(root, cwd, scope, target, scope_write_violation,
                         lexical_path, is_fixable, record_test_edit) -> int:
    """The mutation_harden branch (issue #142): a budget of writes, each under
    a testRoot and none under a sourcePath, a protected config file, or
    analysis/. Taken whenever the lock's DOMAIN says so -- never inferred from
    which fields the lock happens to carry, so a lock missing testRoots is a
    deny, not a fall-through to the single-file branch below."""
    if not target:
        return deny(f"guard_edit_scope: tool_input.file_path missing; failing closed. {ESCAPE_HATCH}")
    target_path = lexical_path(cwd, target)
    reason = scope_write_violation(lexical_path(root, "."), scope, target_path)
    if reason:
        return deny(
            f"Edit target {target!r} refused under the mutation_harden test-scope lock for lane "
            f"{scope.get('findingId')!r}: {reason}. A surviving mutant is killed by a new test, "
            f"never by editing the code it survived in. {ESCAPE_HATCH}"
        )
    if not is_fixable(scope.get("domain"), scope.get("category")):
        return deny(
            f"Remediation scope for lane {scope.get('findingId')!r} has domain={scope.get('domain')!r}, "
            f"which is not in zeugnis's auto-fixable set. {ESCAPE_HATCH}"
        )
    record_test_edit(root)
    return allow()


def run() -> int:
    # Checked first, before stdin is read and before anything touches the
    # filesystem, so a stuck or wrong denial always has an escape that costs
    # nothing -- same placement and exact `== "1"` test as guard_bash_scope.py.
    #
    # ONE REAL DIFFERENCE FROM THAT GUARD, and it is stateful. This hook is the
    # only writer of `consumed: true` in the repo (mark_consumed at the end of
    # the success path). Returning here skips it, so a bypassed edit does not
    # spend the one-shot remediation budget and the NEXT edit gets a fresh one.
    # That is the right semantics for a switch whose whole job is "this call is
    # not a zeugnis remediation" -- an edit the guard never judged should not
    # count against a finding's single authorized fix. But it does mean the var
    # is not free the way it is for the Bash guard, which writes nothing:
    # leaving it set through a real remediation would silently uncap it.
    if os.environ.get("ZEUGNIS_DISABLE_GUARD") == "1":
        return allow()

    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        return deny(f"guard_edit_scope: could not parse hook input JSON ({exc}); failing closed. {ESCAPE_HATCH}")

    tool_name = event.get("tool_name")
    if tool_name not in ("Edit", "Write"):
        return allow()

    cwd = event.get("cwd") or os.getcwd()
    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path")

    # Inert unless this repo shows evidence of using zeugnis (analysis/zeugnis/
    # exists at cwd or an ancestor). Computed with stdlib only, BEFORE
    # importing lib, so a missing/broken lib package can never turn "this repo
    # doesn't even use zeugnis" into a deny -- req #6 bullet: inert when this
    # repo doesn't use the plugin. Walking UP (issue #142) keeps the guard
    # active when the session's cwd sits inside a mutation copy, which has no
    # analysis/zeugnis/ of its own; lib.mutation_scope.find_zeugnis_root is
    # the same walk, unavailable here because lib is not imported yet.
    root = _find_zeugnis_root(cwd)
    if root is None:
        return allow()

    if sys.version_info < MIN_PYTHON:
        return deny(
            f"zeugnis needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}; guard_edit_scope ran under "
            f"{sys.version.split()[0]} ({sys.executable}). Put a newer python3 first on PATH. "
            f"{ESCAPE_HATCH}"
        )

    try:
        from lib.constants import TEST_SCOPE_DOMAINS  # noqa: E402
        from lib.mutation_scope import lexical_path, scope_write_violation  # noqa: E402
        from lib.paths import UnsafeWritePathError, safe_repo_path  # noqa: E402
        from lib.remediation_scope import is_fixable, mark_consumed, read_scope, record_test_edit  # noqa: E402
    except (ImportError, ModuleNotFoundError) as exc:
        print(
            f"guard_edit_scope: internal error ({type(exc).__name__}: {exc}); "
            "zeugnis's lib package is missing or broken. Allowing this edit "
            "rather than denying every future edit in this repo -- this is a "
            "packaging defect, not evidence the edit violates a rule.",
            file=sys.stderr,
        )
        return allow()

    scope = read_scope(root)
    if scope is None:
        # No remediation in flight; this rule set has nothing to enforce.
        return allow()

    if scope.get("domain") in TEST_SCOPE_DOMAINS:
        return _test_scope_decision(root, cwd, scope, target, scope_write_violation,
                                    lexical_path, is_fixable, record_test_edit)

    if scope.get("consumed"):
        return deny(
            "zeugnis-remediator has already applied its one permitted edit for "
            f"finding {scope.get('findingId')!r} (rule: remediator-one-fix-per-finding). "
            f"A second Edit/Write in the same remediation scope is refused. {ESCAPE_HATCH}"
        )

    if not target:
        return deny(f"guard_edit_scope: tool_input.file_path missing; failing closed. {ESCAPE_HATCH}")

    try:
        resolved_target = target if os.path.isabs(target) else os.path.join(cwd, target)
        allowed_resolved = safe_repo_path(root, scope["allowedFile"])
    except UnsafeWritePathError as exc:
        return deny(f"guard_edit_scope: {exc}. {ESCAPE_HATCH}")

    if os.path.realpath(resolved_target) != os.path.realpath(allowed_resolved):
        return deny(
            f"Edit target {target!r} does not match the locked remediation scope's "
            f"allowedFile {scope['allowedFile']!r} for finding {scope.get('findingId')!r} "
            f"(rule: remediator-one-fix-per-finding — scope is limited to the cited "
            f"file:line only). {ESCAPE_HATCH}"
        )

    # Domain/category is validated again here (open_scope already checked
    # it, but a hand-edited or corrupted lock file should not be trusted
    # blindly) — defense in depth for fixable-domains-in-cycle /
    # draft-domains-in-cycle.
    # Calls the shared check rather than repeating it. lib.remediation_scope's
    # own docstring has always CLAIMED this ("...so cycle_engine.py's
    # record-pass-result gate and guard_edit_scope.py's defense-in-depth re-check
    # never drift apart"), while this file kept its own copy of the logic. They
    # happened to agree on every input, so nothing had drifted yet -- but the
    # docstring actively misled a future editor into believing one edit sufficed.
    # lib/ledger.py:63-67 already delegates honestly; this was the only liar.
    #
    # It also closes a fail-open inconsistency. `from lib.constants import ...`
    # sat HERE, outside the ModuleNotFoundError try/except above, so a broken lib
    # package produced a DENY from this line -- the opposite of the degrade-to-
    # allow policy this file documents and issue #24 established. Importing the
    # symbol up there instead brings it under that umbrella, at zero cost:
    # lib.remediation_scope imports lib.constants at module level, so it is
    # already in sys.modules by the time that import succeeds.
    domain = scope.get("domain")
    category = scope.get("category")

    if not is_fixable(domain, category):
        return deny(
            f"Remediation scope for finding {scope.get('findingId')!r} has domain={domain!r} "
            f"category={category!r}, which is not in zeugnis's auto-fixable set "
            f"(rules: fixable-domains-in-cycle, draft-domains-in-cycle). {ESCAPE_HATCH}"
        )

    mark_consumed(cwd)
    return allow()


def main() -> int:
    try:
        return run()
    except Exception as exc:  # noqa: BLE001 - fail-closed handler, intentionally broad
        return deny(f"guard_edit_scope: internal error ({type(exc).__name__}: {exc}); failing closed. {ESCAPE_HATCH}")


if __name__ == "__main__":
    sys.exit(main())
