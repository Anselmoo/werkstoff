#!/usr/bin/env python3
"""Turn a completed prompt-quality review into per-file fix work items. No LLM.

Reads analysis/prompt-review/{synthesis,findings,routing,args}.json and emits one work
item per file, carrying every haiku- or sonnet-tier backlog entry for that file, the
mechanical lint findings on it, the negative-trigger descriptions the collision judge
proposed for it, and the verified findings that back each entry. Opus- and human-tier
entries are listed under `excluded`, never silently dropped.

Files that are synced copies of an rrt artifact (parallel-safe-research-protocol.md) are
redirected to their canonical source when it exists, otherwise excluded — editing a copy
would fail `rrt artifacts --check` on the next run.

Bakes the items into analysis/prompt-review/fix-run.js from
.claude/workflows/prompt-quality-fix.js so the workflow launches by scriptPath.

Usage: build_fix_args.py [--out analysis/prompt-review/fix-args.json]
Exit: 0 written; 1 inputs missing; 2 bad args.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IN = ROOT / "analysis/prompt-review"
RUBRIC = ROOT / "docs/plugin-authoring/references/prompt-quality-rubric.md"
CANON = ROOT / ".claude/workflows/prompt-quality-fix.js"
APPLY_TIERS = {"haiku", "sonnet"}
TIER_RANK = {"haiku": 0, "sonnet": 1, "opus": 2, "human": 3}
ARTIFACT_COPIES = {"references/parallel-safe-research-protocol.md": "tools/symbol-indexer/parallel-safe-research-protocol.md"}
SKIP_LINT = {"M-DUP-CONTENT"}  # duplication is a human decision (five synced copies)


def load(name: str):
    p = IN / name
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
            out.append(cur); cur = ""
        else:
            cur += ch
    out.append(cur)
    parts: list[str] = []
    for piece in out:
        parts += re.split(r"\s+\+\s+|\s+and\s+", piece)
    return [y.strip().strip("`") for x in parts for y in expand_braces(x.strip()) if y.strip()]


def redirect(path: str, excluded: list) -> str | None:
    for suffix, canon in ARTIFACT_COPIES.items():
        if path.endswith(suffix):
            if (ROOT / canon).is_file():
                return canon
            excluded.append({"file": path, "reason": f"synced artifact copy; canonical {canon} not found"})
            return None
    if not path.startswith("plugins/") and not path.startswith("tools/"):
        excluded.append({"file": path, "reason": "outside plugins/"})
        return None
    if not (ROOT / path).is_file():
        excluded.append({"file": path, "reason": "file does not exist"})
        return None
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=IN / "fix-args.json")
    a = ap.parse_args(argv)
    synth, findings, routing, args = load("synthesis.json"), load("findings.json"), load("routing.json"), load("args.json")
    run = load("run.json")
    if not run.get("completed"):
        print("ERROR: run.json is not a completed run", file=sys.stderr)
        return 1

    excluded: list[dict] = []
    items: dict[str, dict] = {}

    def item(path: str) -> dict:
        if path not in items:
            plugin = path.split("/")[1] if path.startswith("plugins/") else "tools"
            items[path] = {"file": path, "plugin": plugin, "tier": "haiku", "entries": []}
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
                excluded.append({"file": b["file"], "reason": f"{b['fix_tier']}-tier", "action": b["action"]})
                continue
            for raw in split_files(b["file"]):
                path = redirect(raw, excluded)
                if not path:
                    continue
                it = item(path)
                bump(it, b["fix_tier"])
                backing = [
                    {"rule_id": f["rule_id"], "line": f.get("line"), "quote": f["quote"], "claim": f["claim"], "suggested_fix": f["suggested_fix"]}
                    for f in verified_by_file.get(raw, []) if f["rule_id"] in b["rule_ids"]
                ][:6]
                it["entries"].append({"source": "backlog", "tier": b["fix_tier"], "rule_ids": b["rule_ids"], "severity": b.get("severity"), "action": b["action"], "findings": backing})

    # 2. lint findings (all haiku-tier by construction)
    for l in findings["lint"]:
        if l["rule_id"] in SKIP_LINT:
            excluded.append({"file": l["file"], "reason": "duplicate-content cluster is a human decision"})
            continue
        path = redirect(l["file"], excluded)
        if not path:
            continue
        it = item(path)
        it["entries"].append({"source": "lint", "tier": "haiku", "rule_ids": [l["rule_id"]], "severity": l["severity"], "action": f"{l['claim']} — {l['suggested_fix']}", "findings": [{"rule_id": l["rule_id"], "line": l.get("line"), "quote": l["quote"], "claim": l["claim"], "suggested_fix": l["suggested_fix"]}]})

    # 3. collision judge: proposed negative-trigger descriptions
    corpus = {**args["corpus"]["skill"], **args["corpus"]["agent"]}
    for j in routing.get("judged", []):
        if j["verdict"] not in {"add-negative-trigger", "rescope"}:
            continue
        tier = j.get("fix_tier") or "sonnet"
        if tier not in APPLY_TIERS:
            excluded.append({"file": f"{j['a']} ~ {j['b']}", "reason": f"{tier}-tier collision fix", "action": j["verdict"]})
            continue
        for d in j.get("proposedDescriptions", []):
            entry = corpus.get(d["id"])
            if not entry:
                excluded.append({"file": d["id"], "reason": "proposed description for unknown id"})
                continue
            path = redirect(entry["path"], excluded)
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
        w["kind"] = "workflow" if w["file"].endswith(".js") else "agent" if "/agents/" in w["file"] else "command" if "/commands/" in w["file"] else "skill" if w["file"].endswith("SKILL.md") else "reference"

    out = {
        "runStamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reviewRunStamp": run["runStamp"],
        "rubricHash": run["rubricHash"],
        "rubric": RUBRIC.read_text(encoding="utf-8"),
        "items": work,
        "excluded": excluded,
    }
    IN.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(a.out)

    src = CANON.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("const A = typeof args === 'string'")), None)
    if idx is None:
        print("ERROR: canonical fix workflow lacks the `const A = typeof args` line", file=sys.stderr)
        return 1
    literal = json.dumps(out, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    lines[idx] = f"const A = {literal} // baked by tools/prompt-review/build_fix_args.py at {out['runStamp']}\n"
    baked = IN / "fix-run.js"
    baked.write_text("".join(lines), encoding="utf-8")

    by_tier = defaultdict(int)
    for w in work:
        by_tier[w["tier"]] += 1
    n_entries = sum(len(w["entries"]) for w in work)
    print(f"wrote {a.out} and {baked}")
    print(f"  {len(work)} files, {n_entries} entries; files by tier: {dict(by_tier)}; excluded {len(excluded)}")
    for w in work:
        print(f"    [{w['tier']:<6}] {w['file']:<70} {len(w['entries'])} entr{'y' if len(w['entries']) == 1 else 'ies'}")
    for e in excluded:
        print(f"    excluded: {e['file']} — {e['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
