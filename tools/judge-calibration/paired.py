#!/usr/bin/env python3
"""The paired tribunal measurement: andon's four-role tribunal (arm A) against one verdict@1
contract judge (arm B) on the same items, five repeats each.

The design is in docs/plugin-authoring/references/judge-calibration.md. This file holds what
must be fixed BEFORE the run, so that nothing about the scoring can be chosen after seeing it:

  * the items: the tribunal's 8 sealed cases plus 12 paired-only cases (test/judge-calibration/
    paired/), every answer re-derived by the same probes as the tribunal's
  * arm B's rubric (andon-wire@1, one criterion per contract criterion, threshold 0.7) and its
    prompt, which holds the same contract, diff and fenced files the tribunal's roles get
  * the per-item outcome: the outcome at least 3 of the 5 repeats agree on, else no-majority,
    which scores as an abstain
  * the DECISION RULE, applied to the per-item outcomes:
        keep the tribunal  iff  arm B has more false passes than arm A,
                                or a lower record (the six-figure weakest) than arm A
        otherwise          ->   collapse it onto the contract, like the passung panels

Usage:
    paired.py check                       items, keys and prompt assembly
    paired.py stage --dest DIR --out ARGS.json   one tree copy per (item, repeat, arm), Workflow args
    paired.py score --raw RAW.json --map MAP.json [--write]   results, both arms, the decision

STDLIB ONLY. Python >= 3.11.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import calibration  # noqa: E402  (same directory; shares the scorer and the canonical judge contract)
import oracles  # noqa: E402
import prompts  # noqa: E402

MIN_PYTHON = (3, 11)
FIX = calibration.FIXTURES
REPEATS = 5
MAJORITY = 3
THRESHOLD = 0.7
TREE = "{TREE}"
OUTCOME_OF = {"green": "pass", "red": "fail", "unknown": "abstain"}


def items() -> list[dict]:
    """(item id, case dir, oracle file, expected outcome): sealed tribunal cases, then paired ones."""
    out = []
    for judge, phase in (("tribunal", "sealed"), ("paired", "paired")):
        answers = calibration.load_json(FIX / judge / "answers.json")
        for cid in sorted(c for c, a in answers.items() if a["split"] == phase):
            out.append({"id": f"{judge}/{cid}", "dir": FIX / judge / "cases" / cid,
                        "oracle": FIX / judge / "oracle" / f"{cid}.json",
                        "expected": answers[cid]["expected"], "native": answers[cid]["nativeExpected"]})
    return out


def rubric(contract: dict) -> dict:
    return {"id": "andon-wire@1", "threshold": THRESHOLD,
            "criteria": [{"id": c["id"], "question": c["text"]} for c in contract["criteria"]]}


ARM_B_HEAD = (
    "Judge this wire against its contract. You are its only judge. Decide each criterion from "
    "evidence you find yourself in the working tree at {TREE}: read it, and run whatever checks "
    "you need from inside it, but change nothing in it.\n\n"
    "Rubric andon-wire@1, threshold 0.7. For every criterion give a score from 0.0 to 1.0 for how "
    "strongly the evidence shows it holds, pass true or false, and evidence naming a file:line or "
    "a command and what it printed. If any criterion cannot be decided from evidence available in "
    "this environment, do not guess: set abstain to true and give the reason.\n\n"
    "Report item {ITEM}."
)


def templates(item: dict, key: str) -> dict[str, Any]:
    """Every prompt of one item with the tree path left as {TREE}. The tribunal's role prompts
    are prompts.py's own; arm B gets the same body after its rubric."""
    contract = calibration.load_json(item["dir"] / "contract.json")
    tree = Path(TREE)
    tp = prompts.tribunal_prompts(contract, item["dir"], item["dir"] / "tree")
    # tribunal_prompts reads the files from the case's own tree; the path it prints is the
    # staged one, so substitute it back to the placeholder.
    real = (item["dir"] / "tree").as_posix()
    defender = tp["defender"].replace(real, TREE)
    challenger = tp["challenger"].replace(real, TREE)
    body = defender.split("\n\n", 1)[1]
    verifier_head = prompts.verifier_prompt(contract, tree, "", "").split("\n\n")[0]
    contract_block = prompts._contract_block(contract)
    adj_head = prompts.adjudicator_prompt(contract, "", "", "").split("\n\n")[0]
    arm_b = ARM_B_HEAD.replace("{ITEM}", key) + "\n\n" + body
    return {"defender": defender, "challenger": challenger, "verifierHead": verifier_head,
            "adjudicatorHead": adj_head, "contractBlock": contract_block, "armB": arm_b}


