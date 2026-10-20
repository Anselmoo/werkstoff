#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Calibration for the fix pass's hook post-check outside werkstoff -- follow-up to issue #117.

build_fix_args.py baked `verify_hooks_deny.py <plugin> --fixtures-root test/plugins/fixtures` into
every hook-script fix. Outside werkstoff that directory does not exist, the verifier exits 2
("violating fixture not found"), the post-check fails on a gap that is not a regression, the lock
is kept, and fix.js re-dispatches the remediator on a non-regression. Now the probe is baked only
when a fixture exists to run it against; otherwise it is skipped by name -- in stderr and in
fix-check.json `postChecks.skipped` -- never fatal, never silent. Each case plants the failure it
names; the last section mutates each defence in a COPY of the source and requires the matching
case to go red (a check that cannot fail is not a check).

 T1 no root          -- a root that does not exist: no probe command, one skipped entry naming the root.
 T2 empty root       -- a root with no fixture: skipped, and the reason names hook-violation-<plugin>.
 T3 plugin fixture   -- hook-violation-<plugin>/ present: probe baked with the absolute root, and a root
                        containing a space survives shlex.split as one argument.
 T4 generic fixture  -- only ledger-missing-blast-radius/ present (werkstoff's andon, cli-scaffold): baked.
 T5 resolution       -- a relative --fixtures-root resolves against the repository root, not the cwd.
 T6 report           -- post_fix_check.py carries skippedChecks into fix-check.json, still clean.
 T7 agreement        -- the vendored verifier does exit 2 exactly where hook_probe_gap reports a gap.
 T8 absolute only    -- a relative root handed to post_checks is refused by name, not used.
 T9 main end to end  -- build_fix_args.main() in a repository with no fixtures: lock opened, skip recorded.

Usage: test_fix_post_checks.py            (exit 0 green, 1 red)
Exit: 0 green; 1 any check red.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # `uv run` has no -B; keep the installed plugin copy free of __pycache__ (#88)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nacharbeit_common as nc  # noqa: E402

LABEL = "hook denies and stays inert"
HOOK = "plugins/demo/hooks/guard.py"
PLUGIN_DIR = "plugins/demo"
BFA = HERE / "build_fix_args.py"
PFC = HERE / "post_fix_check.py"


def load_bfa(mutate: tuple[str, str] | None = None):
    """build_fix_args.py as a module; `mutate` = (needle, replacement) is applied to a COPY of its source."""
    src = BFA.read_text(encoding="utf-8")
    if mutate is not None:
        needle, repl = mutate
        if src.count(needle) != 1:
            raise LookupError(f"sabotage needle not found exactly once in build_fix_args.py: {needle!r}")
        src = src.replace(needle, repl)
    mod = type(sys)("bfa_under_test")
    mod.__dict__["__file__"] = str(BFA)
    sys.modules["bfa_under_test"] = mod
    exec(compile(src, str(BFA), "exec"), mod.__dict__)
    return mod


def probe_cmds(checks: list[dict]) -> list[dict]:
    return [c for c in checks if c["label"] == LABEL]


def hook_checks(bfa, root: Path):
    skipped: list[dict] = []
    checks = bfa.post_checks(HOOK, "hookscript", PLUGIN_DIR, root, skipped=skipped)
    return checks, skipped


def t1_no_root(bfa, td: Path) -> str | None:
    root = td / "t1" / "does-not-exist"
    checks, skipped = hook_checks(bfa, root)
    if probe_cmds(checks):
        return "a probe command was baked against a root that does not exist -- it would exit 2 on every pass"
    if len(skipped) != 1 or skipped[0].get("label") != LABEL or root.as_posix() not in skipped[0].get("reason", ""):
        return f"expected one skipped entry naming the missing root, got {skipped}"
    return None


def t2_empty_root(bfa, td: Path) -> str | None:
    root = td / "t2"
    root.mkdir()
    checks, skipped = hook_checks(bfa, root)
    if probe_cmds(checks):
        return "a probe command was baked against a root with no fixture"
    if len(skipped) != 1 or "hook-violation-demo" not in skipped[0].get("reason", ""):
        return f"expected one skipped entry naming hook-violation-demo, got {skipped}"
    return None


def t3_plugin_fixture(bfa, td: Path) -> str | None:
    root = td / "t3 with space"
    (root / "hook-violation-demo").mkdir(parents=True)
    checks, skipped = hook_checks(bfa, root)
    cmds = probe_cmds(checks)
    if len(cmds) != 1 or skipped:
        return f"expected the probe baked and nothing skipped, got {len(cmds)} probe(s), skipped {skipped}"
    argv = shlex.split(cmds[0]["cmd"])
    if argv[argv.index("--fixtures-root") + 1] != root.as_posix():
        return f"the baked --fixtures-root does not survive shlex.split as one argument: {argv}"
    if PLUGIN_DIR not in argv:
        return f"the plugin dir is missing from the baked argv: {argv}"
    return None


def t4_generic_fixture(bfa, td: Path) -> str | None:
    root = td / "t4"
    (root / "ledger-missing-blast-radius").mkdir(parents=True)
    checks, skipped = hook_checks(bfa, root)
    if len(probe_cmds(checks)) != 1 or skipped:
        return f"the generic fixture is what verify_hooks_deny falls back to; expected the probe baked, got skipped {skipped}"
    return None


def t5_resolution(bfa, td: Path) -> str | None:
    root, elsewhere = td / "t5-root", td / "t5-cwd"
    root.mkdir()
    elsewhere.mkdir()
    here = Path.cwd()
    try:
        os.chdir(elsewhere)
        got = bfa.resolve_fixtures_root(root, Path("rel/fixtures"))
        absolute = bfa.resolve_fixtures_root(root, td / "abs")
    finally:
        os.chdir(here)
    if got != root / "rel" / "fixtures":
        return f"a relative root resolved to {got}, not {root / 'rel' / 'fixtures'}"
    if absolute != td / "abs":
        return f"an absolute root was changed to {absolute}"
    return None


def run_post_fix_check(script: Path, repo: Path) -> tuple[int, str]:
    state = repo / nc.DEFAULT_STATE_DIR
    state.mkdir(parents=True)
    item = {"file": HOOK, "plugin": "demo", "postChecks": [], "entries": [],
            "skippedChecks": [{"label": LABEL, "reason": "no hook-violation-demo/ under /nowhere"}]}
    (state / "fix-args.json").write_text(json.dumps({"items": [item]}), encoding="utf-8")
    (state / "fix_scope.json").write_text("{}", encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(script), "--repo-root", str(repo), "--release-lock",
                        "--contract-diff", str(repo / "no-contract-diff.py")],
                       capture_output=True, text=True, timeout=120, cwd=repo)
    return r.returncode, r.stderr


