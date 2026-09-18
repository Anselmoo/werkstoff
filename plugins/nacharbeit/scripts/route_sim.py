#!/usr/bin/env python3
"""Run ONLY the review's haiku routing simulation, headless, and write routing.json.

usage: route_sim.py --args ARGS.json --out routing.json [--model haiku] [--votes 3] [--dry-run]
       route_sim.py --selftest

The routing simulation normally runs inside the full review workflow, behind the
finder calibration -- far more expensive than the simulation itself. Calibrating
the simulation against trigger_probe.py needs only the simulation, so this runs it
alone, as `claude -p` calls with no tools and a JSON schema.

Nothing is restated here, so nothing can drift: ROUTE_PROMPT and ROUTE_SCHEMA are
EVALUATED out of workflows/review.js in node, and the corpus and known answers come
from the args.json build_args.py writes. The majority rule is review.js's own: a
prompt's winner is the top pick of at least 2 of 3 votes, else none.

Exit: 0 written; 1 a vote failed (nothing written -- a partial simulation is never
persisted as a whole one); 2 usage or unreadable input.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parent / "workflows" / "review.js"
CHUNK = 8  # review.js's chunk size


def review_constants() -> tuple:
    node = shutil.which("node")
    if not node:
        raise SystemExit("node is not on PATH; ROUTE_PROMPT cannot be read from review.js")
    code = ('const s=require("fs").readFileSync(process.argv[1],"utf8");'
            'const grab=n=>{const i=s.indexOf("const "+n+" =");if(i<0)throw new Error(n+" not found");'
            'let d=0,j=s.indexOf("=",i)+1,q=null;for(;j<s.length;j++){const c=s[j];'
            'if(q){if(c==="\\\\"){j++;continue}if(c===q)q=null;continue}'
            'if(c==="`"||c==="\\""||c==="\'"){q=c;continue}if("{[(".includes(c))d++;if("}])".includes(c))d--;'
            'if(d===0&&c==="\\n"&&s.slice(i,j).trim().length>0&&!/[,{[(+]$/.test(s.slice(i,j).trim()))break}'
            'return new Function("return "+s.slice(s.indexOf("=",i)+1,j).trim())()};'
            'process.stdout.write(JSON.stringify({p:grab("ROUTE_PROMPT"),s:grab("ROUTE_SCHEMA")}))')
    r = subprocess.run([node, "-e", code, str(REVIEW)], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"could not read ROUTE_PROMPT/ROUTE_SCHEMA from review.js: {r.stderr.strip()[:300]}")
    d = json.loads(r.stdout)
    return d["p"], d["s"]


def fence(s: str) -> str:
    return "<<<UNTRUSTED\n" + s.replace("<<<UNTRUSTED", "[fence marker stripped]").replace("UNTRUSTED>>>", "[fence marker stripped]") + "\nUNTRUSTED>>>"


def prompts_for(args: dict) -> list:
    return [p for p in args["knownAnswers"] if p.get("router") == "skill"]


def majority(votes: list) -> str | None:
    tops = Counter(v[0] for v in votes if v)
    best = tops.most_common(1)
    return best[0][0] if best and best[0][1] >= 2 else None


def score(prompts: list, by_prompt: dict) -> dict:
    winners = {p["id"]: majority(by_prompt.get(p["id"], [])) for p in prompts}
    correct = sum(winners[p["id"]] == p["expected"] for p in prompts)
    misrouted = [{"id": p["id"], "text": p["text"], "expected": p["expected"], "got": winners[p["id"]],
                  "votes": by_prompt.get(p["id"], [])} for p in prompts if winners[p["id"]] != p["expected"]]
    acc = correct / len(prompts) if prompts else 0.0
    return {"accuracy": round(acc, 4), "correct": correct, "knownAnswerCount": len(prompts),
            "measured": acc >= 0.8, "misrouted": misrouted, "winners": winners}


def call(claude: str, model: str, prompt: str, schema: dict) -> dict | None:
    argv = [claude, "-p", prompt, "--model", model, "--tools", "", "--json-schema", json.dumps(schema),
            "--output-format", "json", "--strict-mcp-config", "--setting-sources", "project",
            "--no-session-persistence"]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
                       cwd=tempfile.gettempdir())
    if r.returncode != 0:
        return None
    try:
        env = json.loads(r.stdout)
    except ValueError:
        return None
    out = env.get("structured_output")
    if out is None and isinstance(env.get("result"), str):
        try:
            out = json.loads(env["result"])
        except ValueError:
            out = None
    return {"routes": out.get("routes", []), "cost": env.get("total_cost_usd") or 0} if isinstance(out, dict) else None


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="route_sim.py", description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--args")
    ap.add_argument("--out")
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--votes", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.args or not a.out:
        ap.error("--args and --out are required")
    args = json.loads(Path(a.args).read_text(encoding="utf-8"))
    route_prompt, route_schema = review_constants()
    prompts = prompts_for(args)
    corpus = [{"id": cid, "plugin": e["plugin"], "description": e["description"]} for cid, e in args["corpus"]["skill"].items()]
    chunks = [prompts[i:i + CHUNK] for i in range(0, len(prompts), CHUNK)]
    print(f"route_sim: {len(prompts)} known-answer prompts, corpus {len(corpus)} skills, "
          f"{len(chunks)} chunk(s) x {a.votes} vote(s) = {len(chunks) * a.votes} {a.model} call(s)")
    if a.dry_run:
        return 0
    claude = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"
    by_prompt: dict = {}
    cost = 0.0
    known = {c["id"] for c in corpus}
    for ci, ch in enumerate(chunks):
        text = (f"{route_prompt}\n\nCorpus ({len(corpus)} components):\n{fence(json.dumps(corpus))}\n\n"
                f"Prompts:\n{fence(json.dumps([{'id': p['id'], 'text': p['text']} for p in ch]))}")
        for v in range(a.votes):
            res = call(claude, a.model, text, route_schema)
            if res is None:
                print(f"FAILED chunk {ci} vote {v}: nothing written -- a partial simulation is not a simulation", file=sys.stderr)
                return 1
            cost += res["cost"]
            for r in res["routes"]:
                # Same rule as review.js: an id not in the corpus is dropped, never a pick.
                by_prompt.setdefault(r.get("promptId"), []).append([p for p in r.get("picks") or [] if p in known])
    out = {**score(prompts, by_prompt), "model": a.model, "votes": a.votes, "cost_usd": round(cost, 4),
           "source": "route_sim.py (review.js ROUTE_PROMPT/ROUTE_SCHEMA, evaluated)"}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"accuracy {out['accuracy']:.2f} ({out['correct']}/{out['knownAnswerCount']}), "
          f"{len(out['misrouted'])} misrouted; spent ${out['cost_usd']}; wrote {a.out}")
    return 0


def selftest() -> int:
    fails = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    p, s = review_constants()
    ok("ROUTE_PROMPT is read out of review.js, not restated", "component router" in p and len(p) > 100)
    ok("ROUTE_SCHEMA is read out of review.js", s.get("required") == ["routes"])
    ok("majority needs 2 of 3 top picks", majority([["a"], ["a", "b"], ["b"]]) == "a" and majority([["a"], ["b"], ["c"]]) is None)
    prompts = [{"id": "k1", "text": "t1", "expected": "a"}, {"id": "k2", "text": "t2", "expected": "b"}]
    sc = score(prompts, {"k1": [["a"], ["a"], ["b"]], "k2": [["a"], ["a"], ["b"]]})
    ok("score: accuracy and misrouted by text", sc["accuracy"] == 0.5 and sc["misrouted"][0]["text"] == "t2" and sc["misrouted"][0]["got"] == "a")
    with tempfile.TemporaryDirectory() as raw:
        stub = Path(raw) / "claude"
        stub.write_text('#!/bin/sh\necho \'{"structured_output":{"routes":[{"promptId":"k1","picks":["a","ghost"]},{"promptId":"k2","picks":["b"]}]},"total_cost_usd":0.01}\'\n')
        stub.chmod(0o755)
        argsf = Path(raw) / "args.json"
        argsf.write_text(json.dumps({"knownAnswers": [dict(x, router="skill") for x in prompts],
                                     "corpus": {"skill": {"a": {"plugin": "p", "description": "A"}, "b": {"plugin": "p", "description": "B"}}}}))
        os.environ["CLAUDE_BIN"] = str(stub)
        rc = main(["--args", str(argsf), "--out", str(Path(raw) / "r.json")])
        r = json.loads((Path(raw) / "r.json").read_text()) if rc == 0 else {}
        ok("end to end against a stub: accuracy 1.0, invented id dropped", rc == 0 and r.get("accuracy") == 1.0 and r["winners"]["k1"] == "a")
        stub.write_text("#!/bin/sh\nexit 1\n")
        rc = main(["--args", str(argsf), "--out", str(Path(raw) / "r2.json")])
        ok("a failed vote writes nothing", rc == 1 and not (Path(raw) / "r2.json").exists())
        del os.environ["CLAUDE_BIN"]
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("route_sim selftest passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
