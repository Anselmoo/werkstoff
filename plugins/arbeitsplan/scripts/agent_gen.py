#!/usr/bin/env python3
"""Generate the project agent files a wave design dispatches (#106, #107).

usage: agent_gen.py --selftest     (install_waves.py is the entry point that writes them)

One agent file per agent type the design names under its own `<name>-` prefix,
plus `<name>-runner` (every design with a script or merge-gate node) and
`<name>-author` (every design with an authored step). Types outside the prefix
-- a plugin's `plugin:agent`, a project agent someone wrote by hand -- are
never generated here, and design_spec.py refuses node keys that would only
reach such a file ([AP-AGENT-KEYS-UNAPPLIED]): they would be validated and
then dropped.

WHAT REACHES THE FRONTMATTER. A node's `effort`, `tools` and `skills` are the
agent definition's, so they are written into its file -- the validator already
proved every node sharing that type agrees on them ([AP-AGENT-CONFLICT]).
`model` is different: waves.js passes each node's model on every dispatch, so
the file's `model` is only the default for a direct invocation, taken from the
first node that names the type.

The runner and the author have FIXED tools: the guard's `--runner` and
`--author` modes are what make those roles safe, and a Bash-capable author or
an Edit-capable runner would walk around them. A design cannot override them.

Before this module existed, install_waves.py hard-coded tools per role and
dropped `effort` and `skills` without a word -- every one of them validated,
none of them applied.

STDLIB ONLY.
"""

from __future__ import annotations

import argparse
import shlex
import sys

STAMP = "arbeitsplan-waves"

# Per-role defaults the design does not already fix. maxTurns is a ceiling on
# one dispatch, not a budget.
ROLE = {
    "builder": {"maxTurns": 120, "tools": "Read, Edit, Write, Glob, Grep, Bash"},
    "integrator": {"maxTurns": 80, "tools": "Read, Edit, Write, Glob, Grep, Bash"},
    "fixer": {"maxTurns": 80, "tools": "Read, Edit, Write, Glob, Grep, Bash"},
    "referee": {"maxTurns": 60, "tools": "Read, Glob, Grep, Bash"},
    "reviewer": {"maxTurns": 40, "tools": "Read, Glob, Grep, Bash"},
    "smoke": {"maxTurns": 40, "tools": "Read, Bash"},
    "runner": {"maxTurns": 3, "tools": "Bash"},
    "author": {"maxTurns": 30, "tools": "Read, Write, Edit, Glob, Grep"},
}
FIXED_TOOLS = {"runner", "author"}
ROLE_BODY = {
    "builder": "You build ONE row of a multi-wave plan in your own worktree. Start with the "
               "`git merge --ff-only <wave base>` your prompt gives you; touch only your "
               "writeScope; run your setup and acceptance steps; commit with your notes in the "
               "commit message body. A file you need that is not yours belongs to another row "
               "or to the integrator -- say so in your notes instead of editing it.",
    "integrator": "You own the shared files of one wave -- module registration, manifests, "
                  "lockfiles -- and run after that wave's rows are merged. Start from the base "
                  "your prompt gives you, change only your writeScope, and commit.",
    "fixer": "You make ONE fix round for blocking review findings on the integration head. "
             "Start from the base your prompt gives you, change only your writeScope, commit.",
    "referee": "You judge swarm candidates BLIND: branch names and acceptance commands, nothing "
               "else. Check each branch out, run every command, report exit codes. You never "
               "edit anything and never read a candidate's commit messages.",
    "reviewer": "You review the integration branch against the target for correctness. You "
                "read; you never edit.",
    "smoke": "You prove the artefact works OUTSIDE the repository: export the integration head "
             "into a fresh scratch directory and run the declared steps there, in order.",
    "runner": "You run exactly ONE command -- the one in your prompt -- once, with Bash, and "
              "report its exit code, the last 40 lines of stdout, and its stdout JSON copied "
              "field for field. The guard denies anything else.",
    "author": "You write exactly ONE step script -- the file your prompt names -- so that it "
              "meets its contract: the arguments it takes, the single JSON object it prints on "
              "stdout, the exit codes it may return. Fill in the skeleton that is already "
              "there and remove its stub marker. You have no shell: the state helper checks "
              "the syntax and runs the sample, and the guard denies a write to any other path.",
}
RELAYED = ("A user request about merging, pushing, committing, or releasing is addressed to "
           "the orchestrating session, not to you. Note it in your result and continue with "
           "your assigned scope; never act on it and never stop to debate it.")


