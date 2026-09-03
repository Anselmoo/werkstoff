#!/usr/bin/env python3
"""PreToolUse hook: deny a write that violates a blocking rule, or that runs
ahead of the unit it depends on.

WHY A HOOK AND NOT A SKILL. This repository measured the enforcement ladder
over ~40 runs, asking "does the guard RUN", not "does it exist":

    prose in a SKILL.md ................. baseline
    a fenced `python3 ...` in a skill ... 1 run in 3
    a guard inside a Workflow script .... workflow dispatched 1 run in 14
    PreToolUse hook, type: "command" .... blocks, first attempt

The complaint that started this plugin -- "superpowers is too loose and easily
creates antipatterns" -- is a statement about that ladder. superpowers ships 14
skills and one SessionStart hook, so all of its discipline sits on the top row.
Everything lehre must hold regardless of model cooperation lives here instead.

TWO GATES, ONE HOOK.
  1. ORDER. A write into unit U is denied while any unit U depends on has not
     been VALIDATED. The done-marker is written by lehre-validate, never by
     lehre-conform -- so "done" means checked, not merely typed.
  2. RULES. A write whose resulting content violates a `severity: blocking`,
     hook-tier rule is denied, quoting the rule's own rationale.

CONTRACT (Claude Code PreToolUse):
  - stdin: JSON with at least {"cwd", "tool_name", "tool_input"}
  - ALLOW: exit 0
  - DENY:  exit 2, reason on stderr, AND stdout JSON of exactly
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
         "permissionDecision": "deny", "permissionDecisionReason": "<why>"}}
    BOTH are required. Omitting hookSpecificOutput.hookEventName, or using
    "systemMessage" in place of "permissionDecisionReason", makes the runtime
    discard the decision -- the hook runs, is ignored, and reports nothing.
    That exact mistake has shipped in this plugin family before; it is the
    fifth row of CLAUDE.md's silent-defect table. `test/plugins/
    verify-hooks-deny.py` is what catches it, so run that after touching this.

INERTNESS. A repository with no `.lehre/ruleset.json` is allowed immediately,
before the payload is even inspected. A hook that denied everywhere would
police every unrelated repository on the machine, and `verify-hooks-deny.py`
checks that inverse case as carefully as it checks the deny.

FAIL-CLOSED. Once that file is confirmed present the repository has opted in,
so any internal error denies rather than silently allowing, with the escape
hatch named in the message.

WHAT THIS HOOK DELIBERATELY DOES NOT GATE. `Bash`. A shell redirection
(`cat > src/api/x.py`) writes a file without ever reaching Write/Edit, and a
check that tried to parse arbitrary shell for redirections would be a regex
over an unbounded grammar -- precisely the silently-wrong construct this repo
has been burned by six times. That bypass is real and is covered one layer
down instead: `lehre-gauge` sweeps the tree as it actually is, and `lehre-pin`
emits a CI check that runs with no agent in the loop. Stated here rather than
left for someone to discover.
"""

from __future__ import annotations

import json
import os
import sys
from typing import NoReturn

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

RULESET = os.path.join(".lehre", "ruleset.json")
ESCAPE_HATCH = (
    "set LEHRE_DISABLE_GUARD=1 to bypass this guard for one session, run "
    "lehre-validate to close the unit this depends on, amend the rule with "
    "lehre-codify, or remove .lehre/ruleset.json if this repository no longer "
    "declares a doctrine"
)
EDIT_TOOLS = ("Write", "Edit", "MultiEdit")

#: The guard's own control plane. Gate 0 protects these from the agent the rest
#: of the guard constrains; see the Gate 0 comment in main() for why.
UNITS_DIR = os.path.join(".lehre", "units")


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


def edit_targets(core, cwd: str, tool_input: dict) -> list:
    """Every file path this payload names, repo-relative.

    A MultiEdit payload does not reliably carry a single top-level `file_path`,
    so every shape is collected. `isinstance(..., list)` rather than a
    truthiness test: iterating a STRING yields characters, each a non-empty
    str, which would fill the list with junk that matches no glob AND make it
    non-empty, so the caller's fail-closed branch would never fire. A malformed
    payload must look empty here, not look full.
    """
    found = []
    single = tool_input.get("file_path")
    if isinstance(single, str) and single:
        found.append(single)
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
    seen, out = set(), []
    for path in found:
        rel = core.relative(cwd, path)
        if rel and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def core_relative(cwd: str, path: str) -> str:
    """Thin indirection so `resulting_content` can normalise a path without
    taking the whole core module as a parameter."""
    import lehre_core
    return lehre_core.relative(cwd, path)


