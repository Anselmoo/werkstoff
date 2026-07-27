#!/usr/bin/env python3
"""cupertino PreToolUse guard.

This is the one place in the plugin where a MUST-NOT rule holds regardless of
whether the model feels like reading a SKILL.md that day. Every check below
corresponds to a specific rule id from the plugin's behavioral spec (named in
comments) and DENIES by raising the tool call, not by asking a model to
reconsider.

Escape hatch: set CUPERTINO_DISABLE_GUARD=1 in the environment to bypass this
guard entirely (e.g. while debugging the plugin itself). Checked first, always
honored, independent of any other state.

Inertness: if this repository has never used cupertino (no `.cupertino/`
state directory), the guard allows everything immediately, before it even
looks at the tool call, so it never polices an unrelated project.

Fail-closed: any internal error (a stat() PermissionError, malformed JSON,
etc.) that happens AFTER we've confirmed `.cupertino/` exists denies the call
rather than silently allowing it, with the escape hatch named in the message.
"""
import json
import os
import re
import sys
from typing import NoReturn

PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "scripts"))

try:
    import validators  # type: ignore  # noqa: E402
except Exception:
    validators = None  # handled defensively below; schema checks degrade to "deny" on write, not "skip"

ESCAPE_HATCH = "set CUPERTINO_DISABLE_GUARD=1 to bypass this guard, or remove .cupertino/ if this repo no longer uses cupertino"

GATED_AFTER_BACKWARDS = {
    "cupertino-focus",
    "cupertino-longevity",
    "cupertino-integrate",
    "cupertino-council",
}

# Matches validators.py's own domain catalog. Artifact-path patterns below
# require one of these exact domains so an unrelated project file that merely
# happens to end in "-handbook.md" (e.g. a user's own "employee-handbook.md")
# is never mistaken for a cupertino artifact and swept into the .cupertino/-only
# write-scope restriction.
DOMAINS = r"(?:code|design|testing|documentation)"

# Regex command matching is a fast, deterministic tripwire for the common
# case, not a sandbox -- it can be evaded by a sufficiently adversarial
# command (env var expansion, wrapping the command in a script file, IFS
# tricks). It is meant to catch a cooperative-but-forgetful model running the
# obvious `git commit`/`rm -rf`, not to contain a deliberately hostile one. A
# fully adversary-proof guarantee here would need a prompt-based hook (an LLM
# judging the command's intent) or sandboxing the shell itself; both are
# outside this hook's scope.
MUTATING_GIT_RE = re.compile(
    r"\bgit\s+(commit|push|reset\s+--hard|clean\s+-f\w*|checkout\s+--|merge|rebase)\b",
    re.IGNORECASE,
)
DESTRUCTIVE_FS_RE = re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b", re.IGNORECASE)


def deny(reason: str) -> NoReturn:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def allow():
    sys.exit(0)


def state_dir(cwd):
    return os.path.join(cwd, ".cupertino")


def flag_set(cwd, name):
    return os.path.isfile(os.path.join(state_dir(cwd), "flags", name))


def resolve_under(cwd, rel_or_abs_path):
    """Resolve a path the same way the Write/Edit tool will, for scope checks."""
    if os.path.isabs(rel_or_abs_path):
        candidate = rel_or_abs_path
    else:
        candidate = os.path.join(cwd, rel_or_abs_path)
    return os.path.realpath(candidate)


def is_cupertino_artifact_path(file_path):
    base = os.path.basename(file_path)
    # Every cupertino artifact lives under .cupertino/, so any write actually
    # targeting that directory is always in scope for the checks below --
    # plus a domain-scoped filename match, in case a skill (correctly or not)
    # tries to write one of these names elsewhere.
    under_state_dir = ".cupertino" + os.sep in file_path or file_path.startswith(".cupertino/")
    return bool(
        under_state_dir
        or re.search(rf"^{DOMAINS}-handbook\.md$", base)
        or re.search(rf"^HANDBOOK_CHECK-{DOMAINS}\.md$", base)
        or re.search(rf"^{DOMAINS}-handbook_summary\.json$", base)
        or re.search(rf"^handbook_check_{DOMAINS}_summary\.json$", base)
    )


def check_write_scope(cwd, file_path):
    if ".." in file_path.split(os.sep):
        deny(f"cupertino: rejecting path traversal in write target: {file_path}")
    allowed_root = os.path.realpath(state_dir(cwd))
    resolved = resolve_under(cwd, file_path)
    if resolved != allowed_root and not resolved.startswith(allowed_root + os.sep):
        deny(
            f"cupertino: write target {file_path!r} resolves outside the plugin's declared "
            f"output directory ({allowed_root}); refusing before dispatch."
        )


