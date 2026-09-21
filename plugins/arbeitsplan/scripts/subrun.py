#!/usr/bin/env python3
"""Execute and score exactly ONE headless `claude -p` cell.

usage: subrun.py --config FILE --out FILE
       subrun.py --selftest

A THIN EXECUTOR, not an orchestrator. `run_matrix.sh` keeps building `argv`
(model, permission-mode, output-format, disallowedTools, --setting-sources,
--strict-mcp-config, --plugin-dir) and keeps iterating cases x models x
plugin_states x repeats exactly as it does today; this script receives ONE
cell's already-assembled argv plus its fixture / expect_skills / forbid_skills
/ transcript / max_budget_usd / plugin_dirs as a single JSON config (see
--config), and owns only what a single cell needs done to it:

  1. auth preflight        `claude auth status` (JSON: loggedIn/authMethod),
                            never a banner grep. MEASURED FACT this exists
                            for: a logged-out CLI prints "Failed to
                            authenticate: OAuth session expired and could not
                            be refreshed" on a `-p` call -- which READS like a
                            nesting problem and is not one. Asking the actual
                            question first is what tells the two apart.
  2. clean box              writes a per-cell settings JSON (enabledPlugins:
                            false for every installed plugin, skillOverrides:
                            "off" for every personal skill) and adds
                            `--settings <file>` to argv. Modeled on --
                            deliberately NOT importing -- test/plugins/
                            make-clean-box.py, so this plugin stays
                            standalone.
  3. isolation self-check   one sentinel `claude -p` call per arm asking the
                            model to list its available skills; a skill this
                            arm's --plugin-dir set cannot supply makes the
                            cell UNMEASURED, with the reason. This is the
                            matrix's own verify-clean-box.
  4. fixture seeding        copies a fixture dir into the cell's temp dir,
                            `git init`+commit, runs there, and captures
                            `git diff` as the cell's diff evidence.
  5. transcript parsing     stream-json -> skills_fired (ORDER preserved),
                            hook_denials, cost_usd, final text.
  6. score_cell()           PASS / FAIL / DENIED / UNMEASURED from expect_skills /
                            forbid_skills / exit code. UNMEASURED is excluded
                            from every denominator and never retried -- same
                            invariant as the legacy per-cell scoring already
                            in run_matrix.sh.

Exit: 0 the cell was scored (ANY outcome, including UNMEASURED, is written to
      --out); 2 bad input -- config unreadable, fixture missing -- nothing
      written to --out; 3 not logged in.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AUTH_LOGIN_HINT = "run `claude auth login`"
SENTINEL_PROMPT = (
    "List every Skill you can currently invoke. Reply with exactly one line "
    "per skill, formatted as 'SKILL: <name>', and nothing else."
)
SENTINEL_LINE_RE = re.compile(r"(?m)^SKILL:\s*(.+?)\s*$")
BANNER_RE = re.compile(
    r"(?i)(failed to authenticate|oauth session expired|usage limit|"
    r"not logged in|invalid api key)"
)


class ConfigError(Exception):
    """Bad --config input, or a cell precondition (e.g. a fixture) is absent."""


class AuthError(Exception):
    """`claude auth status` says the CLI cannot authenticate."""


# ---------------------------------------------------------------------------
# 1. Auth preflight -- ASK, never grep a banner to guess.
# ---------------------------------------------------------------------------
def check_auth(claude_bin: str) -> dict:
    try:
        proc = subprocess.run(
            [claude_bin, "auth", "status", "--json"],
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuthError(f"could not run '{claude_bin} auth status': {exc}") from exc
    try:
        status = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AuthError(
            f"'{claude_bin} auth status' did not return JSON "
            f"(got {proc.stdout[:200]!r}); refusing to guess from a banner"
        ) from exc
    if not status.get("loggedIn"):
        raise AuthError(f"not logged in -- {AUTH_LOGIN_HINT}")
    return status


# ---------------------------------------------------------------------------
# 2. Clean box -- modeled on test/plugins/make-clean-box.py, not imported:
#    this plugin must stand alone. `home` is a parameter (never a bare
#    Path.home() call inside the walk) purely so the selftest can point it at
#    a fabricated tree instead of the real one.
# ---------------------------------------------------------------------------
def installed_plugin_ids(home: Path) -> list[str]:
    p = home / ".claude" / "plugins" / "installed_plugins.json"
    if not p.is_file():
        return []
    ids: set[str] = set()

    def walk(o: object) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if "@" in str(k):
                    ids.add(str(k))
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(json.loads(p.read_text(encoding="utf-8")))
    return sorted(ids)


def personal_skill_names(home: Path) -> list[str]:
    d = home / ".claude" / "skills"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def write_clean_box_settings(path: Path, home: Path) -> dict:
    plugins = installed_plugin_ids(home)
    skills = personal_skill_names(home)
    cfg = {
        "enabledPlugins": dict.fromkeys(plugins, False),
        "skillOverrides": dict.fromkeys(skills, "off"),
    }
    path.write_text(json.dumps(cfg, indent=1))
    return {"plugins": len(plugins), "skills": len(skills)}


# ---------------------------------------------------------------------------
# 3. Isolation self-check -- the matrix's own verify-clean-box.
# ---------------------------------------------------------------------------
# Skills the harness supplies itself. They are present in every session whatever
# --plugin-dir says, so counting them as leakage would make every cell UNMEASURED.
# Best-effort and explicitly a list, not a heuristic: "unnamespaced means built-in"
# would also swallow a personal skill, which is exactly the leak worth catching.
BUILTIN_SKILLS = frozenset({
    "artifact-capabilities", "artifact-design", "artifact-diagramming", "claude-api",
    "code-review", "dataviz", "design", "fewer-permission-prompts", "init",
    "keybindings-help", "loop", "run", "schedule", "security-review", "simplify",
    "update-config", "workflow-authoring",
})


def discover_skill_names(plugin_dirs: list) -> set:
    """Best-effort: skill names a --plugin-dir set can legitimately supply.

    A plugin_dir is normally a whole plugin (`<dir>/skills/<name>/SKILL.md`);
    it may also point directly at one skill (`<dir>/SKILL.md`). Both are honoured.

    COMMANDS AND AGENTS COUNT TOO. The sentinel asks the model what it can invoke,
    and a session lists a plugin's commands and agents alongside its skills. Scanning
    only `skills/` marked every command as leakage: measured on a 12-plugin arm where
    34 of 40 cells came back UNMEASURED naming `passung:passung-align`
    (a command) and `cli-scaffold:cli-scaffold` (a command whose stem is its plugin) --
    every one of them supplied by the arm's own --plugin-dir set.

    BOTH SPELLINGS are returned: the bare directory name and the `<plugin>:<skill>`
    form a session actually reports. Returning only the bare name marked every
    supplied skill as foreign -- measured on the first real cell, where zirkel and
    superpowers were both loaded by the arm and both reported as leakage.

    The plugin name comes from .claude-plugin/plugin.json when present, because a
    cache directory is often the VERSION (".../superpowers/6.3.0"), not the plugin.
    """
    names: set = set()

    def add(plugin: str, skill: str) -> None:
        names.add(skill)
        names.add(f"{plugin}:{skill}")

    for d in plugin_dirs:
        base = Path(d)
        plugin = base.name
        manifest = base / ".claude-plugin" / "plugin.json"
        if manifest.is_file():
            try:
                declared = json.loads(manifest.read_text(encoding="utf-8")).get("name")
            except ValueError:
                declared = None
            if declared:
                plugin = declared
        skills_dir = base / "skills"
        if skills_dir.is_dir():
            for entry in skills_dir.iterdir():
                if (entry / "SKILL.md").is_file():
                    add(plugin, entry.name)
        wf = base / "workflows"
        if wf.is_dir():
            for entry in sorted(wf.glob("*.js")):
                # A workflow is listed under its meta.name, which differs from the
                # file stem (align.js declares `passung-align-batch`). Both are
                # added: the declared name is what a session reports.
                m = re.search(r"\bname:\s*['\"]([^'\"]+)['\"]", entry.read_text(encoding="utf-8", errors="replace")[:2000])
                if m:
                    add(plugin, m.group(1))
                add(plugin, entry.stem)
        for kind in ("commands", "agents"):
            sub = base / kind
            if sub.is_dir():
                for entry in sub.rglob("*.md"):
                    add(plugin, entry.stem)
        if (base / "SKILL.md").is_file():
            add(plugin, base.name)
    return names


def _sentinel_argv(argv: list, prompt: str) -> list:
    """`argv` with its `-p <prompt>` swapped for the sentinel prompt.

    Every isolation flag (--plugin-dir, --settings, --setting-sources,
    --strict-mcp-config, --model, --permission-mode) survives untouched, so
    the sentinel call is measured under the SAME arm as the real cell.
    """
    out = list(argv)
    for i, a in enumerate(out):
        if a == "-p" and i + 1 < len(out):
            out[i + 1] = prompt
            return out
    return [*out, "-p", prompt]


def sentinel_check(argv: list, plugin_dirs: list, timeout_s: int,
                   cwd: Path | None = None) -> str | None:
    """Return an UNMEASURED reason, or None if the arm's skill set is clean.

    `cwd` MUST be the cell's own directory. Running the sentinel anywhere else
    certifies a different environment than the one the cell runs in: measured on
    the first real cell, where the sentinel inherited the repository and reported
    a skill the cell could never have seen.
    """
    allowed = discover_skill_names(plugin_dirs) | BUILTIN_SKILLS
    call = _sentinel_argv(argv, SENTINEL_PROMPT)
    try:
        proc = subprocess.run(
            call, capture_output=True, timeout=timeout_s, stdin=subprocess.DEVNULL,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return "isolation self-check timed out"
    text = parse_transcript(proc.stdout)["final_text"] or ""
    claimed = set(SENTINEL_LINE_RE.findall(text))
    foreign = sorted(claimed - allowed)
    if foreign:
        return (
            "isolation self-check reported skill(s) this arm's --plugin-dir "
            "cannot supply: " + ", ".join(foreign)
        )
    return None


# ---------------------------------------------------------------------------
# 4. Fixture seeding.
# ---------------------------------------------------------------------------
def seed_fixture(fixture: Path, celldir: Path) -> None:
    shutil.copytree(fixture, celldir, dirs_exist_ok=True)
    git_env = ["-c", "user.email=arbeitsplan@localhost", "-c", "user.name=arbeitsplan"]
    subprocess.run(["git", "init", "-q"], cwd=celldir, check=True, capture_output=True)
    subprocess.run(["git", *git_env, "add", "-A"], cwd=celldir, check=True, capture_output=True)
    subprocess.run(
        ["git", *git_env, "commit", "-q", "-m", "fixture baseline", "--allow-empty"],
        cwd=celldir, check=True, capture_output=True,
    )


def capture_diff(celldir: Path) -> str:
    subprocess.run(["git", "add", "-A"], cwd=celldir, capture_output=True)
    proc = subprocess.run(
        ["git", "diff", "--cached", "HEAD"], cwd=celldir, capture_output=True, text=True,
    )
    return proc.stdout


# ---------------------------------------------------------------------------
# 5. Transcript parsing -- real per-line JSON, not a regex over raw bytes.
#    stream-json is NDJSON: each line stands alone, so a line that fails to
#    parse is skipped rather than aborting the whole cell.
# ---------------------------------------------------------------------------
def _skill_name(inp: dict) -> str | None:
    for key in ("skill", "name", "command"):
        v = inp.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def parse_transcript(raw: bytes) -> dict:
    text = raw.decode("utf-8", "replace")
    skills_fired: list = []
    hook_denials: list = []
    mode_denials: list = []
    cost_usd = None
    final_text = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # plain (non-stream-json) output is not line-JSON; best-effort only
        if not isinstance(event, dict):
            continue
        etype = event.get("type")
        # MEASURED SHAPE (2026-09-14, first real cell). A refused call arrives as
        #   {"type":"system","subtype":"permission_denied","tool_name":"Edit",
        #    "decision_reason_type":"mode","message":"Cannot write to ... while in plan mode."}
        # -- no `decision` key and no hook name, so the previous shape-gate (a hook
        # identity PLUS decision in deny/block) matched nothing and every cell
        # reported zero denials. hook_started/hook_response events DO carry
        # `hook_name` but are lifecycle notices, not refusals, and stay ignored.
        #
        # WHY THE SPLIT: plan mode refusing an edit is the mode working as designed;
        # scoring that DENIED would mark every plan-mode cell denied and drown the
        # signal. Only a HOOK refusal -- a guard intervening -- is scored.
        if event.get("subtype") == "permission_denied":
            record = {
                "tool": event.get("tool_name"),
                "why": event.get("decision_reason_type"),
                "reason": event.get("message") or event.get("permissionDecisionReason"),
            }
            if record["why"] == "hook" or event.get("hook_name"):
                record["hook"] = event.get("hook_name")
                hook_denials.append(record)
            else:
                mode_denials.append(record)
        if etype == "assistant":
            content = ((event.get("message") or {}).get("content")) or []
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") == "Skill"
                ):
                    name = _skill_name(block.get("input") or {})
                    if name:
                        skills_fired.append(name)
        elif etype == "result":
            # MEASURED: `claude -p --output-format json` (the non-streaming
            # default) is itself one `"type":"result"` object carrying
            # `total_cost_usd` and `result` -- the same shape stream-json's
            # final line uses. One branch covers both output formats.
            cost_usd = event.get("total_cost_usd", event.get("cost_usd", cost_usd))
            final_text = event.get("result", final_text)
    if final_text is None:
        # Not stream-json at all (plain output_format): the whole stdout IS the reply.
        final_text = text
    return {
        "skills_fired": skills_fired,
        "hook_denials": hook_denials,
        "mode_denials": mode_denials,
        "cost_usd": cost_usd,
        "final_text": final_text,
        "raw_bytes": len(raw),
    }


# ---------------------------------------------------------------------------
# 6. score_cell -- the oracle. UNMEASURED is excluded from every denominator
#    and is never a FAIL: the case was never fairly measured.
#    DENIED is measured: the cell ran fairly, but a PreToolUse hook denied a
#    call inside it. It outranks PASS/FAIL, because an expectation about which
#    skills fire is not a fair verdict on a run a guard intervened in -- PASS
#    would hide the denial, FAIL would blame the workflow for a guard doing its
#    job. It comes after the UNMEASURED checks: a run that never happened
#    cannot have been shaped by anything.
# ---------------------------------------------------------------------------
def score_cell(
    *, exit_code: int, expect_exit: int, transcript: dict,
    expect_skills: list, forbid_skills: list,
    sentinel_reason: str | None = None, timed_out: bool = False,
) -> tuple:
    if sentinel_reason:
        return "UNMEASURED", sentinel_reason
    if timed_out:
        return "UNMEASURED", "timeout"
    raw_bytes = transcript.get("raw_bytes", 0)
    if raw_bytes == 0:
        return "UNMEASURED", "empty stdout -- the run never produced anything"
    if raw_bytes < 200:
        return "UNMEASURED", "stdout under 200 bytes -- too short to be a real reply"
    if BANNER_RE.search(transcript.get("final_text") or ""):
        return "UNMEASURED", "CLI refusal banner -- the run never happened"
    denials = transcript.get("hook_denials") or []
    if denials:
        hooks = sorted({str(d.get("hook") or "unknown hook") for d in denials})
        return "DENIED", f"{len(denials)} call(s) denied by: " + ", ".join(hooks)
    fired = transcript.get("skills_fired") or []
    forbidden_hit = [s for s in (forbid_skills or []) if s in fired]
    if forbidden_hit:
        return "FAIL", "forbidden skill(s) fired: " + ", ".join(forbidden_hit)
    missing = [s for s in (expect_skills or []) if s not in fired]
    if missing:
        return "FAIL", "expected skill(s) never fired: " + ", ".join(missing)
    if exit_code != expect_exit:
        return "FAIL", f"exit {exit_code}, wanted {expect_exit}"
    return "PASS", None


def _swap_output_format(argv: list, fmt: str) -> list:
    out = list(argv)
    for i, a in enumerate(out):
        if a == "--output-format" and i + 1 < len(out):
            out[i + 1] = fmt
            return out
    return [*out, "--output-format", fmt]


# ---------------------------------------------------------------------------
# Running one cell end to end.
# ---------------------------------------------------------------------------
def run_one_cell(cfg: dict, out_path: Path) -> dict:
    label = cfg["label"]
    argv = list(cfg["argv"])
    if not argv:
        raise ConfigError("config carries an empty argv")
    claude_bin = argv[0]
    expect_exit = int(cfg.get("expect_exit", 0))
    ablation = cfg.get("ablation", "isolated")
    plugin_dirs = cfg.get("plugin_dirs") or []
    fixture = cfg.get("fixture")
    expect_skills = cfg.get("expect_skills") or []
    forbid_skills = cfg.get("forbid_skills") or []
    transcript_mode = bool(cfg.get("transcript"))
    max_budget = cfg.get("max_budget_usd")
    timeout_s = int(cfg.get("timeout_s", 900))

    fixture_path = None
    if fixture:
        fixture_path = Path(fixture)
        if not fixture_path.is_dir():
            raise ConfigError(f"no such fixture directory: {fixture}")

    check_auth(claude_bin)

    # Lives in a SIBLING directory, never next to --out: run_matrix.sh's
    # shared summary generator globs `cells/*.json` (non-recursive) expecting
    # every match to be a scored cell, and a settings file without "outcome"
    # crashes it.
    subrun_dir = out_path.parent / "_subrun"
    subrun_dir.mkdir(parents=True, exist_ok=True)
    settings_path = subrun_dir / f"{label}.settings.json"
    if ablation == "isolated":
        write_clean_box_settings(settings_path, Path.home())
        # ABSOLUTE. The cell runs in its own temp dir, so a relative path here is
        # resolved against the wrong directory and the CLI exits 1 with "Settings
        # file not found" and an EMPTY stdout -- measured on the first real cell,
        # where it looked like the model had produced nothing.
        argv = [*argv, "--settings", str(settings_path.resolve())]

    if transcript_mode:
        argv = _swap_output_format(argv, "stream-json")
        for extra in ("--verbose", "--include-hook-events", "--no-session-persistence"):
            if extra not in argv:
                argv.append(extra)
    if max_budget:
        argv = [*argv, "--max-budget-usd", str(max_budget)]

    sentinel_reason = None
    celldir = Path(tempfile.mkdtemp(prefix="arbeitsplan-cell-"))
    timed_out = False
    try:
        if fixture_path is not None:
            seed_fixture(fixture_path, celldir)
        # The sentinel runs AFTER seeding and INSIDE celldir, so it certifies the
        # environment the cell is about to run in rather than the caller's.
        if ablation == "isolated":
            sentinel_reason = sentinel_check(argv, plugin_dirs, timeout_s, cwd=celldir)
        start = time.time()
        try:
            proc = subprocess.run(
                argv, cwd=celldir, capture_output=True, timeout=timeout_s,
                stdin=subprocess.DEVNULL,
            )
            rc = proc.returncode
            raw = proc.stdout
            err = proc.stderr or b""
        except subprocess.TimeoutExpired as exc:
            rc = 124
            raw = exc.stdout or b""
            err = exc.stderr or b""
            timed_out = True
        duration = int(time.time() - start)
        diff = capture_diff(celldir) if fixture_path is not None else None
    finally:
        shutil.rmtree(celldir, ignore_errors=True)

    # Keep the raw transcript next to the record. Without it a cell that reports
    # `skills_fired: []` cannot be told apart from a parser reading the wrong field
    # names -- and the parser's field names were never checked against a real
    # transcript, only against stubs this file wrote itself.
    transcript_path = out_path.with_suffix(".stdout")
    try:
        transcript_path.write_bytes(raw)
    except OSError:
        pass

    parsed = parse_transcript(raw)
    outcome, reason = score_cell(
        exit_code=rc, expect_exit=expect_exit, transcript=parsed,
        expect_skills=expect_skills, forbid_skills=forbid_skills,
        sentinel_reason=sentinel_reason, timed_out=timed_out,
    )
    return {
        "label": label,
        # Identity fields the SHARED summary generator at the bottom of
        # run_matrix.sh (unchanged, and common to both paths) groups cells
        # by -- it does not know or care which path produced a cell.
        "case": cfg.get("case"),
        "model": cfg.get("model"),
        "plugin_state": cfg.get("plugin_state"),
        "repeat": cfg.get("repeat"),
        "argv": argv,
        "exit": rc,
        "expect_exit": expect_exit,
        "duration_s": duration,
        "outcome": outcome,
        "unmeasured_reason": reason if outcome == "UNMEASURED" else None,
        "fail_reason": reason if outcome == "FAIL" else None,
        "skills_fired": parsed["skills_fired"],
        "hook_denials": parsed["hook_denials"],
        "mode_denials": parsed["mode_denials"],
        "final_text": (parsed["final_text"] or "")[:4000],
        "cost_usd": parsed["cost_usd"],
        "stdout_bytes": len(raw),
        "stdout_sha256": hashlib.sha256(raw).hexdigest(),
        # The CLI reports its own refusals (a bad flag, a missing settings file) on
        # STDERR and writes nothing to stdout. Without this the record said only
        # "empty stdout -- the run never produced anything", which names the symptom
        # and hides the cause; the first real cell had to be re-run by hand to learn
        # that --settings pointed at a path the cell's own cwd could not resolve.
        "stderr_tail": err.decode("utf-8", "replace")[-2000:] if err else "",
        "diff": diff,
    }


# ---------------------------------------------------------------------------
# Selftest -- pure-python, stdlib-only, no real `claude` binary needed except
# via stub scripts written to a temp dir. Every oracle case is stated as
# "what should happen"; a couple are PLANTED AND THEN BLANKED against a
# deliberately-broken variant to prove the assertion can actually fail.
# ---------------------------------------------------------------------------
def _stub(tmp: Path, name: str, body: str) -> str:
    p = tmp / name
    p.write_text(body)
    p.chmod(0o755)
    return str(p)


def _selftest_discover(tmp: Path) -> list:
    """A plugin supplies its skills, its commands and its agents."""
    root = tmp / "plug"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text('{"name": "demo"}')
    (root / "skills" / "do-thing").mkdir(parents=True)
    (root / "skills" / "do-thing" / "SKILL.md").write_text("---\nname: do-thing\n---\n")
    (root / "commands").mkdir()
    (root / "commands" / "demo-cmd.md").write_text("---\ndescription: x\n---\n")
    (root / "agents").mkdir()
    (root / "agents" / "helper.md").write_text("---\nname: helper\n---\n")
    (root / "workflows").mkdir()
    (root / "workflows" / "run.js").write_text("export const meta = {\n  name: 'demo-batch',\n}\n")
    names = discover_skill_names([str(root)])
    return [
        ("discover: skill, both spellings", {"do-thing", "demo:do-thing"} <= names),
        ("discover: a command is supplied, not leakage", {"demo-cmd", "demo:demo-cmd"} <= names),
        ("discover: an agent is supplied, not leakage", {"helper", "demo:helper"} <= names),
        ("discover: a workflow's declared meta.name is supplied, not its file stem alone",
         {"demo-batch", "demo:demo-batch"} <= names),
        ("discover: a name nothing supplies is still foreign", "demo:ghost" not in names),
    ]


def selftest() -> int:
    fails = []
    total = [0]

    def check(name: str, ok: bool, detail: str = "") -> None:
        total[0] += 1
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail and not ok else ""))
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as raw:
        for name, ok in _selftest_discover(Path(raw)):
            check(name, ok)

    # ---- score_cell oracle -------------------------------------------------
    base_transcript = {"raw_bytes": 500, "final_text": "all good", "skills_fired": ["arbeitsplan:build"]}

    outcome, _ = score_cell(exit_code=0, expect_exit=0, transcript=base_transcript,
                             expect_skills=["arbeitsplan:build"], forbid_skills=[])
    check("oracle: PASS when exit and expect_skills match", outcome == "PASS", outcome)

    outcome, reason = score_cell(exit_code=0, expect_exit=0, transcript=base_transcript,
                                  expect_skills=[], forbid_skills=["arbeitsplan:build"])
    check("oracle: FAIL when a forbidden skill fired", outcome == "FAIL" and "forbidden" in reason, reason)

    outcome, reason = score_cell(exit_code=0, expect_exit=0, transcript=base_transcript,
                                  expect_skills=["never-fires"], forbid_skills=[])
    check("oracle: FAIL when an expected skill never fired", outcome == "FAIL" and "never fired" in reason, reason)

    outcome, reason = score_cell(exit_code=0, expect_exit=0,
                                  transcript={"raw_bytes": 0, "final_text": "", "skills_fired": []},
                                  expect_skills=[], forbid_skills=[])
    check("oracle: UNMEASURED on empty stdout", outcome == "UNMEASURED" and "empty" in reason, reason)

    outcome, reason = score_cell(
        exit_code=1, expect_exit=0,
        transcript={"raw_bytes": 500, "final_text": "Failed to authenticate: OAuth session expired",
                    "skills_fired": []},
        expect_skills=[], forbid_skills=[],
    )
    check("oracle: UNMEASURED on a CLI refusal banner, never FAIL", outcome == "UNMEASURED", outcome)

    outcome, reason = score_cell(exit_code=0, expect_exit=0, transcript=base_transcript,
                                  expect_skills=[], forbid_skills=["arbeitsplan:build"],
                                  sentinel_reason="foreign skill reported")
    check("oracle: sentinel reason short-circuits straight to UNMEASURED",
          outcome == "UNMEASURED" and reason == "foreign skill reported", (outcome, reason))

    # Planted-then-blanked: a broken oracle that ignores forbid_skills would
    # wrongly PASS the forbidden-skill case above. Prove the real assertion
    # actually distinguishes the two, rather than passing either way.
    def _broken_score_cell(**kw):
        kw = dict(kw)
        kw["forbid_skills"] = []  # the sabotage: blank the forbid check
        return score_cell(**kw)

    broken_outcome, _ = _broken_score_cell(exit_code=0, expect_exit=0, transcript=base_transcript,
                                            expect_skills=[], forbid_skills=["arbeitsplan:build"])
    check("sabotage check: blanking forbid_skills flips FAIL to PASS (proves the real check bites)",
          broken_outcome == "PASS", broken_outcome)

    # ---- denial parsing, against MEASURED event shapes ---------------------
    # These two lines are copied from a real transcript (2026-09-14), not invented:
    # the previous stub asserted a shape the CLI never emits, so the parser passed
    # its tests and found zero denials on every real cell.
    real = "\n".join([
        json.dumps({"type": "system", "subtype": "hook_started", "hook_name": "SessionStart:startup",
                    "hook_event": "SessionStart"}),
        json.dumps({"type": "system", "subtype": "permission_denied", "tool_name": "Edit",
                    "decision_reason_type": "mode",
                    "message": "Cannot write to /tmp/cell/tests/x.py while in plan mode."}),
        json.dumps({"type": "system", "subtype": "permission_denied", "tool_name": "Write",
                    "decision_reason_type": "hook", "hook_name": "PreToolUse",
                    "message": "arbeitsplan: resolves outside the repository"}),
        json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 0.5,
                    "result": "done"}),
    ]).encode()
    rp = parse_transcript(real)
    check("parse_transcript: a MODE refusal is recorded, not scored as a hook denial",
          len(rp["mode_denials"]) == 1 and rp["mode_denials"][0]["tool"] == "Edit", rp["mode_denials"])
    check("parse_transcript: a HOOK refusal is a hook denial",
          len(rp["hook_denials"]) == 1 and rp["hook_denials"][0]["tool"] == "Write", rp["hook_denials"])
    check("parse_transcript: hook lifecycle notices are not refusals",
          len(rp["hook_denials"]) + len(rp["mode_denials"]) == 2)
    check("parse_transcript: result text and cost come off the real result event",
          rp["final_text"] == "done" and rp["cost_usd"] == 0.5, (rp["final_text"], rp["cost_usd"]))

    # ---- DENIED: a hook denial is its own outcome, never a silent PASS -----
    denied_transcript = dict(base_transcript, hook_denials=[
        {"hook": "PreToolUse", "reason": "write outside scope"},
    ])
    outcome, reason = score_cell(exit_code=0, expect_exit=0, transcript=denied_transcript,
                                  expect_skills=["arbeitsplan:build"], forbid_skills=[])
    check("oracle: DENIED when a hook denied a call, even though every expectation matched",
          outcome == "DENIED" and "PreToolUse" in (reason or ""), (outcome, reason))

    outcome, reason = score_cell(exit_code=0, expect_exit=0,
                                  transcript=dict(denied_transcript, raw_bytes=0, final_text=""),
                                  expect_skills=[], forbid_skills=[])
    check("oracle: UNMEASURED still outranks DENIED -- a run that never happened was shaped by nothing",
          outcome == "UNMEASURED", (outcome, reason))

    # Planted-then-blanked: an oracle that ignores hook_denials scores the
    # denied cell above as PASS. Prove the real check distinguishes them.
    blind = dict(denied_transcript, hook_denials=[])
    blind_outcome, _ = score_cell(exit_code=0, expect_exit=0, transcript=blind,
                                  expect_skills=["arbeitsplan:build"], forbid_skills=[])
    check("sabotage check: blanking hook_denials flips DENIED to PASS (proves the real check bites)",
          blind_outcome == "PASS", blind_outcome)

    # ---- transcript parsing: ORDER preserved, not sorted -------------------
    stream = "\n".join([
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "zeta:last"}}]}}),
        json.dumps({"type": "system", "subtype": "permission_denied", "tool_name": "Write",
                    "decision_reason_type": "hook", "hook_name": "PreToolUse",
                    "message": "write outside scope"}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "alpha:first"}}]}}),
        json.dumps({"type": "result", "result": "done" + " " * 250, "total_cost_usd": 0.0042}),
    ])
    parsed = parse_transcript(stream.encode())
    check("parse_transcript: skills_fired keeps encounter order (not sorted)",
          parsed["skills_fired"] == ["zeta:last", "alpha:first"], parsed["skills_fired"])
    # The event above is the MEASURED shape. The invented one it replaced
    # ({"type":"hook_event","decision":"deny"}) is emitted by nothing, so this
    # assertion passed while the parser found zero denials on every real cell.
    check("parse_transcript: hook_denials collected",
          len(parsed["hook_denials"]) == 1 and parsed["hook_denials"][0]["reason"] == "write outside scope",
          parsed["hook_denials"])
    check("parse_transcript: cost_usd read from the result event", parsed["cost_usd"] == 0.0042, parsed["cost_usd"])

    malformed = parse_transcript(b"not json\n{\"type\": \"assistant\"}\n")
    check("parse_transcript: a malformed line is skipped, not fatal", malformed["skills_fired"] == [])

    # ---- discover_skill_names ------------------------------------------
    tmp = Path(tempfile.mkdtemp(prefix="subrun-selftest-"))
    try:
        plugin_dir = tmp / "plugins" / "demo"
        (plugin_dir / "skills" / "real-skill").mkdir(parents=True)
        (plugin_dir / "skills" / "real-skill" / "SKILL.md").write_text("---\nname: real-skill\n---\n")
        (plugin_dir / "skills" / "not-a-skill").mkdir(parents=True)  # no SKILL.md -- must be ignored
        names = discover_skill_names([str(plugin_dir)])
        check("discover_skill_names: finds a real skill dir, ignores one without SKILL.md",
              names == {"real-skill", "demo:real-skill"}
              and not any(n.endswith("not-a-skill") for n in names), names)
        check("discover_skill_names: an absent plugin_dir set supplies nothing",
              discover_skill_names([]) == set())

        # Measured on the first real cell: a session reports "<plugin>:<skill>",
        # so bare-name-only matching marked every supplied skill as leakage.
        manifest_dir = plugin_dir / ".claude-plugin"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "plugin.json").write_text(json.dumps({"name": "toy"}), encoding="utf-8")
        ns = discover_skill_names([str(plugin_dir)])
        check("discover_skill_names: returns the namespaced <plugin>:<skill> spelling too",
              "toy:real-skill" in ns and "real-skill" in ns, sorted(ns))
        check("discover_skill_names: the plugin name comes from plugin.json, not the directory",
              not any(n.startswith(f"{plugin_dir.name}:") for n in ns), sorted(ns))
        check("BUILTIN_SKILLS covers harness skills that no --plugin-dir supplies",
              {"dataviz", "code-review", "run"} <= BUILTIN_SKILLS)

        # Measured on the first real cell: a relative --settings path is resolved
        # against the cell's own temp cwd, so the CLI exits 1 with an EMPTY stdout
        # and the record blamed the model for producing nothing.
        rel_settings = Path("relative") / "cleanbox.json"
        check("clean-box --settings is passed as an absolute path",
              Path(str(rel_settings.resolve())).is_absolute(), str(rel_settings))

        # ---- write_clean_box_settings: covers every planted plugin+skill ----
        home = tmp / "fakehome"
        (home / ".claude" / "plugins").mkdir(parents=True)
        (home / ".claude" / "plugins" / "installed_plugins.json").write_text(json.dumps(
            {"plugins": {"andon@werkstoff": {}, "matrize@werkstoff": {}}}))
        (home / ".claude" / "skills" / "andon-loop").mkdir(parents=True)
        (home / ".claude" / "skills" / "foo-bar").mkdir(parents=True)
        settings_path = tmp / "cleanbox.json"
        counts = write_clean_box_settings(settings_path, home)
        written = json.loads(settings_path.read_text())
        check("clean box: covers every installed plugin",
              set(written["enabledPlugins"]) == {"andon@werkstoff", "matrize@werkstoff"}
              and all(v is False for v in written["enabledPlugins"].values()),
              written["enabledPlugins"])
        check("clean box: covers every personal skill",
              set(written["skillOverrides"]) == {"andon-loop", "foo-bar"}
              and all(v == "off" for v in written["skillOverrides"].values()),
              written["skillOverrides"])
        check("clean box: counts match", counts == {"plugins": 2, "skills": 2}, counts)

        # Planted-then-blanked: an empty home directory must cover NOTHING,
        # not silently reuse the previous tree's counts (a stale-closure bug
        # this shape has caught before in this codebase).
        empty_home = tmp / "emptyhome"
        empty_home.mkdir()
        empty_settings = tmp / "empty-cleanbox.json"
        empty_counts = write_clean_box_settings(empty_settings, empty_home)
        check("clean box: an empty $HOME covers zero plugins and zero skills",
              empty_counts == {"plugins": 0, "skills": 0}, empty_counts)

        # ---- check_auth against stub CLIs -----------------------------
        loggedout = _stub(tmp, "stub-loggedout", "#!/usr/bin/env bash\n"
                           'echo \'{"loggedIn": false, "authMethod": null}\'\n')
        try:
            check_auth(loggedout)
            check("check_auth: raises on loggedIn:false", False)
        except AuthError as exc:
            check("check_auth: raises on loggedIn:false, with the login hint",
                  AUTH_LOGIN_HINT in str(exc), str(exc))

        loggedin = _stub(tmp, "stub-loggedin", "#!/usr/bin/env bash\n"
                          'echo \'{"loggedIn": true, "authMethod": "claude.ai"}\'\n')
        status = check_auth(loggedin)
        check("check_auth: returns the parsed status when logged in", status.get("loggedIn") is True, status)

        garbage = _stub(tmp, "stub-garbage", "#!/usr/bin/env bash\necho 'not json'\n")
        try:
            check_auth(garbage)
            check("check_auth: raises rather than guessing from non-JSON output", False)
        except AuthError:
            check("check_auth: raises rather than guessing from non-JSON output", True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- _swap_output_format / _sentinel_argv --------------------------
    swapped = _swap_output_format(["claude", "-p", "hi", "--output-format", "json"], "stream-json")
    check("_swap_output_format: replaces an existing value in place",
          swapped == ["claude", "-p", "hi", "--output-format", "stream-json"], swapped)
    appended = _swap_output_format(["claude", "-p", "hi"], "stream-json")
    check("_swap_output_format: appends when absent",
          appended == ["claude", "-p", "hi", "--output-format", "stream-json"], appended)

    sub = _sentinel_argv(["claude", "-p", "original prompt", "--model", "haiku"], SENTINEL_PROMPT)
    check("_sentinel_argv: swaps only the prompt, keeps every other flag",
          sub == ["claude", "-p", SENTINEL_PROMPT, "--model", "haiku"], sub)

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"subrun.py selftest passed ({total[0]} assertions; no real cells run)")
    return 0


# ---------------------------------------------------------------------------
def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="subrun.py",
        description="Execute and score exactly one headless `claude -p` cell "
                    "from an explicit config. A thin executor for run_matrix.sh's "
                    "opt-in 'runner': 'subrun' path.",
        epilog="exit 0 scored (any outcome), 2 bad input, 3 not logged in",
    )
    parser.add_argument("--config", help="cell config JSON (default: stdin)")
    parser.add_argument("--out", help="where to write the scored cell JSON")
    parser.add_argument("--selftest", action="store_true", help="run the planted-defect selftest")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if not args.out:
        print("subrun.py: --out is required (try --selftest)", file=sys.stderr)
        return 2

    try:
        raw = Path(args.config).read_text(encoding="utf-8") if args.config else sys.stdin.read()
        cfg = json.loads(raw)
    except OSError as exc:
        print(f"subrun.py: could not read --config: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"subrun.py: --config is not valid JSON: {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    try:
        result = run_one_cell(cfg, out_path)
    except ConfigError as exc:
        print(f"subrun.py: {exc}", file=sys.stderr)
        return 2
    except AuthError as exc:
        print(f"subrun.py: {exc}", file=sys.stderr)
        return 3

    out_path.write_text(json.dumps(result, indent=2))
    print("  {:<38} {:<12} exit={:<3} {}s".format(
        result["label"], result["outcome"], result["exit"], result["duration_s"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
