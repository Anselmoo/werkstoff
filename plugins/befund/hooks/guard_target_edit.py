#!/usr/bin/env python3
"""PreToolUse hook for Edit/Write/MultiEdit: enforces idiom-fix-mode-fix-gate,
transform-execute-gate-transform-mode, and dirty-tree-gate-ask-before-edit
REGARDLESS of whether befund-idiom-fix or befund-transform-execute
cooperates with its own instructions.

Both mode rules already exist as typed-error-raising functions in
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

Scope of enforcement: this hook is inert unless a befund remediator
dispatch has an edit-scope lock open (analysis/befund/edit_scope.json,
written by befund_cli.py's open-edit-scope, called by
befund-idiom-fix / befund-transform-execute immediately before
dispatching idiom-remediator / transform-executor). PreToolUse's payload
carries no field identifying which agent/plugin issued the Edit/Write/
MultiEdit -- so gating on repo-level state ("does this repo look
befund-managed") instead of a per-dispatch lock meant EVERY edit in the
whole session, from any plugin or a direct user edit, got swept into this
gate the moment a repo had .claude/befund.local.md or analysis/
befund/ at all (issue: this hook blocked zeugnis/cupertino/
passung remediators and ordinary direct edits in any
befund-enabled repo). Mirrors zeugnis's guard_edit_scope.py, which is
inert unless analysis/zeugnis/remediation_scope.json is open -- except this
lock holds a LIST of allowed files rather than one, because befund
dispatches one remediator per independent (file, kind) cluster / stage file,
and those dispatches may run in parallel; a single-file lock would race
between them.

Befund writing its own reports (inside output_dir, default
analysis/befund/) is never gated, scope lock or not.

Fails CLOSED once a scope is open: any unexpected exception denies rather
than allows. The deny message always names the escape hatch. The one
exception: a missing/broken scripts/lib/ package (ModuleNotFoundError at
import time) degrades to a single stderr warning + allow, not a deny --
see the try/except around the `from lib...` imports below. A packaging
defect is not evidence the edit violates a rule, and every future edit in
every repo being blocked is a strictly worse failure than one missed
enforcement check (issue #24).

Containment (issue #39): a resolved edit target is checked against cwd
BEFORE it is ever compared to own_output_dir or the lock's allowedFiles.
Without that check, a target outside the target repository entirely (an
absolute path into /tmp, $HOME, or an unrelated sibling repo) fell through
"not own_output_dir, not in allowedFiles" and was silently treated as
target-repository source -- denied by remediator-scope-enforcement, a rule
that was never about it, for the whole window a remediator dispatch holds
the lock open. This hook exists to gate writes into the TARGET repository's
own source, so a target that does not resolve inside cwd at all is outside
every rule this hook enforces and is allowed, not denied -- the fix is an
allow for that case, never a new deny.

Escape hatch: set BEFUND_DISABLE_GUARD=1 to bypass this guard for one call,
checked first in run() before anything else -- see ESCAPE_HATCH below,
which every deny interpolates.
"""

import json
import os
import sys

# This hook lives at plugins/befund/hooks/guard_target_edit.py -- one
# level under the plugin root, unlike zeugnis's scripts/hooks/ nesting. `lib/`
# is at plugins/befund/scripts/lib/, so the path onto sys.path is
# <plugin_root>/scripts, computed directly rather than copy-pasted from a
# different plugin's directory depth (which is what broke this the first time
# -- caught immediately by .claude/hooks/gate-on-write.py's PostToolUse check).
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "scripts"))

ESCAPE_HATCH = (
    "If this edit is not one befund should be gating, set idiom_fix.mode: "
    "'fix' or transform.mode: 'execute' (whichever applies) and, if the tree is "
    "dirty, require_clean_tree: false, in .claude/befund.local.md. To bypass "
    "this guard for one call instead, set BEFUND_DISABLE_GUARD=1."
)


