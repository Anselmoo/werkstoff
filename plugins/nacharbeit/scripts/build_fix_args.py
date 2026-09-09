#!/usr/bin/env python3
"""Turn a completed nacharbeit review into per-file fix work items, open the fix lock,
snapshot the plugins about to change, and bake the fix workflow. No LLM.

Reads <state>/{synthesis,findings,routing,args,run}.json and emits one work item per
file, carrying every haiku- or sonnet-tier backlog entry for that file, the mechanical
lint findings on it, the negative-trigger descriptions the collision judge proposed for
it, the verified findings that back each entry, and the post-checks the verifier must
run for that file's kind. Opus- and human-tier entries are listed under `excluded`,
never silently dropped.

Files that are synced copies of an artifact (--artifact-copies) are redirected to their
canonical source when it exists, otherwise excluded — editing a copy would fail the
artifact check on the next run.

Three side effects the fix pass depends on:
  1. <state>/fix_scope.json — the per-dispatch lock the PreToolUse guard reads. It
     names every file the pass may touch with its tier; hooks/nacharbeit_guard.py
     denies any other edit while it exists. Released by post_fix_check.py --release-lock.
  2. <state>/pre-fix/<plugin>/ — a snapshot of each plugin about to change, for
     contract_diff after the pass.
  3. <state>/fix-run.js — workflows/fix.js with the items baked in, launched by scriptPath.

Refuses when the review is not a completed, calibrated run, or when a lock is already
open (a stale lock is released explicitly, never overwritten).

Usage: build_fix_args.py [--state-dir analysis/nacharbeit] [--write-roots plugins/ tools/]
                         [--artifact-copies JSON] [--skip-lint ID ...] [--rubric FILE] [--workflow FILE]
Exit: 0 written; 1 inputs missing, review incomplete, or a lock already open; 2 bad args.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nacharbeit_common as nc  # noqa: E402

APPLY_TIERS = {"haiku", "sonnet"}
TIER_RANK = {"haiku": 0, "sonnet": 1, "opus": 2, "human": 3}
SNAPSHOT_IGNORE = shutil.ignore_patterns("__pycache__", "node_modules", ".git", "analysis")


def load(state: Path, name: str):
    p = state / name
    if not p.is_file():
        print(f"ERROR: missing {p}", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def expand_braces(s: str) -> list[str]:
    """`a/{x, y}.md` -> [`a/x.md`, `a/y.md`]; nested braces are not expected."""
    m = re.search(r"\{([^{}]*)\}", s)
    if not m:
        return [s]
    alts = [x.strip() for x in m.group(1).split(",") if x.strip()]
    return [y for alt in alts for y in expand_braces(s[:m.start()] + alt + s[m.end():])]


def split_files(field: str) -> list[str]:
    """Backlog `file` fields arrive as one path, `a, b`, `a + b`, or brace groups."""
    out: list[str] = []
    depth, cur = 0, ""
    for ch in field:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    parts: list[str] = []
    for piece in out:
        parts += re.split(r"\s+\+\s+|\s+and\s+", piece)
    return [y.strip().strip("`") for x in parts for y in expand_braces(x.strip()) if y.strip()]


def kind_of(path: str) -> str:
    p = path.replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    if name == "hooks.json" and "/hooks/" in p:
        return "hooks"
    if "/hooks/" in p and name.endswith(".py") and not name.startswith("test_"):
        return "hookscript"
    if name.endswith("-viewer.html"):
        return "viewer"
    if name == "plugin.json":
        return "manifest"
    if name == "README.md":
        return "readme"
    if name == "CHANGELOG.md":
        return "changelog"
    if p.startswith("docs/"):
        return "docs"
    if "/workflows/" in p and p.endswith(".js"):
        return "workflow"
    if "/agents/" in p:
        return "agent"
    if "/commands/" in p:
        return "command"
    if name == "SKILL.md":
        return "skill"
    if "/scripts/" in p or "/hooks/" in p:
        return "script"
    return "reference"


def post_checks(path: str, kind: str, plugin_dir: str, fixtures_root: Path) -> list[dict]:
    """Commands the blind verifier runs after the remediator; a non-zero exit is a regression."""
    checks: list[dict] = []
    me = nc.plugin_root() / "scripts"
    if path.endswith(".py"):
        checks.append({"label": "py_compile", "cmd": f"python3 -m py_compile {path}"})
    if path.endswith(".js"):
        checks.append({"label": "node --check", "cmd": f"node --check {path}"})
    if kind == "hookscript":
        stem = Path(path).stem
        test = Path(path).parent / f"test_{stem}.py"
        if test.is_file():
            checks.append({"label": "hook unit test", "cmd": f"python3 {test.as_posix()}"})
        checks.append({"label": "hook denies and stays inert", "cmd": f"python3 {(me / 'verify_hooks_deny.py').as_posix()} {plugin_dir} --fixtures-root {fixtures_root.as_posix()}"})
    if kind == "hooks":
        checks.append({"label": "hooks.json parses", "cmd": f"python3 -c \"import json,sys; json.load(open('{path}'))\""})
    if kind == "viewer":
        checks.append({"label": "report-viewer standard", "cmd": f"python3 {(me / 'check_viewer_conformance.py').as_posix()} --plugin-dir {plugin_dir}"})
    if kind == "manifest":
        checks.append({"label": "plugin.json parses", "cmd": f"python3 -c \"import json,sys; json.load(open('{path}'))\""})
    if kind in {"skill", "agent", "command"}:
        checks.append({"label": "frontmatter parses", "cmd": f"python3 -c \"import sys,yaml; t=open('{path}').read(); assert t.startswith('---'); yaml.safe_load(t.split('---',2)[1])\""})
    return checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build fix work items, open the fix lock, snapshot, and bake fix.js.")
    ap.add_argument("--repo-root", type=Path, default=None)
    ap.add_argument("--state-dir", type=Path, default=None)
    ap.add_argument("--plugins-root", type=Path, default=nc.DEFAULT_PLUGINS_ROOT)
    ap.add_argument("--fixtures-root", type=Path, default=Path("test/plugins/fixtures"), help="root holding hook-violation-<plugin>/ fixtures for the hook post-check")
    ap.add_argument("--out", type=Path, default=None, help="fix-args JSON (default <state-dir>/fix-args.json)")
    ap.add_argument("--rubric", type=Path, default=None)
    ap.add_argument("--workflow", type=Path, default=nc.plugin_root() / "workflows" / "fix.js")
    ap.add_argument("--write-roots", nargs="+", default=list(nc.DEFAULT_WRITE_ROOTS), help="path prefixes the fix pass may write under")
    ap.add_argument("--artifact-copies", default=None, help="JSON object {suffix: canonical path} redirecting synced copies to their source (default: werkstoff's map inside werkstoff, else none)")
    ap.add_argument("--skip-lint", nargs="*", default=list(nc.DEFAULT_SKIP_LINT), help="lint rule ids whose fix is a human decision")
    ap.add_argument("--force-lock", action="store_true", help="overwrite an existing fix_scope.json (only after confirming no fix pass is in flight)")
    a = ap.parse_args(argv)

    import os
    root = nc.repo_root(a.repo_root)
    os.chdir(root)
    state = nc.state_dir(a.state_dir, root)
    out = a.out or state / "fix-args.json"
    rubric = nc.rubric_path(a.rubric)
    write_roots = [r if r.endswith("/") else r + "/" for r in a.write_roots]
    if a.artifact_copies is not None:
        artifact_copies = json.loads(Path(a.artifact_copies).read_text(encoding="utf-8")) if Path(a.artifact_copies).is_file() else json.loads(a.artifact_copies)
    else:
        artifact_copies = dict(nc.DEFAULT_ARTIFACT_COPIES) if nc.is_werkstoff(root) else {}
    skip_lint = set(a.skip_lint)

    synth, findings, routing, args = load(state, "synthesis.json"), load(state, "findings.json"), load(state, "routing.json"), load(state, "args.json")
    run = load(state, "run.json")
    if not run.get("completed"):
        print("ERROR: run.json is not a completed run", file=sys.stderr)
        return 1
    if not isinstance(run.get("calibration"), dict) or not run["calibration"].get("rounds"):
        print("ERROR: run.json carries no calibration block — uncalibrated findings never reach the fix pass", file=sys.stderr)
        return 1
    lock_path = state / "fix_scope.json"
    if lock_path.is_file() and not a.force_lock:
        old = json.loads(lock_path.read_text(encoding="utf-8"))
        print(f"ERROR: a fix lock is already open ({lock_path}, run {old.get('runStamp')}, opened {old.get('createdAt')}). "
              f"Release it with post_fix_check.py --release-lock, or pass --force-lock if no pass is in flight.", file=sys.stderr)
        return 1

    excluded: list[dict] = []
    items: dict[str, dict] = {}

    def redirect(path: str) -> str | None:
        for suffix, canon in artifact_copies.items():
            if path.endswith(suffix):
                if Path(canon).is_file():
                    return canon
                excluded.append({"file": path, "reason": f"synced artifact copy; canonical {canon} not found"})
                return None
        if not any(path.startswith(r) for r in write_roots):
            excluded.append({"file": path, "reason": f"outside the write roots {write_roots}"})
            return None
        if not Path(path).is_file():
            excluded.append({"file": path, "reason": "file does not exist"})
            return None
        return path

    def plugin_of(path: str) -> str:
        pr = a.plugins_root.as_posix().rstrip("/") + "/"
        if path.startswith(pr):
            return path[len(pr):].split("/", 1)[0]
        return path.split("/", 1)[0]

    def item(path: str) -> dict:
        if path not in items:
            items[path] = {"file": path, "plugin": plugin_of(path), "tier": "haiku", "entries": []}
        return items[path]

    def bump(it: dict, tier: str) -> None:
        if TIER_RANK[tier] > TIER_RANK[it["tier"]]:
            it["tier"] = tier

    verified_by_file = defaultdict(list)
    for f in findings["verified"]:
        verified_by_file[f["file"]].append(f)

    # 1. backlog entries
    for p in synth["perPlugin"]:
        for b in p["backlog"]:
            if b["fix_tier"] not in APPLY_TIERS:
                for raw in split_files(b["file"]):
                    excluded.append({"file": raw, "reason": f"{b['fix_tier']}-tier", "tier": b["fix_tier"], "action": b["action"]})
                continue
            for raw in split_files(b["file"]):
                path = redirect(raw)
                if not path:
                    continue
                it = item(path)
                bump(it, b["fix_tier"])
                backing = [
                    {"rule_id": f["rule_id"], "line": f.get("line"), "quote": f["quote"], "claim": f["claim"], "suggested_fix": f["suggested_fix"]}
                    for f in verified_by_file.get(raw, []) if f["rule_id"] in b["rule_ids"]
                ][:6]
                it["entries"].append({"source": "backlog", "tier": b["fix_tier"], "rule_ids": b["rule_ids"], "severity": b.get("severity"), "action": b["action"], "findings": backing})

    # 2. lint findings (haiku-tier by construction, except the ones whose fix lives outside the plugin)
    for lf in findings["lint"]:
        if lf["rule_id"] in skip_lint or lf.get("fix_tier", "haiku") not in APPLY_TIERS:
            excluded.append({"file": lf["file"], "reason": f"{lf['rule_id']} is a human decision", "tier": lf.get("fix_tier", "human")})
            continue
        path = redirect(lf["file"])
        if not path:
            continue
        it = item(path)
        it["entries"].append({"source": "lint", "tier": "haiku", "rule_ids": [lf["rule_id"]], "severity": lf["severity"], "action": f"{lf['claim']} — {lf['suggested_fix']}", "findings": [{"rule_id": lf["rule_id"], "line": lf.get("line"), "quote": lf["quote"], "claim": lf["claim"], "suggested_fix": lf["suggested_fix"]}]})

    # 3. collision judge: proposed negative-trigger descriptions
    corpus = {**args["corpus"]["skill"], **args["corpus"]["agent"]}
    for j in routing.get("judged", []):
        if j["verdict"] not in {"add-negative-trigger", "rescope"}:
            continue
        tier = j.get("fix_tier") or "sonnet"
        if tier not in APPLY_TIERS:
            excluded.append({"file": f"{j['a']} ~ {j['b']}", "reason": f"{tier}-tier collision fix", "tier": tier, "action": j["verdict"]})
            continue
        for d in j.get("proposedDescriptions", []):
            entry = corpus.get(d["id"])
            if not entry:
                excluded.append({"file": d["id"], "reason": "proposed description for unknown id"})
                continue
            path = redirect(entry["path"])
            if not path:
                continue
            it = item(path)
            bump(it, tier)
            it["entries"].append({
                "source": "collision", "tier": tier, "rule_ids": ["Q-CANN-NEGATIVE"], "severity": "major",
                "action": f"Replace the frontmatter description with the proposed text below (verdict {j['verdict']} vs {j['b'] if d['id'] == j['a'] else j['a']}); keep it ≤1024 chars, third person, what + when.",
                "proposedDescription": d["description"], "findings": [],
            })

    # merge duplicate collision proposals for the same file (keep the longest, note the rest)
    for it in items.values():
        props = [e for e in it["entries"] if e["source"] == "collision"]
        if len(props) > 1:
            keep = max(props, key=lambda e: len(e["proposedDescription"]))
            others = [e for e in props if e is not keep]
            keep["action"] += f" NOTE: {len(others)} other collision judgement(s) also proposed a description for this file; fold their negative triggers in: " + " || ".join(o["proposedDescription"][-300:] for o in others)
            it["entries"] = [e for e in it["entries"] if e["source"] != "collision"] + [keep]

    work = sorted(items.values(), key=lambda x: (x["tier"], x["file"]))
    for w in work:
        w["kind"] = kind_of(w["file"])
        plugin_dir = (a.plugins_root / w["plugin"]).as_posix()
        w["postChecks"] = post_checks(w["file"], w["kind"], plugin_dir, a.fixtures_root)

    out_obj = {
        "runStamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reviewRunStamp": run["runStamp"],
        "rubricHash": run["rubricHash"],
        "rubric": rubric.read_text(encoding="utf-8"),
        "writeRoots": write_roots,
        "stateDir": state.relative_to(root).as_posix() if state.is_relative_to(root) else state.as_posix(),
        "items": work,
        "excluded": excluded,
    }
    state.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out_obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(out)

    # snapshot every plugin about to change, for contract_diff after the pass
    plugins_touched = sorted({w["plugin"] for w in work if (a.plugins_root / w["plugin"]).is_dir()})
    snap_root = state / "pre-fix"
    if snap_root.exists():
        shutil.rmtree(snap_root)
    for p in plugins_touched:
        shutil.copytree(a.plugins_root / p, snap_root / p, ignore=SNAPSHOT_IGNORE)

    # the lock: every file the pass may touch, and every file it must not, with its tier
    files: dict[str, str] = {w["file"]: w["tier"] for w in work}
    for e in excluded:
        f = e.get("file", "")
        if e.get("tier") in {"opus", "human"} and f and "/" in f and f not in files:
            files[f] = e["tier"]
    lock = {
        "runStamp": out_obj["runStamp"],
        "createdAt": out_obj["runStamp"],
        "reviewRunStamp": run["runStamp"],
        "stateDir": out_obj["stateDir"],
        "writeRoots": write_roots,
        "files": files,
    }
    tmp = lock_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(lock, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(lock_path)

    src = a.workflow.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("const A = typeof args === 'string'")), None)
    if idx is None:
        print("ERROR: canonical fix workflow lacks the `const A = typeof args` line", file=sys.stderr)
        return 1
    literal = json.dumps(out_obj, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    lines[idx] = f"const A = {literal} // baked by nacharbeit build_fix_args.py at {out_obj['runStamp']}\n"
    baked = state / "fix-run.js"
    baked.write_text("".join(lines), encoding="utf-8")

    by_tier = defaultdict(int)
    for w in work:
        by_tier[w["tier"]] += 1
    n_entries = sum(len(w["entries"]) for w in work)
    print(f"wrote {out}, {baked}, lock {lock_path} ({len(files)} files), snapshot {snap_root} ({len(plugins_touched)} plugin(s))")
    print(f"  {len(work)} files, {n_entries} entries; files by tier: {dict(by_tier)}; excluded {len(excluded)}")
    for w in work:
        print(f"    [{w['tier']:<6}] {w['file']:<70} {len(w['entries'])} entr{'y' if len(w['entries']) == 1 else 'ies'}  {len(w['postChecks'])} post-check(s)")
    for e in excluded:
        print(f"    excluded: {e['file']} — {e['reason']}")
    print("  The PreToolUse guard now denies every edit outside the lock; release it with post_fix_check.py --release-lock when the pass is done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
