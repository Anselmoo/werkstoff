#!/usr/bin/env python3
"""Install a compiled multi-wave design into a project as project-owned files (#106).

usage: install_waves.py --design FILE [--root DIR] [--python CMD] [--artifact] [--dry-run]
       install_waves.py --selftest

A GENERATOR, not a runtime dependency: it runs once, writes the files below, and
the project runs them without werkstoff installed. A new round of work is a new
design table, not a new script -- the interpreter is the same pinned copy.

  .claude/workflows/<name>.js         workflows/waves.js, pinned and stamped
  .claude/workflows/<name>.plan.json  the validated design + what the interpreter needs
  .claude/workflows/<name>.md         the runbook, for PEOPLE: launch, resume, approve,
                                      re-verify, the node table. Claude Code treats only
                                      `.js` here as a workflow and ignores this file; the
                                      tooling runs without werkstoff, so it carries its own
                                      manual. Byte-identical for an identical design
  .claude/workflows/<name>_state.py   the state/merge/gate helper (waves_state.py)
  .claude/workflows/<name>.steps/     one SKELETON per authored step (assets/step-templates),
                                      in its runtime's language; the plan's author agent
                                      fills it on first launch, verify-step pins its hash.
                                      Gitignored: local tooling, never a dirty checkout
  .claude/hooks/<name>_guard.py       the path and runner guard (waves_guard.py)
  .claude/agents/<agentType>.md       one per agent type the design names under <name>-,
                                      plus <name>-runner; each with model, maxTurns, tools
                                      and the guard in its frontmatter `hooks:`
  .gitignore                          state, state.tmp, the runner and author ledgers and
                                      the steps directory, appended once
  .gitattributes                      export-ignore lines, with --artifact only

THE ONE PREREQUISITE is a Python >= 3.10 for the helper and the guard. It is
RESOLVED here, not assumed: `python3`, `python`, then `py -3` are probed (or
--python names one), and the one that answers is written into every command
the plan and the hooks run -- on Windows `python3` can be a Store stub that
exits non-zero, and a hook whose interpreter is missing must deny, not pass.

Every generated file carries a provenance stamp; a file at a target path WITHOUT
it is refused, never overwritten -- the project may have written its own.

Exit: 0 installed (or --dry-run clean), 1 refused, 2 bad input.
STDLIB ONLY.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_spec  # the same validator compile_spec.py --design runs
import waves_state  # AUTHORABLE, STUB_MARKER, step_path: what verify-step will check
from agent_gen import STAMP, agent_file, agent_types  # one generator, shared with handoff.py

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent

MIN_PYTHON = (3, 10)


class Refused(Exception):
    pass


def plugin_version() -> str:
    return json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())["version"]


def resolve_python(explicit: str | None) -> list:
    """The argv of a Python >= 3.10 that answers, or Refused."""
    candidates = [shlex.split(explicit)] if explicit else [["python3"], ["python"], ["py", "-3"]]
    probe = "import sys; print(int(sys.version_info[:2] >= (3, 10)))"
    for argv in candidates:
        try:
            p = subprocess.run([*argv, "-c", probe], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if p.returncode == 0 and p.stdout.strip() == "1":
            return argv
    raise Refused(f"no Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]} answered among "
                  f"{[' '.join(c) for c in candidates]}; the generated helper and guard need one. "
                  "Pass --python with its command.")


def stamped(text: str, stamp: str, comment: str) -> str:
    return f"{comment} {stamp}\n{text}" if not text.startswith("#!") else \
        text.replace("\n", f"\n{comment} {stamp}\n", 1)


def plan_of(design: dict, python: list) -> dict:
    """The design plus what the interpreter reads: the runner agent, the helper's
    record template, and every helper invocation re-pointed at the resolved
    interpreter so the runner guard's exact match holds on this machine."""
    name = design["name"]
    py = " ".join(shlex.quote(a) for a in python)
    helper = f".claude/workflows/{name}_state.py"
    plan = json.loads(json.dumps(design))
    for n in plan["nodes"]:
        sc = n.get("script")
        if isinstance(sc, dict) and isinstance(sc.get("command"), str):
            argv = sc["command"].split()
            ours = argv[1:2] == [helper] or (
                isinstance(sc.get("author"), dict) and sc.get("runtime") == "python"
                and argv[1:2] == [waves_state.step_path(name, n["id"], "python")])
            if ours and argv[0].startswith("python"):
                sc["command"] = " ".join([py, *argv[1:]])
    plan["runnerAgent"] = f"{name}-runner"
    plan["helper"] = {"record": f"{py} {helper} record --row {{row}} --branch {{branch}} "
                                "--base {base}"}
    if waves_state.authored_nodes(plan):
        plan["authorAgent"] = f"{name}-author"
        plan["helper"]["verify"] = f"{py} {helper} verify-step --node {{node}}"
    plan["installed"] = {"by": STAMP, "version": plugin_version(), "python": python}
    return plan


