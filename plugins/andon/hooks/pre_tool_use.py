#!/usr/bin/env python3
"""
andon PreToolUse hook.

Enforces, independent of model cooperation, the subset of andon rules that
must hold even if the model ignores every instruction in the skills:

  1. Disabled-plugin halt   (settings-read-honored)
  2. Write-scope            (write-scope-enforced-before-dispatch)
  3. log.md append-only     (log-entries-append-only)
  4. Gap-closure gating     (andon-rule conditions 1 & 3: no closing a gap
                             whose evidence is red or a non-overridable Tier 1
                             contradiction)

INERT BY DEFAULT: if this repo has no analysis/andon (or configured
output_dir) directory yet, the hook exits 0 (allow) without inspecting
anything further -- it only starts policing once the repo actually has an
andon ledger. This prevents it from interfering with unrelated repositories
or with the very first andon-preflight run (which only tests writability of
a *parent* directory, never creates the ledger itself).

Fails CLOSED on any internal error (deny), and always names the escape
hatch: set enabled: false in .claude/andon.local.md, or remove the ledger
directory, to stop this hook from evaluating future tool calls.
"""

import json
import os
import re
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.dirname(_HOOK_DIR))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "scripts"))

ESCAPE_HATCH = (
    "Escape hatch: set 'enabled: false' in .claude/andon.local.md, or delete "
    "the ledger directory, to stop this hook from evaluating andon writes."
)


def deny(reason):
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.stdout.write("\n")
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def allow():
    sys.exit(0)


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        # Can't parse the hook payload at all -- fail closed rather than guess.
        deny(f"andon hook: could not parse PreToolUse payload; failing closed. {ESCAPE_HATCH}")
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()

    if tool_name not in ("Write", "Edit"):
        allow()
        return

    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path:
        allow()
        return

    try:
        import andon_core as core
    except Exception as e:
        deny(f"andon hook: failed to import enforcement library ({e}); failing closed. {ESCAPE_HATCH}")
        return

    try:
        settings = core.load_settings(cwd)
        output_dir_abs = os.path.realpath(os.path.join(cwd, settings["output_dir"]))
        ledger_dir_abs = os.path.realpath(os.path.join(cwd, settings["ledger_dir"]))

        # INERT GUARD: only police repos that already use andon.
        if not os.path.isdir(output_dir_abs) and not os.path.isdir(ledger_dir_abs):
            allow()
            return

        # Check the RAW (unresolved) path for a traversal attempt BEFORE
        # realpath collapses it -- otherwise "analysis/andon/ledger/../../../etc/passwd"
        # resolves to a target outside both dirs and would look "unrelated to
        # andon", silently defeating the write-scope guard it was meant to hit.
        norm_raw = file_path.replace(os.sep, "/")
        mentions_andon_dir = (
            settings["output_dir"] in norm_raw or settings["ledger_dir"] in norm_raw
        )
        has_traversal_segment = ".." in norm_raw.split("/")
        if mentions_andon_dir and (has_traversal_segment or os.path.isabs(file_path)):
            deny(
                f"andon hook: write-scope violation -- {file_path!r} names an andon "
                f"directory but contains a path-traversal or absolute-path escape. {ESCAPE_HATCH}"
            )
            return

        target_abs = os.path.realpath(file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path))
        under_output = _is_under(target_abs, output_dir_abs)
        under_ledger = _is_under(target_abs, ledger_dir_abs)

        if not (under_output or under_ledger):
            # This tool call has nothing to do with andon's own artifacts.
            allow()
            return

        # --- Guard 1: disabled-plugin halt --------------------------------
        if settings.get("enabled", True) is False:
            deny(
                "andon hook: .claude/andon.local.md has enabled: false. Refusing "
                f"to write to andon-managed path {file_path!r} while disabled. {ESCAPE_HATCH}"
            )
            return

        # --- Guard 2: write-scope (path traversal / absolute / outside) --
        # file_path is relative to the payload's declared `cwd`, which may
        # differ from this hook process's own OS cwd -- never call
        # os.path.relpath(file_path, cwd) here, since relpath resolves a
        # relative first argument against the real process cwd, not `cwd`.
        rel_to_ledger = file_path if not os.path.isabs(file_path) else os.path.relpath(target_abs, cwd)
        try:
            allowed_dir = settings["ledger_dir"] if under_ledger else settings["output_dir"]
            core.validate_write_path(rel_to_ledger, cwd, allowed_dir)
        except core.AndonError as e:
            deny(f"andon hook: write-scope violation -- {e.message} {ESCAPE_HATCH}")
            return
        except Exception:
            # Absolute path case: validate_write_path always rejects absolute
            # raw paths by design, which is correct here too.
            deny(
                f"andon hook: refusing Write/Edit to {file_path!r} -- absolute "
                f"paths into the andon ledger are never permitted. {ESCAPE_HATCH}"
            )
            return

        log_path = os.path.join(ledger_dir_abs, "log.md")
        if target_abs == os.path.realpath(log_path):
            # --- Guard 3: log.md append-only ------------------------------
            if tool_name == "Write":
                if os.path.isfile(log_path):
                    deny(
                        "andon hook: log.md already exists; the Write tool would "
                        "overwrite/truncate it. log.md is append-only -- use the "
                        "append-log subcommand of andon_core.py (opens in 'a' mode) "
                        f"instead. {ESCAPE_HATCH}"
                    )
                    return
            elif tool_name == "Edit":
                deny(
                    "andon hook: log.md is append-only and must never be edited "
                    "in place (that could rewrite history). Use the append-log "
                    f"subcommand of andon_core.py instead. {ESCAPE_HATCH}"
                )
                return

        # --- Guard 4: gap-closure gating (andon rule conditions 1 & 3) ----
        if under_ledger and re.search(r"/gaps/[^/]+\.md$", target_abs.replace(os.sep, "/")):
            new_content = tool_input.get("content")
            if new_content is None and tool_name == "Edit":
                new_content = tool_input.get("new_string", "")
            if new_content:
                violation = _check_gap_closure(core, new_content, ledger_dir_abs)
                if violation:
                    deny(f"andon hook: {violation} {ESCAPE_HATCH}")
                    return

        allow()
    except SystemExit:
        raise
    except Exception as e:
        # Fail CLOSED on any unexpected internal error.
        deny(f"andon hook: internal error ({e}); failing closed rather than silently allowing. {ESCAPE_HATCH}")


