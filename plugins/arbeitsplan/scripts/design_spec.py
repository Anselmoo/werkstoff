#!/usr/bin/env python3
"""Validate a design table (design.json, schemaVersion "design/1").

usage: imported by compile_spec.py (`--design FILE`); `design_spec.py --selftest`
runs the planted-defect cases on their own.

A design table is the node-by-node answer to WHAT (goal, outputs), WHERE
(primary | worktree | scratch), WHEN (depends_on, human gates between runs) and
HOW (kind, model, schema, write scope, script runtime) for every step of a
workflow, BEFORE anything runs (#107). A design whose nodes carry `wave` is also
the plan table the multi-wave interpreter executes (#106), so both issues share
this one validator. references/design-table-schema.md is the prose contract.

Every rule the issues name is TAGGED ([AP-...], DESIGN_RULES) and has a
committed red fixture under fixtures/red/ (MANIFEST.json, `--design`), proved by
test_red_fixtures.py. Pure shape errors (a missing id, an unknown kind) are
untagged and covered by this module's own selftest, the split compile_spec.py
already uses.

Never infer a missing gating value: a node without a model does NOT default to
the smallest one; the design skill proposes a default and the design must say it.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import land_candidate  # scope_overlap: the one place write-scope overlap is decided

DESIGN_SCHEMA_VERSION = "design/1"
NODE_KINDS = {"agent", "script", "referee", "merge-gate", "human-gate"}
SCRIPTED = {"script", "merge-gate"}  # kinds that execute a declared command
WHERE = {"primary", "worktree", "scratch"}
# Models: an alias, or a full model id. The alias list is what agent()'s
# `model` resolves today; a full `claude-...` id is how a newer model is named
# without editing this file. Never a default -- an omitted model inherits the
# session's, which silently defeats per-node tiering.
MODEL_ALIASES = ("haiku", "sonnet", "opus", "fable")
MODEL_ID_RE = re.compile(r"\Aclaude-[a-z0-9]+(?:[-.][a-z0-9]+)*(?:\[1m\])?\Z")
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
ROLES = {"builder", "referee", "merger", "integrator", "smoke", "reviewer", "fixer", "runner"}
# Toolchains a script node may name. This is a STARTING SET, not a whitelist:
# a design (or a workflow spec) declares any other runtime in its own
# `toolchains` block, which may also override an entry here (a pinned
# interpreter path, a wrapper script). Each entry lists the executables a
# command for it may start with and the ONE version probe preflight runs, so a
# design can never name a runtime the machine was never asked about.
BUILTIN_TOOLCHAINS = {
    "shell": {"executables": ["bash", "sh", "zsh"], "version": "bash --version"},
    "powershell": {"executables": ["pwsh", "powershell"], "version": "pwsh -Version"},
    "python": {"executables": ["python3", "python", "py"], "version": "python3 --version"},
    "uv": {"executables": ["uv", "uvx"], "version": "uv --version"},
    "node": {"executables": ["node", "npm", "npx", "pnpm", "yarn"], "version": "node --version"},
    "deno": {"executables": ["deno"], "version": "deno --version"},
    "bun": {"executables": ["bun", "bunx"], "version": "bun --version"},
    "go": {"executables": ["go"], "version": "go version"},
    "rust": {"executables": ["cargo", "rustc"], "version": "cargo --version"},
    "haskell": {"executables": ["ghc", "runghc", "cabal", "stack"], "version": "ghc --version"},
    "ruby": {"executables": ["ruby", "bundle", "rake"], "version": "ruby --version"},
    "java": {"executables": ["java", "mvn", "gradle", "./gradlew", "./mvnw"],
             "version": "java -version"},
    "dotnet": {"executables": ["dotnet"], "version": "dotnet --version"},
    "julia": {"executables": ["julia"], "version": "julia --version"},
    "r": {"executables": ["Rscript", "R"], "version": "Rscript --version"},
    "elixir": {"executables": ["elixir", "mix"], "version": "elixir --version"},
    "perl": {"executables": ["perl"], "version": "perl --version"},
    "php": {"executables": ["php", "composer"], "version": "php --version"},
    "make": {"executables": ["make"], "version": "make --version"},
    "cmake": {"executables": ["cmake", "ctest"], "version": "cmake --version"},
}
NAME_RE = re.compile(r"\A[a-z][a-z0-9-]{0,39}\Z")
ID_RE = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")
RUN_ID_RE = re.compile(r"\A(?!\.+\Z)(?!.*\.\.)[A-Za-z0-9._-]{1,64}\Z")
# An input is an id or a path, never content: no whitespace, nothing a prompt
# could smuggle a sibling's text through (#106 R8).
INPUT_RE = re.compile(r"\A[A-Za-z0-9._/@{}*-]{1,256}\Z")
# One command, not a pipeline: the runner guard matches it exactly, so chaining
# would let one declared command carry an undeclared second one.
SHELL_COMPOSE = re.compile(r"[;|&`\n]|\$\(")
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")

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
    "AP-SWARM-INCOMPLETE": 106,
    "AP-GATE-NOT-PRIMARY": 106,
    "AP-SMOKE-NOT-SCRATCH": 106,
}


def design_hash(design: dict) -> str:
    """sha256 over canonical JSON -- what an approval binds to (#107 step 2)."""
    canon = json.dumps(design, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


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
    is_object = schema.get("type") == "object" or "properties" in schema
    if is_object:
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


def model_ok(model: object) -> bool:
    return isinstance(model, str) and (model in MODEL_ALIASES or bool(MODEL_ID_RE.match(model)))


MODEL_RULE = (f"an alias {list(MODEL_ALIASES)} or a full model id (claude-...), and is never "
              "omitted -- an omitted model inherits the session's")


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
                       "executable names")
        if not isinstance(ver, str) or not ver.strip() or SHELL_COMPOSE.search(ver):
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


def toolchains_used(doc: dict) -> dict:
    """{runtime: version probe} for every runtime a script node names -- exactly
    what arbeitsplan-preflight must prove installed before the run starts."""
    table = toolchains_of(doc)
    out = {}
    for n in doc.get("nodes") or doc.get("phases") or []:
        script = n.get("script") if isinstance(n, dict) else None
        rt = script.get("runtime") if isinstance(script, dict) else None
        if rt in table:
            out[rt] = table[rt].get("version")
    return out


def _starts_with(cmd: str, executables: list) -> bool:
    first = cmd.split()[0]
    return first in executables or first.replace("\\", "/").rsplit("/", 1)[-1] in executables


def script_problems(script: object, toolchains: dict | None = None) -> list:
    """Why a `script` block is not runnable as declared -- shared by a design's
    script/merge-gate nodes and a workflow spec's `script` phase kind, so the
    two surfaces can never disagree about what a script node is. `toolchains`
    is toolchains_of(<the document>); None means the built-ins only."""
    table = BUILTIN_TOOLCHAINS if toolchains is None else toolchains
    out: list = []
    if not isinstance(script, dict):
        script = {}
    runtime = script.get("runtime")
    if runtime not in table:
        out.append(f"[AP-SCRIPT-NO-RUNTIME] 'script.runtime' {runtime!r} names no toolchain: use "
                   f"a built-in ({', '.join(sorted(BUILTIN_TOOLCHAINS))}) or declare it under "
                   "the document's 'toolchains'. Preflight runs exactly that toolchain's version "
                   "probe, so an unnamed runtime is a check nobody runs")
    cmd = script.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        out.append("[AP-SCRIPT-NO-COMMAND] 'script.command' must be the exact command the "
                   "runner may execute")
    elif SHELL_COMPOSE.search(cmd):
        out.append("[AP-SCRIPT-NO-COMMAND] 'script.command' must be ONE command -- no ; | & ` "
                   "$( or newline; the runner guard matches it exactly, and a chain would "
                   "carry an undeclared second command through")
    elif runtime in table and not _starts_with(cmd, table[runtime].get("executables") or []):
        out.append(f"[AP-SCRIPT-RUNTIME-MISMATCH] toolchain {runtime!r} runs "
                   f"{table[runtime].get('executables')}, but the command starts with "
                   f"{cmd.split()[0]!r}; preflight would check the wrong toolchain")
    exits = script.get("expectExit")
    if (not isinstance(exits, list) or not exits
            or not all(isinstance(x, int) and not isinstance(x, bool) for x in exits)):
        out.append("[AP-SCRIPT-NO-COMMAND] 'script.expectExit' must be a non-empty list of "
                   "exit codes; an unexpected exit halts the run")
    return out


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
    toolchains = toolchains_of(design)

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
        where = f"node {nid}"
        kind = n.get("kind")
        if kind not in NODE_KINDS:
            err(where, f"'kind' must be one of {sorted(NODE_KINDS)}")
            continue
        if not isinstance(n.get("goal"), str) or not n.get("goal"):
            err(where, "'goal' missing -- WHAT the node does is the first question")
        deps = n.get("depends_on")
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            err(where, "'depends_on' must be a list of node ids (empty is allowed)")
        else:
            for d in deps:
                if d not in nodes:
                    err(where, f"[AP-DEPENDS-UNKNOWN] depends_on {d!r}, which is not a node id")
        when = n.get("when")
        if when is not None and (not isinstance(when, dict) or set(when) != {"node", "field", "equals"}
                                 or when.get("node") not in (deps or [])):
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
            # A human gate runs BETWEEN workflow runs; it carries no model,
            # schema or scope because nothing is dispatched for it.
            continue

        if n.get("where") not in WHERE:
            err(where, f"'where' must be one of {sorted(WHERE)} -- WHERE a node runs is never "
                       "inherited from the session's cwd")
        if not model_ok(n.get("model")):
            err(where, f"[AP-NODE-NO-MODEL] 'model' must be {MODEL_RULE}; a script node gets "
                       "the smallest model only when the design says so")
        eff = n.get("effort")
        if eff is not None and eff not in EFFORTS:
            err(where, f"'effort' must be one of {sorted(EFFORTS)} when present")
        schema = n.get("output_schema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            err(where, "[AP-NODE-NO-SCHEMA] 'output_schema' must be a JSON Schema whose top "
                       "level is type: object -- a node with no schema returns prose, and "
                       "prose cannot be validated")
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
            err(where, "'agentType' is required on an agent node -- HOW it runs names the "
                       "agent definition, never the session inline")
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
            for msg in script_problems(n.get("script"), toolchains):
                err(where, msg)

        if kind == "merge-gate" and n.get("where") != "primary":
            err(where, "[AP-GATE-NOT-PRIMARY] a merge-gate runs in the primary checkout: that "
                       "is the only tree with the untracked and gitignored files no worktree "
                       "has, and its report must say findings came from there")
        if role == "smoke" and n.get("where") != "scratch":
            err(where, "[AP-SMOKE-NOT-SCRATCH] a smoke node runs in a scratch directory "
                       "outside the repository, so it proves the artefact installs, not that "
                       "the checkout happens to work")

    if any(e for e in errors if "[AP-DEPENDS-UNKNOWN]" in e):
        return errors, warnings
    order = _topo(nodes)
    if order is None:
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

    _validate_waves(nodes, ancestors, err)
    return errors, warnings


def _validate_waves(nodes: dict, ancestors: dict, err) -> None:
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

    gates: dict = {}
    for w in range(1, count + 1):
        rows = [nid for nid, n in waved.items() if n["wave"] == w and n.get("kind") == "agent"]
        wg = [nid for nid, n in waved.items() if n["wave"] == w and n.get("kind") == "merge-gate"]
        if len(wg) != 1 or not rows:
            err(f"wave {w}", f"[AP-WAVE-NO-GATE] needs >= 1 agent row and exactly one "
                             f"merge-gate; has rows {rows} and gates {wg}. A wave that is not "
                             "merged and gated leaves the next wave with no base")
            continue
        gates[w] = wg[0]
        missing = [r for r in rows if r not in (nodes[wg[0]].get("depends_on") or [])]
        if missing:
            err(f"node {wg[0]}", f"[AP-WAVE-NO-GATE] the wave {w} merge-gate must depend on "
                                 f"every row of its wave; missing {missing}")
        for r in rows:
            n = nodes[r]
            if n.get("where") != "worktree":
                err(f"node {r}", "a wave row runs in its own worktree ('where': 'worktree')")
            swarm = n.get("swarm", 1)
            if isinstance(swarm, bool) or not isinstance(swarm, int) or not 1 <= swarm <= 16:
                err(f"node {r}", "'swarm' must be an int 1..16 when present")
                swarm = 1
            acc = n.get("acceptance")
            if acc is not None and (not isinstance(acc, list)
                                    or not all(isinstance(a, str) and a for a in acc)):
                err(f"node {r}", "'acceptance' must be a list of shell commands")
                acc = None
            if swarm > 1:
                ref = n.get("referee")
                ref_ok = (isinstance(ref, dict) and model_ok(ref.get("model"))
                          and isinstance(ref.get("agentType"), str) and ref.get("agentType"))
                if not acc or not ref_ok:
                    err(f"node {r}", "[AP-SWARM-INCOMPLETE] a swarm row (swarm > 1) needs "
                                     "'acceptance' commands and a 'referee' {model, agentType}: "
                                     "the blind referee sees only branch names and those "
                                     "commands, and nothing else can pick the one to keep")
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                pairs = land_candidate.scopes_overlap(nodes[a].get("writeScope") or [],
                                                      nodes[b].get("writeScope") or [])
                if pairs:
                    x, y = pairs[0]
                    err(f"wave {w}", f"[AP-WAVE-SCOPE-OVERLAP] rows {a!r} and {b!r} may both "
                                     f"write ({x!r} vs {y!r}); parallel rows own disjoint "
                                     "files. Split the shared file -- a dispatcher plus one "
                                     "module per row -- rather than trusting a merge")

    for w, gid in gates.items():
        if w == 1:
            continue
        prev = gates.get(w - 1)
        for nid, n in waved.items():
            if n["wave"] == w and n.get("kind") == "agent" and prev not in ancestors[nid]:
                err(f"node {nid}", f"[AP-WAVE-NO-BASE] a wave {w} row must depend on the wave "
                                   f"{w - 1} merge-gate {prev!r}: its worktree starts with "
                                   "`git merge --ff-only <wave base>`, and an undeclared base "
                                   "is the prototype's wrong-base bug")

    if gates:
        last = gates[max(gates)]
        for nid, n in nodes.items():
            if "wave" in n or n.get("kind") == "human-gate":
                continue
            touches = [a for a in ancestors[nid] if "wave" in nodes[a]]
            if touches and last not in ancestors[nid]:
                err(f"node {nid}", f"[AP-WAVE-ORDER] depends on wave nodes {sorted(touches)} "
                                   f"but not on the last merge-gate {last!r}; a node outside "
                                   "the waves runs before them all or after them all")


def script_commands(design_or_spec: dict) -> list:
    """Every declared command template, for the runner guard's allowlist."""
    out = []
    for n in design_or_spec.get("nodes") or design_or_spec.get("phases") or []:
        if isinstance(n, dict) and isinstance(n.get("script"), dict):
            cmd = n["script"].get("command")
            if isinstance(cmd, str) and cmd:
                out.append({"node": n.get("id"), "command": cmd,
                            "placeholders": PLACEHOLDER_RE.findall(cmd)})
    return out


# --- selftest -----------------------------------------------------------------

def _obj(**props) -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": sorted(props), "properties": props}


GOOD_DESIGN = json.loads((Path(__file__).resolve().parent / "fixtures" / "design"
                          / "waves.design.json").read_text(encoding="utf-8"))


def _node(design: dict, nid: str) -> dict:
    return next(n for n in design["nodes"] if n["id"] == nid)


def _with(nid: str, **over) -> dict:
    d = copy.deepcopy(GOOD_DESIGN)
    n = _node(d, nid)
    for k, v in over.items():
        if v is None:
            n.pop(k, None)
        else:
            n[k] = v
    return d


def selftest() -> int:
    cases = [
        ("clean wave design", GOOD_DESIGN, None),
        ("bad name", {**GOOD_DESIGN, "name": "Bad Name"}, ""),
        ("offLimits absent", {k: v for k, v in GOOD_DESIGN.items() if k != "offLimits"}, ""),
        ("unknown kind", _with("preflight", kind="magic"), ""),
        ("no goal", _with("preflight", goal=None), ""),
        ("no where", _with("preflight", where=None), ""),
        ("agent without agentType", _with("w1-parser", agentType=None), ""),
        ("no model", _with("preflight", model=None), "AP-NODE-NO-MODEL"),
        ("no schema", _with("preflight", output_schema=None), "AP-NODE-NO-SCHEMA"),
        ("array schema", _with("preflight", output_schema={"type": "array"}),
         "AP-NODE-NO-SCHEMA"),
        ("loose schema", _with("preflight", output_schema={"type": "object",
                                                           "properties": {}}),
         "AP-SCHEMA-NOT-STRICT"),
        ("nested loose schema", _with("preflight", output_schema=_obj(
            inner={"type": "object", "properties": {}})), "AP-SCHEMA-NOT-STRICT"),
        ("JSON in a string", _with("preflight", output_schema=_obj(
            stateJson={"type": "string"})), "AP-SCHEMA-NOT-STRICT"),
        ("no writeScope", _with("preflight", writeScope=None), "AP-NODE-NO-SCOPE"),
        ("empty writeScope on a worktree row", _with("w1-parser", writeScope=[]),
         "AP-NODE-NO-SCOPE"),
        ("script without runtime", _with("preflight", script={
            "command": "python3 x.py", "expectExit": [0]}), "AP-SCRIPT-NO-RUNTIME"),
        ("script without command", _with("preflight", script={
            "runtime": "python", "expectExit": [0]}), "AP-SCRIPT-NO-COMMAND"),
        ("script chaining a second command", _with("preflight", script={
            "runtime": "python", "command": "python3 x.py && rm -rf .", "expectExit": [0]}),
         "AP-SCRIPT-NO-COMMAND"),
        ("script without expectExit", _with("preflight", script={
            "runtime": "python", "command": "python3 x.py"}), "AP-SCRIPT-NO-COMMAND"),
        ("go toolchain, python command", _with("preflight", script={
            "runtime": "go", "command": "python3 x.py", "expectExit": [0]}),
         "AP-SCRIPT-RUNTIME-MISMATCH"),
        ("undeclared toolchain", _with("preflight", script={
            "runtime": "zig", "command": "zig build test", "expectExit": [0]}),
         "AP-SCRIPT-NO-RUNTIME"),
        ("go toolchain -- clean", _with("preflight", script={
            "runtime": "go", "command": "go run ./cmd/state preflight", "expectExit": [0]}),
         None),
        ("powershell toolchain -- clean", _with("preflight", script={
            "runtime": "powershell", "command": "pwsh -File tools/state.ps1 preflight",
            "expectExit": [0]}), None),
        ("haskell via a wrapper path -- clean", _with("preflight", script={
            "runtime": "haskell", "command": "cabal run state -- preflight",
            "expectExit": [0]}), None),
        ("java via ./gradlew -- clean", _with("preflight", script={
            "runtime": "java", "command": "./gradlew conformance", "expectExit": [0, 1]}), None),
        ("full model id -- clean", _with("w1-parser", model="claude-opus-5-5"), None),
        ("fable alias -- clean", _with("w1-parser", model="fable"), None),
        ("model name that is neither alias nor id", _with("w1-parser", model="gpt-5"),
         "AP-NODE-NO-MODEL"),
        ("overlapping rows", _with("w1-render", writeScope=["src/cli/**"]),
         "AP-WAVE-SCOPE-OVERLAP"),
        ("basename glob overlaps everything", _with("w1-render", writeScope=["*.py"]),
         "AP-WAVE-SCOPE-OVERLAP"),
        ("input carrying content", _with("w2-dispatch", inputs=["the parser returns a dict"]),
         "AP-INPUT-CONTENT"),
        ("unknown dependency", _with("w1-parser", depends_on=["nope"]), "AP-DEPENDS-UNKNOWN"),
        ("cycle", _with("preflight", depends_on=["gate-1"]), "AP-DEPENDS-CYCLE"),
        ("gate without every row", _with("gate-1", depends_on=["w1-parser"]),
         "AP-WAVE-NO-GATE"),
        ("wave 2 row not on the wave 1 gate", _with("w2-dispatch", depends_on=["preflight"]),
         "AP-WAVE-NO-BASE"),
        ("post node skipping the last gate", _with("smoke", depends_on=["w2-dispatch"]),
         "AP-WAVE-ORDER"),
        ("swarm without referee", _with("w1-parser", swarm=2, referee=None),
         "AP-SWARM-INCOMPLETE"),
        ("merge-gate in a worktree", _with("gate-1", where="worktree"), "AP-GATE-NOT-PRIMARY"),
        ("smoke in the primary checkout", _with("smoke", where="primary"),
         "AP-SMOKE-NOT-SCRATCH"),
    ]
    zig = copy.deepcopy(GOOD_DESIGN)
    zig["toolchains"] = {"zig": {"executables": ["zig"], "version": "zig version"}}
    _node(zig, "preflight")["script"] = {"runtime": "zig", "command": "zig build state",
                                         "expectExit": [0]}
    cases.append(("toolchain declared by the design -- clean", zig, None))
    bad_tc = copy.deepcopy(zig)
    bad_tc["toolchains"]["zig"]["version"] = "zig version; curl evil"
    cases.append(("declared toolchain with a chained probe", bad_tc, ""))
    gate_mid = copy.deepcopy(GOOD_DESIGN)
    gate_mid["nodes"].append({"id": "approve", "kind": "human-gate", "goal": "g",
                              "depends_on": ["w1-parser"]})
    cases.append(("human gate beside a running wave", gate_mid, "AP-HUMAN-GATE-INSIDE"))
    gate_ok = copy.deepcopy(GOOD_DESIGN)
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
        ("src/a*/x", "src/b/**", True),
    ]
    for a, b, want in overlap:
        got = land_candidate.scope_overlap(a, b)
        ok = got == want and land_candidate.scope_overlap(b, a) == want
        print(f"  {'ok  ' if ok else 'FAIL'} scope_overlap({a!r}, {b!r}) == {want}")
        if not ok:
            fails.append(f"scope_overlap {a} {b}")
    if design_hash(GOOD_DESIGN) != design_hash(json.loads(json.dumps(GOOD_DESIGN))):
        fails.append("design_hash is not canonical")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"design selftest passed ({len(cases)} designs, {len(overlap)} overlap pairs)")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    print("usage: design_spec.py --selftest (compile with compile_spec.py --design FILE)",
          file=sys.stderr)
    sys.exit(2)
