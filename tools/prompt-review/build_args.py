#!/usr/bin/env python3
"""Build the `args` object for .claude/workflows/prompt-quality-review.js. No LLM.

Workflow scripts have no filesystem access, so everything the review needs arrives
through `args`: the frozen rubric and its hash, the lint findings (so finders skip M-*
rules), the review batches, the two routing corpora, the handoff graph, the calibration
fixtures, the known-answer routing prompts parsed from docs/prompt-index.md, and the
hand-written ambiguous prompts.

Runs lint_prompts.lint() itself rather than reading a stale lint.json — a lint file left
over from an earlier run would be measured as if it were fresh (CLAUDE.md, "a failed run
leaves the previous output in place").

Usage: build_args.py [--out analysis/prompt-review/args.json] [--plugins-dir plugins]
Exit: 0 on success, 1 if a required input is missing or the leak assertions fail, 2 on bad args.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RUBRIC = ROOT / "docs/plugin-authoring/references/prompt-quality-rubric.md"
PROMPT_INDEX = ROOT / "docs/prompt-index.md"
AMBIGUOUS = HERE / "ambiguous-prompts.json"
FIXTURES = ROOT / "test/plugins/fixtures/prompt-review"
BATCH_MAX_COMPONENTS = 8

spec = importlib.util.spec_from_file_location("lint_prompts", HERE / "lint_prompts.py")
assert spec is not None and spec.loader is not None
lp = importlib.util.module_from_spec(spec)
sys.modules["lint_prompts"] = lp
spec.loader.exec_module(lp)


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT)) if p.is_absolute() else str(p)


def chunk(xs: list, n: int) -> list[list]:
    if len(xs) <= n:
        return [xs]
    k = -(-len(xs) // n)  # ceil
    size = -(-len(xs) // k)
    return [xs[i:i + size] for i in range(0, len(xs), size)]


def build_batches(plugins_dir: Path, units: list) -> list[dict]:
    batches = []
    for pd in sorted(p for p in plugins_dir.iterdir() if p.is_dir()):
        plugin = pd.name
        skills = [u for u in units if u.plugin == plugin and u.kind == "skill"]
        refs = [u for u in units if u.plugin == plugin and u.kind in {"reference", "doc"}]
        agents = [u for u in units if u.plugin == plugin and u.kind == "agent"]
        cmds = [u for u in units if u.plugin == plugin and u.kind == "command"]
        wfs = [u for u in units if u.plugin == plugin and u.kind == "workflow"]
        plugin_refs = [u for u in refs if "skills" not in u.path.parts]

        groups = chunk(skills, BATCH_MAX_COMPONENTS)
        for i, g in enumerate(groups):
            files = []
            for s in g:
                files.append(rel(s.path))
                files += [rel(r.path) for r in refs if r.path.is_relative_to(s.path.parent)]
            if i == 0:
                files += [rel(r.path) for r in plugin_refs]
            suffix = "" if len(groups) == 1 else f":{chr(97 + i)}"
            batches.append({"key": f"{plugin}:skills{suffix}", "plugin": plugin, "kind": "skills", "files": files})
        for i, g in enumerate(chunk(agents, BATCH_MAX_COMPONENTS)):
            if not g:
                continue
            suffix = "" if len(agents) <= BATCH_MAX_COMPONENTS else f":{chr(97 + i)}"
            batches.append({"key": f"{plugin}:agents{suffix}", "plugin": plugin, "kind": "agents", "files": [rel(a.path) for a in g]})
        if cmds:
            batches.append({"key": f"{plugin}:commands", "plugin": plugin, "kind": "commands", "files": [rel(c.path) for c in cmds]})
        if wfs:
            batches.append({"key": f"{plugin}:workflows", "plugin": plugin, "kind": "workflows", "files": [rel(w.path) for w in wfs]})
    return [b for b in batches if b["files"]]


def build_corpus(units: list) -> dict:
    skill: dict[str, dict] = {}
    agent: dict[str, dict] = {}
    for u in units:
        if u.kind not in {"skill", "agent", "command"} or u.fm is None:
            continue
        desc = u.fm.get("description")
        if not isinstance(desc, str):
            continue
        cid = u.fm.get("name") if isinstance(u.fm.get("name"), str) else (u.path.parent.name if u.kind == "skill" else u.path.stem)
        entry = {"plugin": u.plugin, "kind": u.kind, "description": desc.strip(), "path": rel(u.path)}
        (agent if u.kind == "agent" else skill)[cid] = entry
    return {"skill": skill, "agent": agent}


def build_handoffs(units: list, corpus: dict) -> list[dict]:
    ids = set(corpus["skill"]) | set(corpus["agent"])
    by_path = {}
    for kind in ("skill", "agent"):
        for cid, e in corpus[kind].items():
            by_path[e["path"]] = cid
    edges = []
    for u in units:
        src = by_path.get(rel(u.path))
        if not src:
            continue
        desc = (u.fm or {}).get("description") or ""
        for other in sorted(ids - {src}):
            rx = re.compile(rf"(?<![\w-]){re.escape(other)}(?![\w-])")
            in_desc = bool(rx.search(desc if isinstance(desc, str) else ""))
            in_body = bool(rx.search(u.body))
            if in_desc or in_body:
                edges.append({"from": src, "to": other, "inDescription": in_desc})
    return edges


def build_fixtures() -> tuple[list[dict], list[dict]]:
    tune, sealed = [], []
    if not FIXTURES.is_dir():
        return tune, sealed
    for d in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        manifest = d / "planted.json"
        if not manifest.is_file():
            continue
        m = json.loads(manifest.read_text(encoding="utf-8"))
        files = sorted(rel(p) for p in d.rglob("*") if p.is_file() and p.suffix in {".md", ".js", ".py"} and p.name != "planted.json")
        fx = {"name": m["name"], "files": files, "cleanFiles": m.get("cleanFiles", []), "planted": m["planted"]}
        (sealed if d.name.startswith("sealed") else tune).append(fx)
    return tune, sealed


def build_known_answers(corpus: dict) -> tuple[list[dict], int]:
    if not PROMPT_INDEX.is_file():
        return [], 0
    text = PROMPT_INDEX.read_text(encoding="utf-8")
    out, dropped, n = [], 0, 0
    plugin = None
    pending_prompt = None
    for ln in text.splitlines():
        if ln.startswith("## "):
            plugin = ln[3:].strip()
        m = re.match(r'^"(.+)"$', ln.strip())
        if m and pending_prompt is None:
            pending_prompt = m.group(1)
            continue
        t = re.match(r"^> Triggers `([^`]+)`", ln)
        if t and pending_prompt is not None:
            n += 1
            expected = t.group(1)
            router = "agent" if expected in corpus["agent"] else "skill" if expected in corpus["skill"] else None
            if router is None:
                dropped += 1
            else:
                out.append({"id": f"ka-{n:02d}", "router": router, "text": pending_prompt, "expected": expected, "plugin": plugin})
            pending_prompt = None
    return out, dropped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "analysis/prompt-review/args.json")
    ap.add_argument("--plugins-dir", type=Path, default=ROOT / "plugins")
    ap.add_argument("--lint-out", type=Path, default=ROOT / "analysis/prompt-review/lint.json")
    a = ap.parse_args(argv)
    if not a.plugins_dir.is_dir():
        print(f"ERROR: not a directory: {a.plugins_dir}", file=sys.stderr)
        return 2
    if not RUBRIC.is_file():
        print(f"ERROR: rubric missing: {RUBRIC}", file=sys.stderr)
        return 1

    import os
    os.chdir(ROOT)  # lint paths are repo-relative
    plugin_dirs = sorted(p for p in Path("plugins").iterdir() if p.is_dir())
    units = lp.discover(plugin_dirs)
    lint = lp.lint(plugin_dirs)
    lp.write_atomic(a.lint_out, json.dumps(lint, indent=2) + "\n")

    rubric_text = RUBRIC.read_text(encoding="utf-8")
    rubric_hash = hashlib.sha256(RUBRIC.read_bytes()).hexdigest()
    corpus = build_corpus(units)
    batches = build_batches(Path("plugins"), units)
    handoffs = build_handoffs(units, corpus)
    tune, sealed = build_fixtures()
    known, dropped = build_known_answers(corpus)
    amb = json.loads(AMBIGUOUS.read_text(encoding="utf-8"))["prompts"] if AMBIGUOUS.is_file() else []

    # leak assertions — the same ones the workflow re-checks at runtime
    fx_prefix = "test/plugins/fixtures/"
    if any(f.startswith(fx_prefix) for b in batches for f in b["files"]):
        print("ERROR: fixture path leaked into real batches", file=sys.stderr)
        return 1
    if any(not f.startswith(fx_prefix) for fx in tune + sealed for f in fx["files"] + fx["cleanFiles"] + [p["file"] for p in fx["planted"]]):
        print("ERROR: real path leaked into fixtures", file=sys.stderr)
        return 1
    if not tune or not sealed:
        print("ERROR: need at least one tuning and one sealed fixture", file=sys.stderr)
        return 1

    args = {
        "runStamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rubricHash": rubric_hash,
        "rubric": rubric_text,
        "lint": lint["findings"],
        "batches": batches,
        "corpus": corpus,
        "handoffs": handoffs,
        "fixtures": tune,
        "sealed": sealed,
        "knownAnswers": known,
        "ambiguous": [{k: v for k, v in p.items() if k != "between"} for p in amb],
        "ambiguousBetween": {p["id"]: p.get("between", []) for p in amb},
        "plugins": [p.name for p in plugin_dirs],
    }
    lp.write_atomic(a.out, json.dumps(args, indent=1) + "\n")
    print(f"wrote {a.out} ({a.out.stat().st_size // 1024} KB)")

    # Bake: the Workflow tool takes `args` inline only, and 170+ KB of JSON pasted into a
    # tool call is both costly and easy to corrupt. Instead emit a copy of the canonical
    # script with the args embedded as a literal, and launch that by scriptPath. The
    # canonical .claude/workflows file stays the only hand-edited source.
    canon = ROOT / ".claude/workflows/prompt-quality-review.js"
    src = canon.read_text(encoding="utf-8")
    marker = "const A = typeof args === 'string'"
    lines = src.splitlines(keepends=True)
    idx = next((i for i, ln in enumerate(lines) if ln.startswith(marker)), None)
    if idx is None:
        print("ERROR: canonical workflow lacks the `const A = typeof args` line to bake into", file=sys.stderr)
        return 1
    literal = json.dumps(args, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    lines[idx] = f"const A = {literal} // baked by tools/prompt-review/build_args.py at {args['runStamp']}\n"
    baked = a.out.with_name("run.js")
    lp.write_atomic(baked, "".join(lines))
    print(f"wrote {baked} ({baked.stat().st_size // 1024} KB) — launch with Workflow({{scriptPath: ...}})")
    print(f"  batches={len(batches)} files={sum(len(b['files']) for b in batches)} "
          f"corpus skill={len(corpus['skill'])} agent={len(corpus['agent'])} handoffs={len(handoffs)}")
    print(f"  lint findings={len(lint['findings'])} fixtures tune={len(tune)} sealed={len(sealed)} "
          f"planted={sum(len(f['planted']) for f in tune + sealed)}")
    print(f"  knownAnswers={len(known)} (dropped {dropped} whose trigger id is not in the corpus) ambiguous={len(amb)}")
    for b in batches:
        print(f"    {b['key']:<32} {len(b['files'])} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
