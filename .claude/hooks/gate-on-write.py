#!/usr/bin/env python3
"""PostToolUse gate: run the cheap check that matches the file just written.

WHY THIS EXISTS
---------------
This repo already had CI validating SKILL.md frontmatter. Two generated plugins
still shipped 11 files whose frontmatter did not parse — and a file that fails
to parse still LOADS, with no description and no tools, so the skill silently
never triggers. The gate was not missing. It ran at PR time, hours after the
files were written, while conclusions were already being drawn from plugins
whose skills could never fire.

The whole static stack costs ~0.2s. There is no efficiency reason to defer it.
So: run the matching check the moment a file is written, and feed the failure
straight back.

PostToolUse cannot prevent the write — it already happened. Exit 2 sends stderr
back to Claude, which is what we want: not a veto, an immediate correction.

SCOPE
-----
Fires only for paths this repo has gates for. Anything else exits 0 in silence,
so ordinary edits are untouched.

    plugins/*/skills/*/SKILL.md      frontmatter must parse AND have a description
    plugins/*/agents/*.md            same
    plugins/*/workflows/*.js         must parse
    plugins/*/hooks/**               declared hooks must actually deny
    plugins/*/.claude-plugin/*.json  must be valid JSON
    test/plugins/cases.tsv           oracle regexes must not use silent-failure forms,
                                     and every fixture path must resolve
    .rrt.toml                        every declared target must exist

FAILURE MODE
------------
Loud, deliberately. If the gate itself breaks it exits 2 saying so, rather than
exiting 0 and quietly ceasing to protect anything — that silent-degradation
shape is the exact defect class this gate was built for. Since PostToolUse
cannot block the write, a noisy false positive costs a message, not a workflow.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TIMEOUT = 25


def fail(msg: str) -> int:
    print(msg, file=sys.stderr)
    return 2


def ok() -> int:
    return 0


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=TIMEOUT)
    except (subprocess.TimeoutExpired, OSError) as e:
        return -1, f"{type(e).__name__}: {e}"
    return r.returncode, (r.stdout + r.stderr).strip()


def check_frontmatter(path: Path) -> int:
    """Parse-and-has-description. A broken block loads with EMPTY metadata."""
    try:
        import yaml
    except ImportError:
        return ok()  # pyyaml absent: CI still covers this
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return fail(f"[gate] {path.relative_to(REPO)}: no YAML frontmatter. It will load "
                    f"with empty metadata and never trigger.")
    try:
        meta = yaml.safe_load(text.split("---")[1])
    except Exception as e:
        first = str(e).splitlines()[0]
        return fail(
            f"[gate] {path.relative_to(REPO)}: frontmatter does not parse — {first}\n"
            f"        It will still LOAD, with no description and no tools, so the "
            f"skill/agent silently never triggers.\n"
            f"        Common causes here: an unquoted value containing `[` (YAML reads it "
            f"as a flow sequence — write argument-hint: \"[path] [--flag]\"), a bare "
            f"scalar containing `: `, or a multi-line description starting at column 0.")
    if not isinstance(meta, dict) or not meta.get("description"):
        return fail(f"[gate] {path.relative_to(REPO)}: frontmatter parses but has no "
                    f"`description`. Claude uses it to decide when to trigger; without it "
                    f"the skill/agent is effectively invisible.")
    return ok()


def check_js(path: Path) -> int:
    rc, out = run(["node", "--check", str(path)])
    return ok() if rc == 0 else fail(f"[gate] {path.relative_to(REPO)} does not parse:\n{out}")


def check_hooks(path: Path) -> int:
    """A declared hook must actually deny. Existence is not enforcement."""
    plugin = path
    while plugin != REPO and plugin.name != "hooks":
        plugin = plugin.parent
    plugin = plugin.parent
    script = REPO / "test/plugins/verify-hooks-deny.py"
    if not script.is_file():
        return ok()
    rc, out = run(["python3", str(script), str(plugin.relative_to(REPO))])
    if rc == 0:
        return ok()
    return fail(f"[gate] {plugin.name}: a declared hook does not enforce.\n{out}\n"
                f"        A hooks.json plus a well-shaped deny() is not a working hook — "
                f"3 of 4 generated hooks passed inspection and allowed the violation.")


def check_json(path: Path) -> int:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return fail(f"[gate] {path.relative_to(REPO)} is not valid JSON: {e}")
    return ok()


def check_cases() -> int:
    problems: list[str] = []
    rc, out = run(["bash", "test/plugins/lint-oracles.sh"])
    if rc != 0:
        problems.append(out)
    # Every fixture must resolve. When fixtures moved, six cases silently ran
    # against an EMPTY temp dir; the plugin correctly reported "nothing to
    # audit" and the case scored FAIL, which read as a plugin defect.
    cases = REPO / "test/plugins/cases.tsv"
    missing = []
    for line in cases.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        col = line.split("\t")
        if len(col) > 2 and not (REPO / col[2]).is_dir():
            missing.append(f"{col[0]} -> {col[2]}")
    if missing:
        problems.append("fixture paths that do not resolve (cp copies nothing; the case "
                        "runs against an EMPTY dir and FAILs for a non-plugin reason):\n  "
                        + "\n  ".join(missing))
    return fail("[gate] cases.tsv:\n" + "\n".join(problems)) if problems else ok()


def check_rrt() -> int:
    try:
        import tomllib
    except ImportError:
        return ok()
    d = tomllib.loads((REPO / ".rrt.toml").read_text())["tool"]["rrt"]
    missing = [g["changelog_file"] for g in d.get("version_groups", [])
               if not (REPO / g["changelog_file"]).is_file()]
    missing += [t["path"] for g in d.get("version_groups", []) for t in g.get("version_targets", [])
                if not (REPO / t["path"]).is_file()]
    missing += [a["path"] for a in d.get("artifact_targets", []) if not (REPO / a["path"]).is_file()]
    missing += [f["source"] for f in d.get("field_targets", []) if not (REPO / f["source"]).is_file()]
    if missing:
        return fail("[gate] .rrt.toml names files that do not exist — `rrt bump` and "
                    "`rrt artifacts --check` will fail for reasons unrelated to real drift:\n  "
                    + "\n  ".join(missing))
    return ok()


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
        target = (event.get("tool_input") or {}).get("file_path") or ""
        if not target:
            return ok()
        p = Path(target)
        if not p.is_absolute():
            p = REPO / p
        if not p.exists():
            return ok()
        try:
            rel = p.resolve().relative_to(REPO).as_posix()
        except ValueError:
            return ok()  # outside this repo

        if rel == ".rrt.toml":
            return check_rrt()
        if rel == "test/plugins/cases.tsv":
            return check_cases()
        if not rel.startswith("plugins/"):
            return ok()
        if "/hooks/" in rel:
            return check_hooks(p)
        if re.fullmatch(r"plugins/[^/]+/skills/[^/]+/SKILL\.md", rel) or \
           re.fullmatch(r"plugins/[^/]+/agents/[^/]+\.md", rel):
            return check_frontmatter(p)
        if rel.endswith(".js") and "/workflows/" in rel:
            return check_js(p)
        if rel.endswith(".json") and "/.claude-plugin/" in rel:
            return check_json(p)
        return ok()
    except Exception as exc:
        # Loud, not silent. PostToolUse cannot undo the write, so a noisy false
        # positive costs a message; a silent gate costs everything it protects.
        return fail(f"[gate] gate-on-write itself failed: {type(exc).__name__}: {exc}. "
                    f"Checks are NOT running. Fix .claude/hooks/gate-on-write.py.")


if __name__ == "__main__":
    sys.exit(main())
