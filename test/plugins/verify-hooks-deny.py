#!/usr/bin/env python3
"""Gate 2b — a declared hook must actually DENY, not merely exist.

Requirement 6 in the generator asks for a PreToolUse hook. It reliably produces
the artifact and not the behavior: of three generated hooks, all three had a
well-formed hooks.json and a deny() with the right exit code and JSON shape, and
two of them allowed a violating write. One shipped hooks.json with no script at
all — and was reported as a success, because the check was `[ -f hooks.json ]`.

That is the same gap as "the rule exists" vs "the rule runs", one level down.
Existence is cheap to generate and cheap to check; firing is neither. So this
gate does the only thing that settles it: resolve the command the hooks.json
actually declares, feed it a crafted violating event on stdin, and require
exit 2.

Four failure modes it separates, because they need different fixes:

    no-hook       nothing declared            -> requirement 6 produced nothing
    malformed     hooks.json unparseable      -> shape bug
    missing       declares a script not there -> declaration without implementation
    inert         script runs, allows anyway  -> logic bug (the common one)

Also checks the inverse, which matters more than it looks: a hook MUST allow
when the repo does not use that plugin. A hook that denies everywhere would
police every unrelated repository on the machine.

PER-PLUGIN FIXTURES, AND WHY THE GENERIC ONE LIES FOR SOME PLUGINS
--------------------------------------------------------------------
The single global default fixture (an andon ledger with a missing
blast-radius) is only a real violation for a hook whose rule fires
unconditionally. Several hooks are SCOPE-CONDITIONAL by design: confab's
guard_edit_scope.py is only supposed to act when a remediation-scope lock is
present, self-assess's guard_target_edit.py only when the repo shows evidence
of being self-assess-managed. Probed with the generic fixture, both correctly
return "allow" -- which this script would then report as "FAIL: allows a
violating edit", a false negative. This happened for real: confab's hook was
reported broken, hand-verified to be correct, and only then was it clear the
TEST was wrong, not the hook.

So: if `test/plugins/fixtures/hook-violation-<plugin-name>/` exists, it is
used INSTEAD of the generic default for that plugin, and read as the ONLY
correct violating scenario for that plugin's rule -- construct it to actually
violate what that specific hook checks, the way each plugin's own author
would know to. If the fixture directory contains a file named `_GIT_INIT`, the
probe copy is `git init`-ed and committed before the hook runs (needed for any
hook that checks tree cleanliness, e.g. self-assess's dirty-tree-gate).

Usage:
    verify-hooks-deny.py <plugin-dir> [...] [--violating-fixture DIR]
Exit: 0 if every declared hook denies the violating case and allows the inert
case; 1 otherwise. A plugin with no hook is reported, not failed — not every
plugin has an action to gate (advisory plugins genuinely cannot).
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_VIOLATING = "test/plugins/fixtures/ledger-missing-blast-radius"
REPO_ROOT = Path(__file__).resolve().parents[2]


def declared_commands(plugin: Path) -> tuple[list[tuple[list[str], str]], str | None]:
    """Every PreToolUse command hooks.json declares, paired with its matcher.

    The matcher decides the probe shape: a hook registered under "Bash" will
    exit 0 on any Edit-shaped event before it even looks at the violation --
    not because it is inert, but because the probe sent the wrong tool. This
    bit a real hook (confab's guard_bash_scope.py) when the probe always sent
    tool_name="Edit" regardless of what the hook was registered to see.
    """
    j = plugin / "hooks/hooks.json"
    if not j.is_file():
        return [], "no-hook"
    try:
        d = json.loads(j.read_text())
        entries = d["hooks"]["PreToolUse"]
    except Exception as e:
        return [], f"malformed ({type(e).__name__})"
    cmds = []
    for entry in entries:
        matcher = entry.get("matcher", "")
        for h in entry.get("hooks", []):
            if h.get("type") != "command":
                # A "prompt" hook asks a model to decide, which is the
                # model-mediated path a hook exists to replace.
                return [], 'declares type="prompt" — not enforcement'
            raw = h.get("command", "")
            cmd = [w.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin.resolve()))
                   for w in shlex.split(raw)]
            cmds.append((cmd, matcher))
    return cmds, None


def violating_fixture_for(plugin: Path, override: str) -> Path:
    """Prefer a plugin-specific violating fixture over the generic default."""
    specific = REPO_ROOT / "test/plugins/fixtures" / f"hook-violation-{plugin.name}"
    if specific.is_dir():
        return specific
    return Path(override).resolve()


def materialize(fixture: Path) -> tuple[str, str | None]:
    """Copy a fixture into a fresh temp dir, optionally git-init it.

    A fresh copy every probe: the dirty-tree test in particular MUTATES the
    working tree, so reusing one directory across probes would leak state
    between them.

    Returns (tmp_dir, target_override). An optional `_TARGET` file in the
    fixture names the relative path to probe instead of the default
    "src/api.py" -- needed when a hook only gates paths matching a specific
    shape (cupertino's write-scope check only fires on a cupertino-artifact
    filename; probing it with a generic path would silently never reach the
    check being tested, same false-negative shape as the wrong tool_name did
    for a Bash-matched hook).
    """
    tmp = tempfile.mkdtemp()
    shutil.copytree(fixture, tmp, dirs_exist_ok=True)
    git_marker = Path(tmp) / "_GIT_INIT"
    if git_marker.is_file():
        git_marker.unlink()
        subprocess.run(["git", "init", "-q"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "config", "user.email", "hook-test@localhost"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "config", "user.name", "hook-test"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "fixture baseline"], cwd=tmp, capture_output=True)
    target_marker = Path(tmp) / "_TARGET"
    target = None
    if target_marker.is_file():
        target = target_marker.read_text().strip()
        target_marker.unlink()
    return tmp, target


# A mutating shell command, for probing a Bash-matched hook. Deliberately the
# same class of command guard_bash_scope.py's own DANGEROUS_PATTERNS lists —
# the probe must violate whatever the hook is actually watching for.
BASH_VIOLATION = "npm install left-pad"


def tool_event(matcher: str, path: str) -> dict:
    """Build a plausible tool_name/tool_input pair for whatever this hook is
    registered to see. Falls back to Edit for an unrecognized matcher."""
    if "Bash" in matcher and "Edit" not in matcher and "Write" not in matcher:
        return {"tool_name": "Bash", "tool_input": {"command": BASH_VIOLATION}}
    return {"tool_name": "Edit", "tool_input": {"file_path": path, "content": "x = 1\n"}}


def probe(cmd: list[str], cwd: str, matcher: str, path: str = "src/api.py") -> tuple[int, str]:
    payload = json.dumps({"cwd": cwd, **tool_event(matcher, path)})
    try:
        r = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError) as e:
        return -1, f"{type(e).__name__}: {e}"
    return r.returncode, (r.stderr or r.stdout)[:160].replace("\n", " ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify declared hooks actually deny.")
    ap.add_argument("plugin_dirs", nargs="+", type=Path)
    ap.add_argument("--violating-fixture", default=DEFAULT_VIOLATING,
                    help="a repo state the hook is supposed to refuse edits in")
    args = ap.parse_args(argv)

    bad = 0
    print(f"{'plugin':<15}{'script':<26}{'violating':<12}{'unrelated':<12}verdict")
    print("-" * 82)
    with tempfile.TemporaryDirectory() as inert:
        for plugin in args.plugin_dirs:
            cmds, err = declared_commands(plugin)
            if err == "no-hook":
                print(f"{plugin.name:<15}{'—':<26}{'—':<12}{'—':<12}no hook declared")
                continue
            if err:
                print(f"{plugin.name:<15}{'—':<26}{'—':<12}{'—':<12}FAIL: {err}")
                bad += 1
                continue

            fixture = violating_fixture_for(plugin, args.violating_fixture)
            if not fixture.is_dir():
                print(f"ERROR: violating fixture not found: {fixture}", file=sys.stderr)
                return 2
            is_specific = fixture.name.startswith("hook-violation-")

            for cmd, matcher in cmds:
                script = Path(cmd[-1])
                if not script.is_file():
                    print(f"{plugin.name:<15}{script.name:<26}{'—':<12}{'—':<12}"
                          f"FAIL: declared script does not exist")
                    bad += 1
                    continue
                violating, target_override = materialize(fixture)
                try:
                    rc_v, msg = probe(cmd, violating, matcher,
                                      path=target_override or "src/api.py")
                finally:
                    shutil.rmtree(violating, ignore_errors=True)
                rc_i, _ = probe(cmd, inert, matcher)
                ok = (rc_v == 2) and (rc_i == 0)
                if not ok:
                    bad += 1
                why = ("ok" if ok else
                       "FAIL: allows a violating edit" if rc_v != 2 else
                       "FAIL: denies in an unrelated repo")
                tag = " [plugin-specific fixture]" if is_specific else " [generic fixture]"
                print(f"{plugin.name:<15}{script.name:<26}{('exit ' + str(rc_v)):<12}"
                      f"{('exit ' + str(rc_i)):<12}{why}{tag}")
                if not ok and msg:
                    print(f"{'':<15}{'':<26}{msg[:70]}")

    print()
    print("A hook is enforcement only if it denies the violation AND stays inert")
    print("elsewhere. Exit 2 on the violating case is the whole point; anything")
    print("else is a well-shaped file that does nothing.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
