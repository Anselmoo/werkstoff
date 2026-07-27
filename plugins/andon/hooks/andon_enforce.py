#!/usr/bin/env python3
"""PreToolUse hook: deny a source edit while the andon ledger is in a stop state.

WHY A HOOK AND NOT A SKILL
--------------------------
Measured over ~40 runs, every in-plugin layer degrades to the same thing:

  rule as prose in a SKILL.md            the baseline this was meant to fix
  rule as Python that raises             19 rules enforced, 1 case in 5 moved
  guard behind a fenced `python3` block  invoked 1/3 of runs, not 3/3
  guard inside the Workflow script       workflow dispatched 1 of 14 runs

Each is deterministic once entered, and entering it is a sentence the model
chooses to follow. A PreToolUse hook is the only layer the runtime invokes
unconditionally, so it is the only place a rule can actually hold.

The hook must be `type: "command"`. A `type: "prompt"` hook asks a model to
decide, which puts us straight back where we started.

SAFETY: INERT UNLESS THIS REPO USES ANDON
-----------------------------------------
First action is to look for a ledger in the cwd. No ledger -> exit 0, allow,
print nothing. Without that gate this hook would police every edit in every
repository on the machine. Same state-file gate ralph-loop's stop hook uses.

READ GATING VALUES TOLERANTLY
-----------------------------
The rebuilt schema wants `status`/`kind`/`blast_radius` as frontmatter keys, but
every ledger written so far — including 101 production records in
spectrafit-core — encodes them inside `tags: ["kind:wire", "status:open"]`.
Rejecting the old shape as malformed would deny every edit in every existing
andon repo the moment this ships. So: frontmatter key first, then the tags
array, then genuinely absent.

Absent is NOT repaired. A missing blast radius is a stop, never an inferred
value — the halt must not depend on a rating nobody supplied.

FAIL CLOSED
-----------
An internal error denies, and says why, and names the escape hatch. Three
guards failed silently earlier in this work (`[^\\n]` inside a bracket
expression, `\\b` around punctuation, `[^.]` spanning a filename); each looked
present and enforced nothing. A fail-open hook is that same defect with better
manners. `enforcement: off` in `.claude/andon.local.md` turns it off explicitly.

Contract: reads hook JSON on stdin. Allow: hookSpecificOutput JSON on stdout,
exit 0. Deny: hookSpecificOutput JSON (with permissionDecisionReason) on
stdout AND the reason on stderr AND exit 2 -- both mechanisms, belt-and-
braces (see deny()).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_LEDGER_DIR = "analysis/andon/ledger"
DEFAULT_AUTHORIZATION = "local+reversible"
BLAST_RANK = {"local+reversible": 1, "hard-to-reverse": 2, "shared-state-visible": 3}
MAX_CONSECUTIVE_REOPENS = 3
NON_ADVANCING_VERDICTS = ("red", "unknown")
SETTINGS = ".claude/andon.local.md"


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

    Experimentally confirmed (tracer hooks): the runtime ignores a
    `permissionDecision: deny` whose JSON is missing `hookEventName` or that
    puts its reason in `systemMessage` instead of `permissionDecisionReason` --
    the deny is silently dropped and the edit proceeds. Two shapes were
    confirmed to actually block: (1) `exit 2` with the reason on stderr and no
    JSON at all, and (2) stdout JSON matching the exact
    hookSpecificOutput/hookEventName/permissionDecision/permissionDecisionReason
    shape. Emitting both here means a future schema drift in one mechanism
    (the JSON contract changes again, gets mistyped, etc.) still can't
    silently disarm the hook -- the exit-2-plus-stderr path holds regardless.
    """
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }))
    print(reason, file=sys.stderr)
    return 2


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict[str, str] = {}
    for line in parts[1].splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1).replace("-", "_").lower()] = m.group(2).strip().strip("\"'")
    return fm


def tag_value(fm: dict[str, str], key: str) -> str | None:
    """Read `key` from a frontmatter field, else from the `tags` array.

    Legacy records carry `tags: ["kind:wire", "status:open",
    "blast-radius:local+reversible"]`. Reading only the first shape would treat
    every existing ledger as malformed.
    """
    direct = fm.get(key.replace("-", "_"))
    if direct:
        return direct
    for tag in re.findall(r'"([^"]+)"', fm.get("tags", "")):
        if ":" in tag:
            k, v = tag.split(":", 1)
            if k.replace("-", "_").lower() == key.replace("-", "_").lower():
                return v
    return None


