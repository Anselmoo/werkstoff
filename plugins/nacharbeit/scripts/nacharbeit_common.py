#!/usr/bin/env python3
"""Shared path resolution and flag defaults for the nacharbeit scripts.

Every nacharbeit CLI needs the same four roots, and every one of them used to
derive them with `ROOT = HERE.parent.parent` -- which resolves to the repo when
the script lives in `tools/prompt-review/` and to `plugins/nacharbeit` once it
lives inside the plugin. One place computes them; the CLIs only add flags.

    plugin_root()   the plugin directory (parent of scripts/)
    repo_root()     the working directory the scripts are run from, or --repo-root
    rubric_path()   <plugin>/references/rubric.md unless --rubric overrides it
    state_dir()     <repo>/analysis/nacharbeit unless --state-dir overrides it

Usage: imported, never run. `python3 nacharbeit_common.py` prints the resolved
defaults for the current directory so a puzzled operator can see them.
Exit: 0.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
DEFAULT_STATE_DIR = Path("analysis/nacharbeit")
DEFAULT_PLUGINS_ROOT = Path("plugins")
# The calibration fixtures ship INSIDE the plugin, so an installed copy can calibrate in a
# repository that has never heard of werkstoff (#117). Absolute on purpose: it is a property
# of the plugin, not of the repository being reviewed. scripts/ is the subtree the linter
# already skips for fixtures (nacharbeit_lint.discover) and that a synced install carries.
DEFAULT_FIXTURES_ROOT = PLUGIN_ROOT / "scripts" / "fixtures" / "calibration"
STAGED_FIXTURES_NAME = "fixtures"  # <state-dir>/fixtures/: the copy the workflow's agents Read
DEFAULT_DOCS_ROOT = Path("docs")
DEFAULT_REPORT_OUT = Path("docs/prompt-quality-findings.md")
DEFAULT_KNOWN_ANSWERS = Path("docs/prompt-index.md")
DEFAULT_MARKETPLACE = Path(".claude-plugin/marketplace.json")
DEFAULT_PROMPT_INDEX_SCRIPT = Path("tools/prompt-index/build_prompt_index.py")
DEFAULT_CONTRACT_DIFF = Path("tools/plugin-serializer/contract_diff.py")
DEFAULT_WRITE_ROOTS = ("plugins/", "tools/")
DEFAULT_ARTIFACT_COPIES = {
    "references/parallel-safe-research-protocol.md": "tools/symbol-indexer/parallel-safe-research-protocol.md",
}
DEFAULT_SKIP_LINT = ("M-DUP-CONTENT", "P-MARKETPLACE-MEMBER")
DEFAULT_REPO_NAME = "this plugin set"
DEFAULT_REPO_NOTES = ""

# werkstoff itself carries two notes the review must repeat verbatim; any other repo
# passes its own with --repo-notes or none at all.
WERKSTOFF_REPO_NOTES = (
    "Report once, as a nit, that passung ships commands rather than skills "
    "(rubric F6); do not repeat it elsewhere."
)


def plugin_root() -> Path:
    return PLUGIN_ROOT


def repo_root(override: Path | None = None) -> Path:
    return (override or Path.cwd()).resolve()


def rubric_path(override: Path | None = None) -> Path:
    return (override or (PLUGIN_ROOT / "references" / "rubric.md")).resolve()


def state_dir(override: Path | None = None, root: Path | None = None) -> Path:
    if override is not None:
        return override if override.is_absolute() else repo_root(root) / override
    return repo_root(root) / DEFAULT_STATE_DIR


def fixture_inventory(root: Path | None = None) -> dict:
    """What calibration fixtures exist at `root` (default: the set shipped in the plugin):
    {"root", "tune", "sealed", "kinds"} where kinds is the set a tuning AND a sealed fixture
    both cover. Reads each planted.json's `kind` only; build_args.load_fixtures validates."""
    r = (root or DEFAULT_FIXTURES_ROOT)
    tune: set[str] = set()
    sealed: set[str] = set()
    n_tune = n_sealed = 0
    if r.is_dir():
        for d in sorted(p for p in r.iterdir() if (p / "planted.json").is_file()):
            try:
                kind = json.loads((d / "planted.json").read_text(encoding="utf-8")).get("kind", "skills")
            except (OSError, ValueError):
                continue  # build_args names the unusable manifest; a count must not crash on it
            if d.name.startswith("sealed"):
                n_sealed += 1
                sealed.add(kind)
            else:
                n_tune += 1
                tune.add(kind)
    return {"root": r.as_posix(), "tune": n_tune, "sealed": n_sealed, "kinds": sorted(tune & sealed)}


GUARD_SCRIPT = "nacharbeit_guard.py"
GUARD_TOOLS = ("Write", "Edit", "MultiEdit", "Bash")
HEARTBEAT_NAME = "guard-heartbeat.json"
LOCK_NAME = "fix_scope.json"