def _is_under(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _check_gap_closure(core, new_content, ledger_dir_abs):
    fields, _body = core.parse_frontmatter(new_content)
    if fields.get("type") != "gap":
        return None
    if fields.get("status") != "closed":
        return None
    resolved_by = fields.get("resolved_by")
    if not resolved_by:
        return (
            "refusing to write gap doc with status:closed and no 'resolved_by' "
            "evidence link (andon rule condition 1: red/unproven wires cannot advance)."
        )
    slug = re.sub(r"^\[\[|\]\]$", "", str(resolved_by)).split("/")[-1]
    evidence_path = os.path.join(ledger_dir_abs, "evidence", slug + ".md")
    if not os.path.isfile(evidence_path):
        return f"refusing to close gap: linked evidence doc {resolved_by!r} does not exist yet."
    with open(evidence_path, "r", encoding="utf-8") as fh:
        ev_fields, _ = core.parse_frontmatter(fh.read())
    if ev_fields.get("tier") == 1 and ev_fields.get("non_overridable") is True:
        return (
            f"refusing to close gap: linked evidence {resolved_by!r} carries a "
            "Tier 1 non-overridable structural contradiction (andon rule condition 3 "
            "-- never waivable, by anyone, under any circumstance)."
        )
    if ev_fields.get("verdict") != "green":
        return (
            f"refusing to close gap: linked evidence {resolved_by!r} has verdict "
            f"{ev_fields.get('verdict')!r}, not 'green' (andon rule condition 1 -- "
            "a red or unknown wire cannot be advanced past)."
        )
    return None


if __name__ == "__main__":
    main()