def _is_contained(path: str, root: str) -> bool:
    """True if `path` (already normalised the same way as `root`) is `root`
    itself or lives under it. Shared by the lexical and realpath halves of
    the containment check below, which is a permissive branch (it decides
    when to STOP gating, not when to start) -- so EITHER test reporting
    "inside" must be enough to keep the target gated, and only agreement on
    "outside" may allow it. A symlink parked outside the tree can point
    into it: the lexical path still reads as outside while realpath
    resolves inside and the write lands on real, in-repo source. Treating
    that as "outside" because the lexical half said so would open exactly
    the scope-lock bypass this check exists to close. (Contrast
    arbeitsplan_guard.py:420-434, which uses the same pair of tests to
    decide a target IS inside -- a restrictive decision, so it requires
    both to agree on "inside". Here the decision is the other polarity, so
    requiring both to agree on "outside" is the corresponding restrictive
    form -- "realpath only ever narrows what is allowed here, never widens
    it" per that file's own comment.)"""
    return path == root or path.startswith(root + os.sep)


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
    if os.environ.get("BEFUND_DISABLE_GUARD") == "1":
        return allow()

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

    # Inert unless a befund remediator dispatch actually has an edit-scope
    # lock open right now. Checked with stdlib only, BEFORE importing lib, so
    # a missing/broken lib package can never turn "no befund run is in
    # flight" into a deny, and so the common case (no lock) never touches
    # settings/output_dir at all -- this is the fix for the bug where any
    # repo that merely had .claude/befund.local.md or analysis/
    # befund/ present got EVERY edit in the session gated, regardless of
    # which plugin or agent made it.
    scope_path = os.path.join(cwd, "analysis", "befund", "edit_scope.json")
    if not os.path.isfile(scope_path):
        return allow()

    try:
        from lib.settings import load_settings  # noqa: E402
        from lib.gates import check_dirty_tree, check_idiom_fix_mode, check_transform_mode  # noqa: E402
        from lib.errors import SelfAssessError, WriteScopeError  # noqa: E402
        from lib.write_guard import resolve_output_path  # noqa: E402
        from lib.edit_scope import read_scope, safe_repo_path  # noqa: E402
    except (ImportError, ModuleNotFoundError) as exc:
        print(
            f"guard_target_edit: internal error ({type(exc).__name__}: {exc}); "
            "befund's lib package is missing or broken. Allowing this edit "
            "rather than denying every future edit in this repo -- this is a "
            "packaging defect, not evidence the edit violates a rule.",
            file=sys.stderr,
        )
        return allow()

    # Containment (issue #39): this hook exists to gate writes into the
    # TARGET REPOSITORY's own source -- idiom-fix-mode-fix-gate,
    # transform-execute-gate-transform-mode, dirty-tree-gate, and
    # remediator-scope-enforcement are all rules about what a befund
    # remediator does to the repo it was dispatched against. A target that
    # does not even resolve inside cwd (a write to /tmp, $HOME, or an
    # unrelated sibling repository) is therefore never target-repository
    # source and this hook has no rule to apply to it, so it is allowed
    # rather than run through the own_output_dir / allowedFiles logic below.
    #
    # Before this check, "outside own_output_dir and not in allowedFiles"
    # was silently read as "in-repo source, not named in the lock" and
    # denied under remediator-scope-enforcement -- a rule that was never
    # about it -- for the whole window a remediator dispatch held the
    # edit-scope lock open. This runs ahead of both the absolute-path
    # branch just below (an absolute file_path skips straight past the
    # os.path.join(cwd, target) there and never otherwise touches cwd at
    # all) and the own_output_dir early-allow that follows it, so neither
    # can be reached before containment is decided.
    #
    # Lexical containment (os.path.normpath) is necessary but not
    # sufficient -- a symlink can point across the boundary in either
    # direction -- so this is a PERMISSIVE branch (it decides when to STOP
    # gating) and must require both tests to agree on "outside" before it
    # allows. Either test alone reporting "inside" is enough to keep the
    # target gated and fall through to the normal own_output_dir /
    # allowedFiles logic below:
    #   - lexically outside, but the path is a symlink whose realpath
    #     resolves back inside cwd (e.g. an absolute path outside the repo
    #     that happens to point at src/secret.py) -- the write lands on
    #     real in-repo source, so this must stay gated, not read as
    #     "outside" because the lexical half said so;
    #   - lexically inside, but a symlink resolves outside cwd -- falls
    #     through to allowedFiles below, which denies it there (safe
    #     direction) rather than this check inventing a new allow.
    # Only lexically outside AND realpath outside is the case issue #39 is
    # actually about: a target that was never in the repository to begin
    # with. Mirrors arbeitsplan_guard.py:420-434, which runs the same pair
    # of tests for the opposite (restrictive) decision -- deciding a target
    # IS inside a worktree, so it requires both to agree on "inside". Here
    # the polarity is inverted, so the corresponding restrictive form
    # requires both to agree on "outside": "realpath only ever narrows what
    # is allowed here, never widens it" (that file's own comment, still
    # true under either polarity). os.path.normpath has no Path equivalent
    # (Path.resolve() would touch the filesystem and follow symlinks,
    # changing what THIS check itself decides), and Path.relative_to raises
    # instead of returning "../elsewhere" unless walk_up=True, which needs
    # 3.12+ -- the same asymmetry CLAUDE.md documents for takt_guard.py and
    # arbeitsplan_guard.py, kept here too.
    cwd_norm = os.path.normpath(cwd)
    cwd_real = os.path.realpath(cwd)
    target_lexical = os.path.normpath(target if os.path.isabs(target) else os.path.join(cwd, target))
    target_real = os.path.realpath(target_lexical)
    if not _is_contained(target_lexical, cwd_norm) and not _is_contained(target_real, cwd_real):
        return allow()

    settings = load_settings(cwd)
    output_dir = settings.get("output_dir", "analysis/befund")

    # A write befund makes to its OWN report directory is never what
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

    scope = read_scope(cwd)
    if scope is None:
        # Lock file vanished between the os.path.isfile check above and here
        # (e.g. a concurrent close-edit-scope) -- nothing left to enforce.
        return allow()

    try:
        allowed_resolved = {
            os.path.realpath(safe_repo_path(cwd, f)) for f in scope.get("allowedFiles", [])
        }
    except WriteScopeError as exc:
        return deny(f"guard_target_edit: edit-scope lock is corrupt ({exc}). {ESCAPE_HATCH}")

    if resolved_target not in allowed_resolved:
        return deny(
            f"Edit target {target!r} is not one of the files named in the open "
            f"befund edit-scope lock ({sorted(scope.get('allowedFiles', []))!r}) "
            "(rule: remediator-scope-enforcement). "
            f"{ESCAPE_HATCH}"
        )

    mode = scope.get("mode")
    try:
        check_dirty_tree(cwd, require_clean_tree=settings.get("require_clean_tree", True))
    except SelfAssessError as exc:
        return deny(f"{exc} (rule: dirty-tree-gate-ask-before-edit). {ESCAPE_HATCH}")

    # Defense in depth: re-run the mode-specific gate too, in case settings
    # were hand-edited to something that contradicts the open scope's own
    # mode (e.g. idiom_fix.mode flipped back to 'propose' mid-run) -- these
    # re-raise SelfAssessError on the exact documented conditions, nothing
    # new invented here.
    try:
        if mode == "idiom_fix":
            check_idiom_fix_mode(settings)
        elif mode == "transform":
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