def write(path: Path, text: str, name: str, written: list, dry: bool) -> None:
    if path.exists() and f"{STAMP}:{name}" not in path.read_text(encoding="utf-8",
                                                                  errors="replace"):
        raise Refused(f"{path} exists and was not generated by {STAMP} for {name!r}; "
                      "refusing to overwrite it")
    written.append(str(path))
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")


def read_raw(path: Path) -> str:
    """Read WITHOUT newline translation -- read_text() turns CRLF into LF, which
    would hide the very line ending append_lines() must preserve."""
    with path.open(encoding="utf-8", newline="") as fh:
        return fh.read()


def append_lines(path: Path, lines: list, dry: bool) -> list:
    """Append the lines not already present, keeping the file's own line ending."""
    text = read_raw(path) if path.exists() else ""
    have = {ln.strip() for ln in text.splitlines()}
    new = [ln for ln in lines if ln not in have]
    if new and not dry:
        eol = "\r\n" if "\r\n" in text else "\n"
        lead = "" if not text or text.endswith(("\n", "\r\n")) else eol
        with path.open("a", encoding="utf-8", newline="") as fh:
            fh.write(lead + eol.join(new) + eol)
    return new


def _cell(value: object) -> str:
    text = " ".join(str(value).split()) if value not in (None, "", []) else "—"
    return text.replace("|", "\\|")