def js_verifier(t: dict, tree: str, d: str, c: str) -> str:
    """The prompt the workflow assembles for the verifier: must equal prompts.verifier_prompt."""
    fence = prompts._fence()
    return "\n\n".join([t["verifierHead"].replace(TREE, tree), t["contractBlock"],
                        "Defender's case:\n" + fence(d), "Challenger's case:\n" + fence(c)])


def js_adjudicator(t: dict, d: str, c: str, v: str) -> str:
    fence = prompts._fence()
    return "\n\n".join([t["adjudicatorHead"], t["contractBlock"], "Defender's case:\n" + fence(d),
                        "Challenger's case:\n" + fence(c), "Verifier's facts:\n" + fence(v)])


def check() -> list[str]:
    probs = []
    its = items()
    if len(its) != 20:
        probs.append(f"{len(its)} items, the design says 20")
    exp = [i["expected"] for i in its]
    for o in calibration.OUTCOMES:
        if exp.count(o) / len(exp) > 0.5:
            probs.append(f"known-{o} is more than half the items")
    for i in its:
        tree = oracles._tree_of(i["dir"] / "tree")
        truth, _ = oracles.tribunal_truth(tree, calibration.load_json(i["oracle"])["probes"])
        if truth != i["native"]:
            probs.append(f"{i['id']}: the probes say {truth}, the key says {i['native']}")
        t = templates(i, "kX")
        contract = calibration.load_json(i["dir"] / "contract.json")
        if js_verifier(t, "/s/tree", "D", "C") != prompts.verifier_prompt(contract, Path("/s/tree"), "D", "C"):
            probs.append(f"{i['id']}: the verifier's parts do not reassemble prompts.verifier_prompt")
        if js_adjudicator(t, "D", "C", "V") != prompts.adjudicator_prompt(contract, "D", "C", "V"):
            probs.append(f"{i['id']}: the adjudicator's parts do not reassemble prompts.adjudicator_prompt")
        if TREE not in t["defender"] or TREE not in t["armB"]:
            probs.append(f"{i['id']}: a prompt does not carry the tree placeholder")
        if "nativeExpected" in t["armB"] or "answers" in t["armB"]:
            probs.append(f"{i['id']}: arm B's prompt names the answer")
    canon = (HERE.parent / "judge-contract" / "verdict.inline.js").read_text(encoding="utf-8")
    mine = (HERE / "paired_workflow.js").read_text(encoding="utf-8")
    cut = lambda t: t[t.index("// judge-contract:start verdict@1"):t.index("// judge-contract:end")]  # noqa: E731
    if cut(canon) != cut(mine):
        probs.append("paired_workflow.js's verdict@1 block differs from tools/judge-contract/verdict.inline.js")
    return probs


def stage(dest: Path, out: Path, map_file: Path) -> int:
    """One tree copy per (item, repeat, arm), and that run's prompts in their own directory beside
    the stage, never inside a tree. The Workflow args carry only those directories."""
    roles = dest.parent / f"{dest.name}-roles"
    for d in (dest, roles):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    salt = hashlib.sha256(dest.as_posix().encode()).hexdigest()[:8]
    args_items, mapping = [], {}
    for i in items():
        key = "w" + hashlib.sha256(f"{salt}:{i['id']}".encode()).hexdigest()[:8]
        mapping[key] = i["id"]
        t = templates(i, key)
        runs = {}
        for r in range(1, REPEATS + 1):
            for arm in ("a", "b"):
                run = f"{key}-{r}{arm}"
                tree = dest / run / "tree"
                shutil.copytree(i["dir"] / "tree", tree)
                rd = roles / run
                rd.mkdir()
                tp = tree.as_posix()
                files = ({"judge": t["armB"]} if arm == "b" else {
                    "defender": t["defender"], "challenger": t["challenger"],
                    "verifier-head": t["verifierHead"] + "\n\n" + t["contractBlock"],
                    "adjudicator-head": t["adjudicatorHead"] + "\n\n" + t["contractBlock"]})
                for name, text in files.items():
                    (rd / f"{name}.txt").write_text(text.replace(TREE, tp), encoding="utf-8")
                runs[f"{r}{arm}"] = rd.as_posix()
        args_items.append({"key": key, "runs": runs})
    out.write_text(json.dumps({"repeats": REPEATS, "items": args_items}) + "\n", encoding="utf-8")
    map_file.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    print(f"staged {len(args_items)} items x {REPEATS} repeats x 2 arms under {dest.as_posix()}; args {out.as_posix()}")
    return 0


