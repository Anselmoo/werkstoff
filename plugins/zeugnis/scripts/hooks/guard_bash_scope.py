#!/usr/bin/env python3
"""PreToolUse hook for Bash: enforces the dependency-auditor and
assertion-auditor agents' must_refuse guarantees that no amount of prose
in an agent system prompt can fully guarantee on its own:
  - dependency-auditor "cannot use Bash to install, publish, or otherwise
    mutate packages"
  - assertion-auditor "cannot use Bash to install, uninstall, or otherwise
    write" and "cannot run mutation tool in write/patch mode"

Read-only registry lookups (rule: dependency-lookup-timeout) are
unaffected; only commands that match a known mutating pattern are denied.

MUTATION TOOLS ARE NOT READ-ONLY (issue #142). An earlier version of this
docstring allowed `mutmut run` as a "default dry/report mode". mutmut 3 has
no such mode: `run` creates ./mutants/ in the cwd and resumes any leftover
state it finds there, and `apply` writes the mutant into the source file
itself (checked against mutmut 3.8.1). cosmic-ray's `exec` writes each
mutant to the module on disk and restores it afterwards; cargo-mutants'
`--in-place` and StrykerJS's `--inPlace` drop their default copy/sandbox.
Those invocations (COPY_ONLY_* below) are therefore allowed ONLY when the
command's effective cwd lies inside a fresh `git archive` copy that
scripts/mutation_harden.py prepared -- `lib.mutation_scope.copy_root_for`,
a lexical check, decides. Everywhere else, the working tree included, they
are denied. The effective cwd starts at the event's cwd and follows `cd`
through `&&`, `;` and newlines; after `|`, `||`, `&`, a heredoc, `pushd` or
`env -C` it is unknown, and an unknown cwd is never a copy. Heredoc body
lines are text, not commands, and are skipped (_strip_heredoc_bodies), so a
README written through `cat <<'EOF'` may mention `mutmut run`.

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

PYTHON FLOOR (#123): MIN_PYTHON, checked past the inert test. A hook runs under
whatever python3 is on PATH; one that cannot import exits 1, which Claude Code
treats as non-blocking, so it ALLOWS the call. This module therefore stays
importable on old interpreters (`from __future__ import annotations`) and denies
explicitly below the floor instead.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

# Segment separators: shell control operators that start a new command.
# Matched as exact, standalone tokens (see module docstring's scope note).
SEGMENT_SEPARATORS = ("&&", "||", ";", "|", "&")

# Separators after which a preceding `cd` still holds for the next segment.
# `a | b` and `a &` run `a` in a subshell; `cd x || b` runs b only if cd
# FAILED. After any of those the effective cwd is unknown.
CWD_PROPAGATING = ("&&", ";", "(")  # a subshell inherits its parent's cwd

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
}

# Mutation-tool invocations that write mutants to disk in the cwd: allowed
# only inside a mutation_harden copy (module docstring). Verb sets are the
# first non-flag token after the tool; flags are matched anywhere after it.
COPY_ONLY_VERBS: dict[str, set[str]] = {
    "mutmut": {"run", "apply", "browse"},  # browse binds `a` to "Apply mutant to disk"
    "cosmic-ray": {"exec", "apply"},
}
COPY_ONLY_FLAGS: dict[str, set[str]] = {
    "mutmut": {"--patch"},  # mutmut 2.x
    "cosmic-ray": {"--patch"},
    "stryker": {"--inplace"},  # compared case-folded: StrykerJS spells it --inPlace
}
MUTATION_TOOLS = {"mutmut", "cosmic-ray", "cargo", "stryker"}

# Launchers that run a mutation tool named later in their argv
# (`uv run mutmut run`, `python -m mutmut run`, `npx stryker run --inPlace`).
# A tool name is looked for only behind one of these, never anywhere in a
# segment -- `echo mutmut run` is not a mutmut invocation.
LAUNCHER_VERBS: dict[str, set[str]] = {
    "uv": {"run"}, "poetry": {"run"}, "pipenv": {"run"}, "pdm": {"run"},
    "hatch": {"run"}, "pipx": {"run"}, "pnpm": {"exec", "dlx"}, "yarn": {"exec", "dlx"},
}
BARE_LAUNCHERS = {"uvx", "npx", "pnpx", "bunx"}
RE_PYTHON = re.compile(r"^python(\d+(\.\d+)?)?$")

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
    "env": {"-u", "-S", "-C", "--chdir"},
    "nice": {"-n"},
    "xargs": {"-I", "-n", "-P", "-d", "-a", "-s", "-E", "-L", "-l"},
}

RE_VAR_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# scripts/ on sys.path, for the lazy `lib.mutation_scope` import -- the only
# lib import in this file, made only when a copy-only verb is matched, so a
# broken lib package still never denies anything else (issue #24).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MIN_PYTHON = (3, 11)

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

    return None


def _find_zeugnis_root(cwd: str) -> str | None:
    """Nearest ancestor of cwd (itself included) holding analysis/zeugnis/.
    stdlib only, so inertness never depends on lib importing; the same walk
    as lib.mutation_scope.find_zeugnis_root. Walking up keeps the guard
    active when the session's cwd is inside a mutation copy (issue #142)."""
    here = os.path.normpath(os.path.abspath(cwd))
    while True:
        if os.path.isdir(os.path.join(here, "analysis", "zeugnis")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


RE_HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")


def _unquoted_heredocs(line: str) -> list[tuple[bool, str]]:
    """(strip_tabs, delimiter) for each `<<WORD` operator on `line` that sits
    outside quotes -- `echo "a <<EOF"` opens no heredoc."""
    found: list[tuple[bool, str]] = []
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            quote = "" if ch == quote else quote
        elif ch in ("'", '"'):
            quote = ch
        elif line.startswith("<<", i) and not line.startswith("<<<", i):
            match = RE_HEREDOC.match(line, i)
            if match:
                found.append((match.group(1) == "-", match.group(3)))
                i = match.end()
                continue
        i += 1
    return found


def _strip_heredoc_bodies(command: str) -> str:
    """Drop heredoc BODY lines, which are text a command reads, not commands
    the shell runs -- a README written with `cat > f <<'EOF'` may well say
    `mutmut run` (the #73 false-positive class). The `<<WORD` operator line
    itself stays, so the copy-only check still marks the cwd unknown after it.
    A heredoc whose terminator never appears strips NOTHING: the body lines
    are then scanned as commands, which can only deny more, never less."""
    lines = command.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        pending = _unquoted_heredocs(lines[i])
        i += 1
        for strip_tabs, delimiter in pending:
            end = next((j for j in range(i, len(lines))
                        if (lines[j].lstrip("\t") if strip_tabs else lines[j]) == delimiter), None)
            if end is None:
                return command
            i = end + 1
    return "\n".join(out)


def _newlines_as_separators(command: str) -> str:
    """Turn every unquoted newline into ` ; `, so a multi-line command is
    segmented line by line for the copy-only check. shlex.split treats a bare
    newline as whitespace, which would glue `cd x` and the next line's
    `mutmut run` into one segment whose argv[0] is `cd`. A backslash-newline
    is a line continuation and becomes a space."""
    out: list[str] = []
    quote = ""
    i = 0
    while i < len(command):
        ch = command[i]
        if ch == "\\" and quote != "'" and i + 1 < len(command):
            nxt = command[i + 1]
            out.append(" " if nxt == "\n" else ch + nxt)
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "\n":
            out.append(" ; ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# Separators for the copy-only check, which tokenises with shlex's
# punctuation_chars mode: `cat;mutmut run` splits at the `;` there, where the
# plain shlex.split above glues `cat;` into one word (a limit the install
# check documents and keeps). `(` and `)` delimit a subshell, so a `cd` inside
# one is followed only up to the `)`.
COPY_CHECK_SEPARATORS = ("&&", "||", ";", "|", "&", "|&", ";;", "(", ")")


def _copy_check_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(_newlines_as_separators(_strip_heredoc_bodies(command)), posix=True,
                        punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _segments_with_ops(tokens: list[str]) -> list[tuple[str | None, list[str]]]:
    """Like _split_segments, but each segment keeps the separator before it."""
    segments: list[tuple[str | None, list[str]]] = [(None, [])]
    for tok in tokens:
        if tok in COPY_CHECK_SEPARATORS:
            segments.append((tok, []))
        else:
            segments[-1][1].append(tok)
    # Empty segments are kept: `)` followed by `&&` is two separators in a
    # row, and the `)` must still be seen to end the subshell.
    return segments


def _tool_candidates(argv: list[str]) -> list[list[str]]:
    """argv lists, each starting at a mutation tool this segment would run."""
    if not argv:
        return []
    name = argv[0].rsplit("/", 1)[-1].lower()
    if name in MUTATION_TOOLS:
        return [argv]
    rest: list[str] | None = None
    if RE_PYTHON.match(name) and len(argv) >= 3 and argv[1] == "-m":
        return [argv[2:]]
    if name in BARE_LAUNCHERS:
        rest = argv[1:]
    elif name in LAUNCHER_VERBS and len(argv) >= 2 and argv[1].lower() in LAUNCHER_VERBS[name]:
        rest = argv[2:]
    if rest is None:
        return []
    # A launcher flag's VALUE may itself be a tool name (`uv run --with mutmut
    # mutmut run`), so every position is a candidate, not just the first.
    return [rest[i:] for i, tok in enumerate(rest) if tok.rsplit("/", 1)[-1].lower() in MUTATION_TOOLS]


def _copy_only_invocation(segment: list[str]) -> str | None:
    """Describes a mutation-tool invocation that writes mutants in its cwd."""
    for argv in _tool_candidates(_skip_wrappers(segment)):
        tool = argv[0].rsplit("/", 1)[-1].lower()
        rest = [t.lower() for t in argv[1:]]
        if tool == "cargo":
            if rest[:1] == ["mutants"] and "--in-place" in rest:
                return "cargo mutants --in-place"
            continue
        flags = COPY_ONLY_FLAGS.get(tool, set())
        hit = next((t for t in rest if t in flags), None)
        if hit:
            return f"{argv[0]} ... {hit}"
        verb = next((t for t in rest if not t.startswith("-")), None)
        if verb in COPY_ONLY_VERBS.get(tool, set()):
            return f"{argv[0]} {verb}"
    return None


def _uses_env_chdir(segment: list[str]) -> bool:
    for tok in segment:
        if tok in ("-C", "--chdir") or tok.startswith("--chdir="):
            return True
        if not (RE_VAR_ASSIGN.match(tok) or tok.startswith("-")
                or tok.rsplit("/", 1)[-1].lower() in WRAPPER_COMMANDS):
            return False
    return False


def _copy_only_denial(command: str, cwd: str) -> str | None:
    """The deny reason for the first copy-only invocation whose effective cwd
    is not inside a mutation copy, or None. See the module docstring."""
    try:
        tokens = _copy_check_tokens(command)
    except ValueError:
        return None  # run() already refused an untokenisable command
    current: str | None = os.path.normpath(os.path.abspath(cwd))
    moved = False
    heredoc = False
    subshells: list[tuple[str | None, bool]] = []
    for op, segment in _segments_with_ops(tokens):
        if op == "(":
            subshells.append((current, moved))
        elif op == ")":
            # Whatever the subshell's `cd` did ends here.
            current, moved = subshells.pop() if subshells else (None, True)
        elif moved and op is not None and op not in CWD_PROPAGATING:
            current = None
        if not segment:
            continue
        argv = _skip_wrappers(segment)
        # After a heredoc the cwd is unknown (its body was stripped above, but a
        # body whose terminator was missing is still here as text). Sticky, so a
        # later absolute `cd` cannot revive it.
        heredoc = heredoc or any(tok.startswith("<<") for tok in segment)
        if heredoc:
            current = None
        invocation = _copy_only_invocation(segment)
        if invocation:
            where = None if _uses_env_chdir(segment) else current
            copy_root = None
            if where is not None:
                try:
                    from lib.mutation_scope import copy_root_for  # noqa: E402
                except (ImportError, ModuleNotFoundError) as exc:
                    return (f"{invocation!r} needs lib.mutation_scope to prove it runs inside a "
                            f"mutation copy, and lib failed to import ({exc}); failing closed")
                copy_root = copy_root_for(where)
            if copy_root is None:
                place = "an unknown directory" if where is None else repr(where)
                return (f"{invocation!r} would run in {place}, which is not inside a mutation copy. "
                        "Mutation tools write mutants into their cwd (mutmut 3 `run` creates ./mutants/ "
                        "and `apply` rewrites the source file), so they run only inside a fresh "
                        "`git archive` copy prepared by scripts/mutation_harden.py under "
                        "analysis/zeugnis/mutation/<runId>/ -- use its run-shard/prove subcommands")
        name = argv[0].rsplit("/", 1)[-1] if argv else ""
        if name in ("cd", "pushd", "popd"):
            moved = True
            target = next((t for t in argv[1:] if not t.startswith("-")), None)
            target = os.path.expanduser(target or "~")
            if heredoc or name != "cd" or target == "-" or (current is None and not os.path.isabs(target)):
                current = None  # pushd/popd stacks and `cd -` are not followed
            else:
                # Lexical: os.path.normpath, never realpath -- see lib.mutation_scope.
                current = os.path.normpath(os.path.join(current or "/", target))
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
    if _find_zeugnis_root(cwd) is None:
        return allow()  # inert unless this repo actually uses zeugnis

    if sys.version_info < MIN_PYTHON:
        return deny(
            f"zeugnis needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}; guard_bash_scope ran under "
            f"{sys.version.split()[0]} ({sys.executable}). Put a newer python3 first on PATH. "
            f"{ESCAPE_HATCH}"
        )

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
                "assertion-auditor agents may only perform read-only registry lookups, never "
                "install/publish operations. "
                f"{ESCAPE_HATCH}"
            )

    denial = _copy_only_denial(command, cwd)
    if denial:
        return deny(f"Refusing Bash command {command!r}: {denial}. {ESCAPE_HATCH}")

    return allow()


def main() -> int:
    try:
        return run()
    except Exception as exc:  # noqa: BLE001 - fail-closed handler, intentionally broad
        return deny(f"guard_bash_scope: internal error ({type(exc).__name__}: {exc}); failing closed. {ESCAPE_HATCH}")


if __name__ == "__main__":
    sys.exit(main())