def runbook(design: dict, python: list, stamp: str) -> str:
    """The generated tooling's manual, derived from the design alone -- no clock,
    no path of this machine but the interpreter the commands already carry."""
    name = design["name"]
    py = " ".join(shlex.quote(a) for a in python)
    helper = f"{py} .claude/workflows/{name}_state.py"
    nodes = plan_of(design, python)["nodes"]  # the commands as INSTALLED, interpreter resolved
    integ = design.get("integration") or {}
    steps = waves_state.authored_nodes(design)
    rows = []
    for n in nodes:
        sc = n.get("script") or {}
        runs = (f"`{sc['command']}`" if sc.get("command")
                else ", ".join(f"`{st['command']}`" for st in (n.get("steps") or n.get(
                    "acceptance") or [])) or n.get("skip") or "")
        rows.append(f"| {_cell(n['id'])} | {_cell(n.get('kind'))} | {_cell(n.get('wave'))} | "
                    f"{_cell(n.get('where'))} | {_cell(', '.join(n.get('depends_on') or []))} | "
                    f"{_cell(n.get('model'))} | {_cell(', '.join(n.get('writeScope') or []))} | "
                    f"{_cell(runs)} |")
    out = [
        f"<!-- {stamp} -- generated from the design; edit the design and re-install, not this -->",
        f"# {name} — multi-wave plan",
        "",
        f"Installed by werkstoff's `arbeitsplan` from design run `{design['runId']}` "
        f"(sha256 `{design_spec.design_hash(design)}`). **Everything here runs without "
        "werkstoff.** Claude Code treats only `.js` files in this directory as workflows; this "
        "file is for the people who own the tooling.",
        "",
        "## Files",
        "",
        "| file | what it is |",
        "|---|---|",
        f"| `.claude/workflows/{name}.js` | the pinned wave interpreter (a Workflow script) |",
        f"| `.claude/workflows/{name}.plan.json` | the validated design it executes |",
        f"| `.claude/workflows/{name}_state.py` | state, merge, gate and verify helper "
        "(Python >= 3.10, stdlib only) |",
        f"| `.claude/workflows/{name}.state.json` | the run's state (gitignored) |",
        f"| `.claude/hooks/{name}_guard.py` | the path, runner and author guard every generated "
        "agent carries |",
        f"| `.claude/agents/{name}-*.md` | one agent file per agent type |",
        *([f"| `.claude/workflows/{name}.steps/` | authored step scripts (gitignored, pinned "
           "by hash) |"] if steps else []),
        "",
        "## Run it",
        "",
        "1. After an install that added agent types, **start a fresh session**: agent types "
        "added mid-session do not resolve.",
        "2. From the **primary checkout**, never a linked worktree, read the state:",
        "",
        "   ```bash",
        f"   {helper} show",
        "   ```",
        "",
        f"3. Launch the Workflow tool with `scriptPath: .claude/workflows/{name}.js` and "
        f"`args: {{plan: <the parsed {name}.plan.json>, state: <the output above>}}`, both as "
        "objects. Relaunching with a fresh `show` is the whole resume: finished waves, "
        "recorded builders and verified steps are skipped.",
        "",
        "## When it stops",
        "",
        "| result | do |",
        "|---|---|",
        f"| `pending_human_gate: <id>` | approve between runs: `{helper} approve --gate <id>`, "
        "then relaunch |",
        "| a red gate | read `findings` (`primary-only` = only the primary checkout's untracked "
        "or ignored files produced it) and the `kept` worktrees. Do not merge by hand |",
        "| `PRIMARY CHECKOUT ONLY` | relaunch from the primary checkout |",
        "| `WRONG BASE` | a builder's worktree (it starts from `worktree.baseRef`: the remote's "
        "default branch unless `\"head\"`) could not fast-forward to the wave base. Push the "
        "base, or set `worktree.baseRef` to `\"head\"` in `.claude/settings.json` |",
        "| `SCRIPT CONTRACT` | a declared command exited unexpectedly or broke its schema |",
        *([f"| `AUTHOR CONTRACT` | an authored step failed verification after its retries; "
           f"re-check by hand with `{helper} verify-step --node <id>` |"] if steps else []),
        "",
        "## Nodes",
        "",
        "| node | kind | wave | where | after | model | writes | runs |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        f"Waves merge into `{integ.get('branch')}`; `{integ.get('target')}` moves only after a "
        "green gate. Gates, run in the primary checkout and in a clean worktree: "
        + ", ".join(f"`{g['command']}`" for g in design.get("gates") or []) + ".",
    ]
    if steps:
        out += ["", "## Authored steps", "",
                "Written by the plan's author agent on the first launch, then verified: syntax, "
                "the sample in a scratch worktree, stdout against the node's schema. The guard "
                "refuses to run a step whose file or contract changed since.", "",
                "| node | language | file | sample |", "|---|---|---|---|"]
        for n in steps:
            sc = n["script"]
            out.append(f"| {_cell(n['id'])} | {_cell(sc['runtime'])} | "
                       f"`{waves_state.step_path(name, n['id'], sc['runtime'])}` | "
                       f"`{' '.join(sc['author']['sample'].get('args') or []) or '(no args)'}` |")
    out += ["", "## See it", "",
            "With werkstoff installed, `arbeitsplan`'s `build_design_html.py` renders this plan "
            "as a graph, with the state overlaid:", "", "```bash",
            f"{helper} show > {name}.show.json",
            f"python3 <werkstoff>/plugins/arbeitsplan/scripts/build_design_html.py "
            f"--design .claude/workflows/{name}.plan.json --state {name}.show.json "
            f"--out {name}-design.html", "```", ""]
    return "\n".join(out)


def stub_text(design: dict, node: dict, python: list) -> str:
    """The skeleton for one authored step, filled with its contract. Every value
    lands in a comment or a plain string literal; the purpose is flattened to
    one line so it cannot close a comment early."""
    sc = node["script"]
    author = sc["author"]
    tpl = (PLUGIN / "assets" / "step-templates"
           / f"step.{waves_state.AUTHORABLE[sc['runtime']]['ext']}").read_text(encoding="utf-8")
    py = " ".join(shlex.quote(a) for a in python)
    fills = {"NODE": node["id"], "PLAN": design["name"],
             "PURPOSE": " ".join(str(author.get("purpose") or "").split()),
             "EXITS": json.dumps(sc.get("expectExit")),
             "SAMPLE": json.dumps((author.get("sample") or {}).get("args", [])),
             "HELPER": f"{py} .claude/workflows/{design['name']}_state.py"}
    for key, val in fills.items():
        tpl = tpl.replace("{{" + key + "}}", val)
    return tpl