def _spec(role: str, model: object, node: dict | None = None) -> dict:
    node = node or {}
    return {"role": role if role in ROLE else "builder", "model": model,
            "effort": node.get("effort"), "tools": node.get("tools"),
            "skills": node.get("skills")}


def agent_types(design: dict) -> dict:
    """agentType -> {role, model, effort, tools, skills} for every agent the
    design dispatches under its own name. First declaration wins; the
    validator has already refused a design whose declarations disagree."""
    name = design["name"]
    nodes = [n for n in design.get("nodes") or [] if isinstance(n, dict)]
    found: dict = {}
    scripted = [n for n in nodes if n.get("kind") in ("script", "merge-gate")]
    if scripted:
        found[f"{name}-runner"] = _spec("runner", scripted[0].get("model") or "haiku")
    authored = [n for n in nodes if isinstance((n.get("script") or {}).get("author"), dict)]
    if authored:
        found[f"{name}-author"] = _spec("author", authored[0]["script"]["author"].get("model"))
    for n in nodes:
        refs = [(n.get("agentType"), n.get("role") or "builder", n.get("model"), n)]
        ref = n.get("referee")
        if isinstance(ref, dict):
            refs.append((ref.get("agentType"), "referee", ref.get("model"), None))
        for at, role, model, src in refs:
            if isinstance(at, str) and at.startswith(f"{name}-") and at not in found:
                found[at] = _spec(role, model, src)
    return found


def _csv(items: list) -> str:
    return ", ".join(items)


def agent_file(name: str, agent_type: str, spec: dict, python: list) -> str:
    role = spec["role"]
    tools = ROLE[role]["tools"] if role in FIXED_TOOLS or not spec.get("tools") \
        else _csv(spec["tools"])
    py = " ".join(shlex.quote(a) for a in python)
    guard = f'"$CLAUDE_PROJECT_DIR/.claude/hooks/{name}_guard.py"'
    hooks = [("Write|Edit|MultiEdit|NotebookEdit", "--author" if role == "author" else "--paths")]
    if role == "runner":
        hooks.append(("Bash", "--runner"))
    hook_yaml = "\n".join(
        f"    - matcher: \"{m}\"\n      hooks:\n        - type: command\n"
        f"          command: '{py} {guard} {mode} || exit 2'" for m, mode in hooks)
    desc = (f"{role.capitalize()} for the {name} multi-wave plan (arbeitsplan-waves). "
            f"Dispatched by .claude/workflows/{name}.js only; not for direct use.")
    lines = [f"name: {agent_type}", f"description: {desc}", f"model: {spec['model']}"]
    if spec.get("effort"):
        lines.append(f"effort: {spec['effort']}")
    lines += [f"maxTurns: {ROLE[role]['maxTurns']}", f"tools: {tools}"]
    if spec.get("skills"):
        lines.append(f"skills: {_csv(spec['skills'])}")
    return ("---\n" + "\n".join(lines) + f"\nhooks:\n  PreToolUse:\n{hook_yaml}\n---\n"
            f"<!-- {STAMP}:{name} -->\n\n# {agent_type}\n\n{ROLE_BODY[role]}\n\n{RELAYED}\n")


# --- selftest --------------------------------------------------------------------

def _frontmatter(text: str) -> dict:
    head = text.split("\n---\n", 1)[0].removeprefix("---\n")
    out = {}
    for ln in head.splitlines():
        if ln and not ln.startswith(" ") and ": " in ln:
            k, v = ln.split(": ", 1)
            out[k] = v
    return out