# ---------------------------------------------------------------------------- scoring

def outcome_a(adjudicator: str | None) -> str:
    native = calibration.parse_native("tribunal", adjudicator or "")
    return calibration.map_tribunal(native)[0]


def outcome_b(report: Any, contract: dict, key: str) -> tuple[str, dict]:
    v = calibration.judge_contract.decide(report, rubric(contract), item=key)
    return v["outcome"], v


def majority(outcomes: list[str]) -> str:
    for o in calibration.OUTCOMES:
        if outcomes.count(o) >= MAJORITY:
            return o
    return "abstain"  # no-majority scores as an abstain, fixed before the run


def binom_two_sided(b: int, c: int) -> float:
    """Exact McNemar: P(at least this lopsided | discordant pairs split 50/50)."""
    n, k = b + c, min(b, c)
    if n == 0:
        return 1.0
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def score(raw: dict, mapping: dict[str, str]) -> dict:
    by_id = {i["id"]: i for i in items()}
    per_item: dict[str, dict] = {}
    for run in raw["runs"]:
        iid = mapping[run["key"]]
        it = by_id[iid]
        rec = per_item.setdefault(iid, {"expected": it["expected"], "a": [], "b": [], "bVerdicts": []})
        contract = calibration.load_json(it["dir"] / "contract.json")
        if run["arm"] == "a":
            rec["a"].append(outcome_a(run.get("adjudicator")))
        else:
            o, v = outcome_b(run.get("report"), contract, run["key"])
            rec["b"].append(o)
            rec["bVerdicts"].append(v)
    probs = [f"{iid}: {len(r['a'])} arm-A and {len(r['b'])} arm-B runs, want {REPEATS} each"
             for iid, r in per_item.items() if len(r["a"]) != REPEATS or len(r["b"]) != REPEATS]
    if len(per_item) != len(by_id) or probs:
        raise ValueError("incomplete run: " + "; ".join(probs or [f"{len(per_item)}/{len(by_id)} items"]))
    out: dict[str, Any] = {"items": {}, "arms": {}}
    for arm in ("a", "b"):
        exp = {iid: r["expected"] for iid, r in per_item.items()}
        got = {iid: majority(r[arm]) for iid, r in per_item.items()}
        m = calibration.metrics(calibration.confusion(exp, got))
        runs_exp = {f"{iid}#{k}": r["expected"] for iid, r in per_item.items() for k in range(REPEATS)}
        runs_got = {f"{iid}#{k}": r[arm][k] for iid, r in per_item.items() for k in range(REPEATS)}
        mr = calibration.metrics(calibration.confusion(runs_exp, runs_got))
        unanimous = sum(1 for r in per_item.values() if len(set(r[arm])) == 1)
        out["arms"][arm] = {"items": m, "record": calibration.derive_record(m, 0.8), "runs": mr,
                            "unanimousItems": unanimous}
    b_only = sum(1 for r in per_item.values() if majority(r["a"]) != r["expected"] == majority(r["b"]))
    a_only = sum(1 for r in per_item.values() if majority(r["b"]) != r["expected"] == majority(r["a"]))
    out["discordant"] = {"onlyTribunalRight": a_only, "onlyContractJudgeRight": b_only,
                         "mcnemarExactP": binom_two_sided(a_only, b_only)}
    A, B = out["arms"]["a"], out["arms"]["b"]
    keep = (B["items"]["falsePasses"] > A["items"]["falsePasses"]
            or B["record"]["agreement"] < A["record"]["agreement"])
    out["decision"] = {"rule": "keep the tribunal iff arm B has more false passes, or a lower record, than arm A",
                       "keepTribunal": keep,
                       "falsePasses": {"tribunal": A["items"]["falsePasses"], "contractJudge": B["items"]["falsePasses"]},
                       "record": {"tribunal": A["record"]["agreement"], "contractJudge": B["record"]["agreement"]}}
    for iid, r in sorted(per_item.items()):
        out["items"][iid] = {"expected": r["expected"], "tribunal": r["a"], "contractJudge": r["b"],
                             "tribunalMajority": majority(r["a"]), "contractJudgeMajority": majority(r["b"]),
                             "contractJudgeAbstainReasons": sorted({v["abstainReason"] for v in r["bVerdicts"]
                                                                    if v["abstainReason"]})}
    return out


