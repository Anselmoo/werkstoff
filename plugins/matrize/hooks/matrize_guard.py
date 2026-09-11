#!/usr/bin/env python3
"""matrize PreToolUse guard — the two refusals that cannot be left to prose.

Why a hook at all
-----------------
Measured over ~40 runs in this workshop, asking "does the guard *run*" rather than
"does it exist": prose in a SKILL.md is the baseline, a fenced command in a skill runs
about 1 run in 3, a guard inside a Workflow script gets dispatched about 1 run in 14,
and a PreToolUse `type: "command"` hook blocks on the first attempt. So the two rules
that must hold regardless of model cooperation live here and nowhere else.

What it denies — exactly three things
-------------------------------------
1. Any write or edit under ``<root>/references/``. Invariant I1: references are
   read-only. This is how the copyright boundary is carried mechanically instead of by
   good intentions — values and rules may be extracted from a reference, assets may
   never be copied, and a reference whose rights grade is R2 or R3 must not be edited
   into a derivative in place.
2. Any write to ``<root>/system/tokens.json`` or under ``<root>/out/`` while a
   ``spread`` choice record is unanswered. An n-proposal portfolio with no forced
   choice is a procrastination machine; the choice is the point of the phase.
3. A write that introduces a **colour-only categorical encoding** into a file the project
   has explicitly declared a branded surface (``surfaces:`` in the settings file). Not a
   hue count: measured with ``scripts/cvd.py``, every categorical palette in this
   workshop is below the dichromacy separation floor *including the five-hue scale*, so
   a cap would enforce a safety claim the numbers do not support. What does carry it is
   "colour is never the only channel", and that is decidable.

   Scope, stated rather than implied: a ``Write`` carries the whole file, so the full
   check runs. An ``Edit`` carries a fragment with no use sites in it, so only the
   self-contained palette-index pattern is checked there. Undecidable content is ALLOWED
   — a detector that guesses costs more than one that abstains, and that is different
   from the fail-closed behaviour on an internal error.

It denies nothing else, deliberately. A guard that policed every write outside the
design root would police an unrelated repository the moment the plugin was installed.

Inertness
---------
Inert unless the configured design root is a real directory in the event's cwd. Root
comes from ``.claude/matrize.local.md`` frontmatter (``root:``), defaulting to
``.design``. The same file carries ``enforcement: off``.

Escape hatch
------------
``MATRIZE_DISABLE_GUARD=1``, named in every deny message. The guard fails CLOSED: an
unexpected exception denies rather than silently dropping enforcement.

Usage:
    matrize_guard.py            # reads one PreToolUse event as JSON on stdin
Exit: 0 allow, 2 deny (the reason is on stderr and in the stdout JSON).
Calibration: python3 plugins/matrize/hooks/test_matrize_guard.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SETTINGS = ".claude/matrize.local.md"
# Surfaces the project has declared branded. Inert unless the setting names some: this
# guard never sweeps a repository it was not pointed at.
SURFACES_KEY = "surfaces"
DEFAULT_ROOT = ".design"
ESCAPE = "MATRIZE_DISABLE_GUARD=1"
CHOICE_RECORD = "system/spread-choice.json"

# Tool inputs that name a path, across the Write/Edit/MultiEdit family. A MultiEdit
# payload does NOT necessarily repeat its path at the top level -- it can carry them in
# `edits[].file_path` or a `file_paths` list. A guard that reads only `file_path` finds
# no target on such a payload and returns allow, which is a silent bypass of exactly the
# shape this repo keeps getting burned by: the code looks correct and does nothing.
PATH_KEYS = ("file_path", "path", "notebook_path")
LIST_KEYS = ("file_paths", "paths")
NESTED_KEYS = ("edits", "files")


def allow(message: str | None = None) -> int:
    out: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    if message:
        out["systemMessage"] = message
    print(json.dumps(out))
    return 0


def deny(reason: str) -> int:
    """Deny via BOTH mechanisms the runtime actually honors.

    Confirmed in this repo against andon's tracer-hook finding: the runtime silently
    DROPS a `permissionDecision: deny` whose JSON omits `hookEventName`, or that puts
    its reason in `systemMessage` rather than `permissionDecisionReason` — the hook
    runs, is ignored, and the edit proceeds. Two shapes were confirmed to block:
    `exit 2` with the reason on stderr, and the exact four-key hookSpecificOutput
    shape below. Emitting both means a future schema drift in either one cannot
    silently disarm the guard.
    """
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
            }
        )
    )
    print(reason, file=sys.stderr)
    return 2


def frontmatter(text: str) -> dict[str, str]:
    """Parse the leading `---` block into flat key/value pairs.

    Deliberately not a YAML parser: this file is ours, one level deep, and pulling in
    PyYAML would make the hook fail closed on any machine that lacks it.
    """
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out: dict[str, str] = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def settings(cwd: Path) -> dict[str, str]:
    path = cwd / SETTINGS
    try:
        if path.is_file():
            return frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        # An unreadable settings file must not be read as "no settings" — that would
        # silently drop an `enforcement: off` the user set. Fall through to the
        # caller's fail-closed path instead.
        raise
    return {}


def raw_targets(tool_input: dict) -> list[str]:
    """Every path a Write/Edit/MultiEdit payload might name.

    Scalar keys, list-of-string keys, and lists of edit objects each carrying their own
    path. Any one of them landing inside a guarded directory is enough to deny: a
    MultiEdit that touches one reference and nine legitimate files is still an edit to a
    reference.
    """
    found: list[str] = []
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            found.append(value)
    for key in LIST_KEYS:
        for value in tool_input.get(key) or []:
            if isinstance(value, str) and value:
                found.append(value)
    for key in NESTED_KEYS:
        for item in tool_input.get(key) or []:
            if isinstance(item, str) and item:
                found.append(item)
            elif isinstance(item, dict):
                for inner in PATH_KEYS:
                    value = item.get(inner)
                    if isinstance(value, str) and value:
                        found.append(value)
    return found


def resolve_target(cwd: Path, raw: str) -> Path | None:
    if not raw:
        return None
    try:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = cwd / candidate
        return candidate.resolve()
    except OSError:
        return None


def under(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def choice_is_open(root: Path) -> str | None:
    """Return the unanswered spread id, or None.

    A record whose `chosen` is absent, null or empty is unanswered. A record that
    cannot be parsed is treated as unanswered on purpose: the gate exists to stop an
    emit that outran its decision, and a corrupt record is not evidence a decision
    was made.
    """
    record = root / CHOICE_RECORD
    if not record.is_file():
        return None
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "(unreadable spread-choice.json)"
    if isinstance(data, dict) and str(data.get("chosen") or "").strip():
        return None
    spread_id = ""
    if isinstance(data, dict):
        spread_id = str(data.get("id") or "").strip()
    return spread_id or "(unnamed spread)"


def glob_match(path: str, pattern: str) -> bool:
    """Glob with a real `**`, because `fnmatch` does not have one.

    `fnmatch` maps every `*` to `.*`, so `docs/**/*.html` demands an intermediate
    directory and silently fails to match `docs/chart.html` — the pattern a person would
    naturally write, missing the file they meant. A guard whose scope pattern quietly
    matches nothing enforces nothing.

    `**` spans any number of segments including none; `*` and `?` stay within one.
    """
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.fullmatch("".join(out), path) is not None


def colour_only_sites(blob: str, whole_file: bool) -> list[str]:
    """Colour-only categorical sites in this payload, or [] when undecidable.

    A Write carries the whole file, so use sites are visible and the full check runs. An
    Edit carries a fragment: use sites are not in it, so only the self-contained
    palette-index pattern is decidable and the rule-based check is skipped rather than
    guessed at.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import redundancy
    except Exception:
        return []          # the detector is unavailable; this rule simply does not apply
    sites = redundancy.audit(blob) if whole_file else redundancy.find_palette_indexing(blob)
    if not whole_file:
        for s in sites:
            ok, _ = redundancy.redundancy_near(blob, s.line)
            s.verdict = "redundant" if ok else "COLOUR-ONLY"
    return [f"line {s.line}: {s.detail}" for s in sites if s.verdict == "COLOUR-ONLY"]


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    try:
        if os.environ.get("MATRIZE_DISABLE_GUARD") == "1":
            return allow()

        cwd = Path(event.get("cwd") or ".").resolve()
        cfg = settings(cwd)
        if (cfg.get("enforcement") or "").lower() in ("off", "false", "disabled"):
            return allow()

        root = (cwd / (cfg.get("root") or DEFAULT_ROOT)).resolve()
        if not root.is_dir():
            return allow()  # not a matrize project — say nothing at all

        tool_input = event.get("tool_input") or {}
        targets = [t for t in (resolve_target(cwd, r) for r in raw_targets(tool_input)) if t]
        if not targets:
            return allow()

        references = root / "references"
        hit = next((t for t in targets if under(t, references)), None)
        if hit is not None:
            target = hit
            return deny(
                f"matrize: {target} is inside the reference store, which is read-only.\n\n"
                "Invariant I1 — references are never written to or edited. Values and "
                "rules may be extracted from a reference; its assets and prose may not "
                "be copied or rewritten in place. Record what you measured as a Design "
                f"Card under {root / 'system'} instead.\n\n"
                f"(matrize guard. Override with {ESCAPE}, or `enforcement: off` in "
                f"{SETTINGS}.)"
            )

        tokens = root / "system" / "tokens.json"
        out_dir = root / "out"
        gated = next((t for t in targets if t == tokens or under(t, out_dir)), None)
        if gated is not None:
            target = gated
            pending = choice_is_open(root)
            if pending:
                return deny(
                    f"matrize: spread {pending} has no recorded choice, so {target} "
                    "may not be written yet.\n\n"
                    "A portfolio of n proposals with no forced choice is a "
                    "procrastination machine — the choice is the phase's whole "
                    f"output. Record it in {root / CHOICE_RECORD} as "
                    '`{"chosen": "<proposal-id>"}` together with what is deliberately '
                    "NOT adopted and why, then emit.\n\n"
                    f"(matrize guard. Override with {ESCAPE}, or `enforcement: off` in "
                    f"{SETTINGS}.)"
                )

        # --- rule 3: colour is never the only channel, on a declared surface ----------
        declared = [g.strip() for g in (cfg.get(SURFACES_KEY) or "").split(",") if g.strip()]
        if declared:
            rel = None
            for t in targets:
                try:
                    rel = str(t.relative_to(cwd))
                except ValueError:
                    continue
                if any(glob_match(rel, g) for g in declared):
                    break
                rel = None
            if rel is not None:
                content = tool_input.get("content")
                fragment = tool_input.get("new_string")
                blob, whole = (content, True) if isinstance(content, str) else (fragment, False)
                if isinstance(blob, str) and blob.strip():
                    findings = colour_only_sites(blob, whole)
                    if findings:
                        return deny(
                            f"matrize: {rel} is a declared branded surface, and this write "
                            f"introduces a categorical encoding carried by colour alone.\n\n"
                            + "\n".join(f"  - {f}" for f in findings)
                            + "\n\nEvery categorical palette in this repository is below the "
                            "dichromacy separation floor — the five-hue scale included, at "
                            "dE00 5.70 deuteranopia — so a reader cannot invert colour back "
                            "to a category. Add a second channel where the category is "
                            "RENDERED: a label, a glyph, a dash pattern, a shape. A legend "
                            "elsewhere maps name to hue and cannot be read backwards.\n\n"
                            f"(matrize guard. Override with {ESCAPE}, or `enforcement: off` "
                            f"in {SETTINGS}.)"
                        )

        return allow()
    except Exception as exc:  # fail CLOSED
        return deny(
            f"matrize guard failed: {type(exc).__name__}: {exc}. Denying rather than "
            f"silently dropping enforcement. Set {ESCAPE} or `enforcement: off` in "
            f"{SETTINGS} to override."
        )


if __name__ == "__main__":
    sys.exit(main())
