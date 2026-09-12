#!/usr/bin/env python3
"""PreToolUse hook: deny an edit or a dispatch that runs ahead of its beat.

usage: takt_guard.py   (no arguments; the hook event arrives as JSON on stdin)

  Registered by hooks/hooks.json and invoked by Claude Code, not by hand. To
  exercise it directly, pipe one event in:
      echo '{"cwd":".","tool_name":"Edit","tool_input":{"file_path":"a.tsx"}}' \
          | python3 plugins/takt/hooks/takt_guard.py; echo "exit=$?"
  Its calibration is plugins/takt/hooks/test_takt_guard.py.

Several skills in this marketplace declare where in a build they belong --
cupertino-council says "before writing any code ... never after",
compass-clarify-scope says "before any work begins". A declaration in prose is
honored on the order of 1 run in 3 (see the enforcement ladder in this repo's
CLAUDE.md); a PreToolUse hook of type "command" is invoked every time. This
hook is the difference between a documented beat order and an enforced one.

Contract (Claude Code's PreToolUse hook protocol):
  - stdin: JSON with at least {"cwd": ..., "tool_name": ..., "tool_input": {...}}
  - to ALLOW: exit 0
  - to DENY: exit code 2, reason on stderr, AND stdout JSON of exactly
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
         "permissionDecision": "deny", "permissionDecisionReason": "<why>"}}
    Both are required -- omitting hookSpecificOutput.hookEventName or using
    "systemMessage" instead of "permissionDecisionReason" makes the runtime
    silently ignore the deny. That exact mistake has shipped in this plugin
    family before and was caught only by test/plugins/verify-hooks-deny.py --
    run it after touching this file.

Inertness: a repository that has not declared beats (no .claude/takt.local.md)
is allowed immediately, before the tool call is even inspected, so this never
polices an unrelated project. Fail-closed: once that file is confirmed to
exist, any internal error denies rather than silently allowing, with the
escape hatch named in the message.

Matching is fnmatch, never regex. Every silent-failure regex form this repo has
been burned by -- [^.]{0,80} that cannot span a dotted filename, [^\n] in a
bracket expression, \b next to a non-word character -- is a regex-only failure
mode, and a glob cannot express any of them.

Declaring beats -- .claude/takt.local.md, one fenced json block:

    ```json
    {
      "beats": [
        {
          "id": "ui-before-council",
          "tools": ["Write", "Edit", "MultiEdit"],
          "paths": ["*.tsx", "*.jsx", "*.vue", "*.svelte", "src/ui/*"],
          "require": ".takt/council-done",
          "reason": "cupertino-council runs before UI code, never after."
        }
      ]
    }
    ```

A beat matches on `paths` (for Write/Edit/MultiEdit) or on `skills` (for
Skill/Task/Agent). It denies when its `require` marker does not yet exist.
Whatever performs the beat creates that marker; nothing here writes files.

An edit payload may name more than one file -- a MultiEdit does not reliably
carry a single top-level `file_path` -- so every path the payload exposes is
collected (`file_path`, `edits[].file_path`, `file_paths`) and the beat is
violated if ANY of them is gated. If a beat gates the current edit tool but no
path can be determined at all, the call is DENIED rather than allowed: an edit
that cannot be checked against a gate the repository opted into is exactly the
silent bypass this hook exists to prevent. The same rule applies to dispatches --
a Skill/Task/Agent call whose name cannot be determined is denied by a beat that
gates dispatches, for identical reasons.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path
from typing import NoReturn

SETTINGS = Path(".claude") / "takt.local.md"
ESCAPE_HATCH = (
    "set TAKT_DISABLE_GUARD=1 to bypass this guard, create the required marker "
    "once the beat has actually run, or remove .claude/takt.local.md if this "
    "repository no longer declares beats"
)
RUN_ID_RE = re.compile(r"\A(?!.*\.\.)[A-Za-z0-9._-]{1,64}\Z")

EDIT_TOOLS = ("Write", "Edit", "MultiEdit")
DISPATCH_TOOLS = ("Skill", "Task", "Agent")


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


def allow() -> NoReturn:
    sys.exit(0)


def load_declaration(settings_path: str) -> tuple:
    """Read the first fenced json block. String search, not regex -- a regex
    over a fence is one of the forms that fails silently on odd whitespace.

    Returns (run_id, beats). run_id is "" when the declaration omits it, which
    is the pre-runId behaviour: a relative `require` then resolves against cwd
    exactly as before. A declaration WITH a runId namespaces every relative
    marker under .takt/<run_id>/, so a marker left behind by an earlier run
    cannot satisfy this run's beat -- the whole point, for a generated
    declaration that describes one run rather than a durable project fact."""
    text = Path(settings_path).read_text(encoding="utf-8")
    start = text.find("```json")
    if start == -1:
        return "", []
    body_start = text.index("\n", start) + 1
    end = text.find("```", body_start)
    if end == -1:
        return "", []
    parsed = json.loads(text[body_start:end])
    run_id = parsed.get("runId", "")
    if run_id is None:
        run_id = ""
    if not isinstance(run_id, str):
        # A non-string runId would stringify into a path component. Refuse.
        raise ValueError("runId must be a string")
    if run_id and not RUN_ID_RE.match(run_id):
        # runId becomes a PATH COMPONENT. Anything with a separator or a dot
        # segment could escape .takt/ entirely, so this is fail-closed by
        # charset rather than by sanitising -- sanitising invites a bypass.
        raise ValueError(
            f"runId {run_id!r} is not [A-Za-z0-9._-]{{1,64}} without '..'"
        )
    beats = parsed.get("beats", [])
    return run_id, (beats if isinstance(beats, list) else [])


def marker_path_for(cwd: str, run_id: str, marker: str) -> str:
    """Absolute path of a beat's required marker.

    Three cases, and the middle one is the reason this is not a one-liner:

      absolute            taken literally, runId or not. An explicit path is an
                          explicit path.
      already under .takt/  taken as-is. This is a REPO-LEVEL marker -- a durable
                          fact like ".takt/council-done" -- and namespacing it per
                          run would point every run at a path that cannot exist yet,
                          so a fact that IS true would read as false forever.
      a bare name         namespaced under .takt/<run_id>/ when a runId is
                          declared. This is a PER-RUN marker, and namespacing is
                          the whole point: last week's run must not satisfy today's.

    The split falls exactly along the existing convention -- takt's own README
    example writes `.takt/council-done` -- so every declaration written before
    runId existed keeps its precise meaning, whether or not a runId is added
    later. It also lets ONE declaration carry both kinds at once, which is what
    a compiled union of per-run beats and repo-level plugin beats needs.
    """
    if Path(marker).is_absolute():
        return marker
    normalized = marker.replace(os.sep, "/")
    if normalized == ".takt" or normalized.startswith(".takt/"):
        return str(Path(cwd) / marker)
    if run_id:
        return str(Path(cwd) / ".takt" / run_id / marker)
    return str(Path(cwd) / marker)


def relative(cwd: str, path: str) -> str:
    """Repo-relative posix form, so a glob written as src/ui/* matches whether
    the tool reported an absolute or a relative path."""
    if not path:
        return ""
    # normpath/relpath kept deliberately: Path has no lexical normpath (only
    # .resolve(), which touches the filesystem and follows symlinks), and
    # Path.relative_to raises where relpath returns "../outside" unless
    # walk_up=True, which is Python 3.12+. A hook runs under whatever python3
    # the machine has, and a hook that cannot import denies every call.
    candidate = path if Path(path).is_absolute() else str(Path(cwd) / path)
    try:
        rel = os.path.relpath(os.path.normpath(candidate), os.path.normpath(cwd))
    except ValueError:
        rel = path
    return rel.replace(os.sep, "/")


def matches(target: str, patterns) -> bool:
    if not target or not isinstance(patterns, list):
        return False
    base = target.rsplit("/", 1)[-1]
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        if fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(base, pattern):
            return True
    return False


def first_match(targets, patterns):
    """The first target matching any pattern, or None. An edit payload can name
    several files; a beat is violated if ANY of them is gated."""
    for target in targets:
        if matches(target, patterns):
            return target
    return None


def edit_targets(cwd: str, tool_input: dict) -> list:
    """Every file path an edit payload names, repo-relative.

    A MultiEdit payload does not reliably carry a single top-level `file_path`.
    This repository already records that shape in
    `plugins/self-assess/hooks/guard_target_edit.py`, which allows when it cannot
    find one -- defensible there, because that hook is scope-checking. takt is
    fail-closed, so it gathers every path the payload does expose, and its caller
    denies rather than allows when the set comes back empty.
    """
    found = []
    single = tool_input.get("file_path")
    if isinstance(single, str) and single:
        found.append(single)

    # `isinstance(..., list)` rather than a truthiness check: iterating a STRING
    # yields characters, every one of which is a non-empty str, which would fill
    # `found` with junk that matches no glob -- and, worse, would make the set
    # non-empty so the caller's fail-closed branch never fires. A malformed
    # payload must look empty here, not look full.
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for entry in edits:
            if isinstance(entry, dict):
                path = entry.get("file_path")
                if isinstance(path, str) and path:
                    found.append(path)

    plural = tool_input.get("file_paths")
    if isinstance(plural, list):
        for path in plural:
            if isinstance(path, str) and path:
                found.append(path)

    return [relative(cwd, path) for path in found]


def dispatch_target(tool_input: dict) -> str:
    for key in ("skill", "subagent_type", "name", "agent", "command"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def main() -> NoReturn:
    if os.environ.get("TAKT_DISABLE_GUARD") == "1":
        allow()

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        allow()  # not a payload this hook can read; never police what it cannot parse

    cwd = event.get("cwd") or str(Path.cwd())
    settings_path = Path(cwd) / SETTINGS
    if not settings_path.is_file():
        allow()  # inert: this repository has not declared any beats

    # Past this point the repository opted in, so errors deny rather than allow.
    try:
        tool_name = event.get("tool_name") or ""
        tool_input = event.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        run_id, beats = load_declaration(settings_path)
        for beat in beats:
            if not isinstance(beat, dict):
                continue
            tools = beat.get("tools")
            if not isinstance(tools, list) or not tools:
                tools = list(EDIT_TOOLS)
            if tool_name not in tools:
                continue

            beat_id = beat.get("id") or "unnamed beat"
            reason = beat.get("reason") or "this beat has not run yet"

            if tool_name in EDIT_TOOLS:
                patterns = beat.get("paths")
                if not isinstance(patterns, list) or not patterns:
                    continue  # this beat does not gate file edits
                targets = edit_targets(cwd, tool_input)
                if not targets:
                    # Fail closed. An edit whose targets cannot be determined
                    # cannot be checked against this beat, and allowing it would
                    # be a silent bypass of a gate the repository opted into.
                    deny(
                        f"takt: beat '{beat_id}' gates {tool_name}, but the payload "
                        f"carried no determinable file path, so the beat could not be "
                        f"evaluated. Refusing rather than allowing an unchecked edit. "
                        f"{ESCAPE_HATCH}"
                    )
                target = first_match(targets, patterns)
            elif tool_name in DISPATCH_TOOLS:
                patterns = beat.get("skills")
                if not isinstance(patterns, list) or not patterns:
                    continue  # this beat does not gate dispatches
                name = dispatch_target(tool_input)
                if not name:
                    # Same rule as the edit side: a dispatch that cannot be
                    # identified cannot be checked against a beat that gates it.
                    deny(
                        f"takt: beat '{beat_id}' gates {tool_name}, but the payload "
                        f"carried no determinable skill or agent name, so the beat "
                        f"could not be evaluated. Refusing rather than allowing an "
                        f"unchecked dispatch. {ESCAPE_HATCH}"
                    )
                target = first_match([name], patterns)
            else:
                continue

            if target is None:
                continue

            marker = beat.get("require")
            if not isinstance(marker, str) or not marker:
                continue
            marker_path = marker_path_for(cwd, run_id, marker)
            # requireKind: what SHAPE satisfies this beat.
            #
            # Default "any" is os.path.exists, byte-identical to every
            # declaration written before this field existed. "file" exists
            # because a beat can now gate on a real produced ARTIFACT rather
            # than an empty marker, and `mkdir MODERNIZATION_BRIEF.md` would
            # otherwise open that gate -- a one-command bypass nobody would
            # think to look for. cupertino's equivalent gate already uses
            # isfile; this lets a declaration say which it means.
            require_kind = beat.get("requireKind") or "any"
            if require_kind not in ("file", "dir", "any"):
                raise ValueError(
                    f"requireKind {require_kind!r} must be 'file', 'dir' or 'any'"
                )
            probe = Path(marker_path)
            if require_kind == "file":
                satisfied = probe.is_file()
            elif require_kind == "dir":
                satisfied = probe.is_dir()
            else:
                satisfied = probe.exists()
            if satisfied:
                continue

            shape = "" if require_kind == "any" else f" as a {require_kind}"
            deny(
                f"takt: '{target}' runs ahead of beat '{beat_id}'. {reason} "
                f"Required marker '{marker}' does not exist{shape}. {ESCAPE_HATCH}"
            )
    except SystemExit:
        raise
    except Exception as exc:  # fail-closed, per the module docstring
        deny(
            f"takt: beat declaration could not be evaluated "
            f"({type(exc).__name__}: {exc}). Refusing rather than allowing an "
            f"unchecked call. {ESCAPE_HATCH}"
        )

    allow()


if __name__ == "__main__":
    main()
