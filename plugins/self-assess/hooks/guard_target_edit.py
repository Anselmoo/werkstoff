#!/usr/bin/env python3
"""PreToolUse hook for Edit/Write/MultiEdit: enforces idiom-fix-mode-fix-gate
and dirty-tree-gate-ask-before-edit REGARDLESS of whether self-assess-idiom-fix
or self-assess-transform-execute cooperates with its own instructions.

Both rules already exist as typed-error-raising functions in
scripts/lib/gates.py (check_idiom_fix_mode, check_transform_mode,
check_dirty_tree) -- reused here unchanged, not reimplemented. What was
missing was a call site the runtime enters unconditionally rather than a
call site a model chooses to reach. Measured this session: a rule reached
only via "the skill is supposed to call this function" is honored on the
order of 1 run in 3; a PreToolUse hook is invoked every time.

Contract (from Claude Code's PreToolUse hook protocol):
  - stdin: JSON with at least {"cwd": ..., "tool_name": ..., "tool_input": {...}}
  - to ALLOW: exit 0 (no output required)
  - to DENY: exit code 2, reason on stderr, AND stdout JSON of exactly
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
         "permissionDecision": "deny", "permissionDecisionReason": "<why>"}}
    Both are required -- omitting hookSpecificOutput.hookEventName or using
    "systemMessage" instead of "permissionDecisionReason" makes the runtime
    silently ignore the deny. (This exact mistake shipped once already in
    this plugin family and was caught only by a dedicated hook-behavior gate,
    test/plugins/verify-hooks-deny.py -- run that after touching this file.)

Scope of enforcement: this hook only acts on a Write/Edit/MultiEdit whose
target resolves OUTSIDE self-assess's own output_dir (default
analysis/self-assess/). Self-assess writing its own reports is never gated;
only a write that reaches into the target repository's actual source is,
because that is the only kind of write either gated rule is about. Inert
entirely when .claude/self-assess.local.md's settings resolve output_dir in
a way that makes the target ambiguous only if the target cannot be resolved
at all (fails closed in that case, see below).

Fails CLOSED: any unexpected exception denies rather than allows. The deny
message always names the escape hatch (the setting to change). The one
exception: a missing/broken scripts/lib/ package (ModuleNotFoundError at
import time) degrades to a single stderr warning + allow, not a deny --
see the try/except around the `from lib...` imports below. A packaging
defect is not evidence the edit violates a rule, and every future edit in
every repo being blocked is a strictly worse failure than one missed
enforcement check (issue #24).
"""

import json
import os
import sys

# This hook lives at plugins/self-assess/hooks/guard_target_edit.py -- one
# level under the plugin root, unlike confab's scripts/hooks/ nesting. `lib/`
# is at plugins/self-assess/scripts/lib/, so the path onto sys.path is
# <plugin_root>/scripts, computed directly rather than copy-pasted from a
# different plugin's directory depth (which is what broke this the first time
# -- caught immediately by .claude/hooks/gate-on-write.py's PostToolUse check).
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "scripts"))