def write_stubs(design: dict, root: Path, python: list, dry: bool) -> dict:
    """A missing step, or one that is still a stub, gets a fresh skeleton. An
    AUTHORED step is never overwritten -- stamped or not, it is somebody's work,
    and its hash is what verify-step pinned."""
    written, kept = [], []
    for n in waves_state.authored_nodes(design):
        path = root / waves_state.step_path(design["name"], n["id"], n["script"]["runtime"])
        if path.is_file() and waves_state.STUB_MARKER not in path.read_text(
                encoding="utf-8", errors="replace"):
            kept.append(str(path))
            continue
        written.append(str(path))
        if not dry:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(stub_text(design, n, python), encoding="utf-8", newline="\n")
    return {"written": written, "kept": kept}


def install(design: dict, root: Path, python: list, artifact: bool, dry: bool) -> dict:
    errors, _w = design_spec.validate_design(design)
    if errors:
        raise Refused("the design does not validate -- compile it with compile_spec.py "
                      "--design first:\n  " + "\n  ".join(errors))
    if not any("wave" in n for n in design["nodes"]):
        raise Refused("this design has no waves; a single change runs through arbeitsplan-run, "
                      "not an installed wave interpreter")
    name = design["name"]
    stamp = f"{STAMP}:{name} v{plugin_version()}"
    wf, hooks, agents = root / ".claude" / "workflows", root / ".claude" / "hooks", \
        root / ".claude" / "agents"
    written: list = []

    js = (PLUGIN / "workflows" / "waves.js").read_text(encoding="utf-8")
    end = js.index("\n}\n") + 3  # the meta block stays first -- a Workflow script begins with it
    write(wf / f"{name}.js", js[:end] + f"// {stamp} -- generated; edit the design, not this\n"
          + js[end:], name, written, dry)
    write(wf / f"{name}.plan.json", json.dumps({**plan_of(design, python), "_stamp": stamp},
                                               indent=2) + "\n", name, written, dry)
    write(wf / f"{name}.md", runbook(design, python, stamp), name, written, dry)
    write(wf / f"{name}_state.py", stamped((HERE / "waves_state.py").read_text(encoding="utf-8"),
                                           stamp, "#"), name, written, dry)
    write(hooks / f"{name}_guard.py", stamped((HERE / "waves_guard.py").read_text(
        encoding="utf-8"), stamp, "#"), name, written, dry)
    types = agent_types(design)
    for at, spec in sorted(types.items()):
        write(agents / f"{at}.md", agent_file(name, at, spec, python), name, written, dry)

    steps = write_stubs(design, root, python, dry)
    ignored = append_lines(root / ".gitignore", [
        f".claude/workflows/{name}.state.json", f".claude/workflows/{name}.state.tmp",
        f".claude/workflows/{name}.runner/", f".claude/workflows/{name}.author/",
        f".claude/workflows/{name}.steps/"], dry)
    exported = append_lines(root / ".gitattributes", [
        f".claude/workflows/{name}* export-ignore", f".claude/hooks/{name}_guard.py export-ignore",
        *[f".claude/agents/{at}.md export-ignore" for at in sorted(types)]], dry) if artifact else []
    return {"written": written, "agents": sorted(types), "gitignore": ignored,
            "gitattributes": exported, "python": python, "steps": steps}