def _fake_raw(a_mode: str, b_mode: str) -> tuple[dict, dict]:
    """Fabricated runs: 'right' answers every item correctly; 'pass' always passes; 'split'
    gives each item a 2-2-1 spread (no majority); 'abstain' always abstains."""
    word = {"pass": "green", "fail": "red", "abstain": "unknown"}
    mapping, runs = {}, []
    for n, it in enumerate(items()):
        key = f"w{n:02d}"
        mapping[key] = it["id"]
        contract = calibration.load_json(it["dir"] / "contract.json")
        crit = [c["id"] for c in contract["criteria"]]
        for r in range(REPEATS):
            for arm, mode in (("a", a_mode), ("b", b_mode)):
                if mode == "split":
                    o = ["pass", "pass", "fail", "fail", "abstain"][r]
                elif mode == "abstain":
                    o = "abstain"
                else:
                    o = it["expected"] if mode == "right" else "pass"
                if arm == "a":
                    runs.append({"key": key, "arm": "a", "adjudicator": f"Overall: {word[o]}"})
                elif o == "abstain":
                    runs.append({"key": key, "arm": "b", "report": {"item": key, "criteria": [], "abstain": True,
                                                                     "abstainReason": "production only"}})
                else:
                    ok = o == "pass"
                    runs.append({"key": key, "arm": "b", "report": {"item": key, "abstain": False, "abstainReason": None,
                                 "criteria": [{"id": c, "score": 0.9 if ok else 0.1, "pass": ok, "evidence": "x"} for c in crit]}})
    return {"runs": runs}, mapping


def selftest() -> int:
    bad = []
    rep = score(*_fake_raw("right", "right"))
    if rep["decision"]["keepTribunal"]:
        bad.append("two perfect arms kept the tribunal (a tie must collapse it)")
    rep = score(*_fake_raw("right", "pass"))
    if not rep["decision"]["keepTribunal"] or rep["arms"]["b"]["items"]["falsePasses"] == 0:
        bad.append("a contract judge that passes everything did not keep the tribunal")
    rep = score(*_fake_raw("pass", "right"))
    if rep["decision"]["keepTribunal"]:
        bad.append("a tribunal that passes everything was kept over a perfect contract judge")
    rep = score(*_fake_raw("right", "abstain"))
    if rep["arms"]["b"]["items"]["falsePasses"] != 0 or not rep["decision"]["keepTribunal"]:
        bad.append("a contract judge that abstains on everything (no false pass, record 0) did not keep the tribunal")
    rep = score(*_fake_raw("split", "right"))
    if any(v["tribunalMajority"] != "abstain" for v in rep["items"].values()):
        bad.append("a 2-2-1 spread was given a majority")
    raw, mp = _fake_raw("right", "right")
    raw["runs"].pop()
    try:
        score(raw, mp)
        bad.append("an incomplete run was scored")
    except ValueError:
        pass
    if binom_two_sided(0, 6) > 0.032 or binom_two_sided(3, 3) != 1.0:
        bad.append("the exact McNemar p is wrong (0 vs 6 should be 2/64)")
    for b in bad:
        print(f"FAIL {b}")
    print(f"paired selftest: {len(bad)} failure(s)")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print("ERROR: needs Python >= 3.11", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("selftest")
    s = sub.add_parser("stage")
    s.add_argument("--dest", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--map", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--raw", type=Path, required=True)
    s.add_argument("--map", type=Path, required=True)
    s.add_argument("--write", type=Path)
    a = p.parse_args(argv)
    if a.cmd == "check":
        probs = check()
        for x in probs:
            print(f"PAIRED {x}")
        print(f"paired measurement: {len(items())} items, {len(probs)} problem(s)")
        return 1 if probs else 0
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "stage":
        return stage(a.dest, a.out, a.map)
    rep = score(calibration.load_json(a.raw), calibration.load_json(a.map))
    text = json.dumps(rep, indent=2) + "\n"
    if a.write:
        a.write.write_text(text, encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("decision", "discordant")}, indent=2))
    for arm, name in (("a", "tribunal"), ("b", "contract judge")):
        m = rep["arms"][arm]["items"]
        print(f"{name}: per-item agreement {m['agreement']:.2f}, false passes {m['falsePasses']}, "
              f"record {rep['arms'][arm]['record']['agreement']}, per-run agreement {rep['arms'][arm]['runs']['agreement']:.2f}, "
              f"unanimous items {rep['arms'][arm]['unanimousItems']}/20")
    return 0


if __name__ == "__main__":
    sys.exit(main())
