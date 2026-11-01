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

Python floor: MIN_PYTHON, checked past the inert test. A hook runs under whatever
python3 is on PATH; one that cannot import exits 1, which Claude Code treats as
non-blocking, so it ALLOWS the call. This module therefore stays importable on old
interpreters (`from __future__ import annotations` -- the `Exception | None`
annotation below raised TypeError at import under 3.9) and denies explicitly instead.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import NoReturn

PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "scripts"))

_validators_import_error: Exception | None = None
try:
    import validators  # type: ignore  # noqa: E402
except Exception as exc:
    validators = None  # handled defensively below; schema checks degrade to "deny" on write, not "skip"
    _validators_import_error = exc

_repair_import_error: Exception | None = None
try:
    import repair_lib  # type: ignore  # noqa: E402
except Exception as exc:
    repair_lib = None  # an active repair run with no library to read it denies, never allows
    _repair_import_error = exc

MIN_PYTHON = (3, 11)

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
# During a repair run every source write goes through Write/Edit (scoped to the
# active item below) and every delete through scripts/apply_delete.py (reversible).
# These are the shell routes around both. Same caveat as above: a tripwire for a
# cooperative model, not a sandbox.
REPAIR_SHELL_WRITE_RE = re.compile(
    r"\b(?:rm|unlink|shred|truncate|mv|cp|rsync|tee|dd|install)\b|\bgit\s+(?:rm|mv|apply|stash|restore)\b"
    r"|\bsed\s+(?:-\w*\s+)*-i|\bperl\s+-\w*i|\bfind\b[^|;&]*-delete\b|(?<![0-9&])>{1,2}\s*(?!&|/dev/null)[\w./~\"'$-]",
    re.IGNORECASE,
)
REPAIR_GATED_SKILLS = {"cupertino-council", "cupertino-elevate", "cupertino-unbox", "cupertino-reveal"}


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
        deny(
            f"cupertino: validator module failed to load ({type(_validators_import_error).__name__}: "
            f"{_validators_import_error}); refusing to write unvalidated persisted state. " + ESCAPE_HATCH
        )
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


def _repair_run(cwd):
    """(root, run_id) of the active repair run, or None. Fails closed if unreadable."""
    marker = os.path.join(state_dir(cwd), "repair", "ACTIVE")
    if not os.path.isfile(marker):
        return None
    if repair_lib is None:
        deny(f"cupertino: a repair run is active but repair_lib failed to load ({_repair_import_error}); "
             "refusing rather than allowing an unscoped edit. " + ESCAPE_HATCH)
    root = repair_lib.project_root(cwd)
    try:
        run_id = repair_lib.active_run(root)
    except repair_lib.RepairError as e:
        deny(f"cupertino: {e}. " + ESCAPE_HATCH)
    return root, run_id


def check_repair_write(cwd, file_path):
    """While a repair run is active, a source edit must belong to the active approved item.

    This is what makes "fix the KPI row" unable to also restyle the chart: the
    model may edit only the paths the user approved, one item at a time, and only
    after an objective and a baseline exist to verify against.
    """
    run = _repair_run(cwd)
    if run is None:
        return
    root, run_id = run
    try:
        rel = repair_lib.rel_posix(root, file_path)
    except repair_lib.RepairError as e:
        deny(f"cupertino-repair: {e}; a repair edits only inside the project.")
    rdir_rel = f".cupertino/repair/{run_id}/"
    if rel.startswith(".cupertino/"):
        if rel.startswith(rdir_rel):
            inner = rel[len(rdir_rel):]
            top = inner.split("/", 1)[0]
            if inner in repair_lib.SCRIPT_ONLY or top in repair_lib.SCRIPT_ONLY_DIRS:
                deny(f"cupertino-repair: {rel} is written only by the repair scripts (preflight, baseline, "
                     "repair_state, apply_delete, verify) -- a verification result or a gate that a model can "
                     "write is not a verification.")
            rdir = root / ".cupertino" / "repair" / run_id
            if inner == "changeset.json" and (rdir / "active-item").is_file():
                deny("cupertino-repair: an item is being applied; finish-item it before changing the changeset "
                     "(and a changed changeset must be approved again).")
        return
    rdir = root / ".cupertino" / "repair" / run_id
    missing = [name for name, p in (("objective.json", rdir / "objective.json"),
                                     ("baseline (baseline.py)", rdir / "baseline" / "baseline.json"))
               if not p.is_file()]
    if missing:
        deny(f"cupertino-repair: no source edit before {' and '.join(missing)} exist -- without an objective and a "
             f"baseline there is nothing to verify the change against. Target: {rel}")
    try:
        changeset = repair_lib.approved_changeset(root, run_id)
    except repair_lib.RepairError as e:
        deny(f"cupertino-repair: {e}. Target: {rel}")
    active = rdir / "active-item"
    if not active.is_file():
        deny(f"cupertino-repair: no item is active -- run `repair_state.py start-item <id>` for the approved item "
             f"that names {rel}.")
    item_id = active.read_text(encoding="utf-8").strip()
    item = next((i for i in changeset["items"] if i["id"] == item_id), None)
    if item is None:
        deny(f"cupertino-repair: active item {item_id!r} is not in the approved changeset.")
    if item["op"] not in repair_lib.WRITE_OPS:
        deny(f"cupertino-repair: item {item_id} is a {item['op']!r} item, which edits nothing"
             + (" -- deletes go through scripts/apply_delete.py." if item["op"] == "delete" else "."))
    paths = [repair_lib.rel_posix(root, p) for p in item["paths"]]
    if rel not in paths:
        deny(f"cupertino-repair: {rel} is not in active item {item_id}'s approved paths {paths}. If it must change, "
             "stop, add an item for it, show the changeset to the user and approve again.")
    exists = (root / rel).exists()
    if item["op"] == "create" and exists:
        deny(f"cupertino-repair: item {item_id} is a create, but {rel} already exists -- that is a modify, and "
             "must be approved as one.")
    if item["op"] in ("modify", "add") and not exists:
        deny(f"cupertino-repair: item {item_id} is a {item['op']} of {rel}, which does not exist -- creating a "
             "file needs a create item.")


