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

WHAT REACHES THE FRONTMATTER. A node's `tools` and `skills` are the agent
definition's, so they are written into its file -- the validator already proved
every node sharing that type agrees on them ([AP-AGENT-CONFLICT]). `model` and
`effort` are different: agent() takes both per call and waves.js passes every
node's own, so the file's values are only defaults for a node that states none. They
are written ONLY when EVERY node sharing the type states the SAME value -- taken from
one node they would reach the others as a value they never chose, which for a node
that omits its model means running on another node's instead of inheriting (#118).
When the nodes disagree, or any omits it, the file carries no `model:` / `effort:` and
each node's own per-call value (or none) decides. The runner's and the author's
`effort` is never written.

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


def shared_model(values: list) -> object:
    """The one value every node of an agent type states, else None. Absent next
    to present, or two different ones, is None: a file default taken from one
    node would reach the others as a value they never chose (#118)."""
    if not values or values[0] is None or any(v != values[0] for v in values):
        return None
    return values[0]


def agent_types(design: dict, pick=shared_model) -> dict:
    """agentType -> {role, model, effort, tools, skills} for every agent the
    design dispatches under its own name. role, tools and skills: first
    declaration wins (the validator has already refused a design whose
    declarations disagree). model and effort: only a value EVERY node of the
    type states, and states identically (shared_model); otherwise none, so a node
    that omits one is never handed another node's (#118)."""
    name = design["name"]
    nodes = [n for n in design.get("nodes") or [] if isinstance(n, dict)]
    found: dict = {}
    stated: dict = {}  # agentType -> [(model, effort)] for each node dispatching it

    def note(at: str, role: str, model: object, effort: object, src: dict | None) -> None:
        found.setdefault(at, _spec(role, None, src))
        stated.setdefault(at, []).append((model, effort))

    for n in nodes:
        if n.get("kind") in ("script", "merge-gate"):
            note(f"{name}-runner", "runner", n.get("model"), None, None)
        author = (n.get("script") or {}).get("author")
        if isinstance(author, dict):
            note(f"{name}-author", "author", author.get("model"), None, None)
    for n in nodes:
        refs = [(n.get("agentType"), n.get("role") or "builder", n.get("model"),
                 n.get("effort"), n)]
        ref = n.get("referee")
        if isinstance(ref, dict):
            refs.append((ref.get("agentType"), "referee", ref.get("model"), None, None))
        for at, role, model, effort, src in refs:
            if isinstance(at, str) and at.startswith(f"{name}-"):
                note(at, role, model, effort, src)
    for at, spec in found.items():
        spec["model"] = pick([m for m, _ in stated[at]])
        spec["effort"] = pick([e for _, e in stated[at]])
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
    lines = [f"name: {agent_type}", f"description: {desc}"]
    if spec.get("model"):  # an omitted model stays omitted: the agent inherits (#118)
        lines.append(f"model: {spec['model']}")
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


def _first_wins(models: list) -> object:
    """The defect #118's review found: the file's model from the FIRST node, so a
    node that omits its own silently runs on another node's. Selftest-only."""
    return models[0] if models else None


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
    rich["nodes"][0].pop("model", None)  # the runner declares none: it must inherit
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
        out.append(("an omitted model is absent, never defaulted (#118)",
                    "model" not in got.get("rebuild-cli-runner", {})))
        return out

    for name, ok in contract(agent_types, agent_file):
        check(name, ok)

    def mixed(types) -> list:
        """The #118 claim, one design per way nodes of ONE type can disagree on
        model: the file carries a model only when every node states the same."""
        def model_of(mutate, at: str):
            d = copy.deepcopy(design)
            mutate(d["nodes"])
            return _render_all(d, types, agent_file).get(at, {}).get("model")

        def node(nodes, nid):
            return next(n for n in nodes if n["id"] == nid)

        def omit_later(nodes):
            node(nodes, "w1-render").pop("model")

        def omit_first(nodes):
            node(nodes, "w1-parse").pop("model")

        def differ(nodes):
            node(nodes, "w1-render")["model"] = "sonnet"

        def runner_omit_later(nodes):
            node(nodes, "gate-1").pop("model")

        def author_two(nodes):
            for nid in ("preflight", "gate-1"):
                node(nodes, nid)["script"]["author"] = {
                    "model": "sonnet", "purpose": "p", "sample": {"args": [], "expectExit": [0]}}
            node(nodes, "gate-1")["script"]["author"].pop("model")

        def effort_of(mutate, at: str):
            d = copy.deepcopy(design)
            mutate(d["nodes"])
            return _render_all(d, types, agent_file).get(at, {}).get("effort")

        def omit_effort_later(nodes):
            node(nodes, "w1-render").pop("effort", None)

        b = "rebuild-cli-builder"
        return [
            ("a later node omits its effort: the file carries none",
             effort_of(omit_effort_later, b) is None),
            ("every node states the same model: it is the file's", model_of(lambda n: None, b)
             == "opus"),
            ("a later node omits its model: the file carries none", model_of(omit_later, b)
             is None),
            ("the first node omits its model: the file carries none", model_of(omit_first, b)
             is None),
            ("two nodes of one type state different models: the file carries none",
             model_of(differ, b) is None),
            ("a later script node omits its model: the runner carries none",
             model_of(runner_omit_later, "rebuild-cli-runner") is None),
            ("a later authored step omits the author model: the author carries none",
             model_of(author_two, "rebuild-cli-author") is None),
        ]

    for name, ok in mixed(agent_types):
        check(name, ok)
    first = [n for n, ok in mixed(lambda d: agent_types(d, _first_wins)) if not ok]
    # The two cases first-wins also satisfies (agreement; the FIRST node omitting) are
    # not the ones that can see it -- the other five must each go red on their own.
    check("sabotage: first-node-wins turns the five later-node cases red",
          len(first) == 5 and not any("same model" in n or "first node omits" in n for n in first),
          first)
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

    for key in ("model", "effort", "tools", "skills"):
        broken = [n for n, ok in contract(agent_types, drop(key)) if not ok]
        check(f"sabotage: dropping {key!r} turns the contract red", bool(broken), broken)
    def defaulted(design_, at, spec, py):
        return agent_file(design_, at, {**spec, "model": spec["model"] or "haiku"}, py)

    injected = [n for n, ok in contract(agent_types, defaulted) if not ok]
    check("sabotage: defaulting an omitted model turns the contract red", bool(injected), injected)
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