def check_handbook_schema(file_path, content):
    base = os.path.basename(file_path)
    is_draft_summary = bool(re.search(rf"^{DOMAINS}-handbook_summary\.json$", base))
    is_check_summary = bool(re.search(rf"^handbook_check_{DOMAINS}_summary\.json$", base))
    if not (is_draft_summary or is_check_summary):
        return
    if validators is None:
        deny("cupertino: validator module failed to load; refusing to write unvalidated persisted state. " + ESCAPE_HATCH)
    try:
        obj = json.loads(content)
        if is_draft_summary:
            validators.validate_handbook_draft_summary(obj)
        else:
            validators.validate_handbook_check_summary(obj)
    except json.JSONDecodeError as e:
        deny(f"cupertino: {file_path} is not valid JSON ({e}); a gating artifact must be well-formed before it is ever written")
    except validators.ValidationError as e:
        deny(f"cupertino: {file_path} failed schema validation on write: {e}")


def check_handbook_overwrite(cwd, file_path, content):
    base = os.path.basename(file_path)
    if not re.search(rf"^{DOMAINS}-handbook\.md$", base):
        return
    resolved = resolve_under(cwd, file_path)
    if os.path.isfile(resolved) and "<!-- cupertino-overwrite-confirmed -->" not in content.splitlines()[:1]:
        deny(
            f"cupertino: {file_path} already exists. cupertino-handbook-draft MUST NOT overwrite an "
            f"existing handbook without asking the user first. Ask, then retry with "
            f"'<!-- cupertino-overwrite-confirmed -->' as the file's first line."
        )


def handle_write_or_edit(cwd, tool_input):
    file_path = tool_input.get("file_path", "")
    if not file_path or not is_cupertino_artifact_path(file_path):
        return
    check_write_scope(cwd, file_path)
    content = tool_input.get("content")
    if content is not None:
        check_handbook_schema(file_path, content)
        check_handbook_overwrite(cwd, file_path, content)


def handle_bash(cwd, tool_input):
    command = tool_input.get("command", "") or ""
    if flag_set(cwd, "handbook-fix-active") or flag_set(cwd, "handbook-check-active"):
        if MUTATING_GIT_RE.search(command):
            deny(
                "cupertino: a handbook fix/check pass is active (.cupertino/flags/handbook-fix-active or "
                "handbook-check-active); handbook-remediator and handbook-verifier MUST NOT commit, push, "
                "or otherwise mutate repository state. " + ESCAPE_HATCH
            )
        if DESTRUCTIVE_FS_RE.search(command):
            deny("cupertino: destructive filesystem command blocked during an active handbook pass. " + ESCAPE_HATCH)


def handle_skill(cwd, tool_input):
    skill_name = (tool_input.get("skill") or tool_input.get("name") or "").split(":")[-1]
    args_str = str(tool_input.get("args") or "")

    if skill_name == "cupertino-cannibalize" and flag_set(cwd, "review-pipeline-active"):
        deny(
            "cupertino: cupertino-cannibalize MUST NOT run automatically as part of cupertino-review's "
            "pipeline. It is user-invoked only -- finish or exit the review pipeline, then invoke "
            "cupertino-cannibalize explicitly and separately."
        )

    if skill_name in GATED_AFTER_BACKWARDS and not flag_set(cwd, "backwards-done"):
        deny(
            f"cupertino: {skill_name} commits to architecture/design direction, which requires "
            f"cupertino-backwards to run first in this scope (no .cupertino/flags/backwards-done marker "
            f"found). Run cupertino-backwards first, or if it already ran, have it write the marker via "
            f"`python3 {PLUGIN_ROOT}/scripts/state.py set backwards-done`."
        )

    if skill_name == "cupertino-handbook-apply" and args_str.strip():
        domain = re.split(r"\s+", args_str.strip())[0].lower()
        handbook_path = os.path.join(cwd, ".cupertino", f"{domain}-handbook.md")
        if not os.path.isfile(handbook_path):
            deny(
                f"cupertino: no handbook found at .cupertino/{domain}-handbook.md. "
                f"cupertino-handbook-apply MUST stop and ask the user to run cupertino-handbook-draft "
                f"for domain '{domain}' first."
            )

    if skill_name == "cupertino-handbook-fix":
        settings_path = os.path.join(cwd, ".claude", "cupertino.local.md")
        mode_is_fix = False
        if os.path.isfile(settings_path):
            try:
                with open(settings_path) as f:
                    text = f.read()
                # Only look inside the actual YAML frontmatter block (between
                # the first pair of "---" lines) -- never in the document
                # body, so prose that merely *mentions* "fix:"/"mode: fix"
                # (e.g. documentation quoting the required syntax) can never
                # be mistaken for the real, deliberate setting.
                frontmatter = re.match(r"^---\n(.*?\n)---\n", text, re.DOTALL)
                if frontmatter:
                    fix_block = re.search(r"(?m)^fix:\s*\n((?:[ \t]+.*\n?)+)", frontmatter.group(1))
                    if fix_block and re.search(r"(?m)^\s*mode:\s*[\"']?fix[\"']?\s*$", fix_block.group(1)):
                        mode_is_fix = True
            except OSError:
                mode_is_fix = False
        if not mode_is_fix:
            deny(
                "cupertino: handbook.fix.mode is not 'fix'. cupertino-handbook-fix MUST stop and report "
                "this plainly rather than applying any edit. Enable it explicitly in "
                ".claude/cupertino.local.md with a `fix:` block containing `mode: fix`."
            )