def edit_targets(tool_input):
    """Every path an edit payload names: file_path, notebook_path, edits[].file_path, file_paths.

    Reading only file_path let a payload carrying its paths elsewhere through every
    check unexamined (nacharbeit H-MULTI-PATH; takt_guard.py's edit_targets is the model).
    """
    targets = []
    for key in ("file_path", "notebook_path"):
        value = tool_input.get(key)
        # isinstance, not truthiness: a str is iterable, and iterating one yields characters.
        if isinstance(value, str) and value:
            targets.append(value)
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("file_path"), str) and edit["file_path"]:
            targets.append(edit["file_path"])
    for value in tool_input.get("file_paths") or []:
        if isinstance(value, str) and value:
            targets.append(value)
    return targets


def handle_write_or_edit(cwd, tool_input):
    targets = edit_targets(tool_input)
    if not targets and _repair_run(cwd) is not None:
        deny("cupertino-repair: this edit names no path the guard can read (file_path, edits[].file_path, "
             "file_paths), so it cannot be scoped to the active item; refusing rather than letting it through.")
    for file_path in targets:
        check_repair_write(cwd, file_path)
        handle_artifact_write(cwd, file_path, tool_input)


def handle_artifact_write(cwd, file_path, tool_input):
    if not is_cupertino_artifact_path(file_path):
        return
    check_write_scope(cwd, file_path)
    content = tool_input.get("content")
    if content is not None:
        check_handbook_schema(file_path, content)
        check_handbook_overwrite(cwd, file_path, content)


def handle_bash(cwd, tool_input):
    command = tool_input.get("command", "") or ""
    run = _repair_run(cwd)
    if run is not None:
        if MUTATING_GIT_RE.search(command):
            deny("cupertino-repair: a repair run is active; no commit, push, reset, checkout, merge or rebase until "
                 "verify.py has written a verdict and `repair_state.py end` closed the run. " + ESCAPE_HATCH)
        only_plugin_scripts = all(
            "cupertino" in seg and "/scripts/" in seg
            for seg in re.split(r"&&|\|\||;|\n", command) if seg.strip()
        )
        if not only_plugin_scripts and REPAIR_SHELL_WRITE_RE.search(command):
            deny("cupertino-repair: a repair run is active, and this command can write or delete files outside the "
                 "approved item. Edit with Write/Edit (scoped to the active item); delete only with "
                 "`python3 <plugin>/scripts/apply_delete.py --item <id>` (restorable). " + ESCAPE_HATCH)
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

    if skill_name in REPAIR_GATED_SKILLS and _repair_run(cwd) is not None:
        deny(
            f"cupertino: {skill_name} builds something new; a repair run is active, and a repair changes only "
            "what its approved changeset names. Finish the run first, or add the new work to the changeset as "
            "an approved add/create item and apply it there."
        )

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
        # Inert for every tool EXCEPT cupertino's own gated skills. Invoking the
        # plugin is using it: allowing a gated skill here meant the ordering gate
        # never fired on first use -- measured in docs/examples/design-ui.md, where
        # both runs fired cupertino-council first with zero denials.
        if payload.get("tool_name") == "Skill":
            ti = payload.get("tool_input", {}) or {}
            name = (ti.get("skill") or ti.get("name") or "").split(":")[-1]
            if name in GATED_AFTER_BACKWARDS:
                deny(
                    f"cupertino: {name} requires cupertino-backwards to run first in this repo, and this repo has "
                    f"no .cupertino/ state yet. Run cupertino-backwards first. Changing an EXISTING system "
                    f"instead? That is cupertino-repair, not {name}."
                )
        allow()

    if sys.version_info < MIN_PYTHON:
        deny(
            f"cupertino needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}; this hook ran under "
            f"{sys.version.split()[0]} ({sys.executable}). Put a newer python3 first on PATH. "
            f"{ESCAPE_HATCH}"
        )

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
        elif tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
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