def settings(root: Path) -> dict[str, str]:
    p = root / SETTINGS
    return frontmatter(p.read_text(encoding="utf-8", errors="replace")) if p.is_file() else {}


def _list_md(d: Path) -> list[Path]:
    """List *.md, RAISING if the directory exists but cannot be read.

    `Path.glob` swallows PermissionError and yields nothing, so an unreadable
    ledger looked exactly like an empty one: no gaps found, no stop condition,
    edit allowed. The hook failed open while appearing to work — the same silent
    failure this whole design is built to avoid. os.listdir raises, so the
    fail-closed handler in main() can actually fire.
    """
    import os

    if not d.is_dir():
        return []
    return sorted(d / n for n in os.listdir(d) if n.endswith(".md"))


def stop_reason(ledger: Path, authorization: str) -> str | None:
    """The first stop condition that holds, or None. Contract §3 + §9.2."""
    gaps = _list_md(ledger / "gaps")
    for p in gaps:
        fm = frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        status = tag_value(fm, "status")
        if status and status.lower() not in ("open", "reopened"):
            continue  # closed gaps do not gate anything

        blast = tag_value(fm, "blast_radius") or tag_value(fm, "blast-radius")
        if not blast:
            return (f"STOP (required-field integrity, contract §9.2): gap "
                    f"'{p.name}' carries no blast-radius value, so the "
                    f"authorization ceiling has no input to check. This value is "
                    f"never inferred — a human must supply one of "
                    f"{', '.join(BLAST_RANK)}. Source edits are denied until then.")
        if blast not in BLAST_RANK:
            return (f"STOP: gap '{p.name}' has blast-radius {blast!r}, which is "
                    f"not one of {', '.join(BLAST_RANK)}.")
        if BLAST_RANK[blast] > BLAST_RANK.get(authorization, 1):
            return (f"STOP (andon rule / condition 2): gap '{p.name}' has blast "
                    f"radius {blast!r}, exceeding authorization_level "
                    f"{authorization!r}. A human must raise authorization for "
                    f"this one fix.")
        reopens = tag_value(fm, "reopen_count") or tag_value(fm, "reopen-count")
        if reopens and reopens.isdigit() and int(reopens) >= MAX_CONSECUTIVE_REOPENS:
            return (f"STOP (sub-cycle escalation): gap '{p.name}' has reopened "
                    f"{reopens} times, reaching the threshold of "
                    f"{MAX_CONSECUTIVE_REOPENS}. It is the stream's constraint "
                    f"now, not a sub-cycle — escalate rather than retry.")

    ev = _list_md(ledger / "evidence")
    for p in ev:
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = frontmatter(text)
        verdict = tag_value(fm, "verdict")
        if not verdict:
            m = re.search(r"^\s*[-*]\s*Verdict:\s*(\S+)", text, re.MULTILINE)
            verdict = m.group(1).strip("`*.,") if m else None
        if verdict and verdict.lower() in NON_ADVANCING_VERDICTS:
            return (f"STOP (andon rule / condition 1): evidence '{p.name}' "
                    f"records verdict {verdict!r}. The wire is not proven; the "
                    f"loop may not advance past it.")
    return None


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    try:
        cwd = Path(event.get("cwd") or ".").resolve()
        cfg = settings(cwd)
        if (cfg.get("enforcement") or "").lower() in ("off", "false", "disabled"):
            return allow()

        ledger = cwd / (cfg.get("ledger_dir") or DEFAULT_LEDGER_DIR)
        if not ledger.is_dir():
            return allow()          # not an andon repo — say nothing at all

        target = (event.get("tool_input") or {}).get("file_path") or ""
        if target:
            try:
                resolved = Path(target) if Path(target).is_absolute() else (cwd / target)
                resolved = resolved.resolve()
                if resolved == ledger or ledger in resolved.parents:
                    return allow()  # the loop must always be able to record its halt
            except OSError:
                pass

        reason = stop_reason(ledger, cfg.get("authorization_level") or DEFAULT_AUTHORIZATION)
        if reason:
            return deny(reason + "\n\n(andon enforcement hook. Override by setting "
                                 "`enforcement: off` in .claude/andon.local.md.)")
        return allow()
    except Exception as exc:                                    # fail CLOSED
        return deny(
            f"andon enforcement hook failed: {type(exc).__name__}: {exc}. "
            f"Denying rather than silently dropping enforcement. Set "
            f"`enforcement: off` in .claude/andon.local.md to override.")


if __name__ == "__main__":
    sys.exit(main())