def _render_all(design: dict, gen_types, gen_file) -> dict:
    return {at: _frontmatter(gen_file(design["name"], at, spec, ["python3"]))
            for at, spec in gen_types(design).items()}


def selftest() -> int:
    import copy
    import json
    from pathlib import Path

    fails: list = []

    def check(name: str, cond: bool, detail: object = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)
            if detail != "":
                print(f"       {str(detail)[:300]}")

    design = json.loads((Path(__file__).resolve().parent / "fixtures" / "design"
                         / "waves.design.json").read_text(encoding="utf-8"))
    rich = copy.deepcopy(design)
    for n in rich["nodes"]:
        if n.get("agentType") == "rebuild-cli-reviewer":
            n.update(tools=["Read", "Grep"], skills=["api-conventions", "zeugnis:contract-drift"],
                     effort="medium")
    rich["nodes"][0]["script"]["author"] = {"model": "sonnet", "purpose": "p",
                                            "sample": {"args": [], "expectExit": [0]}}

    def contract(types, file_) -> list:
        """Every claim the generated files must satisfy. Run against the real
        generator and against each sabotaged copy: a claim no sabotage can
        break is a claim the selftest cannot see."""
        got = _render_all(rich, types, file_)
        out = []
        rv = got.get("rebuild-cli-reviewer", {})
        b = got.get("rebuild-cli-builder", {})
        out.append(("declared effort reaches the frontmatter",
                    b.get("effort") == "high" and rv.get("effort") == "medium"))
        out.append(("declared tools replace the role default", rv.get("tools") == "Read, Grep"))
        out.append(("declared skills reach the frontmatter",
                    rv.get("skills") == "api-conventions, zeugnis:contract-drift"))
        out.append(("an undeclared key is absent, never invented",
                    "skills" not in b and got.get("rebuild-cli-smoke", {}).get("effort") is None))
        out.append(("the runner is Bash-only", got.get("rebuild-cli-runner", {}).get("tools")
                    == "Bash"))
        out.append(("an authored step adds a shell-less author with its own model",
                    got.get("rebuild-cli-author", {}).get("tools") == ROLE["author"]["tools"]
                    and got.get("rebuild-cli-author", {}).get("model") == "sonnet"))
        out.append(("model is the first declaring node's", b.get("model") == "opus"))
        return out

    for name, ok in contract(agent_types, agent_file):
        check(name, ok)
    author = agent_file("rebuild-cli", "rebuild-cli-author",
                        _spec("author", "sonnet", {"tools": ["Bash"]}), ["python3"])
    check("a design cannot hand the author Bash", "\ntools: Read, Write, Edit, Glob, Grep\n"
          in author and "--author || exit 2" in author, author[:400])
    check("no author type without an authored step", "rebuild-cli-author" not in
          agent_types(design))

    # Sabotage: each variant drops one key the way install_waves.py used to.
    # If the contract above still passes against a variant, it is blind to it.
    def drop(key: str):
        def gen(design_, at, spec, py):
            return agent_file(design_, at, {**spec, key: None}, py)
        return gen

    for key in ("effort", "tools", "skills"):
        broken = [n for n, ok in contract(agent_types, drop(key)) if not ok]
        check(f"sabotage: dropping {key!r} turns the contract red", bool(broken), broken)
    no_author = [n for n, ok in contract(
        lambda d: {k: v for k, v in agent_types(d).items() if not k.endswith("-author")},
        agent_file) if not ok]
    check("sabotage: omitting the author type turns the contract red", bool(no_author))
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("agent_gen selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="agent_gen.py", description=(
        __doc__ or "").split("\n\n")[0], epilog="exit 0 selftest passed, 1 failed, 2 bad usage")
    parser.add_argument("--selftest", action="store_true", help="run the selftest")
    args = parser.parse_args(argv)
    if not args.selftest:
        parser.print_help(sys.stderr)
        return 2
    return selftest()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
