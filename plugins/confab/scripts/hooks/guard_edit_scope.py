#!/usr/bin/env python3
"""PreToolUse hook for Edit and Write: enforces remediator-one-fix-per-
finding, fixable-domains-in-cycle, and draft-domains-in-cycle REGARDLESS
of whether the confab-remediator agent (or the orchestrating session)
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
(analysis/confab/remediation_scope.json, written by
scripts/remediation_scope_cli.py open ... immediately before
confab-remediator is dispatched) is present. With no active scope, there
is nothing this rule set governs, so the hook is inert — it does not
police unrelated edits in a confab-enabled repository, only edits made
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
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ESCAPE_HATCH = (
    "If this edit is unrelated to a confab remediation, remove "
    "analysis/confab/remediation_scope.json (or the whole analysis/confab/ "
    "directory) to clear stuck state, or run confab-cycle without --fix."
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


def run() -> int:
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

    # Inert unless this repo shows evidence of using confab (analysis/confab/
    # exists). Computed with stdlib only, BEFORE importing lib, so a
    # missing/broken lib package can never turn "this repo doesn't even use
    # confab" into a deny -- req #6 bullet: inert when this repo doesn't use
    # the plugin.
    if not os.path.isdir(os.path.join(cwd, "analysis", "confab")):
        return allow()

    try:
        from lib.paths import UnsafeWritePathError, safe_repo_path  # noqa: E402
        from lib.remediation_scope import read_scope, mark_consumed  # noqa: E402
    except (ImportError, ModuleNotFoundError) as exc:
        print(
            f"guard_edit_scope: internal error ({type(exc).__name__}: {exc}); "
            "confab's lib package is missing or broken. Allowing this edit "
            "rather than denying every future edit in this repo -- this is a "
            "packaging defect, not evidence the edit violates a rule.",
            file=sys.stderr,
        )
        return allow()

    scope = read_scope(cwd)
    if scope is None:
        # No remediation in flight; this rule set has nothing to enforce.
        return allow()

    if scope.get("consumed"):
        return deny(
            "confab-remediator has already applied its one permitted edit for "
            f"finding {scope.get('findingId')!r} (rule: remediator-one-fix-per-finding). "
            f"A second Edit/Write in the same remediation scope is refused. {ESCAPE_HATCH}"
        )

    if not target:
        return deny(f"guard_edit_scope: tool_input.file_path missing; failing closed. {ESCAPE_HATCH}")

    try:
        resolved_target = safe_repo_path(cwd, target) if not os.path.isabs(target) else target
        allowed_resolved = safe_repo_path(cwd, scope["allowedFile"])
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
    from lib.constants import DRAFT_ONLY_DOMAINS, FIXABLE_DOMAINS  # noqa: E402

    domain = scope.get("domain")
    category = scope.get("category")
    fixable = False
    if domain not in DRAFT_ONLY_DOMAINS:
        policy = FIXABLE_DOMAINS.get(domain)
        if policy and (policy["mode"] == "all" or (policy["mode"] == "category" and category in policy["categories"])):
            fixable = True

    if not fixable:
        return deny(
            f"Remediation scope for finding {scope.get('findingId')!r} has domain={domain!r} "
            f"category={category!r}, which is not in confab's auto-fixable set "
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