def _count_marker(prompt, marker):
    return len(re.findall(rf"(?m)^\s*{marker}\s*:", prompt, re.IGNORECASE))


def handle_agent_dispatch(tool_input):
    subagent_type = (tool_input.get("subagent_type") or tool_input.get("subagentType") or "").split(":")[-1]
    prompt = tool_input.get("prompt") or tool_input.get("description") or ""

    if subagent_type == "handbook-dimension-analyst":
        n = _count_marker(prompt, "DIMENSION")
        if n != 1:
            deny(
                f"cupertino: handbook-dimension-analyst MUST be dispatched with exactly one 'DIMENSION:' "
                f"marker in its prompt (one dimension per dispatch); found {n}."
            )

    if subagent_type == "handbook-drift-auditor":
        n = _count_marker(prompt, "RULE")
        if n != 1:
            deny(
                f"cupertino: handbook-drift-auditor MUST be dispatched with exactly one 'RULE:' marker "
                f"in its prompt (one rule per dispatch); found {n}."
            )

    if subagent_type == "handbook-verifier":
        n = _count_marker(prompt, "LOCATION")
        if n != 1:
            deny(
                f"cupertino: handbook-verifier MUST judge exactly one 'LOCATION:' per dispatch so verdicts "
                f"stay independent; found {n} in this prompt."
            )
        if re.search(r"remediator", prompt, re.IGNORECASE):
            deny(
                "cupertino: handbook-verifier MUST be blind to handbook-remediator's own output -- its "
                "prompt must never mention the remediator's description, rationale, or confidence."
            )

    if subagent_type == "handbook-remediator":
        if re.search(r"\bgit\s+(commit|push)\b", prompt, re.IGNORECASE):
            deny("cupertino: handbook-remediator MUST NOT be asked to commit or push; it only edits files.")


def main():
    if os.environ.get("CUPERTINO_DISABLE_GUARD") == "1":
        allow()

    # cwd MUST come from the hook's own stdin payload -- that is how Claude
    # Code's PreToolUse protocol actually communicates the invoking session's
    # working directory, and how every other hook in this plugin family reads
    # it (andon_enforce.py, guard_edit_scope.py, guard_target_edit.py). The
    # previous version read only CLAUDE_PROJECT_DIR / the hook PROCESS's own
    # os.getcwd(), which is not the session's cwd in general -- it made the
    # .cupertino/ check pass or fail based on wherever the hook happened to be
    # invoked FROM rather than the repo actually being edited, so the guard
    # was silently checking the wrong directory. Caught by
    # test/plugins/verify-hooks-deny.py, which showed "allows a violating
    # edit" for a reason that turned out to be this, not hook logic.
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        deny(f"cupertino: could not parse hook payload ({e}); failing closed. {ESCAPE_HATCH}")

    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    try:
        cupertino_active = os.path.isdir(state_dir(cwd))
    except OSError as e:
        deny(f"cupertino: could not check for .cupertino/ ({e}); failing closed. {ESCAPE_HATCH}")

    if not cupertino_active:
        allow()

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    try:
        if tool_name == "Skill":
            handle_skill(cwd, tool_input)
        elif tool_name in ("Task", "Agent"):
            # Subagent dispatch is named "Task" in some Claude Code builds and
            # "Agent" in others; matching both keeps this hook portable
            # across environments rather than silently doing nothing in one
            # of them.
            handle_agent_dispatch(tool_input)
        elif tool_name in ("Write", "Edit"):
            handle_write_or_edit(cwd, tool_input)
        elif tool_name == "Bash":
            handle_bash(cwd, tool_input)
    except SystemExit:
        raise
    except Exception as e:
        deny(f"cupertino: internal guard error ({e}); failing closed. {ESCAPE_HATCH}")

    allow()


if __name__ == "__main__":
    main()
