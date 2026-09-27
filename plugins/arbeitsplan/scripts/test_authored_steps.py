#!/usr/bin/env python3
"""End-to-end proof of authored step scripts, one language at a time.

usage: test_authored_steps.py [--only shell,ruby,...]

For every authorable runtime (waves_state.AUTHORABLE) it installs a wave design
whose post-wave script node AUTHORS its step, into a scratch git repository,
then drives the vendored files exactly as a run would:

  install     writes the skeleton, in that language, carrying the stub marker
  verify      refuses the skeleton (it is not a step)
  author      a hand-written stand-in for the author agent fills the file
  verify      syntax-checks it, runs the sample in a scratch worktree, checks
              stdout against output_schema, pins sha256 + contract in state
  show        reports the step `verified`
  guard       the runner may run it -- and may not once the file is edited,
              once the node's contract changes, or before it was ever verified
  broken      a syntax error and an output that breaks the schema are refused
  re-install  keeps the authored step; rewrites a step that is still a stub

A runtime whose interpreter is not on PATH is SKIPPED with its name, never
passed: `skip powershell: pwsh not on PATH`. ARBEITSPLAN_REQUIRE_TOOLCHAINS=1
turns every skip into a failure -- CI sets it, on runners that carry all five.

It also proves the two restated copies agree: the guard's STEP_EXT and
contract_digest against the helper's AUTHORABLE and contract_digest.

Exit: 0 passed, 1 failed. STDLIB ONLY. No network.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_waves
import waves_guard
import waves_state

HERE = Path(__file__).resolve().parent

STEP = ".claude/workflows/rebuild-cli.steps/api-surface"
# The command each runtime's node declares, and a correct body for its step:
# print {"package": <first argument>, "exported": []} and exit 0. Each body also
# drops RAN_MARKER into its working directory -- the side effect a real step
# might have, and the only way to see WHERE the sample ran: verify-step must run
# it in a scratch worktree, so the primary checkout never gets the marker.
RAN_MARKER = ".sample-ran"
LANGS = {
    "shell": (f"bash {STEP}.sh cmd/tool",
              "#!/usr/bin/env bash\nset -euo pipefail\n: > .sample-ran\n"
              "printf '{\"package\": \"%s\", \"exported\": []}\\n' \"$1\"\n"),
    "powershell": (f"pwsh -NoProfile -NonInteractive -File {STEP}.ps1 cmd/tool",
                   "param([string]$Dir)\n"
                   "New-Item -ItemType File -Force .sample-ran | Out-Null\n"
                   "[Console]::Out.WriteLine((@{package = $Dir; exported = @()} | "
                   "ConvertTo-Json -Compress))\n"),
    "ruby": (f"ruby {STEP}.rb cmd/tool",
             "require 'json'\nFile.write('.sample-ran', '')\n"
             "puts JSON.generate({ package: ARGV[0], exported: [] })\n"),
    "node": (f"node {STEP}.mjs cmd/tool",
             "import { writeFileSync } from 'node:fs'\nwriteFileSync('.sample-ran', '')\n"
             "process.stdout.write(JSON.stringify({ package: process.argv[2], exported: [] }) "
             "+ '\\n')\n"),
    "python": (f"python3 {STEP}.py cmd/tool",
               "import json\nimport sys\n\nopen('.sample-ran', 'w').close()\n"
               "print(json.dumps({'package': sys.argv[1], 'exported': []}))\n"),
}
BROKEN_SYNTAX = {"shell": "if then fi (\n", "powershell": "function {\n", "ruby": "def x(\n",
                 "node": "function (\n", "python": "def x(\n"}
WRONG_OUTPUT = {"shell": "echo '{\"pkg\": 1}'\n",
                "powershell": "[Console]::Out.WriteLine('{\"pkg\": 1}')\n",
                "ruby": "puts '{\"pkg\": 1}'\n", "node": "console.log('{\"pkg\": 1}')\n",
                "python": "print('{\"pkg\": 1}')\n"}


def design_for(runtime: str) -> dict:
    d = json.loads((HERE / "fixtures" / "design" / "authored.design.json").read_text())
    node = next(n for n in d["nodes"] if n["id"] == "api-surface")
    node["script"]["runtime"] = runtime
    node["script"]["command"] = LANGS[runtime][0]
    return d


def exe_of(runtime: str) -> str:
    return "pwsh" if runtime == "powershell" else LANGS[runtime][0].split()[0]


def run_case(runtime: str, check) -> None:
    design = design_for(runtime)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
               "GIT_CONFIG_GLOBAL": os.devnull, "ARBEITSPLAN_WAVES_CASEFOLD": "0"}

        def git(*args: str) -> None:
            subprocess.run(["git", "-c", "init.defaultBranch=trunk", *args], cwd=root,
                           env=env, check=True, capture_output=True)

        git("init")
        (root / "README").write_text("scratch\n")
        res = install_waves.install(design, root, [sys.executable], artifact=False, dry=False)
        git("add", "-A")
        git("commit", "-m", "install")
        wf = root / ".claude" / "workflows"
        step = root / f"{STEP}.{waves_state.AUTHORABLE[runtime]['ext']}"
        plan = json.loads((wf / "rebuild-cli.plan.json").read_text())
        cmd = next(n for n in plan["nodes"] if n["id"] == "api-surface")["script"]["command"]
        tag = f"[{runtime}]"

        def helper(*args: str) -> tuple:
            p = subprocess.run([sys.executable, str(wf / "rebuild-cli_state.py"), *args],
                               cwd=root, env=env, capture_output=True, text=True)
            try:
                return p.returncode, json.loads(p.stdout or "null"), p.stderr
            except json.JSONDecodeError:
                return p.returncode, None, p.stdout + p.stderr

        def guard(agent_id: str) -> int:
            return subprocess.run([sys.executable, str(root / ".claude" / "hooks"
                                                       / "rebuild-cli_guard.py"), "--runner"],
                                  input=json.dumps({"tool_name": "Bash", "agent_id": agent_id,
                                                    "tool_input": {"command": cmd}}),
                                  env=env, capture_output=True, text=True).returncode

        def status() -> str:
            _c, shown, _e = helper("show")
            return (shown or {}).get("steps", {}).get("api-surface", {}).get("status", "?")

        check(f"{tag} install writes the skeleton with the stub marker",
              step.is_file() and waves_state.STUB_MARKER in step.read_text()
              and str(step) in res["steps"]["written"], res["steps"])
        book = (wf / "rebuild-cli.md").read_text()
        check(f"{tag} the runbook lists the authored step, its language and its file",
              "## Authored steps" in book and f"| api-surface | {runtime} |" in book
              and step.name in book, book[-600:])
        check(f"{tag} the steps directory is gitignored",
              ".claude/workflows/rebuild-cli.steps/" in (root / ".gitignore").read_text())
        check(f"{tag} the plan names the author agent and the verify template",
              plan.get("authorAgent") == "rebuild-cli-author"
              and "verify-step --node {node}" in plan["helper"].get("verify", ""))
        check(f"{tag} an author agent file is generated, without Bash",
              "\ntools: Read, Write, Edit, Glob, Grep\n" in (
                  root / ".claude" / "agents" / "rebuild-cli-author.md").read_text())
        code, out, err = helper("verify-step", "--node", "api-surface")
        check(f"{tag} verify refuses the skeleton", code == 1 and out
              and waves_state.STUB_MARKER in out["problem"], (code, out, err))
        check(f"{tag} show reports the skeleton as a stub", status() == "stub")
        check(f"{tag} the runner guard denies an unverified step", guard("r0") == 2)

        step.write_text(BROKEN_SYNTAX[runtime])
        code, out, err = helper("verify-step", "--node", "api-surface")
        check(f"{tag} verify refuses a syntax error without running it",
              code == 1 and out and out["problem"].startswith("syntax"), (code, out, err))
        step.write_text(WRONG_OUTPUT[runtime])
        code, out, err = helper("verify-step", "--node", "api-surface")
        check(f"{tag} verify refuses output that breaks output_schema",
              code == 1 and out and "output_schema" in out["problem"], (code, out, err))

        step.write_text(LANGS[runtime][1])
        code, out, err = helper("verify-step", "--node", "api-surface")
        check(f"{tag} verify accepts the written step", code == 0 and out and out["verified"],
              (code, out, err))
        check(f"{tag} show reports it verified", status() == "verified")
        check(f"{tag} the runner guard allows the verified step", guard("r1") == 0)
        check(f"{tag} the sample ran in a scratch worktree, not the primary checkout",
              not (root / RAN_MARKER).exists()
              and len(subprocess.run(["git", "worktree", "list"], cwd=root, capture_output=True,
                                     text=True).stdout.splitlines()) == 1)

        original = step.read_bytes()
        step.write_bytes(original + b"\n")
        check(f"{tag} an edit after verify makes the step stale", status() == "stale")
        check(f"{tag} the runner guard denies the edited step", guard("r2") == 2)
        step.write_bytes(original)
        check(f"{tag} restoring the verified bytes restores the verdict", guard("r3") == 0)

        replanned = copy.deepcopy(plan)
        next(n for n in replanned["nodes"] if n["id"] == "api-surface")["script"]["author"][
            "purpose"] += " Also count them."
        (wf / "rebuild-cli.plan.json").write_text(json.dumps(replanned))
        check(f"{tag} a changed contract makes the step stale", status() == "stale")
        check(f"{tag} the runner guard denies a step verified against an old contract",
              guard("r4") == 2)
        (wf / "rebuild-cli.plan.json").write_text(json.dumps(plan))

        again = install_waves.install(design, root, [sys.executable], artifact=False, dry=False)
        check(f"{tag} re-install keeps the authored step untouched",
              step.read_bytes() == original and str(step) in again["steps"]["kept"])
        step.write_text(waves_state.STUB_MARKER + "\n")
        third = install_waves.install(design, root, [sys.executable], artifact=False, dry=False)
        check(f"{tag} re-install rewrites a step that is still a stub",
              str(step) in third["steps"]["written"] and "Step api-surface of plan rebuild-cli"
              in step.read_text())


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="test_authored_steps.py", description=(
        __doc__ or "").split("\n\n")[0], epilog="exit 0 passed, 1 failed")
    parser.add_argument("--only", help="comma-separated runtimes (default: all)")
    args = parser.parse_args(argv)
    fails: list = []
    skips: list = []

    def check(name: str, cond: bool, detail: object = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)
            if detail != "":
                print(f"       {str(detail)[:400]}")

    check("the guard's step extensions are the helper's",
          waves_guard.STEP_EXT == {k: v["ext"] for k, v in waves_state.AUTHORABLE.items()})
    sample = next(n for n in design_for("python")["nodes"] if n["id"] == "api-surface")
    check("the guard's contract digest is the helper's",
          waves_guard.contract_digest(sample) == waves_state.contract_digest(sample))
    changed = copy.deepcopy(sample)
    changed["output_schema"]["required"] = ["package"]
    check("the contract digest moves when the output schema does",
          waves_state.contract_digest(changed) != waves_state.contract_digest(sample))
    check("every authorable runtime has a template",
          all((HERE.parent / "assets" / "step-templates" / f"step.{v['ext']}").is_file()
              for v in waves_state.AUTHORABLE.values()))
    check("this test covers every authorable runtime", set(LANGS) == set(waves_state.AUTHORABLE))
    # Checkable without pwsh: the rendered parse command is what PowerShell will
    # see. `{{` would be a scriptblock literal that never runs its `exit 1`.
    ps = [a.replace("{exe}", "pwsh").replace("{path}", "x.ps1")
          for a in waves_state.AUTHORABLE["powershell"]["check"]][-1]
    check("the PowerShell parse command has single braces and exits 1 on an error",
          "{{" not in ps and "}}" not in ps and "'x.ps1'" in ps and "exit 1 }" in ps, ps)

    wanted = args.only.split(",") if args.only else sorted(LANGS)
    for runtime in wanted:
        if shutil.which(exe_of(runtime)) is None:
            skips.append(f"skip {runtime}: {exe_of(runtime)} not on PATH")
            print(f"  {skips[-1]}")
            continue
        run_case(runtime, check)
    if skips and os.environ.get("ARBEITSPLAN_REQUIRE_TOOLCHAINS") == "1":
        fails.extend(skips)
        print("  FAIL ARBEITSPLAN_REQUIRE_TOOLCHAINS=1 and a runtime was skipped")
    print()
    if fails:
        print(f"FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    ran = len(wanted) - len(skips)
    print(f"authored steps passed ({ran} runtime(s) end to end"
          + (f"; {len(skips)} skipped: {', '.join(s.split(':')[0][5:] for s in skips)}"
             if skips else "") + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