ESCAPE_HATCH = (
    "If this edit is not one self-assess should be gating, set idiom_fix.mode: "
    "'fix' or transform.mode: 'execute' (whichever applies) and, if the tree is "
    "dirty, require_clean_tree: false, in .claude/self-assess.local.md."
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
        return deny(f"guard_target_edit: could not parse hook input JSON ({exc}); failing closed. {ESCAPE_HATCH}")

    tool_name = event.get("tool_name")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return allow()

    cwd = event.get("cwd") or os.getcwd()
    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path")
    if not target:
        return allow()  # no single target (e.g. some MultiEdit shapes) -- nothing to scope-check

    # Inert unless this repo shows evidence of being self-assess-managed:
    # settings file present, or the plugin's default output dir already
    # exists here. Computed with stdlib only, BEFORE importing lib, so a
    # missing/broken lib package can never turn "this repo doesn't even use
    # self-assess" into a deny -- without this, the hook would deny
    # target-repo edits in EVERY repository on the machine, self-assess-
    # enabled or not, the same class of mistake andon's ledger-existence
    # check and confab's remediation-scope-existence check both exist
    # specifically to prevent. A settings file with a customized output_dir
    # is still caught by has_settings alone; you can't have a non-default
    # output_dir without a settings file that set it.
    settings_path = os.path.join(cwd, ".claude", "self-assess.local.md")
    has_settings = os.path.isfile(settings_path)
    has_default_output_dir = os.path.isdir(os.path.join(cwd, "analysis", "self-assess"))

    if not (has_settings or has_default_output_dir):
        return allow()

    try:
        from lib.settings import load_settings  # noqa: E402
        from lib.gates import check_dirty_tree, check_idiom_fix_mode, check_transform_mode  # noqa: E402
        from lib.errors import SelfAssessError, WriteScopeError  # noqa: E402
        from lib.write_guard import resolve_output_path  # noqa: E402
    except (ImportError, ModuleNotFoundError) as exc:
        print(
            f"guard_target_edit: internal error ({type(exc).__name__}: {exc}); "
            "self-assess's lib package is missing or broken. Allowing this edit "
            "rather than denying every future edit in this repo -- this is a "
            "packaging defect, not evidence the edit violates a rule.",
            file=sys.stderr,
        )
        return allow()

    settings = load_settings(cwd)
    output_dir = settings.get("output_dir", "analysis/self-assess")

    # A write self-assess makes to its OWN report directory is never what
    # idiom-fix-mode-fix-gate or dirty-tree-gate are about -- only a write
    # that reaches into the target repo's actual source is.
    try:
        resolved_target = os.path.realpath(
            target if os.path.isabs(target) else os.path.join(cwd, target)
        )
        own_output_dir = os.path.realpath(resolve_output_path(cwd, output_dir, "."))
    except WriteScopeError as exc:
        return deny(f"guard_target_edit: {exc}. {ESCAPE_HATCH}")

    if resolved_target == own_output_dir or resolved_target.startswith(own_output_dir + os.sep):
        return allow()

    # Outside self-assess's own output directory: this is exactly the shape
    # of edit idiom-fix-mode-fix-gate and dirty-tree-gate exist to gate.
    # Neither transform-execute nor idiom-fix's authorization can both be
    # satisfied and denied at once, so: allowed only if AT LEAST ONE mode is
    # actively authorized, and even then only if the tree gate also passes.
    idiom_ok = settings.get("idiom_fix", {}).get("mode") == "fix"
    transform_ok = settings.get("transform", {}).get("mode") == "execute"

    if not (idiom_ok or transform_ok):
        return deny(
            "Neither idiom_fix.mode='fix' nor transform.mode='execute' is set in "
            ".claude/self-assess.local.md, so no self-assess skill is authorized to "
            f"edit target-repository source ({target!r}) right now (rules: "
            f"idiom-fix-mode-fix-gate, transform-execute-gate-transform-mode). {ESCAPE_HATCH}"
        )

    try:
        check_dirty_tree(cwd, require_clean_tree=settings.get("require_clean_tree", True))
    except SelfAssessError as exc:
        return deny(f"{exc} (rule: dirty-tree-gate-ask-before-edit). {ESCAPE_HATCH}")

    # Defense in depth: re-run the mode-specific gate too, in case settings
    # were hand-edited to something that satisfies the OR above by accident
    # (e.g. a typo'd idiom_fix.mode that happens to also not equal transform's
    # 'execute' string) -- these re-raise SelfAssessError on the exact
    # documented conditions, nothing new invented here.
    try:
        if idiom_ok:
            check_idiom_fix_mode(settings)
        elif transform_ok:
            check_transform_mode(settings)
    except SelfAssessError as exc:
        return deny(f"{exc} {ESCAPE_HATCH}")

    return allow()


def main() -> int:
    try:
        return run()
    except Exception as exc:  # noqa: BLE001 - fail-closed handler, intentionally broad
        return deny(f"guard_target_edit: internal error ({type(exc).__name__}: {exc}); failing closed. {ESCAPE_HATCH}")


if __name__ == "__main__":
    sys.exit(main())