def ruleset_weakenings(core, current: dict, proposed_text: str) -> str:
    """Return a human-readable reason the proposed ruleset is WEAKER, or "".

    Weaker means exactly two things, both decided by set comparison over parsed
    JSON -- no regex, consistent with the evaluator's stance:

      * a rule that currently denies writes no longer does (its id is gone, or
        its severity dropped out of `blocking`, or its check kind moved off the
        hook tier)
      * a unit dependency edge disappeared, which would unblock a build order
        the repository declared

    Everything else passes untouched: adding rules, raising a severity,
    extending a `forbid` list, editing prose fields, reordering.

    A proposed file that will not parse or will not validate is treated as a
    weakening, not as an error to pass through -- an unusable ruleset makes the
    hook fail closed on every later write, which is a denial-of-service on the
    repository's own doctrine rather than an honest tightening.
    """
    try:
        proposed = core.validate_ruleset(json.loads(proposed_text))
    except Exception as exc:  # noqa: BLE001 -- any unusable result is a weakening
        return f"The proposed doctrine is not a usable ruleset ({type(exc).__name__}: {exc})."

    def denying_ids(data: dict) -> set:
        return {r["id"] for r in data.get("rules", [])
                if r.get("severity") == "blocking" and r.get("enforcement") == "hook"}

    lost_rules = denying_ids(current) - denying_ids(proposed)
    if lost_rules:
        return (f"{len(lost_rules)} rule(s) would stop denying writes: "
                f"{sorted(lost_rules)}.")

    current_edges = {(u["id"], dep) for u in current.get("units", [])
                     for dep in u.get("depends_on", [])}
    proposed_edges = {(u["id"], dep) for u in proposed.get("units", [])
                      for dep in u.get("depends_on", [])}
    lost_edges = current_edges - proposed_edges
    if lost_edges:
        return (f"{len(lost_edges)} build-order dependency edge(s) would disappear: "
                f"{sorted(lost_edges)}.")
    return ""


class ContentUnknown(Exception):
    """The post-write content of a file could not be reconstructed."""


def resulting_content(cwd: str, tool_name: str, tool_input: dict, rel_path: str) -> str:
    """What the file will contain AFTER this call, reconstructed exactly.

    Not approximated from the fragment being inserted: a layering rule asks
    what the whole module imports, and judging only `new_string` would miss a
    forbidden import already present and would misjudge one being removed.
    """
    if tool_name == "Write":
        content = tool_input.get("content")
        if isinstance(content, str):
            return content
        raise ContentUnknown("Write payload carried no string content")

    abs_path = os.path.join(cwd, rel_path)
    try:
        with open(abs_path, "r", encoding="utf-8") as handle:
            current = handle.read()
    except OSError as exc:
        raise ContentUnknown(f"cannot read {rel_path}: {exc}") from exc

    pending = []
    if tool_name == "Edit":
        pending.append(tool_input)
    else:
        entries = tool_input.get("edits")
        if not isinstance(entries, list):
            raise ContentUnknown("MultiEdit payload carried no edits list")
        pending = [e for e in entries if isinstance(e, dict)]

    for entry in pending:
        # A MultiEdit may name several files; apply only the edits aimed at the
        # file currently being judged. Compared on the repo-relative form, since
        # the payload may carry either absolute or relative paths.
        entry_path = entry.get("file_path")
        if isinstance(entry_path, str) and entry_path:
            if core_relative(cwd, entry_path) != rel_path:
                continue
        old = entry.get("old_string")
        new = entry.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str):
            raise ContentUnknown("edit carried non-string old_string/new_string")
        if old == "":
            raise ContentUnknown("edit carried an empty old_string")
        if old not in current:
            raise ContentUnknown("old_string does not occur in the file on disk")
        current = current.replace(old, new) if entry.get("replace_all") else current.replace(old, new, 1)
    return current


