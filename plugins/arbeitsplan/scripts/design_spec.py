#!/usr/bin/env python3
"""Validate a design table (design.json, schemaVersion "design/1").

usage: design_spec.py --selftest     (compile a design with compile_spec.py --design)

A design table is the node-by-node answer to WHAT (goal, outputs), WHERE
(primary | worktree | scratch), WHEN (depends_on, human gates between runs) and
HOW (kind, model, schema, write scope, declared commands) for every step of a
workflow, BEFORE anything runs (#107). A design whose nodes carry `wave` is also
the plan table the multi-wave interpreter executes (#106), so both issues share
this one validator. references/design-table-schema.md is the prose contract.

LANGUAGE-NEUTRAL BY CONSTRUCTION. Both issues were written after observing one
project; nothing here may assume its ecosystem. Every command a design runs --
a script node, a row's acceptance and setup, a wave gate, a smoke step --
names a TOOLCHAIN, and a toolchain is a built-in starting set
(BUILTIN_TOOLCHAINS) or one the design declares itself. Preflight runs each
used toolchain's version probe and passes on exit 0 alone, since `go version`,
`java -version` and friends do not share one output convention.

Every rule the issues name is TAGGED ([AP-...], DESIGN_RULES) and has a
committed red fixture under fixtures/red/ (MANIFEST.json, `--design`), proved by
test_red_fixtures.py. Pure shape errors (a missing id, an unknown kind) are
untagged and covered by this module's own selftest -- the split compile_spec.py
already uses.

Never infer a missing gating value: a node without a model does NOT default to
the smallest one; the design skill proposes a default and the design says it.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import land_candidate  # scope_overlap: the one place write-scope overlap is decided
import waves_state  # AUTHORABLE, step_path: the vendored helper verifies what this admits

DESIGN_SCHEMA_VERSION = "design/1"
NODE_KINDS = {"agent", "script", "referee", "merge-gate", "human-gate"}
SCRIPTED = {"script", "merge-gate"}  # kinds that execute a declared command
WHERE = {"primary", "worktree", "scratch"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
ROLES = {"builder", "referee", "merger", "integrator", "smoke", "reviewer", "fixer", "runner"}
PARSE_MODES = {"json", "exit-only"}

# Models: an alias, or a full model id. The alias list is what agent()'s
# `model` resolves today; a full `claude-...` id is how a newer model is named
# without editing this file. Never a default -- an omitted model inherits the
# session's, which silently defeats per-node tiering.
MODEL_ALIASES = ("haiku", "sonnet", "opus", "fable")
MODEL_ID_RE = re.compile(r"\Aclaude-[a-z0-9]+(?:[-.][a-z0-9]+)*(?:\[1m\])?\Z")
MODEL_RULE = (f"an alias {list(MODEL_ALIASES)} or a full model id (claude-...), and is never "
              "omitted -- an omitted model inherits the session's")

# Toolchains. A STARTING SET, not a whitelist: a design (or a workflow spec)
# declares any other runtime in its own `toolchains` block, which may also
# override an entry here (a pinned interpreter, a wrapper script). `executables`
# are fnmatch patterns matched against the command's argv[0] basename, so
# `.venv/bin/python`, `python3.12` and `./gradlew` resolve without special
# cases. `version` is the ONE probe preflight runs; exit 0 means installed.
BUILTIN_TOOLCHAINS = {
    "shell": {"executables": ["bash", "sh", "zsh", "dash"], "version": "sh -c true"},
    "powershell": {"executables": ["pwsh", "pwsh.exe", "powershell", "powershell.exe"],
                   "version": "pwsh -NoProfile -Command $PSVersionTable.PSVersion"},
    "cmd": {"executables": ["cmd", "cmd.exe"], "version": "cmd /c ver"},
    "python": {"executables": ["python3*", "python", "python.exe", "py", "py.exe"],
               "version": "python3 --version"},
    "uv": {"executables": ["uv", "uvx"], "version": "uv --version"},
    "poetry": {"executables": ["poetry"], "version": "poetry --version"},
    "node": {"executables": ["node", "npm", "npx", "pnpm", "yarn", "corepack"],
             "version": "node --version"},
    "deno": {"executables": ["deno"], "version": "deno --version"},
    "bun": {"executables": ["bun", "bunx"], "version": "bun --version"},
    "go": {"executables": ["go", "gofmt"], "version": "go version"},
    "rust": {"executables": ["cargo", "rustc", "rustup"], "version": "cargo --version"},
    "haskell": {"executables": ["ghc", "runghc", "cabal", "stack"], "version": "ghc --version"},
    "ruby": {"executables": ["ruby", "bundle", "rake", "gem"], "version": "ruby --version"},
    "java": {"executables": ["java", "javac", "mvn", "gradle", "gradlew", "mvnw", "gradlew.bat"],
             "version": "java -version"},
    "kotlin": {"executables": ["kotlin", "kotlinc", "gradle", "gradlew"],
               "version": "kotlinc -version"},
    "scala": {"executables": ["sbt", "scala", "scala-cli"], "version": "sbt --script-version"},
    "dotnet": {"executables": ["dotnet", "dotnet.exe"], "version": "dotnet --version"},
    "swift": {"executables": ["swift", "xcodebuild"], "version": "swift --version"},
    "julia": {"executables": ["julia"], "version": "julia --version"},
    "r": {"executables": ["Rscript", "R"], "version": "Rscript --version"},
    "elixir": {"executables": ["elixir", "mix", "iex"], "version": "elixir --version"},
    "erlang": {"executables": ["erl", "rebar3", "escript"], "version": "rebar3 version"},
    "ocaml": {"executables": ["dune", "opam", "ocaml"], "version": "dune --version"},
    "zig": {"executables": ["zig"], "version": "zig version"},
    "perl": {"executables": ["perl", "prove"], "version": "perl --version"},
    "php": {"executables": ["php", "composer"], "version": "php --version"},
    "lua": {"executables": ["lua", "luajit", "luarocks"], "version": "lua -v"},
    "dart": {"executables": ["dart", "flutter"], "version": "dart --version"},
    "c-cpp": {"executables": ["cc", "gcc", "g++", "clang", "clang++", "cl", "cl.exe"],
              "version": "cc --version"},
    "make": {"executables": ["make", "gmake", "nmake", "just", "task"],
             "version": "make --version"},
    "cmake": {"executables": ["cmake", "ctest", "cpack"], "version": "cmake --version"},
    "bazel": {"executables": ["bazel", "bazelisk"], "version": "bazel --version"},
    "nix": {"executables": ["nix", "nix-shell"], "version": "nix --version"},
    "docker": {"executables": ["docker", "podman"], "version": "docker --version"},
}

NAME_RE = re.compile(r"\A[a-z][a-z0-9-]{0,39}\Z")
ID_RE = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")
RUN_ID_RE = re.compile(r"\A(?!\.+\Z)(?!.*\.\.)[A-Za-z0-9._-]{1,64}\Z")
BRANCH_RE = re.compile(r"\A(?!/)(?!.*\.\.)(?!.*//)[A-Za-z0-9._/-]{1,128}(?<![/.])\Z")
# An input is an id or a path, never content: no whitespace, nothing a prompt
# could smuggle a sibling's text through (#106 R8). POSIX-style separators only.
INPUT_RE = re.compile(r"\A[A-Za-z0-9._/@{}*-]{1,256}\Z")
# One command, not a chain: `;`, `|`, `&` (which also refuses `2>&1` -- redirect
# inside the script instead), a backtick, `$(` and a newline, OUTSIDE quotes.
# Quoted text is inert (`julia -e 'using Pkg; Pkg.test()'` is one command); the
# runner guard then matches the whole string exactly, so a declared chain would
# be allowed only because someone declared it.
SHELL_COMPOSE = re.compile(r"[;|&`\n]|\$\(")
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")
# The values the multi-wave interpreter (workflows/waves.js) supplies. A
# placeholder outside this set in a wave design is a slot nothing fills.
WAVE_PLACEHOLDERS = {"name", "runId", "wave", "stage", "final", "branches", "discard", "base",
                     "integration", "target"}
# The contract between a wave design and workflows/waves.js + the vendored
# state helper: what the merge-gate must be told, and what the interpreter
# reads back from each kind of node. Checked here so a design that would make
# the interpreter guess is refused before anything runs.
GATE_PLACEHOLDERS = {"wave", "stage", "final", "branches", "discard"}
GATE_OUTPUT = {"green", "integrationSha", "targetMoved", "findings", "kept"}
PREFLIGHT_OUTPUT = {"linkedWorktree", "dirty", "head"}
BUILDER_OUTPUT = {"branch", "baseSha"}

DESIGN_RULES = {
    "AP-NODE-NO-MODEL": 107,
    "AP-NODE-NO-SCHEMA": 107,
    "AP-NODE-NO-SCOPE": 107,
    "AP-SCHEMA-NOT-STRICT": 106,
    "AP-SCRIPT-NO-RUNTIME": 107,
    "AP-SCRIPT-NO-COMMAND": 107,
    "AP-SCRIPT-RUNTIME-MISMATCH": 107,
    "AP-WAVE-SCOPE-OVERLAP": 107,
    "AP-INPUT-CONTENT": 106,
    "AP-HUMAN-GATE-INSIDE": 107,
    "AP-DEPENDS-UNKNOWN": 107,
    "AP-DEPENDS-CYCLE": 107,
    "AP-WAVE-NO-GATE": 106,
    "AP-WAVE-NO-BASE": 106,
    "AP-WAVE-ORDER": 106,
    "AP-GATES-UNDECLARED": 106,
    "AP-SWARM-INCOMPLETE": 106,
    "AP-GATE-NOT-PRIMARY": 106,
    "AP-SMOKE-NOT-SCRATCH": 106,
    "AP-SMOKE-UNDECLARED": 106,
    "AP-AGENT-CONFLICT": 107,
    "AP-AGENT-KEYS-UNAPPLIED": 107,
    "AP-AUTHOR-LANG": 107,
    "AP-AUTHOR-COMMAND": 107,
    "AP-AUTHOR-KIND": 107,
    "AP-AUTHOR-NO-CONTRACT": 107,
}
AUTHOR_KEYS = {"model", "purpose", "sample"}
SAMPLE_ARG_RE = re.compile(r"\A[A-Za-z0-9._/,=:@+-]{1,128}\Z")  # the guard's safe value class
# The node keys that belong to the agent DEFINITION, not to one dispatch: one
# agent type has one frontmatter, so every node naming it must agree on them.
# `model` is deliberately absent -- the interpreter passes it per dispatch.
AGENT_KEYS = ("role", "effort", "tools", "skills")


def design_hash(design: dict) -> str:
    """sha256 over canonical JSON -- what an approval binds to (#107 step 2)."""
    canon = json.dumps(design, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def model_ok(model: object) -> bool:
    return isinstance(model, str) and (model in MODEL_ALIASES or bool(MODEL_ID_RE.match(model)))


def strict_problems(schema: object, where: str = "output_schema") -> list:
    """Why `schema` is not a strict JSON Schema, as a list of strings.

    Strict means: every object level says `additionalProperties: false`, and no
    string property is JSON-in-a-string (named *json, or described as JSON) --
    the prototype passed its state as a JSON string the script then
    JSON.parse'd, which is exactly the fragility agent()'s schema enforcement
    exists to remove (#106 comment, item 1).
    """
    out: list = []
    if not isinstance(schema, dict):
        return [f"{where} is not an object"]
    if schema.get("type") == "object" or "properties" in schema:
        if schema.get("additionalProperties") is not False:
            out.append(f"{where} lacks additionalProperties: false")
        props = schema.get("properties") or {}
        if not isinstance(props, dict):
            out.append(f"{where}.properties is not an object")
            props = {}
        for key, sub in props.items():
            if isinstance(sub, dict) and sub.get("type") == "string":
                desc = str(sub.get("description") or "").lower()
                if key.lower().endswith("json") or "json" in desc:
                    out.append(f"{where}.properties.{key} is JSON-in-a-string; declare its "
                               "structure as an object instead")
            out.extend(strict_problems(sub, f"{where}.properties.{key}"))
    if schema.get("type") == "array" and "items" in schema:
        out.extend(strict_problems(schema["items"], f"{where}.items"))
    for comb in ("anyOf", "oneOf", "allOf"):
        for j, sub in enumerate(schema.get(comb) or []):
            out.extend(strict_problems(sub, f"{where}.{comb}[{j}]"))
    return out


# --- toolchains and commands ---------------------------------------------------

def toolchain_problems(declared: object) -> list:
    """Shape of a document's own `toolchains` block (absent is fine)."""
    if declared is None:
        return []
    if not isinstance(declared, dict):
        return ["'toolchains' must be an object {name: {executables[], version}}"]
    out = []
    for name, tc in declared.items():
        exes = tc.get("executables") if isinstance(tc, dict) else None
        ver = tc.get("version") if isinstance(tc, dict) else None
        if (not isinstance(exes, list) or not exes
                or not all(isinstance(e, str) and e and " " not in e for e in exes)):
            out.append(f"toolchains.{name}: 'executables' must be a non-empty list of "
                       "executable names (fnmatch patterns allowed)")
        if not isinstance(ver, str) or not ver.strip() or composes(ver):
            out.append(f"toolchains.{name}: 'version' must be ONE command preflight can run "
                       "to prove the toolchain is installed")
    return out


def toolchains_of(doc: dict) -> dict:
    """Built-ins overlaid by the document's own declarations."""
    merged = dict(BUILTIN_TOOLCHAINS)
    declared = doc.get("toolchains")
    if isinstance(declared, dict):
        merged.update({k: v for k, v in declared.items() if isinstance(v, dict)})
    return merged


def composes(cmd: str) -> bool:
    """Does `cmd` chain a second command outside quotes?"""
    return bool(SHELL_COMPOSE.search(QUOTED.sub("''", cmd)))


def argv0(cmd: str) -> str:
    """The executable's basename, however it is spelled or quoted."""
    try:
        first = shlex.split(cmd, posix=True)[0]
    except (ValueError, IndexError):
        first = cmd.split()[0] if cmd.split() else ""
    return first.replace("\\", "/").rsplit("/", 1)[-1]


def command_problems(step: object, table: dict, where: str, need_exit: bool) -> list:
    """Why one declared command is not runnable as declared. A script node's
    `script` (need_exit=True: it declares expectExit) and every plain step --
    acceptance, setup, gate, smoke (need_exit=False: exit 0 passes) -- share
    this, so no surface can disagree with another about what a command is."""
    out: list = []
    if not isinstance(step, dict):
        step = {}
    runtime = step.get("runtime")
    if runtime not in table:
        out.append(f"[AP-SCRIPT-NO-RUNTIME] {where}.runtime {runtime!r} names no toolchain: use "
                   f"a built-in ({', '.join(sorted(BUILTIN_TOOLCHAINS))}) or declare it under "
                   "the document's 'toolchains'. Preflight runs exactly that toolchain's "
                   "version probe, so an unnamed runtime is a check nobody runs")
    cmd = step.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        out.append(f"[AP-SCRIPT-NO-COMMAND] {where}.command must be the exact command to run")
    elif composes(cmd):
        out.append(f"[AP-SCRIPT-NO-COMMAND] {where}.command must be ONE command -- no unquoted "
                   "; | & ` $( or newline (redirect inside the script instead); the runner "
                   "guard matches it exactly, and a chain would carry a second command through")
    elif runtime in table:
        exes = table[runtime].get("executables") or []
        if not any(fnmatch.fnmatchcase(argv0(cmd), pat) for pat in exes):
            out.append(f"[AP-SCRIPT-RUNTIME-MISMATCH] toolchain {runtime!r} runs {exes}, but "
                       f"{where}.command starts with {argv0(cmd)!r}; preflight would check "
                       "the wrong toolchain")
    if need_exit:
        exits = step.get("expectExit")
        if (not isinstance(exits, list) or not exits
                or not all(isinstance(x, int) and not isinstance(x, bool) for x in exits)):
            out.append(f"[AP-SCRIPT-NO-COMMAND] {where}.expectExit must be a non-empty list of "
                       "exit codes; an unexpected exit halts the run")
        parse = step.get("parse")
        if parse is not None and parse not in PARSE_MODES:
            out.append(f"{where}.parse must be one of {sorted(PARSE_MODES)} when present")
    return out


def script_problems(script: object, toolchains: dict | None = None) -> list:
    """A script node's / script phase's `script` block. `toolchains` is
    toolchains_of(<the document>); None means the built-ins only."""
    table = BUILTIN_TOOLCHAINS if toolchains is None else toolchains
    return command_problems(script, table, "script", need_exit=True)


def steps_of(doc: dict) -> list:
    """(where, step) for every declared command in a design or spec."""
    out = []
    for i, g in enumerate(doc.get("gates") or []):
        out.append((f"gates[{i}]", g))
    for n in doc.get("nodes") or doc.get("phases") or []:
        if not isinstance(n, dict):
            continue
        if isinstance(n.get("script"), dict):
            out.append((f"{n.get('id')}.script", n["script"]))
        for key in ("acceptance", "setup", "steps"):
            val = n.get(key)
            for j, st in enumerate(val if isinstance(val, list) else []):
                out.append((f"{n.get('id')}.{key}[{j}]", st))
    return out


def toolchains_used(doc: dict) -> dict:
    """{toolchain: version probe} for every toolchain any declared command names
    -- exactly what arbeitsplan-preflight must prove installed first."""
    table = toolchains_of(doc)
    out = {}
    for _where, st in steps_of(doc):
        rt = st.get("runtime") if isinstance(st, dict) else None
        if rt in table:
            out[rt] = table[rt].get("version")
    return out


def script_commands(design_or_spec: dict) -> list:
    """Every declared script-node command template, for the runner guard's
    allowlist. Plain steps (acceptance, gates, smoke) are not here: they are
    run by the builder, the state helper or the smoke agent, never by the
    script runner."""
    out = []
    for n in design_or_spec.get("nodes") or design_or_spec.get("phases") or []:
        if isinstance(n, dict) and isinstance(n.get("script"), dict):
            cmd = n["script"].get("command")
            if isinstance(cmd, str) and cmd:
                out.append({"node": n.get("id"), "command": cmd,
                            "placeholders": PLACEHOLDER_RE.findall(cmd)})
    return out


# --- graph ---------------------------------------------------------------------

def _topo(nodes: dict) -> list | None:
    """Kahn's order over depends_on, or None on a cycle."""
    indeg = {nid: 0 for nid in nodes}
    for nid, n in nodes.items():
        for d in n.get("depends_on") or []:
            if d in nodes:
                indeg[nid] += 1
    ready = sorted(nid for nid, k in indeg.items() if k == 0)
    order = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for mid, m in nodes.items():
            if nid in (m.get("depends_on") or []):
                indeg[mid] -= 1
                if indeg[mid] == 0:
                    ready.append(mid)
                    ready.sort()
    return order if len(order) == len(nodes) else None


def _ancestors(nid: str, nodes: dict) -> set:
    seen: set = set()
    stack = list(nodes[nid].get("depends_on") or [])
    while stack:
        d = stack.pop()
        if d in seen or d not in nodes:
            continue
        seen.add(d)
        stack.extend(nodes[d].get("depends_on") or [])
    return seen


# --- the validator ---------------------------------------------------------------

def validate_design(design: dict) -> tuple:
    """Returns (errors, warnings), both `"{where}: {msg}"` strings, like validate()."""
    errors: list = []
    warnings: list = []

    def err(where: str, msg: str) -> None:
        errors.append(f"{where}: {msg}")

    if not isinstance(design, dict):
        return ["design: not a JSON object"], warnings
    if design.get("schemaVersion") != DESIGN_SCHEMA_VERSION:
        err("schemaVersion", f"must be {DESIGN_SCHEMA_VERSION!r}")
    if not isinstance(design.get("name"), str) or not NAME_RE.match(design.get("name") or ""):
        err("name", "must be [a-z][a-z0-9-]{0,39} -- it names generated files")
    run_id = design.get("runId")
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        err("runId", "must be [A-Za-z0-9._-]{1,64} without '..' -- it is a path component")
    if not isinstance(design.get("problemRef"), str) or not design.get("problemRef"):
        err("problemRef", "must name the approved problem statement (a path)")
    off = design.get("offLimits")
    if not isinstance(off, list) or not all(isinstance(o, str) and o for o in off):
        err("offLimits", "must be a list of globs (empty is allowed, absent is not)")
    budget = design.get("budget")
    if budget is not None:
        total = budget.get("totalDispatches") if isinstance(budget, dict) else None
        if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
            err("budget", "when present must be {totalDispatches: positive int}; absent means "
                          "no cap (#106 R9: subscription limits stop the run, resume is cheap)")
    for msg in toolchain_problems(design.get("toolchains")):
        err("toolchains", msg)
    table = toolchains_of(design)

    raw_nodes = design.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        err("nodes", "must be a non-empty list")
        return errors, warnings

    nodes: dict = {}
    for i, n in enumerate(raw_nodes):
        if not isinstance(n, dict):
            err(f"nodes[{i}]", "not an object")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not ID_RE.match(nid):
            err(f"nodes[{i}]", "'id' must be [A-Za-z0-9._-]{1,64}")
            continue
        if nid in nodes:
            err(f"nodes[{i}] ({nid})", "duplicate node id")
            continue
        nodes[nid] = n

    for nid, n in nodes.items():
        _validate_node(nid, n, nodes, table, err)

    if any("[AP-DEPENDS-UNKNOWN]" in e for e in errors):
        return errors, warnings
    if _topo(nodes) is None:
        err("nodes", "[AP-DEPENDS-CYCLE] depends_on has a cycle; WHEN a node runs must be "
                     "decidable before anything runs")
        return errors, warnings

    ancestors = {nid: _ancestors(nid, nodes) for nid in nodes}
    for gid, g in nodes.items():
        if g.get("kind") != "human-gate":
            continue
        concurrent = sorted(nid for nid in nodes if nid != gid and nid not in ancestors[gid]
                            and gid not in ancestors[nid])
        if concurrent:
            err(f"node {gid}", f"[AP-HUMAN-GATE-INSIDE] {concurrent} run neither before nor "
                               "after this gate; a workflow run cannot pause for input, so a "
                               "human gate must cut the graph into a run before and a run after")

    _validate_waves(design, nodes, ancestors, table, err)
    _validate_agent_types(design, nodes, err)
    _validate_authored(design, nodes, err)
    return errors, warnings


def _validate_authored(design: dict, nodes: dict, err) -> None:
    """A script node whose step is WRITTEN by the plan rather than found.

    `script.author = {model, purpose, sample: {args, expectExit}}`. There is no
    path and no language key: the runtime is the language, and the path is
    fixed (waves_state.step_path) -- two keys that could only disagree with
    something else are two keys a design cannot get wrong.
    """
    waves = any("wave" in n for n in nodes.values())
    name = design.get("name") if isinstance(design.get("name"), str) else ""
    for nid, n in nodes.items():
        sc = n.get("script")
        author = sc.get("author") if isinstance(sc, dict) else None
        if author is None:
            continue
        where = f"node {nid}"
        if n.get("kind") != "script" or n.get("writeScope") != [] or not waves:
            err(where, "[AP-AUTHOR-KIND] only a script node with writeScope [] in a WAVE "
                       "design may author its step: install_waves.py is the only thing that "
                       "writes step files, and a merge-gate's command is the state helper's")
            continue
        if not isinstance(author, dict) or set(author) - AUTHOR_KEYS:
            extra = sorted(set(author) - AUTHOR_KEYS) if isinstance(author, dict) else author
            err(where, f"'script.author' carries only {sorted(AUTHOR_KEYS)}; {extra} is not "
                       "one -- the path and language follow from the runtime")
            continue
        runtime = sc.get("runtime")
        if runtime not in waves_state.AUTHORABLE:
            err(where, f"[AP-AUTHOR-LANG] runtime {runtime!r} cannot be authored; the "
                       f"authorable ones are {sorted(waves_state.AUTHORABLE)}, each with a "
                       "syntax check the state helper runs before the sample does")
            continue
        if not model_ok(author.get("model")):
            err(where, f"[AP-NODE-NO-MODEL] 'script.author.model' must be {MODEL_RULE}: the "
                       "author is a dispatch of its own")
        if NAME_RE.match(name):
            rel = waves_state.step_path(name, nid, runtime)
            try:
                argv = shlex.split(str(sc.get("command") or ""))
            except ValueError:
                argv = []
            exes = waves_state.AUTHORABLE[runtime]["exes"]
            first = next((a for a in argv[1:] if not a.startswith("-")), None)
            ok = (bool(argv) and any(fnmatch.fnmatchcase(argv0(argv[0]), e) for e in exes)
                  and first == rel)
            if ok and runtime == "powershell":
                ok = argv[argv.index(rel) - 1].lower() == "-file"
            if not ok:
                err(where, f"[AP-AUTHOR-COMMAND] an authored {runtime} step runs as "
                           f"`{exes[0]} {'-File ' if runtime == 'powershell' else ''}{rel} "
                           "[args]`: the interpreter the syntax check uses, then the one file "
                           "the author writes")
        sample = author.get("sample")
        exits = (sc.get("expectExit") if isinstance(sc.get("expectExit"), list) else [])
        good = (isinstance(author.get("purpose"), str) and author["purpose"].strip()
                and isinstance(sample, dict) and set(sample) <= {"args", "expectExit"}
                and isinstance(sample.get("args"), list)
                and all(isinstance(a, str) and SAMPLE_ARG_RE.match(a) for a in sample["args"])
                and isinstance(sample.get("expectExit"), list) and sample["expectExit"]
                and all(isinstance(x, int) and not isinstance(x, bool) and x in exits
                        for x in sample["expectExit"]))
        if not good:
            err(where, "[AP-AUTHOR-NO-CONTRACT] an authored step needs 'purpose' (what the "
                       "author writes) and 'sample' {args: [plain ids, paths or values], "
                       "expectExit: [a subset of script.expectExit]}: the author writes "
                       "against that contract and verify-step runs exactly that sample")


def _agent_decl(n: dict, key: str) -> object:
    """A node's value for one AGENT_KEYS key, normalised so that order in a
    list and the implicit builder role are not disagreements."""
    val = n.get(key)
    if key == "role":
        return val or "builder"
    if isinstance(val, list):
        return tuple(sorted(str(v) for v in val))
    return val


def _validate_agent_types(design: dict, nodes: dict, err) -> None:
    """One agent type, one definition (#107 'how': agentType, skills, tools).

    [AP-AGENT-CONFLICT] -- nodes naming the same agentType disagree on a key
    the agent FILE carries. Absent vs present is a disagreement too: the
    generated file can say `effort: high` or nothing, not both.

    [AP-AGENT-KEYS-UNAPPLIED] -- in a wave design, install_waves.py generates
    the files for `<name>-*` types only. A node that declares effort, tools or
    skills on any other type (a plugin's, one written by hand) has declared
    keys nothing will ever write: validated, then silently dropped."""
    by_type: dict = {}
    for nid, n in nodes.items():
        at = n.get("agentType")
        if isinstance(at, str) and at and n.get("kind") != "human-gate":
            by_type.setdefault(at, []).append(nid)
    for at, ids in sorted(by_type.items()):
        for key in AGENT_KEYS:
            vals = {_agent_decl(nodes[i], key) for i in ids}
            if len(vals) > 1:
                shown = ", ".join(f"{i}={nodes[i].get(key)!r}" for i in ids)
                err(f"agentType {at}", f"[AP-AGENT-CONFLICT] nodes disagree on '{key}' ({shown}). "
                                       "An agent type is ONE file with ONE frontmatter; make "
                                       "them agree, or give the odd one out its own agentType")
    name = design.get("name")
    if (not any("wave" in n for n in nodes.values()) or not isinstance(name, str)
            or not NAME_RE.match(name)):
        return  # an invalid name is already an error; its prefix proves nothing
    for nid, n in nodes.items():
        at = n.get("agentType")
        declared = [k for k in ("effort", "tools", "skills") if n.get(k) is not None]
        if isinstance(at, str) and declared and not at.startswith(f"{name}-"):
            err(f"node {nid}", f"[AP-AGENT-KEYS-UNAPPLIED] declares {declared} on agentType "
                               f"{at!r}, which this design does not generate (only {name}-* "
                               "types are written); those keys would reach no file. Name a "
                               f"{name}-* type, or drop the keys and rely on {at!r}'s own "
                               "definition")


def _validate_steps(where: str, steps: object, table: dict, err, required: bool) -> None:
    if steps is None and not required:
        return
    if not isinstance(steps, list) or (required and not steps):
        err(where, "must be a list of {runtime, command} steps")
        return
    for j, st in enumerate(steps):
        for msg in command_problems(st, table, f"{where.rsplit('.', 1)[-1]}[{j}]",
                                    need_exit=False):
            err(where.rsplit(".", 1)[0], msg)


def _validate_node(nid: str, n: dict, nodes: dict, table: dict, err) -> None:
    where = f"node {nid}"
    kind = n.get("kind")
    if kind not in NODE_KINDS:
        err(where, f"'kind' must be one of {sorted(NODE_KINDS)}")
        return
    if not isinstance(n.get("goal"), str) or not n.get("goal"):
        err(where, "'goal' missing -- WHAT the node does is the first question")
    deps = n.get("depends_on")
    if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
        err(where, "'depends_on' must be a list of node ids (empty is allowed)")
        deps = []
    for d in deps:
        if d not in nodes:
            err(where, f"[AP-DEPENDS-UNKNOWN] depends_on {d!r}, which is not a node id")
    when = n.get("when")
    if when is not None and (not isinstance(when, dict) or set(when) != {"node", "field", "equals"}
                             or when.get("node") not in deps):
        err(where, "'when' must be {node, field, equals} naming a node this one depends_on "
                   "-- a condition on a node that may not have run is no condition")
    role = n.get("role")
    if role is not None and role not in ROLES:
        err(where, f"'role' must be one of {sorted(ROLES)} when present")
    for j, inp in enumerate(n.get("inputs") or []):
        if not isinstance(inp, str) or not INPUT_RE.match(inp):
            shown = inp[:40] + "..." if isinstance(inp, str) and len(inp) > 40 else inp
            err(where, f"[AP-INPUT-CONTENT] inputs[{j}] {shown!r} is not an id or a path; a "
                       "prompt carries ids and paths only, never a sibling's content")

    if kind == "human-gate":
        # A human gate runs BETWEEN workflow runs; it carries no model, schema
        # or scope because nothing is dispatched for it.
        return

    if n.get("where") not in WHERE:
        err(where, f"'where' must be one of {sorted(WHERE)} -- WHERE a node runs is never "
                   "inherited from the session's cwd")
    if not model_ok(n.get("model")):
        err(where, f"[AP-NODE-NO-MODEL] 'model' must be {MODEL_RULE}; a script node gets the "
                   "smallest model only when the design says so")
    eff = n.get("effort")
    if eff is not None and eff not in EFFORTS:
        err(where, f"'effort' must be one of {sorted(EFFORTS)} when present")
    schema = n.get("output_schema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        err(where, "[AP-NODE-NO-SCHEMA] 'output_schema' must be a JSON Schema whose top level "
                   "is type: object -- a node with no schema returns prose, and prose cannot "
                   "be validated")
    else:
        probs = strict_problems(schema)
        if probs:
            err(where, "[AP-SCHEMA-NOT-STRICT] " + "; ".join(probs[:3]))
    scope = n.get("writeScope")
    if not isinstance(scope, list) or not all(isinstance(s, str) and s for s in scope):
        err(where, "[AP-NODE-NO-SCOPE] 'writeScope' must be a list of globs on every "
                   "dispatched node (an empty list says 'writes nothing'; absent is never "
                   "read as 'anything')")
    elif kind == "agent" and n.get("where") == "worktree" and not scope:
        err(where, "[AP-NODE-NO-SCOPE] a worktree agent node builds something; an empty "
                   "writeScope would make every one of its edits out of scope")
    if kind == "agent" and not (isinstance(n.get("agentType"), str) and n.get("agentType")):
        err(where, "'agentType' is required on an agent node -- HOW it runs names the agent "
                   "definition, never the session inline")
    for key in ("skills", "tools"):
        val = n.get(key)
        if val is not None and (not isinstance(val, list)
                                or not all(isinstance(v, str) and v for v in val)):
            err(where, f"'{key}' must be a list of non-empty strings when present")
    retries = n.get("retries")
    if retries is not None and (isinstance(retries, bool) or not isinstance(retries, int)
                                or not 0 <= retries <= 3):
        err(where, "'retries' must be an int 0..3 when present")

    if kind in SCRIPTED:
        for msg in command_problems(n.get("script"), table, "script", need_exit=True):
            err(where, msg)
    elif n.get("script") is not None:
        err(where, "'script' belongs to a script or merge-gate node only")
    _validate_steps(f"{where}.acceptance", n.get("acceptance"), table, err, required=False)
    _validate_steps(f"{where}.setup", n.get("setup"), table, err, required=False)

    if kind == "merge-gate" and n.get("where") != "primary":
        err(where, "[AP-GATE-NOT-PRIMARY] a merge-gate runs in the primary checkout: that is "
                   "the only tree with the untracked and gitignored files no worktree has, and "
                   "its report must say which findings only appeared there")
    if role == "smoke":
        if n.get("where") != "scratch":
            err(where, "[AP-SMOKE-NOT-SCRATCH] a smoke node runs in a scratch directory outside "
                       "the repository, so it proves the artefact works outside the checkout, "
                       "not that the checkout happens to work")
        steps, skip = n.get("steps"), n.get("skip")
        if isinstance(skip, str) and skip.strip():
            if steps:
                err(where, "a smoke node declares 'steps' or 'skip', not both")
        elif not isinstance(steps, list) or not steps:
            err(where, "[AP-SMOKE-UNDECLARED] a smoke node declares its own 'steps' "
                       "({runtime, command}: build, install, run -- whatever THIS artefact "
                       "needs) or 'skip' with the reason it has no smoke test; installing "
                       "'the package' is not a default every ecosystem shares")
        else:
            _validate_steps(f"{where}.steps", steps, table, err, required=True)


def _validate_waves(design: dict, nodes: dict, ancestors: dict, table: dict, err) -> None:
    waved = {nid: n for nid, n in nodes.items() if "wave" in n}
    if not waved:
        return
    for nid, n in waved.items():
        w = n.get("wave")
        if isinstance(w, bool) or not isinstance(w, int) or w < 1:
            err(f"node {nid}", "'wave' must be an int >= 1")
            return
        if n.get("kind") not in ("agent", "merge-gate"):
            err(f"node {nid}", "only agent rows and a merge-gate carry 'wave'")
    count = max(n["wave"] for n in waved.values())
    if sorted({n["wave"] for n in waved.values()}) != list(range(1, count + 1)):
        err("nodes", f"waves must be numbered 1..{count} without gaps")
        return

    integ = design.get("integration")
    if (not isinstance(integ, dict) or not BRANCH_RE.match(str(integ.get("branch") or ""))
            or not BRANCH_RE.match(str(integ.get("target") or ""))
            or integ.get("branch") == integ.get("target")):
        err("integration", "a wave design names {branch, target}: waves merge into 'branch', "
                           "and 'target' is fast-forwarded only after a green gate. Neither is "
                           "inferred -- 'main' is a convention, not a fact about this repo")
    gates = design.get("gates")
    if not isinstance(gates, list) or not gates:
        err("gates", "[AP-GATES-UNDECLARED] a wave design declares its gates as {id, runtime, "
                     "command} steps; a merge-gate that runs gates nobody declared runs gates "
                     "nobody can check are installed")
    else:
        ids = set()
        for i, g in enumerate(gates):
            gid = g.get("id") if isinstance(g, dict) else None
            if not isinstance(gid, str) or not ID_RE.match(gid) or gid in ids:
                err(f"gates[{i}]", "needs a unique 'id'")
            ids.add(gid)
            for msg in command_problems(g, table, f"gates[{i}]", need_exit=False):
                err("gates", msg)

    for nid, n in nodes.items():
        if isinstance(n.get("script"), dict):
            unknown = (set(PLACEHOLDER_RE.findall(str(n["script"].get("command") or "")))
                       - WAVE_PLACEHOLDERS)
            if unknown:
                err(f"node {nid}", f"placeholders {sorted(unknown)} are filled by nothing; the "
                                   f"wave interpreter supplies {sorted(WAVE_PLACEHOLDERS)}")

    pre_id = integ.get("preflight") if isinstance(integ, dict) else None
    pre = nodes.get(pre_id) if isinstance(pre_id, str) else None
    if (pre is None or pre.get("kind") != "script"
            or any("wave" in nodes[a] for a in ancestors.get(pre_id, set()))):
        err("integration", "'preflight' must name a script node that runs before every wave: "
                           "it refuses a linked worktree and a dirty checkout, and its head is "
                           "wave 1's base")
    elif _requires(pre, PREFLIGHT_OUTPUT):
        err(f"node {pre_id}", f"the preflight's output_schema must require "
                              f"{sorted(_requires(pre, PREFLIGHT_OUTPUT))}")
    for nid, n in waved.items():
        if n.get("kind") != "merge-gate":
            continue
        slots = set(PLACEHOLDER_RE.findall(str((n.get("script") or {}).get("command") or "")))
        if GATE_PLACEHOLDERS - slots:
            err(f"node {nid}", f"a merge-gate command must take {sorted(GATE_PLACEHOLDERS)}; "
                               f"missing {sorted(GATE_PLACEHOLDERS - slots)}")
        if _requires(n, GATE_OUTPUT):
            err(f"node {nid}", f"a merge-gate's output_schema must require "
                               f"{sorted(_requires(n, GATE_OUTPUT))}")
    for nid, n in nodes.items():
        if ("wave" not in n and n.get("kind") == "agent" and n.get("where") == "worktree"
                and _requires(n, BUILDER_OUTPUT)):
            err(f"node {nid}", f"a worktree node after the waves must require "
                               f"{sorted(_requires(n, BUILDER_OUTPUT))} -- its branch goes "
                               "through the last merge-gate again")

    gate_of: dict = {}
    for w in range(1, count + 1):
        rows = [nid for nid, n in waved.items() if n["wave"] == w and n.get("kind") == "agent"]
        wg = [nid for nid, n in waved.items() if n["wave"] == w and n.get("kind") == "merge-gate"]
        if len(wg) != 1 or not rows:
            err(f"wave {w}", f"[AP-WAVE-NO-GATE] needs >= 1 agent row and exactly one "
                             f"merge-gate; has rows {rows} and gates {wg}. A wave that is not "
                             "merged and gated leaves the next wave with no base")
            continue
        gate_of[w] = wg[0]
        missing = [r for r in rows if r not in ancestors[wg[0]]]
        if missing:
            err(f"node {wg[0]}", f"[AP-WAVE-NO-GATE] the wave {w} merge-gate must come after "
                                 f"every row of its wave; missing {missing}")
        for r in rows:
            _validate_row(r, nodes[r], err)
        # Only CONCURRENT rows need disjoint scopes. A row that depends on
        # another row of its wave (an integrator registering modules, taking a
        # lockfile) runs on their merged result, so it may own the shared files
        # every ecosystem with a module manifest needs edited per new module.
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if a in ancestors[b] or b in ancestors[a]:
                    continue
                pairs = land_candidate.scopes_overlap(nodes[a].get("writeScope") or [],
                                                      nodes[b].get("writeScope") or [])
                if pairs:
                    x, y = pairs[0]
                    err(f"wave {w}", f"[AP-WAVE-SCOPE-OVERLAP] concurrent rows {a!r} and {b!r} "
                                     f"may both write ({x!r} vs {y!r}). Give the shared file to "
                                     "one owner: an integrator row that depends on both, a "
                                     "scaffold row in an earlier wave, or a split into one "
                                     "file per row -- never a merge that hopes")

    for w in gate_of:
        if w == 1:
            continue
        prev = gate_of.get(w - 1)
        for nid, n in waved.items():
            if n["wave"] == w and n.get("kind") == "agent" and prev not in ancestors[nid]:
                err(f"node {nid}", f"[AP-WAVE-NO-BASE] a wave {w} row must come after the wave "
                                   f"{w - 1} merge-gate {prev!r}: its worktree starts with "
                                   "`git merge --ff-only <wave base>`, and an undeclared base "
                                   "is the prototype's wrong-base bug")

    if gate_of:
        last = gate_of[max(gate_of)]
        for nid, n in nodes.items():
            if "wave" in n or n.get("kind") == "human-gate":
                continue
            touches = [a for a in ancestors[nid] if "wave" in nodes[a]]
            if touches and last not in ancestors[nid]:
                err(f"node {nid}", f"[AP-WAVE-ORDER] depends on wave nodes {sorted(touches)} "
                                   f"but not on the last merge-gate {last!r}; a node outside "
                                   "the waves runs before them all or after them all")


def _requires(n: dict, keys: set) -> set:
    schema = n.get("output_schema") if isinstance(n.get("output_schema"), dict) else {}
    return keys - set(schema.get("required") or [])


def _validate_row(nid: str, n: dict, err) -> None:
    missing = _requires(n, BUILDER_OUTPUT)
    if missing:
        err(f"node {nid}", f"a wave row's output_schema must require {sorted(missing)}: the "
                           "interpreter merges the branch it names and halts when baseSha is "
                           "not the wave base")
    if n.get("where") != "worktree":
        err(f"node {nid}", "a wave row runs in its own worktree ('where': 'worktree')")
    swarm = n.get("swarm", 1)
    if isinstance(swarm, bool) or not isinstance(swarm, int) or not 1 <= swarm <= 16:
        err(f"node {nid}", "'swarm' must be an int 1..16 when present")
        swarm = 1
    if swarm > 1:
        ref = n.get("referee")
        ref_ok = (isinstance(ref, dict) and model_ok(ref.get("model"))
                  and isinstance(ref.get("agentType"), str) and ref.get("agentType"))
        if not n.get("acceptance") or not ref_ok:
            err(f"node {nid}", "[AP-SWARM-INCOMPLETE] a swarm row (swarm > 1) needs "
                               "'acceptance' steps and a 'referee' {model, agentType}: the blind "
                               "referee sees only branch names and those commands, and nothing "
                               "else can pick the one to keep")


# --- selftest ------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "design"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _node(design: dict, nid: str) -> dict:
    return next(n for n in design["nodes"] if n["id"] == nid)


def _obj(**props) -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": sorted(props), "properties": props}


def selftest() -> int:
    good = _load("waves.design.json")
    rust = _load("integrator.design.json")
    auth = _load("authored.design.json")

    def w(nid: str, base: dict | None = None, **over) -> dict:
        d = copy.deepcopy(good if base is None else base)
        n = _node(d, nid)
        for k, v in over.items():
            if v is None:
                n.pop(k, None)
            else:
                n[k] = v
        return d

    def top(base: dict | None = None, **over) -> dict:
        d = copy.deepcopy(good if base is None else base)
        for k, v in over.items():
            if v is None:
                d.pop(k, None)
            else:
                d[k] = v
        return d

    def sc(runtime: str, command: str, exits: list | None = None) -> dict:
        return {"runtime": runtime, "command": command, "expectExit": exits or [0]}

    pre = "preflight"
    cases = [
        ("clean Go wave design", good, None),
        ("clean Rust design with an integrator row", rust, None),
        ("bad name", top(name="Bad Name"), ""),
        ("offLimits absent", top(offLimits=None), ""),
        ("unknown kind", w(pre, kind="magic"), ""),
        ("no goal", w(pre, goal=None), ""),
        ("no where", w(pre, where=None), ""),
        ("agent without agentType", w("w1-parse", agentType=None), ""),
        ("integration absent", top(integration=None), ""),
        ("integration target == branch", top(integration={"branch": "trunk", "target": "trunk"}),
         ""),
        ("unknown placeholder", w(pre, script=sc("python", "python3 x.py {colour}")), ""),
        ("no model", w(pre, model=None), "AP-NODE-NO-MODEL"),
        ("model that is neither alias nor id", w("w1-parse", model="gpt-5"),
         "AP-NODE-NO-MODEL"),
        ("full model id -- clean", w("w1-parse", model="claude-opus-5-5"), None),
        ("fable alias -- clean", w("w1-parse", model="fable"), None),
        ("no schema", w("review", output_schema=None), "AP-NODE-NO-SCHEMA"),
        ("array schema", w("review", output_schema={"type": "array"}), "AP-NODE-NO-SCHEMA"),
        ("loose schema", w("review", output_schema={"type": "object", "properties": {}}),
         "AP-SCHEMA-NOT-STRICT"),
        ("nested loose schema", w("review", output_schema=_obj(
            inner={"type": "object", "properties": {}})), "AP-SCHEMA-NOT-STRICT"),
        ("JSON in a string", w("review", output_schema=_obj(stateJson={"type": "string"})),
         "AP-SCHEMA-NOT-STRICT"),
        ("no writeScope", w(pre, writeScope=None), "AP-NODE-NO-SCOPE"),
        ("empty writeScope on a worktree row", w("w1-parse", writeScope=[]),
         "AP-NODE-NO-SCOPE"),
        ("script without runtime", w(pre, script={"command": "python3 x.py",
                                                  "expectExit": [0]}), "AP-SCRIPT-NO-RUNTIME"),
        ("undeclared toolchain", w(pre, script=sc("gleam", "gleam run")),
         "AP-SCRIPT-NO-RUNTIME"),
        ("toolchain declared by the design -- clean", top(
            w(pre, script=sc("gleam", "gleam run -m state")),
            toolchains={"gleam": {"executables": ["gleam"], "version": "gleam --version"}}),
         None),
        ("declared toolchain with a chained probe", top(
            w(pre, script=sc("gleam", "gleam run -m state")),
            toolchains={"gleam": {"executables": ["gleam"], "version": "gleam -V; curl x"}}),
         ""),
        ("script without command", w(pre, script={"runtime": "python", "expectExit": [0]}),
         "AP-SCRIPT-NO-COMMAND"),
        ("script chaining a second command", w(pre, script=sc(
            "python", "python3 x.py && rm -rf .")), "AP-SCRIPT-NO-COMMAND"),
        ("script redirecting 2>&1", w(pre, script=sc("python", "python3 x.py 2>&1")),
         "AP-SCRIPT-NO-COMMAND"),
        ("quoted ';' is one command -- clean", w(pre, script=sc(
            "julia", "julia -e 'using Pkg; Pkg.test()'")), None),
        ("script without expectExit", w(pre, script={"runtime": "python",
                                                     "command": "python3 x.py"}),
         "AP-SCRIPT-NO-COMMAND"),
        ("go toolchain, python command", w(pre, script=sc("go", "python3 x.py")),
         "AP-SCRIPT-RUNTIME-MISMATCH"),
        ("gate step toolchain mismatch", top(gates=[{"id": "vet", "runtime": "rust",
                                                     "command": "go vet ./..."}]),
         "AP-SCRIPT-RUNTIME-MISMATCH"),
        ("acceptance step toolchain mismatch", w("w1-parse", acceptance=[
            {"runtime": "node", "command": "go test ./internal/parse/..."}]),
         "AP-SCRIPT-RUNTIME-MISMATCH"),
        ("powershell -- clean", w(pre, script=sc("powershell",
                                                 "pwsh -NoProfile -File tools/state.ps1")), None),
        ("haskell via cabal -- clean", w(pre, script=sc("haskell",
                                                        "cabal run state -- preflight")), None),
        ("java via ./gradlew -- clean", w(pre, script=sc("java", "./gradlew conformance",
                                                         [0, 1])), None),
        ("python via .venv/bin/python -- clean", w(pre, script=sc(
            "python", ".venv/bin/python tools/state.py")), None),
        ("python3.12 -- clean", w(pre, script=sc("python", "python3.12 tools/state.py")), None),
        ("dotnet -- clean", w(pre, script=sc("dotnet", "dotnet run --project tools/State")),
         None),
        ("overlapping concurrent rows", w("w1-render", writeScope=["internal/**"]),
         "AP-WAVE-SCOPE-OVERLAP"),
        ("basename glob overlaps everything", w("w1-render", writeScope=["*.go"]),
         "AP-WAVE-SCOPE-OVERLAP"),
        ("case-only difference overlaps", w("w1-render", writeScope=["Internal/Parse/**"]),
         "AP-WAVE-SCOPE-OVERLAP"),
        ("integrator made concurrent -> overlap", w("gate-1", w("w1-register", rust,
                                                                depends_on=["preflight"]),
                                                    depends_on=["w1-lexer", "w1-eval",
                                                                "w1-register"]),
         "AP-WAVE-SCOPE-OVERLAP"),
        ("input carrying content", w("w2-cli", inputs=["the parser now returns a struct"]),
         "AP-INPUT-CONTENT"),
        ("unknown dependency", w("w1-parse", depends_on=["nope"]), "AP-DEPENDS-UNKNOWN"),
        ("cycle", w(pre, depends_on=["gate-1"]), "AP-DEPENDS-CYCLE"),
        ("gate without every row", w("gate-1", depends_on=["w1-parse"]), "AP-WAVE-NO-GATE"),
        ("wave 2 row not after the wave 1 gate", w("w2-cli", depends_on=["preflight"]),
         "AP-WAVE-NO-BASE"),
        ("post node skipping the last gate", w("smoke", depends_on=["w2-cli"]),
         "AP-WAVE-ORDER"),
        ("gates undeclared", top(gates=None), "AP-GATES-UNDECLARED"),
        ("swarm without referee", w("w1-parse", swarm=2, referee=None), "AP-SWARM-INCOMPLETE"),
        ("merge-gate in a worktree", w("gate-1", where="worktree"), "AP-GATE-NOT-PRIMARY"),
        ("smoke in the primary checkout", w("smoke", where="primary"), "AP-SMOKE-NOT-SCRATCH"),
        ("smoke with neither steps nor skip", w("smoke", steps=None), "AP-SMOKE-UNDECLARED"),
        ("smoke skipped with a reason -- clean", w("smoke", steps=None,
                                                   skip="a library with no entry point"), None),
        ("one builder type, effort on only some nodes", w("w1-render", effort=None),
         "AP-AGENT-CONFLICT"),
        ("one builder type, two roles", w("w2-cli", role="integrator"), "AP-AGENT-CONFLICT"),
        ("one builder type, same tools in another order -- clean",
         w("w2-cli", w("w1-render", w("w1-parse", tools=["Read", "Bash"]),
                       tools=["Bash", "Read"]), tools=["Read", "Bash"]), None),
        ("one builder type, skills on one node only", w("w1-parse", skills=["api-conventions"]),
         "AP-AGENT-CONFLICT"),
        ("different models on one type -- clean (model is per dispatch)",
         w("w2-cli", model="sonnet"), None),
        ("skills on a plugin agent in a wave design",
         w("review", agentType="arbeitsplan:synthesizer", skills=["api-conventions"]),
         "AP-AGENT-KEYS-UNAPPLIED"),
        ("plugin agent without agent keys -- clean",
         w("review", agentType="arbeitsplan:synthesizer"), None),
    ]
    def au(runtime: str | None = None, command: str | None = None, **author) -> dict:
        """The authored fixture with its step's script or author block changed."""
        d = copy.deepcopy(auth)
        sc = _node(d, "api-surface")["script"]
        if runtime:
            sc["runtime"] = runtime
        if command:
            sc["command"] = command
        for k, v in author.items():
            if v is None:
                sc["author"].pop(k, None)
            else:
                sc["author"][k] = v
        return d

    step = ".claude/workflows/rebuild-cli.steps/api-surface"
    cases += [
        ("authored python step -- clean", auth, None),
        ("authored shell step -- clean", au("shell", f"bash {step}.sh cmd/tool"), None),
        ("authored powershell step -- clean", au("powershell",
                                                 f"pwsh -NoProfile -NonInteractive -File {step}.ps1 "
                                                 "cmd/tool"), None),
        ("authored ruby step -- clean", au("ruby", f"ruby {step}.rb cmd/tool"), None),
        ("authored node step is .mjs -- clean", au("node", f"node {step}.mjs cmd/tool"), None),
        ("authored step with placeholders -- clean", au(command=f"python3 {step}.py {{base}}"),
         None),
        ("authored go step", au("go", "go run ./tools/api-surface"), "AP-AUTHOR-LANG"),
        ("authored step at another path", au(command="python3 tools/api_surface.py cmd/tool"),
         "AP-AUTHOR-COMMAND"),
        ("authored node step as .js", au("node", f"node {step}.js cmd/tool"),
         "AP-AUTHOR-COMMAND"),
        ("authored powershell step without -File", au("powershell", f"pwsh {step}.ps1"),
         "AP-AUTHOR-COMMAND"),
        ("authored step with no sample", au(sample=None), "AP-AUTHOR-NO-CONTRACT"),
        ("authored step with no purpose", au(purpose=""), "AP-AUTHOR-NO-CONTRACT"),
        ("sample exit the script never expects", au(sample={"args": [], "expectExit": [3]}),
         "AP-AUTHOR-NO-CONTRACT"),
        ("sample argument carrying a space", au(sample={"args": ["a b"], "expectExit": [0]}),
         "AP-AUTHOR-NO-CONTRACT"),
        ("authored step without an author model", au(model=None), "AP-NODE-NO-MODEL"),
        ("author carrying a path key", au(path="x.py"), ""),
        ("author on a merge-gate", w("gate-1", auth, script={
            **_node(auth, "gate-1")["script"], "author": _node(auth, "api-surface")["script"][
                "author"]}), "AP-AUTHOR-KIND"),
        ("author on a node that writes", w("api-surface", auth, writeScope=["x/**"]),
         "AP-AUTHOR-KIND"),
    ]
    flat = copy.deepcopy(auth)
    for n in flat["nodes"]:
        n.pop("wave", None)
    cases.append(("author in a design without waves", flat, "AP-AUTHOR-KIND"))

    gate_mid = copy.deepcopy(good)
    gate_mid["nodes"].append({"id": "approve", "kind": "human-gate", "goal": "g",
                              "depends_on": ["w1-parse"]})
    cases.append(("human gate beside a running wave", gate_mid, "AP-HUMAN-GATE-INSIDE"))
    gate_ok = copy.deepcopy(good)
    gate_ok["nodes"].append({"id": "approve", "kind": "human-gate", "goal": "g",
                             "depends_on": ["gate-1"]})
    for n in gate_ok["nodes"]:
        if n.get("wave") == 2:
            n["depends_on"] = [*n["depends_on"], "approve"]
    cases.append(("human gate between wave 1 and wave 2 -- clean", gate_ok, None))

    fails = []
    for name, design, want in cases:
        errs, _w = validate_design(design)
        if want is None:
            ok = not errs
        elif want == "":
            ok = bool(errs) and not any("[AP-" in e for e in errs)
        else:
            ok = bool(errs) and all(f"[{want}]" in e for e in errs)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {len(errs)} error(s)")
        if not ok:
            fails.append(name)
            for e in errs:
                print(f"        {e}")
    overlap = [
        ("src/a/**", "src/b/**", False), ("src/**", "src/a/x.py", True),
        ("src/a.py", "src/a.py", True), ("src/a.py", "src/b.py", False),
        ("a.py", "src/a.py", True), ("src/*", "src/a/b.py", True),
        ("src/cli/*.py", "docs/**", False), ("*.md", "docs/x/**", True),
        ("src/a*/x", "src/b/**", True), ("Src/A.go", "src/a.go", True),
        ("Docs/**", "docs/x.md", True),
    ]
    for a, b, want in overlap:
        got = land_candidate.scope_overlap(a, b)
        ok = got == want and land_candidate.scope_overlap(b, a) == want
        print(f"  {'ok  ' if ok else 'FAIL'} scope_overlap({a!r}, {b!r}) == {want}")
        if not ok:
            fails.append(f"scope_overlap {a} {b}")
    used = toolchains_used(good)
    if set(used) != {"go", "python"}:
        fails.append(f"toolchains_used(Go design) == {sorted(used)}, expected go + python")
    if design_hash(good) != design_hash(json.loads(json.dumps(good))):
        fails.append("design_hash is not canonical")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"design selftest passed ({len(cases)} designs, {len(overlap)} overlap pairs)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="design_spec.py",
        description="Design-table validator (#107/#106). Compile a design with "
                    "compile_spec.py --design --spec FILE; this entry point only runs the "
                    "planted-defect selftest.",
        epilog="exit 0 selftest passed, 1 failed, 2 bad usage")
    parser.add_argument("--selftest", action="store_true", help="run the selftest")
    args = parser.parse_args(argv)
    if not args.selftest:
        parser.print_help(sys.stderr)
        return 2
    return selftest()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
