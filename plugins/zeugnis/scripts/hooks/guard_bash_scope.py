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

ARGV MATCHING, NOT RAW-STRING SEARCH (issue #73)
--------------------------------------------------
An earlier version of this hook ran its patterns with `re.search` over the
whole raw command string. That refused perfectly read-only commands that
merely *mention* an install phrase -- `grep -rn "pip install" docs/`,
`rg 'npm install' README.md`, a heredoc that quotes one as example text --
because the pattern never distinguished "this string is being executed"
from "this string is being read". This version tokenises the command with
`shlex.split` (quote-aware, so `"pip install"` stays one argument) and
matches only against argv positions, the same shape as
`plugins/nacharbeit/hooks/nacharbeit_guard.py`'s `GIT_STATE_VERBS` check
(`:58-61` at the time of writing).

Known, documented scope limits (same posture as that file's own docstring
-- "a redirect-based bypass is documented, not gated"):
  - Segments are split on `&&`, `||`, `;`, `|` only when they appear as
    their OWN token (i.e. surrounded by whitespace or otherwise not glued
    to another word by shlex's tokeniser). `cmd1;cmd2` with no surrounding
    whitespace tokenises as a single opaque word and is not split; this
    trades a rare false-negative for never having to re-implement a shell
    parser. `&` (backgrounding) and shell substitutions are out of scope.
  - argv[0] is compared by basename (`npm`, not `/usr/local/bin/npm`), so
    a fully-qualified or relative path to the same binary is still caught.

WRAPPER SKIPPING
----------------
Anchoring argv[0] fixed the false-positive (grep for "pip install"), but on
its own it introduced a false-negative the old raw-string search did not
have: the old pattern did not care what came before the tool name, so
`sudo npm install x` was still caught by substring search alone. Argv-based
matching loses that for free, because `sudo` -- an ordinary, non-adversarial
prefix a cooperative model writes all the time -- now sits at argv[0]
instead of `npm`.

`_skip_wrappers` strips, in a loop, any combination of leading `VAR=VALUE`
shell assignments and the commands named in `WRAPPER_COMMANDS` (with their
own flags) before argv[0]/argv[1] are tested, so `sudo npm install x`,
`env FOO=1 npm install x`, and `xargs npm install` are checked as `npm
install`. See `WRAPPER_COMMANDS`'s own comment for exactly what is skipped
and why each one is safe to skip (none of them change what command actually
executes). The list is deliberately short and named rather than a general
"skip anything that looks like a flag" heuristic -- a wrapper list that
grows silently, unreviewed, is exactly the "looks correct and does nothing"
failure shape CLAUDE.md's defect table warns about; anything added here
should come with a case in test_guard_bash_scope.py. The skip loop
terminates the moment argv is exhausted (`env` with nothing after it) or the
next token is not a wrapper/assignment -- it never raises and never treats
running out of tokens as a match.
"""

import json
import os
import re
import shlex
import sys

# Segment separators: shell control operators that start a new command.
# Matched as exact, standalone tokens (see module docstring's scope note).
SEGMENT_SEPARATORS = ("&&", "||", ";", "|")

# `<tool> <verb>` mutators: argv[0] (by basename) plus argv[1], both
# case-folded. This is the "clean argv form" issue #73 asks for -- these
# tools are always the command being *run*, never merely mentioned, when
# they sit at argv[0]/argv[1] of a shell segment.
TWO_TOKEN_MUTATORS: dict[str, set[str]] = {
    "npm": {"install", "i", "ci", "publish", "uninstall", "remove", "rm", "link"},
    "yarn": {"add", "remove", "publish"},
    "pnpm": {"add", "remove", "publish", "install"},
    "pip": {"install", "uninstall"},
    "pip3": {"install", "uninstall"},
    "poetry": {"add", "remove", "publish"},
    "cargo": {"install", "publish", "uninstall", "yank"},
    "gem": {"install", "uninstall", "push"},
    "bundle": {"install", "update"},
    "go": {"install"},
    "twine": {"upload"},
    "mutmut": {"apply"},
    "cosmic-ray": {"apply"},
}

# argv[0]-only mutators: the command name alone is mutating, no verb needed.
ONE_TOKEN_MUTATORS = {"easy_install"}

# Wrapper commands skipped before testing argv[0]/argv[1] (see the module
# docstring's "WRAPPER SKIPPING" section for why each is safe to skip -- none
# of them change what command actually runs, only how/as-whom it runs:
#   sudo     runs the rest as another user -- same command either way
#   env      sets environment for the rest (also covers bare VAR=VALUE
#            prefixes with no literal `env`, e.g. `FOO=1 npm install x`)
#   command  bypasses a shell function/alias of the same name as the next word
#   nohup    detaches the rest from the controlling terminal
#   nice     changes the rest's scheduling priority
#   time     times how long the rest takes to run (a bash keyword, but a real
#            /usr/bin/time binary exists and can appear in argv[0] too)
#   xargs    builds and runs a command line from its own arguments
# Deliberately short and named -- see the module docstring for why a longer,
# unreviewed list would defeat the point. Add an entry only with a matching
# case in test_guard_bash_scope.py.
WRAPPER_COMMANDS = {"sudo", "env", "command", "nohup", "nice", "time", "xargs"}

# Flags on a wrapper that consume the following token as a value, so that
# value is not mistaken for the start of the real command
# (`sudo -u root npm install x` -- `root` must be skipped along with `-u`).
WRAPPER_FLAGS_WITH_VALUE: dict[str, set[str]] = {
    "sudo": {"-u", "-g", "-h", "-p", "-r", "-t", "-C", "-U"},
    "env": {"-u", "-S"},
    "nice": {"-n"},
    "xargs": {"-I", "-n", "-P", "-d", "-a", "-s", "-E", "-L", "-l"},
}

RE_VAR_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

ESCAPE_HATCH = (
    "If this command is genuinely needed and unrelated to a zeugnis audit, "
    "set ZEUGNIS_DISABLE_GUARD=1 for this one call, run it outside a "
    "zeugnis-managed session, or remove analysis/zeugnis/ from this "
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


def _split_segments(tokens: list[str]) -> list[list[str]]:
    """Split a flat, already-quote-aware token list on control-operator
    tokens into per-command argv lists, so a pipeline or `&&` chain is
    checked command by command rather than as one blob."""
    segments: list[list[str]] = [[]]
    for tok in tokens:
        if tok in SEGMENT_SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(tok)
    return [seg for seg in segments if seg]


def _skip_wrappers(argv: list[str]) -> list[str]:
    """Strip leading `VAR=VALUE` assignments and `WRAPPER_COMMANDS` (with
    their value-taking flags) so argv[0]/argv[1] land on the command that
    actually runs, not on `sudo`/`env`/etc. See the module docstring's
    "WRAPPER SKIPPING" section.

    Terminates the moment argv runs out or the next token is neither an
    assignment nor a known wrapper -- a wrapper with nothing after it
    (`env`, bare) is simply not dangerous, and this must return an empty
    list rather than raise or loop."""
    argv = list(argv)
    while argv:
        if RE_VAR_ASSIGN.match(argv[0]):
            argv.pop(0)
            continue

        name = argv[0].rsplit("/", 1)[-1].lower()
        if name not in WRAPPER_COMMANDS:
            break
        argv.pop(0)

        value_flags = WRAPPER_FLAGS_WITH_VALUE.get(name, set())
        while argv and argv[0].startswith("-") and argv[0] != "-":
            flag = argv.pop(0)
            if flag in value_flags and argv:
                argv.pop(0)

        if name == "env":
            # `env FOO=1 BAR=2 cmd ...` -- assignments after env's own flags.
            while argv and RE_VAR_ASSIGN.match(argv[0]):
                argv.pop(0)

    return argv


def _matched_mutator(segment: list[str]) -> str | None:
    """Returns a description of the matched mutating invocation, or None."""
    argv = _skip_wrappers(segment)
    if not argv:
        return None

    argv0_raw = argv[0]
    argv0 = argv0_raw.rsplit("/", 1)[-1].lower()

    if argv0 in ONE_TOKEN_MUTATORS:
        return f"{argv0_raw} (mutating by itself)"

    rest = argv[1:]
    rest_lower = [t.lower() for t in rest]

    if len(argv) >= 2:
        argv1 = argv[1]
        verbs = TWO_TOKEN_MUTATORS.get(argv0)
        if verbs and argv1.lower() in verbs:
            return f"{argv0_raw} {argv1}"

        # `go get -u`: force-updates modules, so it is treated the same as
        # `go install`. The original pattern (`\bgo\s+get\s+.*-u\b`) allowed
        # arbitrary tokens between `get` and `-u`, so we check for `-u`
        # anywhere in the remaining argv rather than requiring adjacency.
        if argv0 == "go" and argv1.lower() == "get" and "-u" in rest_lower[1:]:
            return "go get ... -u"

    # `mutmut`/`cosmic-ray` with `--patch`: this is the one pattern with no
    # clean argv[0]/argv[1] shape. `--patch` is a flag, not a subcommand,
    # and the original pattern deliberately allowed it either side of the
    # mode verb (`mutmut --patch run` and `mutmut run --patch` both
    # matched). There is no fixed position to anchor it to, so we anchor
    # only the tool name to argv[0] (never a bare substring match anywhere
    # in the command -- that laxity is exactly what let the old guard
    # refuse a grep for the word "mutmut") and accept `--patch` anywhere
    # in the rest of that segment's argv.
    if argv0 in ("mutmut", "cosmic-ray") and "--patch" in rest_lower:
        return f"{argv0_raw} ... --patch"

    return None


def run() -> int:
    # Checked first, before anything else touches stdin or the filesystem,
    # so a stuck/wrong denial always has an escape that costs nothing.
    if os.environ.get("ZEUGNIS_DISABLE_GUARD") == "1":
        return allow()

    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        return deny(f"guard_bash_scope: could not parse hook input JSON ({exc}); failing closed. {ESCAPE_HATCH}")

    if event.get("tool_name") != "Bash":
        return allow()

    cwd = event.get("cwd") or os.getcwd()
    if not os.path.isdir(os.path.join(cwd, "analysis", "zeugnis")):
        return allow()  # inert unless this repo actually uses zeugnis

    command = (event.get("tool_input") or {}).get("command") or ""

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        # Unbalanced quotes: this file is fail-closed, so an unparseable
        # command is refused rather than silently let through unchecked.
        return deny(
            f"guard_bash_scope: could not tokenise Bash command ({exc}); "
            f"failing closed rather than allowing an unparsed command through. {ESCAPE_HATCH}"
        )

    for segment in _split_segments(tokens):
        matched = _matched_mutator(segment)
        if matched:
            return deny(
                f"Refusing Bash command: segment {segment!r} matches mutating invocation "
                f"{matched!r} (matched by argv position, not a raw-string search of the "
                f"whole command): {command!r}. zeugnis's dependency-auditor and "
                "assertion-auditor agents may only perform read-only registry lookups and "
                "read-only mutation-tool runs, never install/publish/patch operations. "
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