def main() -> NoReturn:
    if os.environ.get("LEHRE_DISABLE_GUARD") == "1":
        allow()

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        allow()  # never police a payload this hook cannot read

    cwd = event.get("cwd") or os.getcwd()
    ruleset_path = os.path.join(cwd, RULESET)
    if not os.path.isfile(ruleset_path):
        allow()  # inert: this repository has not declared a doctrine

    try:
        import lehre_core as core
    except Exception as exc:  # noqa: BLE001 -- opted-in repo, so this must deny
        deny(f"lehre: guard could not load its evaluator ({type(exc).__name__}: {exc}). "
             f"Refusing rather than allowing an unchecked write. {ESCAPE_HATCH}")

    try:
        tool_name = event.get("tool_name") or ""
        if tool_name not in EDIT_TOOLS:
            allow()
        tool_input = event.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        ruleset = core.load_ruleset(ruleset_path)
        units = ruleset.get("units", [])
        blocking = [r for r in ruleset["rules"]
                    if r["severity"] == "blocking" and r["enforcement"] == "hook"]

        targets = edit_targets(core, cwd, tool_input)
        if not targets:
            # Fail closed. An edit whose targets cannot be determined cannot be
            # checked against a doctrine the repository opted into, and allowing
            # it is exactly the silent bypass this hook exists to prevent.
            deny(f"lehre: {tool_name} carried no determinable file path, so neither the "
                 f"unit order nor any blocking rule could be evaluated. Refusing rather "
                 f"than allowing an unchecked write. {ESCAPE_HATCH}")

        # --- Gate 0: the guard's own control plane ------------------------
        #
        # Gates 1 and 2 both read state the agent could otherwise write. A model
        # that hits the order gate can create the done-marker itself; a model
        # that hits the rule gate can set "rules": [] and every later write
        # passes. Neither is caught downstream, because lehre-pin's CI runs the
        # gauge against whatever ruleset is on disk -- a gutted one exits 0 and
        # CI is green.
        #
        # "Only lehre-validate writes the marker" was prose, which this repo
        # measures at the bottom of the enforcement ladder, guarding the file
        # the top of the ladder depends on.
        #
        # Neither clause costs a legitimate author anything: `lehre_cli.py close`
        # writes the marker through Bash, and this hook does not match Bash.
        for rel_path in targets:
            if rel_path.startswith(UNITS_DIR + "/") or rel_path == UNITS_DIR:
                # Deliberately does NOT name the path, the unit, or the marker
                # convention. The Gate 1 message used to end with "it writes
                # .lehre/units/<unit>.done", which told a blocked model exactly
                # what to forge; a denial should not be a set of instructions.
                deny(
                    f"lehre: refusing to write unit-validation state directly. That state "
                    f"records that a unit's rules and seams were CHECKED, so writing it by "
                    f"hand would assert a check that never ran. Run lehre-validate on the "
                    f"unit instead -- it writes this itself once the unit actually passes. "
                    f"{ESCAPE_HATCH}"
                )
            if rel_path == RULESET:
                try:
                    proposed_text = resulting_content(cwd, tool_name, tool_input, rel_path)
                except ContentUnknown as exc:
                    deny(f"lehre: the doctrine file is being edited but its resulting content "
                         f"could not be reconstructed ({exc}), so this change could not be "
                         f"checked for weakening. {ESCAPE_HATCH}")
                weakening = ruleset_weakenings(core, ruleset, proposed_text)
                if weakening:
                    deny(
                        f"lehre: refusing to weaken the doctrine from inside a run it governs. "
                        f"{weakening} Tightening is allowed and needs no bypass -- adding a rule, "
                        f"raising a severity, or extending a forbid list all pass this gate. "
                        f"Removing enforcement is a decision for lehre-codify with a human in "
                        f"the loop. {ESCAPE_HATCH}"
                    )

        # --- Gate 1: unit order -------------------------------------------
        for rel_path in targets:
            unit = core.unit_for(rel_path, units)
            if unit is None:
                continue
            pending = core.blocking_dependencies(cwd, unit)
            if pending:
                deny(
                    f"lehre: '{rel_path}' belongs to unit '{unit['id']}', which depends on "
                    f"{pending} -- and {'none of those have' if len(pending) > 1 else 'that has not'} "
                    f"been validated yet. {unit.get('reason', '')} "
                    f"Build order is enforced, not advisory: run lehre-validate on "
                    f"'{pending[0]}' first. {ESCAPE_HATCH}"
                )

        # --- Gate 2: blocking rules ---------------------------------------
        for rel_path in targets:
            applicable = [r for r in blocking if core.matches(rel_path, r["check"]["paths"])]
            if not applicable:
                continue
            needs_content = [r for r in applicable
                             if r["check"]["kind"] in ("python-import", "python-construct")]
            content = None
            if needs_content:
                try:
                    content = resulting_content(cwd, tool_name, tool_input, rel_path)
                except ContentUnknown as exc:
                    deny(f"lehre: {len(needs_content)} blocking rule(s) apply to '{rel_path}' but its "
                         f"resulting content could not be reconstructed ({exc}). Refusing rather than "
                         f"allowing an unchecked write. {ESCAPE_HATCH}")
            for rule in applicable:
                try:
                    hits = core.evaluate_file(rule, rel_path, content)
                except core.UnparseablePython as exc:
                    deny(f"lehre: blocking rule '{rule['id']}' applies to '{rel_path}', but the file "
                         f"would not parse as Python after this write ({exc}), so the rule could not "
                         f"be decided. {ESCAPE_HATCH}")
                if hits:
                    first = hits[0]
                    where = f"{first.path}:{first.line}" if first.line else first.path
                    extra = f" (+{len(hits) - 1} more in this file)" if len(hits) > 1 else ""
                    deny(
                        f"lehre: blocking rule '{rule['id']}' denies this write. "
                        f"{where} {first.detail}{extra}. Why this rule exists: {first.rationale} "
                        f"Authority: {rule['authority'].get('source')}. {ESCAPE_HATCH}"
                    )
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 -- fail-closed, per the module docstring
        deny(f"lehre: doctrine could not be evaluated ({type(exc).__name__}: {exc}). "
             f"Refusing rather than allowing an unchecked write. {ESCAPE_HATCH}")

    allow()


if __name__ == "__main__":
    main()
