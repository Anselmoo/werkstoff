#!/usr/bin/env python3
"""PreToolUse hook for Bash: enforces the dependency-auditor and
assertion-auditor agents' must_refuse guarantees that no amount of prose
in an agent system prompt can fully guarantee on its own:
  - dependency-auditor "cannot use Bash to install, publish, or otherwise
    mutate packages"
  - assertion-auditor "cannot use Bash to install, uninstall, or otherwise
    write" and "cannot run mutation tool in write/patch mode"

Read-only registry lookups (rule: dependency-lookup-timeout) and read-only
mutation-tool invocations (e.g. `mutmut run --paths-to-mutate` in its
default dry/report mode) are unaffected; only commands that match a known
mutating pattern are denied.

Same fail-closed / inert-when-absent / escape-hatch contract as
guard_edit_scope.py — see that file's docstring for the full protocol
description.
"""

import json
import os
import re
import sys

DANGEROUS_PATTERNS = [
    r"\bnpm\s+(install|i|ci|publish|uninstall|remove|rm)\b",
    r"\bnpm\s+link\b",
    r"\byarn\s+(add|remove|publish)\b",
    r"\bpnpm\s+(add|remove|publish|install)\b",
    r"\bpip3?\s+install\b",
    r"\bpip3?\s+uninstall\b",
    r"\beasy_install\b",
    r"\bpoetry\s+(add|remove|publish)\b",
    r"\bcargo\s+(install|publish|uninstall|yank)\b",
    r"\bgo\s+install\b",
    r"\bgo\s+get\s+.*-u\b",
    r"\bgem\s+(install|uninstall|push)\b",
    r"\bbundle\s+(install|update)\b",
    r"\btwine\s+upload\b",
    r"\bmutmut\s+apply\b",
    r"\bcosmic-ray\s+apply\b",
    r"\b--patch\b.*\bmutmut\b",
    r"\bmutmut\b.*\b--patch\b",
]
COMPILED = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]

ESCAPE_HATCH = (
    "If this command is genuinely needed and unrelated to a confab audit, "
    "run it outside a confab-managed session, or remove analysis/confab/ from this "
    "repository to disable this guard."
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
        return deny(f"guard_bash_scope: could not parse hook input JSON ({exc}); failing closed. {ESCAPE_HATCH}")

    if event.get("tool_name") != "Bash":
        return allow()

    cwd = event.get("cwd") or os.getcwd()
    if not os.path.isdir(os.path.join(cwd, "analysis", "confab")):
        return allow()  # inert unless this repo actually uses confab

    command = (event.get("tool_input") or {}).get("command") or ""
    for pattern in COMPILED:
        if pattern.search(command):
            return deny(
                f"Refusing Bash command matching mutating pattern {pattern.pattern!r}: "
                f"{command!r}. confab's dependency-auditor and assertion-auditor agents "
                "may only perform read-only registry lookups and read-only mutation-tool "
                "runs, never install/publish/patch operations. "
                f"{ESCAPE_HATCH}"
            )

    return allow()


def main() -> int:
    try:
        return run()
    except Exception as exc:  # noqa: BLE001 - fail-closed handler, intentionally broad
        return deny(f"guard_bash_scope: internal error ({type(exc).__name__}: {exc}); failing closed. {ESCAPE_HATCH}")


if __name__ == "__main__":
    sys.exit(main())
