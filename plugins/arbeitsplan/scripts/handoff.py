#!/usr/bin/env python3
"""Hand an approved design over to its execution: same session or a new one (#107).

usage: handoff.py snapshot --root DIR --out FILE
       handoff.py plan --design FILE --snapshot FILE [--worktree PATH] [--branch NAME] [--json]
       handoff.py --selftest

`snapshot` records which project agent types exist WHEN THE DESIGN IS MADE
(.claude/agents/*.md). `plan` compares the design's agent types against it.

Agent types added to .claude/agents/ in the middle of a session do not resolve
in the TURN that wrote them -- an agent() or Agent-tool dispatch of one fails
with "agent type ... not found", even 30 s later -- and do resolve from the next
turn (probe P4, `probe_runtime.py`, CLI 2.1.283, ADR 0004; #106 R2 measured
only the first half). So when the design needs a project agent type the
snapshot lacks, `plan` says the launch must come in a LATER TURN than the
install, names the types, and prints a fresh session's start prompt as the
alternative that works on any CLI version. Either way the same session may
`EnterWorktree` into the branch or worktree the run produced (its cwd,
settings and CLAUDE.md move with it; agents and hooks are read through from
the main checkout).

Namespaced types (plugin:agent) are never "new": they load with their plugin.

Exit: 0 printed, 2 bad input. STDLIB ONLY.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_gen
import design_spec


def project_agents(root: Path) -> list:
    d = root / ".claude" / "agents"
    return sorted(p.stem for p in d.glob("*.md")) if d.is_dir() else []


def needed_types(design: dict) -> list:
    """Every project-local agent type the design dispatches. A wave design's
    generated types -- `<name>-runner`, `<name>-author` when a step is
    authored -- come from agent_gen, the generator install_waves.py writes
    them with, so the two can never disagree about which files appear."""
    found = set()
    for n in design.get("nodes") or []:
        for at in (n.get("agentType"), (n.get("referee") or {}).get("agentType")):
            if isinstance(at, str) and at and ":" not in at:
                found.add(at)
    if any("wave" in n for n in design.get("nodes") or []):
        found.update(agent_gen.agent_types(design))
    return sorted(found)


def start_prompt(design: dict, digest: str, waves: bool) -> str:
    run_dir = f"analysis/arbeitsplan/{design['runId']}"
    how = (f"install nothing further -- the files are in place. Launch "
           f".claude/workflows/{design['name']}.js with the Workflow tool, args "
           f"{{plan: .claude/workflows/{design['name']}.plan.json, state: the output of "
           f"`.claude/workflows/{design['name']}_state.py show`}} as objects, via "
           f"/arbeitsplan:arbeitsplan-waves" if waves else
           f"run /arbeitsplan:arbeitsplan-run on {run_dir}/workflow.json")
    return (f"Execute the approved arbeitsplan design {design['name']} (run {design['runId']}). "
            f"The design is {run_dir}/design.json, sha256 {digest}; refuse to run if the file's "
            f"hash differs, because the approval was given for that hash. From the PRIMARY "
            f"checkout (not a linked worktree), {how}. Stop at the first red gate or pending "
            f"human gate and report it; do not retry.")


def plan(design: dict, snapshot: list, worktree: str | None, branch: str | None) -> dict:
    digest = design_spec.design_hash(design)
    waves = any("wave" in n for n in design.get("nodes") or [])
    new = [t for t in needed_types(design) if t not in snapshot]
    result = {"design": design["name"], "sha256": digest, "newAgentTypes": new,
              "laterTurnRequired": bool(new),
              "newSessionPrompt": start_prompt(design, digest, waves)}
    if worktree or branch:
        result["sameSession"] = (f"EnterWorktree into {worktree or branch} for review or the "
                                 "next step; cwd, settings and CLAUDE.md move with it.")
    return result


def render(r: dict) -> str:
    lines = [f"handoff for {r['design']} (sha256 {r['sha256'][:12]}...)"]
    if r["laterTurnRequired"]:
        lines += ["", "LAUNCH IN A LATER TURN -- the design needs agent types this session did not "
                  "start with. agent() cannot resolve a type in the turn that wrote it, and does "
                  "from the next turn on (probe P4, CLI 2.1.283, ADR 0004):",
                  *[f"  {t}" for t in r["newAgentTypes"]], "",
                  "End the turn that installed them; launch on the next one."]
    if r.get("sameSession"):
        lines += ["", r["sameSession"]]
    elif not r["laterTurnRequired"]:
        lines += ["", "Same session: nothing new to load; continue here."]
    lines += ["", "Or, in a fresh session (works on any CLI version), with exactly this prompt:",
              "", r["newSessionPrompt"]]
    return "\n".join(lines)


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="handoff.py", description=(
        __doc__ or "").split("\n\n")[0], epilog="exit 0 printed, 2 bad input")
    parser.add_argument("--selftest", action="store_true", help="run the selftest")
    sub = parser.add_subparsers(dest="cmd")
    s = sub.add_parser("snapshot", help="record the project agent types that exist now")
    s.add_argument("--root", default=".")
    s.add_argument("--out", required=True)
    p = sub.add_parser("plan", help="say how the approved design is executed")
    p.add_argument("--design", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--worktree")
    p.add_argument("--branch")
    p.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        if args.cmd == "snapshot":
            agents = project_agents(Path(args.root))
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps({"agents": agents}, indent=2) + "\n")
            print(f"snapshot: {len(agents)} project agent type(s) -> {args.out}")
            return 0
        if args.cmd == "plan":
            design = json.loads(Path(args.design).read_text(encoding="utf-8"))
            snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))["agents"]
            r = plan(design, snap, args.worktree, args.branch)
            print(json.dumps(r, indent=2) if args.json else render(r))
            return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"cannot hand off: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    parser.print_help(sys.stderr)
    return 2


def selftest() -> int:
    fails = []
    design = json.loads((Path(__file__).resolve().parent / "fixtures" / "design"
                         / "waves.design.json").read_text())
    everything = needed_types(design)
    cases = [
        ("new project agent types -> a later turn is required, with the prompt",
         plan(design, [], None, None), True),
        ("every type existed at design time -> same session allowed",
         plan(design, everything, ".claude/worktrees/x", None), False),
        ("one missing type (the runner) is enough to require a later turn",
         plan(design, [t for t in everything if not t.endswith("-runner")], None, None), True),
    ]
    for name, r, want in cases:
        ok = r["laterTurnRequired"] is want and design["runId"] in r["newSessionPrompt"] \
            and r["sha256"] in r["newSessionPrompt"]
        if not want:
            ok = ok and "EnterWorktree" in r.get("sameSession", "")
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        if not ok:
            fails.append(name)
    ns = dict(design, nodes=[dict(n, agentType="arbeitsplan:implementer")
                             if n.get("agentType") else n for n in design["nodes"]])
    ok = "rebuild-cli-builder" not in needed_types(ns)
    print(f"  {'ok  ' if ok else 'FAIL'} a namespaced plugin agent is never counted as new")
    if not ok:
        fails.append("namespaced")
    text = render(cases[0][1])
    ok = "LAUNCH IN A LATER TURN" in text and "rebuild-cli-runner" in text \
        and cases[0][1]["newSessionPrompt"] in text
    print(f"  {'ok  ' if ok else 'FAIL'} the rendered handoff says a later turn, names the types, "
          "and still prints the fresh-session prompt")
    if not ok:
        fails.append("render")
    text = render(cases[1][1])
    ok = "LAUNCH IN A LATER TURN" not in text and "EnterWorktree" in text
    print(f"  {'ok  ' if ok else 'FAIL'} nothing new to load -> no later-turn demand, same session")
    if not ok:
        fails.append("render-same")
    both = plan(design, [], ".claude/worktrees/x", None)
    ok = both["laterTurnRequired"] and "EnterWorktree" in both.get("sameSession", "")
    print(f"  {'ok  ' if ok else 'FAIL'} new types no longer forbid the same session, only this turn")
    if not ok:
        fails.append("same-session-with-new")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("handoff selftest passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