def t6_report(td: Path, script: Path = PFC) -> str | None:
    repo = td / "t6"
    repo.mkdir()
    rc, err = run_post_fix_check(script, repo)
    if rc != 0:
        return f"post_fix_check exited {rc}; a skipped probe must not unclean the pass: {err[-200:]}"
    report = json.loads((repo / nc.DEFAULT_STATE_DIR / "fix-check.json").read_text(encoding="utf-8"))
    want = [{"file": HOOK, "label": LABEL, "reason": "no hook-violation-demo/ under /nowhere"}]
    if report.get("postChecks", {}).get("skipped") != want:
        return f"fix-check.json postChecks.skipped is {report.get('postChecks', {}).get('skipped')!r}, expected {want}"
    if report.get("clean") is not True or report.get("lockReleased") is not True:
        return f"expected clean and lockReleased, got clean={report.get('clean')} lockReleased={report.get('lockReleased')}"
    if "WARN post-check skipped" not in err:
        return f"the skip is not on stderr: {err[-200:]!r}"
    return None


def t7_agreement(bfa, td: Path) -> str | None:
    plug = td / "t7" / "demo"
    (plug / "hooks").mkdir(parents=True)
    (plug / "hooks" / "g.py").write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
    (plug / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Edit", "hooks": [{"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/g.py"}]}]}}), encoding="utf-8")
    cwd = td / "t7-cwd"  # the verifier looks in the cwd first; keep it free of any fixture
    cwd.mkdir()
    empty, full = td / "t7-empty", td / "t7-full"
    empty.mkdir()
    (full / "hook-violation-demo").mkdir(parents=True)
    (full / "hook-violation-demo" / "README").write_text("x\n", encoding="utf-8")
    msg = "violating fixture not found"
    verifier = HERE / "verify_hooks_deny.py"
    for root, gap_expected in ((empty, True), (full, False)):
        r = subprocess.run([sys.executable, "-B", str(verifier), str(plug), "--fixtures-root", str(root)],
                           capture_output=True, text=True, timeout=120, cwd=cwd)
        said = msg in r.stderr
        gap = bfa.hook_probe_gap(f"plugins/{plug.name}", root)
        if said != gap_expected or (gap is not None) != gap_expected:
            return (f"root {root.name}: verifier said {msg!r}={said}, hook_probe_gap reported gap={gap is not None}, "
                    f"expected both {gap_expected} (rc {r.returncode}, stderr {r.stderr[-120:]!r})")
        if gap_expected and r.returncode != 2:
            return f"the verifier exited {r.returncode} on a missing fixture, expected 2"
    return None


def t8_absolute_only(bfa, td: Path) -> str | None:
    try:
        bfa.post_checks(HOOK, "hookscript", PLUGIN_DIR, Path("test/plugins/fixtures"), skipped=[])
    except ValueError as e:
        return None if "must be absolute" in str(e) else f"ValueError without the reason: {e}"
    return "a relative fixtures root was accepted; the gap check and the verifier would look in different places"


def minimal_review_state(repo: Path) -> None:
    state = repo / nc.DEFAULT_STATE_DIR
    state.mkdir(parents=True)
    hook = repo / HOOK
    hook.parent.mkdir(parents=True)
    hook.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    backlog = {"fix_tier": "haiku", "file": HOOK, "rule_ids": ["H-DEMO"], "action": "tidy", "severity": "minor"}
    for name, obj in {
        "synthesis.json": {"perPlugin": [{"backlog": [backlog]}]},
        "findings.json": {"verified": [], "lint": []},
        "routing.json": {"judged": []},
        "args.json": {"corpus": {"skill": {}, "agent": {}}},
        "run.json": {"completed": True, "calibration": {"rounds": [1]}, "runStamp": "2026-01-01T00:00:00Z", "rubricHash": "x"},
    }.items():
        (state / name).write_text(json.dumps(obj), encoding="utf-8")


def t9_main(bfa, td: Path) -> str | None:
    here = Path.cwd()
    results = {}
    for name, with_fixture in (("bare", False), ("fixture", True)):
        repo = td / f"t9-{name}"
        repo.mkdir()
        minimal_review_state(repo)
        if with_fixture:
            (repo / "test" / "plugins" / "fixtures" / "hook-violation-demo").mkdir(parents=True)
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = bfa.main(["--repo-root", str(repo)])
        except Exception as e:
            return f"main() raised {type(e).__name__}: {e} in the {name} repository"
        finally:
            os.chdir(here)
        if rc != 0:
            return f"main() exited {rc} in the {name} repository: {err.getvalue()[-200:]!r}"
        results[name] = (json.loads((repo / nc.DEFAULT_STATE_DIR / "fix-args.json").read_text(encoding="utf-8")), err.getvalue(), repo)
    item = results["bare"][0]["items"][0]
    if probe_cmds(item["postChecks"]) or len(item["skippedChecks"]) != 1:
        return f"bare repository: expected the probe skipped once, got postChecks {item['postChecks']} skippedChecks {item['skippedChecks']}"
    if "WARN post-check skipped" not in results["bare"][1]:
        return "bare repository: the skip is not announced on stderr"
    if not (results["bare"][2] / nc.DEFAULT_STATE_DIR / "fix_scope.json").is_file():
        return "bare repository: the lock was not opened -- a skipped probe must not stop the pass"
    item = results["fixture"][0]["items"][0]
    cmds = probe_cmds(item["postChecks"])
    root = (results["fixture"][2] / "test" / "plugins" / "fixtures").resolve().as_posix()
    if len(cmds) != 1 or item["skippedChecks"] or root not in shlex.split(cmds[0]["cmd"]):
        return f"repository with a fixture: expected the probe baked with the absolute root {root}, got {item['postChecks']} / {item['skippedChecks']}"
    return None


CASES = (("T1 no root", t1_no_root), ("T2 empty root", t2_empty_root), ("T3 plugin fixture", t3_plugin_fixture),
         ("T4 generic fixture", t4_generic_fixture), ("T5 resolution", t5_resolution), ("T7 agreement", t7_agreement),
         ("T8 absolute only", t8_absolute_only), ("T9 main end to end", t9_main))


def run_cases(bfa, td: Path) -> dict[str, str | None]:
    """Every case against `bfa`; T6 runs post_fix_check.py, which is not a build_fix_args mutation target."""
    out: dict[str, str | None] = {}
    td.mkdir(parents=True)
    for name, fn in CASES:
        sub = td / name.split()[0]
        sub.mkdir()
        out[name] = fn(bfa, sub)
    return out


def check_green(td: Path) -> int:
    red = 0
    bfa = load_bfa()
    results = run_cases(bfa, td / "green")
    sub = td / "green" / "T6"
    sub.mkdir()
    results["T6 report"] = t6_report(sub)
    for name in sorted(results):
        if results[name] is not None:
            print(f"RED  {name}: {results[name]}")
            red += 1
        else:
            print(f"     {name}: ok")
    return red


# (label, needle in build_fix_args.py, replacement, the cases that must go red)
MUTATIONS = (
    ("S1 gap check always passes", "    if not fixtures_root.is_absolute():\n        raise ValueError(",
     "    return None\n    if not fixtures_root.is_absolute():\n        raise ValueError(", {"T1 no root", "T2 empty root", "T9 main end to end"}),
    ("S2 skip is dropped silently", '            skipped.append({"label": "hook denies and stays inert", "reason": gap})',
     "            pass", {"T1 no root", "T2 empty root", "T9 main end to end"}),
    ("S3 absolute-path check removed", "    if not fixtures_root.is_absolute():\n        raise ValueError(",
     "    if False:\n        raise ValueError(", {"T8 absolute only"}),
    ("S4 baked root unquoted", "--fixtures-root {shlex.quote(fixtures_root.as_posix())}",
     "--fixtures-root {fixtures_root.as_posix()}", {"T3 plugin fixture"}),
    ("S5 root never resolved", "return arg if arg.is_absolute() else root / arg", "return arg", {"T5 resolution", "T9 main end to end"}),
    ("S6 main passes the unresolved root", "plugin_dir, fixtures_root, skipped=w", "plugin_dir, a.fixtures_root, skipped=w", {"T9 main end to end"}),
)


def sabotage(td: Path) -> int:
    red = 0
    for i, (label, needle, repl, expect) in enumerate(MUTATIONS):
        try:
            mutated = load_bfa((needle, repl))
        except LookupError as e:
            print(f"RED  sabotage {label}: {e}; update the check")
            red += 1
            continue
        results = run_cases(mutated, td / f"sab{i}")
        went_red = {k for k, v in results.items() if v is not None}
        if not expect <= went_red:
            print(f"RED  sabotage {label}: expected {sorted(expect)} to go red, only {sorted(went_red)} did -- that defence is not load-bearing")
            red += 1
        else:
            print(f"     sabotage {label}: {', '.join(sorted(expect))} went red")
    # S7: post_fix_check.py drops the skipped list from the report
    src = PFC.read_text(encoding="utf-8")
    needle = '"postChecks": {"passed": passed, "failed": failed, "skipped": skipped}'
    if src.count(needle) != 1:
        print("RED  sabotage S7: the report line this check blanks is no longer where it was; update the check")
        return red + 1
    scripts = td / "sab-pfc"
    scripts.mkdir()
    shutil.copy(HERE / "nacharbeit_common.py", scripts / "nacharbeit_common.py")
    (scripts / "post_fix_check.py").write_text(src.replace(needle, '"postChecks": {"passed": passed, "failed": failed}'), encoding="utf-8")
    sub = td / "sab-pfc-run"
    sub.mkdir()
    if t6_report(sub, scripts / "post_fix_check.py") is None:
        print("RED  sabotage S7 report drops the skipped list: T6 stayed green -- the report case is not load-bearing")
        red += 1
    else:
        print("     sabotage S7 report drops the skipped list: T6 report went red")
    return red


def main() -> int:
    red = 0
    here = Path.cwd()
    with tempfile.TemporaryDirectory() as t:
        td = Path(t).resolve()
        for check in (check_green, sabotage):
            red += check(td)
    os.chdir(here)
    print("GREEN" if not red else f"RED ({red})")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
