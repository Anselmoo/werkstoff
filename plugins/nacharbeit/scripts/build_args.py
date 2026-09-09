#!/usr/bin/env python3
"""Build the `args` object for workflows/review.js and bake it into a launchable copy. No LLM.

Workflow scripts have no filesystem access, so everything the review needs arrives
through `args`: the frozen rubric and its hash, the lint findings (so finders skip the
mechanical ids), the review batches per (plugin, kind), the two routing corpora, the
handoff graph, the calibration fixtures per family, the known-answer routing prompts
(parsed from a prompt index when one exists), and the hand-written ambiguous prompts.

Runs nacharbeit_lint.lint() itself rather than reading a stale lint.json — a lint file
left over from an earlier run would be measured as if it were fresh (CLAUDE.md, "a
failed run leaves the previous output in place").

Every werkstoff-specific location is a flag with a werkstoff default, so the same script
runs in any repository that keeps its plugins under one directory.

Usage: build_args.py [--plugins-root plugins] [--plugin NAME ...] [--state-dir analysis/nacharbeit]
                     [--fixtures-root test/plugins/fixtures/nacharbeit] [--known-answers docs/prompt-index.md]
                     [--ambiguous FILE] [--repo-name NAME] [--repo-notes TEXT] [--docs-root docs]
                     [--marketplace FILE] [--rubric FILE] [--workflow FILE] [--out FILE]
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
sys.path.insert(0, str(HERE))
import nacharbeit_common as nc  # noqa: E402

spec = importlib.util.spec_from_file_location("nacharbeit_lint", HERE / "nacharbeit_lint.py")
assert spec is not None and spec.loader is not None
lp = importlib.util.module_from_spec(spec)
sys.modules["nacharbeit_lint"] = lp
spec.loader.exec_module(lp)

BATCH_MAX_COMPONENTS = 8
FIXTURE_SUFFIXES = {".md", ".js", ".py", ".sh", ".json", ".html", ".css", ".toml", ".mjs", ".vue"}


def rel(p: Path) -> str:
    return p.as_posix()


def chunk(xs: list, n: int) -> list[list]:
    if len(xs) <= n:
        return [xs]
    k = -(-len(xs) // n)  # ceil
    size = -(-len(xs) // k)
    return [xs[i:i + size] for i in range(0, len(xs), size)]


def build_batches(plugin_dirs: list[Path], units: list, state: Path, docs_root: Path | None) -> list[dict]:
    batches = []
    docs_shared = []
    if docs_root is not None:
        for f in (docs_root / "orchestration" / "README.md", docs_root / "orchestration" / "references" / "hazards.md",
                  docs_root / "orchestration" / "references" / "routing.md", Path("README.md"), Path("CLAUDE.md")):
            if f.is_file():
                docs_shared.append(rel(f))
    for pd in plugin_dirs:
        plugin = pd.name
        by = lambda *kinds: [u for u in units if u.plugin == plugin and u.kind in kinds and u.exists]  # noqa: E731
        skills, refs, agents, cmds, wfs = by("skill"), by("reference", "doc"), by("agent"), by("command"), by("workflow")
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

        readme = [u for u in by("readme")]
        readme_files = [rel(u.path) for u in readme]
        hooks = by("hooks") + by("hookscript")
        if hooks:
            files = [rel(u.path) for u in hooks]
            for h in by("hookscript"):
                t = h.path.parent / f"test_{h.path.stem}.py"
                if t.is_file():
                    files.append(rel(t))
            batches.append({"key": f"{plugin}:hooks", "plugin": plugin, "kind": "hooks", "files": files + readme_files})
        scripts = [u for u in by("script") if rel(u.path) not in {f for b in batches for f in b["files"]}]
        # keep each test_x.py beside its subject x.py so one finder sees both
        scripts.sort(key=lambda u: (u.path.parent.as_posix(), u.path.stem.removeprefix("test_"), u.path.stem.startswith("test_")))
        groups = chunk(scripts, BATCH_MAX_COMPONENTS)
        for i, g in enumerate(groups):
            if not g:
                continue
            suffix = "" if len(groups) == 1 else f":{chr(97 + i)}"
            batches.append({"key": f"{plugin}:scripts{suffix}", "plugin": plugin, "kind": "scripts", "files": [rel(s.path) for s in g]})
        viewers = by("viewer")
        if viewers:
            files = [rel(v.path) for v in viewers]
            files += [rel(s.path) for s in by("script") if s.path.suffix == ".py" and any(v.path.name in s.text or "__DESIGN_TOKENS__" in s.text for v in viewers)]
            batches.append({"key": f"{plugin}:assets", "plugin": plugin, "kind": "assets", "files": files + readme_files})
        manifest = by("manifest")
        if manifest:
            files = [rel(u.path) for u in manifest] + readme_files + [rel(u.path) for u in by("changelog")]
            mp = lp.OPTIONS.get("marketplace")
            if mp:
                try:
                    entry = next((e for e in json.loads(Path(mp).read_text(encoding="utf-8")).get("plugins", []) if e.get("name") == plugin), None)
                except Exception:  # noqa: BLE001
                    entry = None
                if entry is not None:
                    snap = state / f"marketplace-{plugin}.json"
                    lp.write_atomic(snap, json.dumps(entry, indent=1, ensure_ascii=False) + "\n")
                    files.append(rel(snap))
            batches.append({"key": f"{plugin}:manifest", "plugin": plugin, "kind": "manifest", "files": files})
        docs = by("docs")
        if docs and docs_root is not None:
            files = [rel(u.path) for u in docs] + docs_shared + readme_files
            batches.append({"key": f"{plugin}:docs", "plugin": plugin, "kind": "docs", "files": files})
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


def build_fixtures(fixtures_root: Path) -> tuple[list[dict], list[dict]]:
    tune, sealed = [], []
    if not fixtures_root.is_dir():
        return tune, sealed
    for d in sorted(p for p in fixtures_root.iterdir() if p.is_dir()):
        manifest = d / "planted.json"
        if not manifest.is_file():
            continue
        m = json.loads(manifest.read_text(encoding="utf-8"))
        files = sorted(rel(p) for p in d.rglob("*") if p.is_file() and p.suffix in FIXTURE_SUFFIXES and p.name != "planted.json")
        fx = {"name": m["name"], "kind": m.get("kind", "skills"), "files": files, "cleanFiles": m.get("cleanFiles", []), "planted": m["planted"]}
        (sealed if d.name.startswith("sealed") else tune).append(fx)
    return tune, sealed


def build_known_answers(index: Path | None, corpus: dict) -> tuple[list[dict], int]:
    if index is None or not index.is_file():
        return [], 0
    text = index.read_text(encoding="utf-8")
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
    ap = argparse.ArgumentParser(description="Build and bake the args for nacharbeit's review workflow.")
    ap.add_argument("--repo-root", type=Path, default=None, help="run as if from this directory (default: cwd)")
    ap.add_argument("--plugins-root", type=Path, default=nc.DEFAULT_PLUGINS_ROOT)
    ap.add_argument("--plugin", action="append", default=[], help="review only this plugin (repeatable); the routing corpus stays complete")
    ap.add_argument("--state-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None, help="args JSON (default <state-dir>/args.json)")
    ap.add_argument("--lint-out", type=Path, default=None, help="lint JSON (default <state-dir>/lint.json)")
    ap.add_argument("--rubric", type=Path, default=None)
    ap.add_argument("--fixtures-root", type=Path, default=nc.DEFAULT_FIXTURES_ROOT)
    ap.add_argument("--known-answers", type=Path, default=None, help=f"prompt index with known-answer prompts (default {nc.DEFAULT_KNOWN_ANSWERS} when present)")
    ap.add_argument("--ambiguous", type=Path, default=None, help="ambiguous-prompts JSON (default: the bundled werkstoff set, only inside werkstoff)")
    ap.add_argument("--repo-name", default=None)
    ap.add_argument("--repo-notes", default=None, help="repository-specific instructions for the cross-plugin synthesis")
    ap.add_argument("--docs-root", type=Path, default=None, help=f"docs site root for the docs batches and D-* rules (default {nc.DEFAULT_DOCS_ROOT} when present)")
    ap.add_argument("--marketplace", type=Path, default=nc.DEFAULT_MARKETPLACE)
    ap.add_argument("--workflow", type=Path, default=nc.plugin_root() / "workflows" / "review.js")
    a = ap.parse_args(argv)

    import os
    root = nc.repo_root(a.repo_root)
    os.chdir(root)  # every path in args is repo-relative
    state = nc.state_dir(a.state_dir, root)
    out = a.out or state / "args.json"
    lint_out = a.lint_out or state / "lint.json"
    rubric = nc.rubric_path(a.rubric)
    werkstoff = nc.is_werkstoff(root)
    known = a.known_answers if a.known_answers is not None else (nc.DEFAULT_KNOWN_ANSWERS if nc.DEFAULT_KNOWN_ANSWERS.is_file() else None)
    ambiguous = a.ambiguous if a.ambiguous is not None else (HERE / "ambiguous-prompts.json" if werkstoff else None)
    docs_root = a.docs_root if a.docs_root is not None else (nc.DEFAULT_DOCS_ROOT if nc.DEFAULT_DOCS_ROOT.is_dir() else None)
    repo_name = a.repo_name or ("werkstoff" if werkstoff else nc.DEFAULT_REPO_NAME)
    repo_notes = a.repo_notes if a.repo_notes is not None else (nc.WERKSTOFF_REPO_NOTES if werkstoff else nc.DEFAULT_REPO_NOTES)

    if not a.plugins_root.is_dir():
        print(f"ERROR: not a directory: {a.plugins_root}", file=sys.stderr)
        return 2
    if not rubric.is_file():
        print(f"ERROR: rubric missing: {rubric}", file=sys.stderr)
        return 1
    all_dirs = sorted(p for p in a.plugins_root.iterdir() if p.is_dir() and (p / ".claude-plugin" / "plugin.json").is_file())
    if a.plugin:
        unknown = [n for n in a.plugin if not any(d.name == n for d in all_dirs)]
        if unknown:
            print(f"ERROR: no such plugin under {a.plugins_root}: {unknown}", file=sys.stderr)
            return 2
    plugin_dirs = [d for d in all_dirs if not a.plugin or d.name in a.plugin]

    lp.configure(marketplace=a.marketplace, readme_markers=None, viewer_checker=HERE / "check_viewer_conformance.py", docs_root=docs_root)
    all_units = lp.discover(all_dirs)  # the routing corpus must see every plugin, reviewed or not
    lint = lp.lint(plugin_dirs)
    lp.write_atomic(lint_out, json.dumps(lint, indent=2) + "\n")
    units = [u for u in all_units if any(u.plugin == d.name for d in plugin_dirs)]

    rubric_text = rubric.read_text(encoding="utf-8")
    rubric_hash = hashlib.sha256(rubric.read_bytes()).hexdigest()
    mechanical_ids, judgement_ids = lp.rubric_ids(rubric)
    corpus = build_corpus(all_units)
    batches = build_batches(plugin_dirs, units, state, docs_root)
    handoffs = build_handoffs(all_units, corpus)
    tune, sealed = build_fixtures(a.fixtures_root)
    known_answers, dropped = build_known_answers(known, corpus)
    amb = json.loads(ambiguous.read_text(encoding="utf-8"))["prompts"] if ambiguous and ambiguous.is_file() else []

    # leak assertions — the same ones the workflow re-checks at runtime
    fx_prefix = a.fixtures_root.as_posix().rstrip("/") + "/"
    if any(f.startswith(fx_prefix) for b in batches for f in b["files"]):
        print("ERROR: fixture path leaked into real batches", file=sys.stderr)
        return 1
    if any(not f.startswith(fx_prefix) for fx in tune + sealed for f in fx["files"] + fx["cleanFiles"] + [p["file"] for p in fx["planted"]]):
        print("ERROR: real path leaked into fixtures", file=sys.stderr)
        return 1
    if not tune or not sealed:
        print(f"ERROR: need at least one tuning and one sealed fixture under {a.fixtures_root}", file=sys.stderr)
        return 1
    kinds_reviewed = {b["kind"] for b in batches}
    kinds_calibrated = {fx["kind"] for fx in tune} & {fx["kind"] for fx in sealed}
    uncalibrated = sorted(kinds_reviewed - kinds_calibrated - {"agents", "commands", "workflows"} | ({"skills"} & kinds_reviewed - kinds_calibrated))
    if uncalibrated:
        print(f"ERROR: batch kind(s) {uncalibrated} have no tuning + sealed fixture pair; a finder cannot grade what it was never calibrated on", file=sys.stderr)
        return 1

    args = {
        "runStamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rubricHash": rubric_hash,
        "rubric": rubric_text,
        "mechanicalIds": mechanical_ids,
        "judgementIds": judgement_ids,
        "lint": lint["findings"],
        "batches": batches,
        "corpus": corpus,
        "handoffs": handoffs,
        "fixtures": tune,
        "sealed": sealed,
        "fixturePrefix": fx_prefix,
        "knownAnswers": known_answers,
        "ambiguous": [{k: v for k, v in p.items() if k != "between"} for p in amb],
        "ambiguousBetween": {p["id"]: p.get("between", []) for p in amb},
        "plugins": [p.name for p in plugin_dirs],
        "repoName": repo_name,
        "repoNotes": repo_notes,
    }
    lp.write_atomic(out, json.dumps(args, indent=1) + "\n")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")

    # Bake: the Workflow tool takes `args` inline only, and 170+ KB of JSON pasted into a
    # tool call is both costly and easy to corrupt. Instead emit a copy of the canonical
    # script with the args embedded as a literal, and launch that by scriptPath. The
    # canonical workflows/review.js stays the only hand-edited source.
    src = a.workflow.read_text(encoding="utf-8")
    marker = "const A = typeof args === 'string'"
    lines = src.splitlines(keepends=True)
    idx = next((i for i, ln in enumerate(lines) if ln.startswith(marker)), None)
    if idx is None:
        print("ERROR: canonical workflow lacks the `const A = typeof args` line to bake into", file=sys.stderr)
        return 1
    literal = json.dumps(args, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    lines[idx] = f"const A = {literal} // baked by nacharbeit build_args.py at {args['runStamp']}\n"
    baked = out.with_name("run.js")
    lp.write_atomic(baked, "".join(lines))
    print(f"wrote {baked} ({baked.stat().st_size // 1024} KB) — launch with Workflow({{scriptPath: ...}})")
    print(f"  plugins={len(plugin_dirs)} batches={len(batches)} files={sum(len(b['files']) for b in batches)} "
          f"corpus skill={len(corpus['skill'])} agent={len(corpus['agent'])} handoffs={len(handoffs)}")
    print(f"  lint findings={len(lint['findings'])} skipped rules={len(lint.get('skipped', []))} "
          f"fixtures tune={len(tune)} sealed={len(sealed)} planted={sum(len(f['planted']) for f in tune + sealed)} kinds={sorted(kinds_calibrated)}")
    print(f"  knownAnswers={len(known_answers)} (dropped {dropped} whose trigger id is not in the corpus) ambiguous={len(amb)} repoName={repo_name}")
    for b in batches:
        print(f"    {b['key']:<32} {len(b['files'])} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
