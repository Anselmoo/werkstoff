#!/usr/bin/env python3
"""cupertino PreToolUse guard.

usage: python3 pretooluse_guard.py < payload.json   (registered in hooks/hooks.json; Claude Code
       pipes the PreToolUse payload on stdin). Exit 0 allow; 2 deny, with the reason on stderr
       and a hookSpecificOutput deny decision on stdout.

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
import shlex
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
    r"\b(?:rm|unlink|shred|truncate|mv|cp|rsync|tee|dd|install|touch|ln|patch)\b"
    r"|\bgit\s+(?:rm|mv|apply|stash|restore|checkout)\b"
    # sed/perl in-place anywhere in the command, not only right after the program name:
    # `sed -e s/a/b/ -i f` and `sed --in-place f` both edit f.
    r"|\bsed\b[^|;&\n]*\s(?:-[a-zA-Z]*i|--in-place)\b|\bperl\b[^|;&\n]*\s-[a-zA-Z]*i"
    r"|\bfind\b[^|;&]*-(?:delete|exec)\b"
    # Any output redirection -- `>`, `>>`, `1>`, `&>`, `>|` -- except to a file descriptor
    # (`2>&1`) or /dev/null. The old lookbehind excluded a digit or `&` before `>`, which
    # is exactly what `1>file` and `&>file` are.
    r"|>{1,2}\|?\s*(?!&\d|/dev/null\b)[^\s&]"
    # Interpreter one-liners that write: python -c / node -e opening a file for writing,
    # or calling the usual write and delete APIs.
    r"|\b(?:open|fopen)\s*\([^)]*['\"][wax]b?\+?['\"]|\.(?:write_text|write_bytes|unlink|rmdir|rename|replace)\s*\("
    r"|\b(?:os\.(?:remove|unlink|rename|replace)|shutil\.(?:rmtree|move|copy\w*))\s*\("
    r"|\b(?:(?:write|append)File(?:Sync)?|(?:unlink|rm|rmdir|rename|copyFile|truncate)Sync|createWriteStream)\s*\(",
    re.IGNORECASE,
)
# Scripts a model may run during a repair run without the write tripwire: they write only
# under .cupertino/ (or, for build_repair_html.py, wherever --out points, which the exemption
# also confines to .cupertino/). repair_state.py approve is NOT among them: approval is the
# user's (see REPAIR_APPROVE_RE).
REPAIR_EXEMPT_SCRIPTS = {"preflight_repair.py", "baseline.py", "verify.py", "repair_state.py", "apply_delete.py",
                         "probes.py", "design_sources.py", "state.py", "build_repair_html.py"}
# The approval of a changeset is the user's decision, so the model may not record it: run by
# the model, `repair_state.py approve` is denied, and the user runs it in a terminal or with
# Claude Code's `!` prefix (which runs the command directly, not as a model tool call).
REPAIR_APPROVE_RE = re.compile(r"\brepair_state\.py\b[^|;&\n]*\bapprove\b")
# Inside .cupertino/repair/ a model may write only these two files of the ACTIVE run: the
# objective until the baseline freezes it, and the changeset while no item is applied.
# Everything else there -- ACTIVE, other runs' directories, verdicts.jsonl, applied.jsonl,
# the gates -- is written by the scripts alone; a Write that could create a second, fake
# "approved" run, or empty the round log the HALT counts, is a Write that forges the check.
REPAIR_MODEL_WRITABLE = ("objective.json", "changeset.json")
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


def find_state_root(start, project_dir):
    """Stdlib copy of scripts/repair_lib.find_state_root -- the hook must resolve the root
    even when repair_lib cannot be imported. hooks/test_repair_guard.py asserts the two
    agree on every case, so the copy cannot drift silently."""
    here = os.path.abspath(start)
    # The walk stops at the project: CLAUDE_PROJECT_DIR when `start` is inside it, else the
    # nearest ancestor holding .git. Unbounded, a stray ~/.cupertino/ governed every repo
    # below it -- its ACTIVE run denied edits in an unrelated project, its flags satisfied
    # another project's ordering gates.
    boundary = None
    if project_dir:
        pd = os.path.abspath(project_dir)
        if here == pd or here.startswith(pd.rstrip(os.sep) + os.sep):
            boundary = pd
    if boundary is None:
        d = here
        while True:
            if os.path.exists(os.path.join(d, ".git")):
                boundary = d
                break
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    while True:
        if os.path.isdir(os.path.join(here, ".cupertino")):
            return here
        parent = os.path.dirname(here)
        if here == boundary or parent == here:
            break
        here = parent
    return project_dir if project_dir else os.path.abspath(start)


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


def _plugin_script_only(command, session_cwd):
    """True only when `command` is nothing but `python3 <this plugin's scripts>/<exempt>.py ...`
    joined by `&&`, `||` or `;`. Parsed, not substring-matched: the old test exempted any segment
    containing the words "cupertino" and "/scripts/", so `verify.py | tee src/x` or
    `echo x > src/x # cupertino/scripts/` passed as "only plugin scripts".
    """
    if re.search(r"`|\$\(|<\(|>\(", command):
        return False  # command substitution can run anything
    scripts_dir = os.path.realpath(os.path.join(PLUGIN_ROOT, "scripts"))
    state_root = os.path.realpath(os.path.join(find_state_root(session_cwd, os.environ.get("CLAUDE_PROJECT_DIR")),
                                               ".cupertino"))
    for line in command.splitlines():
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            tokens = list(lex)
        except ValueError:
            return False
        segments, seg = [], []
        for tok in tokens:
            if tok in ("&&", "||", ";"):
                segments.append(seg)
                seg = []
            elif tok and set(tok) <= set("|&<>;()"):
                return False  # a pipe, a redirection, a background job or a subshell
            else:
                seg.append(tok)
        segments.append(seg)
        for argv in segments:
            if not argv:
                continue
            if not re.fullmatch(r"python(?:3(?:\.\d+)?)?", os.path.basename(argv[0])):
                return False
            i = 1
            while i < len(argv) and argv[i] in ("-B", "-u", "-I", "-E", "-s", "-X", "utf8", "-Xutf8"):
                i += 1
            if i >= len(argv):
                return False
            script = os.path.realpath(argv[i] if os.path.isabs(argv[i]) else os.path.join(session_cwd, argv[i]))
            if os.path.dirname(script) != scripts_dir or os.path.basename(script) not in REPAIR_EXEMPT_SCRIPTS:
                return False
            rest = argv[i + 1:]
            for k, tok in enumerate(rest):
                out = rest[k + 1] if tok == "--out" and k + 1 < len(rest) else (tok[6:] if tok.startswith("--out=") else None)
                if out is not None:
                    real = os.path.realpath(out if os.path.isabs(out) else os.path.join(session_cwd, out))
                    if real != state_root and not real.startswith(state_root + os.sep):
                        return False
    return True


def check_repair_state_write(cwd, file_path):
    """Write/Edit inside .cupertino/repair/, whether or not a run is active.

    Only the active run's objective.json (until the baseline freezes it) and changeset.json
    (while no item is being applied) are the model's to write. Without an active run nothing
    there is: a model that could write ACTIVE and a run directory could forge an approved run.
    """
    root = find_state_root(cwd, os.environ.get("CLAUDE_PROJECT_DIR"))
    repair_root = os.path.realpath(os.path.join(root, ".cupertino", "repair"))
    target = os.path.realpath(file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path))
    if target != repair_root and not target.startswith(repair_root + os.sep):
        return
    inner = os.path.relpath(target, repair_root).replace(os.sep, "/")
    run = _repair_run(cwd)
    run_id = run[1] if run else None
    if run_id is None or inner not in {f"{run_id}/{name}" for name in REPAIR_MODEL_WRITABLE}:
        deny(f"cupertino-repair: .cupertino/repair/{inner} is written only by the repair scripts. A model may "
             "write the active run's objective.json (until baseline.py freezes it) and changeset.json (while no "
             "item is applied) -- nothing else: the run marker, other runs, the round log and the gates are what "
             "the verification rests on. " + ESCAPE_HATCH)


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
            if inner == "objective.json" and (rdir / "baseline" / "baseline.json").is_file():
                deny("cupertino-repair: the objective is frozen once baseline.py has measured it -- verify grades "
                     "against the objective the baseline saw, so changing it now could turn a regression into "
                     "'done'. A different objective needs a new run: `repair_state.py end --abandon`, then preflight.")
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
    if item["op"] == "create":
        # A create may write its file as often as it needs to (write, then fix a typo); what it
        # may not do is overwrite a file that existed before the run. The baseline hashed every
        # file in scope, so "existed before" is a recorded fact, not today's filesystem -- the
        # old check denied the item's own second write as "that is a modify".
        try:
            before = repair_lib.read_json(rdir / "baseline" / "baseline.json").get("files", {})
        except repair_lib.RepairError as e:
            deny(f"cupertino-repair: {e}. Target: {rel}")
        if rel in before:
            deny(f"cupertino-repair: item {item_id} is a create, but {rel} existed when the baseline was taken -- "
                 "that is a modify, and must be approved as one.")
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


def handle_write_or_edit(cwd, tool_input, session_cwd=None):
    # A relative path is relative to the session, not to the state root.
    base = session_cwd or cwd
    targets = [t if os.path.isabs(t) else os.path.join(base, t) for t in edit_targets(tool_input)]
    if not targets and _repair_run(cwd) is not None:
        deny("cupertino-repair: this edit names no path the guard can read (file_path, edits[].file_path, "
             "file_paths), so it cannot be scoped to the active item; refusing rather than letting it through.")
    for file_path in targets:
        check_repair_state_write(cwd, file_path)
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


def handle_bash(cwd, tool_input, session_cwd=None):
    command = tool_input.get("command", "") or ""
    session_cwd = session_cwd or cwd
    # CUPERTINO_REPAIR_PREAPPROVED=1 is a human's standing approval, set in the environment
    # Claude Code (and so this hook) was started with -- a headless test case whose author
    # approved in advance. A model cannot set it for the hook: `VAR=1 cmd` changes only cmd.
    if REPAIR_APPROVE_RE.search(command) and os.environ.get("CUPERTINO_REPAIR_PREAPPROVED") != "1":
        deny("cupertino-repair: approving the changeset is the user's decision, so the model may not run "
             "`repair_state.py approve`. Show the user the changeset and its hash, and ask them to approve it "
             "themselves -- in their own terminal, or in Claude Code with the `!` prefix: "
             f"`! python3 {os.path.join(PLUGIN_ROOT, 'scripts', 'repair_state.py')} approve`. " + ESCAPE_HATCH)
    # The run's state is the scripts' to write, with or without an active run (see
    # check_repair_state_write): a shell write naming .cupertino/repair is the same forgery.
    if ".cupertino/repair" in command.replace(os.sep, "/") and REPAIR_SHELL_WRITE_RE.search(command) \
            and not _plugin_script_only(command, session_cwd):
        deny("cupertino-repair: this command could write inside .cupertino/repair/, which only the repair scripts "
             "write. " + ESCAPE_HATCH)
    run = _repair_run(cwd)
    if run is not None:
        if MUTATING_GIT_RE.search(command):
            deny("cupertino-repair: a repair run is active; no commit, push, reset, checkout, merge or rebase until "
                 "verify.py has written a verdict and `repair_state.py end` closed the run. " + ESCAPE_HATCH)
        # A plugin script told to write its output outside .cupertino/ is a source write by
        # another name (build_repair_html.py --out app/index.html); the write regex sees no
        # `>` in it, so it is denied here, explicitly.
        for m in re.finditer(r"--out(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)", command):
            out = m.group(1).strip("\"'")
            real = os.path.realpath(out if os.path.isabs(out) else os.path.join(session_cwd, out))
            sdir = os.path.realpath(state_dir(cwd))
            if real != sdir and not real.startswith(sdir + os.sep):
                deny(f"cupertino-repair: a repair run is active and --out {out} points outside .cupertino/ -- a "
                     "script's output is a write like any other. Write reports under .cupertino/. " + ESCAPE_HATCH)
        only_plugin_scripts = _plugin_script_only(command, session_cwd)
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

    # The session's working directory (relative edit paths resolve against it) and the
    # state root (where .cupertino/ lives) are different things; the root comes from the
    # one rule the scripts use, so a run begun from the repo root governs a session
    # working in a subdirectory.
    session_cwd = payload.get("cwd") or os.getcwd()
    try:
        cwd = find_state_root(session_cwd, os.environ.get("CLAUDE_PROJECT_DIR"))
    except OSError as e:
        deny(f"cupertino: could not resolve the .cupertino/ root ({e}); failing closed. {ESCAPE_HATCH}")

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
            handle_write_or_edit(cwd, tool_input, session_cwd)
        elif tool_name == "Bash":
            handle_bash(cwd, tool_input, session_cwd)
    except SystemExit:
        raise
    except Exception as e:
        deny(f"cupertino: internal guard error ({e}); failing closed. {ESCAPE_HATCH}")

    allow()


if __name__ == "__main__":
    main()