def _probe(cmd_template: str, root: Path, tool: str, tool_input: dict, lock: bool) -> tuple[int, str, str] | str:
    """Run the guard's own registered command against a synthetic payload in a throwaway
    repository, with or without a fix lock. A string result is an execution failure."""
    command = shlex.split(cmd_template.replace("${CLAUDE_PLUGIN_ROOT}", root.as_posix()))
    env = {k: v for k, v in os.environ.items() if k not in {"NACHARBEIT_DISABLE_GUARD", "NACHARBEIT_STATE_DIR"}}
    with tempfile.TemporaryDirectory(prefix="nacharbeit-guard-probe-") as td:
        if lock:
            state = Path(td) / "analysis" / "nacharbeit"
            state.mkdir(parents=True)
            (state / LOCK_NAME).write_text(json.dumps({"runStamp": "probe", "createdAt": "probe", "files": {"inside.md": "haiku"}}), encoding="utf-8")
        payload = json.dumps({"cwd": td, "tool_name": tool, "tool_input": tool_input})
        try:
            r = subprocess.run(command, input=payload, capture_output=True, text=True, cwd=td, env=env, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            return f"could not run `{' '.join(command[:2])} ...`: {type(e).__name__}: {e}"
    return r.returncode, r.stdout, r.stderr


def guard_status(plugin_root: Path | None = None) -> dict:
    """Is nacharbeit's own fix-lock guard present, declared, runnable and denying in THIS
    copy of the plugin? {"ok": bool, "problem": str | None, "detail": [...]}.

    The scripts run from the same directory the runtime loads hooks from, so a copy that
    was synced without hooks/ (issue #117) is caught here as a missing hooks.json, instead
    of a fix pass running unguarded. This proves the files and the declared command, not
    that the runtime registered them: the heartbeat that build_fix_args.py --confirm-guard
    reads proves that, once a lock is open."""
    root = plugin_root or PLUGIN_ROOT
    hj = root / "hooks" / "hooks.json"

    def bad(problem: str) -> dict:
        return {"ok": False, "problem": problem, "detail": []}

    if os.environ.get("NACHARBEIT_DISABLE_GUARD") == "1":
        return bad("NACHARBEIT_DISABLE_GUARD=1 is set in this environment, so the guard allows every call; unset it before a fix pass")
    if not hj.is_file():
        return bad(f"{hj.as_posix()} does not exist: this copy of the plugin was installed or synced without hooks/, "
                   f"so the fix-lock guard is not registered and a fix pass would run unguarded -- reinstall nacharbeit with its hooks/ directory")
    try:
        entries = json.loads(hj.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        return bad(f"{hj.as_posix()} does not declare a PreToolUse hook list ({type(e).__name__}: {e})")
    declared = None
    for entry in entries if isinstance(entries, list) else []:
        for h in entry.get("hooks", []) if isinstance(entry, dict) else []:
            if isinstance(h, dict) and h.get("type") == "command" and GUARD_SCRIPT in str(h.get("command", "")):
                declared = (str(entry.get("matcher", "")), str(h["command"]))
    if declared is None:
        return bad(f"{hj.as_posix()} declares no `type: command` PreToolUse hook running {GUARD_SCRIPT}")
    matcher, command = declared
    try:
        uncovered = [t for t in GUARD_TOOLS if not re.fullmatch(matcher, t)]
    except re.error as e:
        return bad(f"the guard's matcher {matcher!r} is not a valid pattern: {e}")
    if uncovered:
        return bad(f"the guard's matcher {matcher!r} does not cover {', '.join(uncovered)}")
    script = root / "hooks" / GUARD_SCRIPT
    if not script.is_file():
        return bad(f"{script.as_posix()} does not exist although hooks.json declares it")

    denied = _probe(command, root, "Write", {"file_path": "outside.md", "content": "x"}, lock=True)
    if isinstance(denied, str):
        return bad(denied)
    rc, out, _err = denied
    try:
        shaped = json.loads(out)["hookSpecificOutput"]
        shape_ok = shaped.get("hookEventName") == "PreToolUse" and shaped.get("permissionDecision") == "deny"
    except (ValueError, KeyError, TypeError, AttributeError):
        shape_ok = False
    if rc != 2 or not shape_ok:
        return bad(f"with a fix lock open the guard did not deny an edit outside it (exit {rc}, stdout {out[:80]!r}); a guard that does not deny is not a guard")
    inert = _probe(command, root, "Write", {"file_path": "outside.md", "content": "x"}, lock=False)
    if isinstance(inert, str):
        return bad(inert)
    if inert[0] != 0:
        return bad(f"with no fix lock the guard exited {inert[0]}; it must stay inert outside a fix pass or it blocks every edit in the session")
    return {"ok": True, "problem": None, "detail": [f"declared: {matcher} -> {command}", "denies outside the lock, inert without one"]}


def is_werkstoff(root: Path | None = None) -> bool:
    """True when the working directory is the werkstoff workshop itself, which is the
    only repo whose defaults (VitePress report, F6 note, artifact copies) should apply."""
    r = repo_root(root)
    return (r / ".rrt.toml").is_file() and (r / "plugins" / "nacharbeit" / ".claude-plugin" / "plugin.json").is_file()


def rel(p: Path, root: Path | None = None) -> str:
    """Repo-relative POSIX path when p is under the repo, else the path unchanged."""
    r = repo_root(root)
    q = p if p.is_absolute() else (r / p)
    try:
        return q.resolve().relative_to(r).as_posix()
    except ValueError:
        return p.as_posix()


def main() -> int:
    print(f"plugin_root  {plugin_root()}")
    print(f"repo_root    {repo_root()}")
    print(f"rubric       {rubric_path()}")
    print(f"state_dir    {state_dir()}")
    print(f"werkstoff    {is_werkstoff()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