def notice(result: dict, name: str) -> str:
    return "\n".join([
        f"installed {len(result['written'])} file(s) for {name} "
        f"(python: {' '.join(result['python'])})",
        *[f"  {p}" for p in result["written"]],
        "",
        *(["authored step skeleton(s) -- the Author phase fills them on the first launch:",
           *[f"  {p}" for p in result["steps"]["written"]]] if result["steps"]["written"] else []),
        *([f"authored step(s) kept as written: {', '.join(result['steps']['kept'])}"]
          if result["steps"]["kept"] else []),
        "",
        "START A FRESH SESSION before launching. Agent types added to .claude/agents/ in the",
        "middle of a session do not resolve in agent() -- the run would dispatch to nothing:",
        f"  {', '.join(result['agents'])}",
        "",
        "Then, from the PRIMARY checkout (never a linked worktree), launch the Workflow tool with",
        f"scriptPath .claude/workflows/{name}.js and args {{plan: <{name}.plan.json>, state: "
        f"<`{name}_state.py show`>}} -- both as objects, never JSON strings.",
    ])


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="install_waves.py", description=(
        __doc__ or "").split("\n\n")[0], epilog="exit 0 installed, 1 refused, 2 bad input")
    parser.add_argument("--design", help="a design.json compiled with compile_spec.py --design")
    parser.add_argument("--root", default=".", help="project root (default: .)")
    parser.add_argument("--python", help="the Python >= 3.10 command (default: probe)")
    parser.add_argument("--artifact", action="store_true",
                        help="the repository is itself an installable artefact: export-ignore "
                             "the generated tooling")
    parser.add_argument("--dry-run", action="store_true", help="validate and list, write nothing")
    parser.add_argument("--selftest", action="store_true", help="run the selftest")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.design:
        parser.error("--design is required")
    try:
        design = json.loads(Path(args.design).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read the design: {exc}", file=sys.stderr)
        return 2
    try:
        python = resolve_python(args.python)
        result = install(design, Path(args.root).resolve(), python, args.artifact, args.dry_run)
    except Refused as exc:
        print(f"REFUSED {exc}", file=sys.stderr)
        return 1
    print(notice(result, design["name"]) if not args.dry_run
          else json.dumps(result, indent=2))
    return 0


def selftest() -> int:
    import tempfile

    fails: list = []

    def check(name: str, cond: bool, detail: object = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)
            if detail != "":
                print(f"       {str(detail)[:300]}")

    design = json.loads((HERE / "fixtures" / "design" / "waves.design.json").read_text())
    py = [sys.executable]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".gitignore").write_text("node_modules/\r\n", newline="")
        res = install(design, root, py, artifact=True, dry=False)
        wf = root / ".claude" / "workflows"
        names = {Path(p).name for p in res["written"]}
        check("writes the interpreter, plan, helper, guard and agents",
              {"rebuild-cli.js", "rebuild-cli.plan.json", "rebuild-cli_state.py",
               "rebuild-cli_guard.py", "rebuild-cli-runner.md", "rebuild-cli-builder.md",
               "rebuild-cli-smoke.md", "rebuild-cli-reviewer.md", "rebuild-cli-fixer.md"} <= names,
              sorted(names))
        js = (wf / "rebuild-cli.js").read_text()
        check("the interpreter still begins with its meta block", js.startswith("export const meta"))
        check("the interpreter carries the stamp", f"{STAMP}:rebuild-cli" in js)
        plan = json.loads((wf / "rebuild-cli.plan.json").read_text())
        gate = next(n for n in plan["nodes"] if n["id"] == "gate-1")["script"]["command"]
        check("helper commands run the RESOLVED interpreter", gate.startswith(shlex.quote(
            sys.executable) + " .claude/workflows/rebuild-cli_state.py merge"), gate)
        check("the plan names the runner agent and the record template",
              plan["runnerAgent"] == "rebuild-cli-runner" and "{row}" in plan["helper"]["record"])
        builder = (root / ".claude" / "agents" / "rebuild-cli-builder.md").read_text()
        check("an agent file declares model and maxTurns", "\nmodel: opus\n" in builder
              and "\nmaxTurns: 120\n" in builder, builder[:300])
        check("the design's effort reaches the agent file (it used to be dropped)",
              "\neffort: high\n" in builder, builder[:300])
        check("every agent's guard hook is referenced via $CLAUDE_PROJECT_DIR and fails closed",
              '"$CLAUDE_PROJECT_DIR/.claude/hooks/rebuild-cli_guard.py" --paths || exit 2'
              in builder)
        runner = (root / ".claude" / "agents" / "rebuild-cli-runner.md").read_text()
        check("the runner is Bash-only and guarded in --runner mode",
              "\ntools: Bash\n" in runner and "--runner || exit 2" in runner)
        gi = read_raw(root / ".gitignore")
        check(".gitignore gains the state, tmp and ledger, in the file's own CRLF endings",
              ".claude/workflows/rebuild-cli.state.json\r\n" in gi
              and ".claude/workflows/rebuild-cli.runner/\r\n" in gi, repr(gi))
        check("--artifact export-ignores the generated tooling", "export-ignore" in (
            root / ".gitattributes").read_text())
        book = (wf / "rebuild-cli.md").read_text()
        check("the runbook is written next to the interpreter, stamped, for people",
              book.startswith(f"<!-- {STAMP}:rebuild-cli") and "runs without werkstoff" in book
              and "only `.js` files in this directory as workflows" in book, book[:300])
        check("the runbook's commands carry the resolved interpreter, the node table too",
              f"{shlex.quote(sys.executable)} .claude/workflows/rebuild-cli_state.py show" in book
              and "approve --gate <id>" in book and "`python3 .claude" not in book)
        check("the runbook shows a smoke node's declared steps", "`go run ./cmd/tool --help`"
              in book, book)
        check("the runbook's node table has a row for every node",
              all(f"| {n['id']} |" in book for n in design["nodes"]), book)
        check("a design without authored steps gets no authored-steps section",
              "## Authored steps" not in book and "AUTHOR CONTRACT" not in book)
        again = install(design, root, py, artifact=True, dry=False)
        check("re-install writes a byte-identical runbook", (wf / "rebuild-cli.md").read_text()
              == book)
        check("re-install is idempotent: no line appended twice",
              not again["gitignore"] and not again["gitattributes"]
              and (root / ".gitignore").read_text().count("rebuild-cli.state.json") == 1)
        (root / ".claude" / "agents" / "rebuild-cli-smoke.md").write_text("hand-written\n")
        try:
            install(design, root, py, artifact=False, dry=False)
            check("a hand-written file at a target path is refused", False)
        except Refused:
            check("a hand-written file at a target path is refused", True)
        text = notice(res, "rebuild-cli")
        check("the notice demands a fresh session and names the new agent types",
              "START A FRESH SESSION" in text and "rebuild-cli-runner" in text)
        bad = json.loads(json.dumps(design))
        bad["nodes"][0].pop("model")
        try:
            install(bad, Path(tmp) / "other", py, artifact=False, dry=True)
            check("an invalid design is refused before anything is written", False)
        except Refused:
            check("an invalid design is refused before anything is written",
                  not (Path(tmp) / "other").exists())
        guard = root / ".claude" / "hooks" / "rebuild-cli_guard.py"
        (root / ".git").mkdir()
        p = subprocess.run([sys.executable, str(guard), "--paths"], input=json.dumps({
            "cwd": str(root), "tool_name": "Edit", "tool_input": {"file_path": "secrets/k"}}),
            capture_output=True, text=True)
        check("the installed guard denies an offLimits path from the installed plan",
              p.returncode == 2, p.stderr)
        rp = subprocess.run([sys.executable, str(guard), "--runner"], input=json.dumps({
            "tool_name": "Bash", "agent_id": "a1",
            "tool_input": {"command": gate.replace("{wave}", "1").replace("{stage}", "0")
                           .replace("{final}", "1").replace("{branches}", "w1-parse=agent/x")
                           .replace("{discard}", "none")}}), capture_output=True, text=True)
        check("the installed guard allows the installed gate command, rendered", rp.returncode == 0,
              rp.stdout + rp.stderr)
        node = subprocess.run(["node", "-e", "const fs=require('fs');const s=fs.readFileSync("
                               "process.argv[1],'utf8').replace(/^export\\s+(?=const\\s+meta\\b)/m,"
                               "'');new (Object.getPrototypeOf(async()=>{}).constructor)('args',"
                               "'agent','parallel','pipeline','phase','log','budget',s)",
                               str(wf / "rebuild-cli.js")], capture_output=True, text=True)
        check("the installed interpreter compiles as a Workflow body", node.returncode == 0,
              node.stderr[-300:])
    try:
        resolve_python(f"{shlex.quote(sys.executable)}")
        check("resolve_python accepts a working interpreter", True)
    except Refused as exc:
        check("resolve_python accepts a working interpreter", False, exc)
    try:
        resolve_python("definitely-not-a-python-xyz")
        check("resolve_python refuses a missing interpreter", False)
    except Refused:
        check("resolve_python refuses a missing interpreter", True)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("install_waves selftest passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
