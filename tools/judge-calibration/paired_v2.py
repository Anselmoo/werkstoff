#!/usr/bin/env python3
"""The second paired tribunal measurement: andon's four-role tribunal (arm A) against one
verdict@2 contract judge (arm B), on 16 items neither arm has seen, five repeats each.

The first measurement (paired.py, wf_589ce94f-c60) kept the tribunal by one item, paired-12:
a failed criterion beside one only production could settle, which a verdict@1 judge can only
abstain on. verdict@2 lets a criterion be undecidable and lets a fail dominate it. This run
asks whether that closes the gap. Nothing from the first run is re-scored.

Everything that decides the result is fixed here, and committed, BEFORE the run:

  * the items: test/judge-calibration/paired-v2/, 16 cases written for this run and never shown
    to either arm before it -- 5 green, 6 red (4 of them a failed criterion beside an
    undecidable one, the failed one first, in the middle and last), 5 unknown (a decided pass
    beside an undecidable one; two carry a decoy, two list the undecidable criterion first).
    Two greens carry a criterion that names production but is decided by reading the code.
    Every key is re-derived by its probes (exit 0 holds, 3 undecidable, anything else fails).
  * arm A: the tribunal exactly as the first run dispatched it (prompts.py's role prompts,
    paired_v2_workflow.js's dispatch order, no model named).
  * arm B: rubric andon-wire@2 (one criterion per contract criterion, threshold 0.7) and the
    prompt ARM_B_HEAD below, decided by the canonical judge_contract.decide(): pass -> green,
    fail -> red, abstain (whole or undecidable:<ids>) -> unknown.
  * the per-item outcome: the outcome at least 3 of the 5 repeats agree on, else no-majority,
    which scores as an abstain.
  * DECISION_RULE, word for word the first run's, applied to the per-item outcomes.

Usage:
    paired_v2.py check
    paired_v2.py selftest
    paired_v2.py stage --dest DIR --out ARGS.json --map MAP.json
    paired_v2.py collect --run-dir DIR --map MAP.json --out RAW.json
    paired_v2.py score --raw RAW.json --map MAP.json [--write OUT.json] [--errata ERRATA.json]

KEY ERRATA. A sealed key later shown wrong is never edited: answers.json, the oracle and
results/score.json stay what the seal said and what it scored. results/key-errata.json records
each correction (the sealed and corrected key, the criterion, a probe that reproduces the defect
on the staged tree, who found it, and how both arms were audited for others), and
results/score-corrected.json is the same run.json scored under the corrected keys. check
re-runs every erratum probe -- it must fail the staged tree with an AssertionError, so a probe
that errors for any other reason reproduces nothing -- and recomputes both scores.

STDLIB ONLY. Python >= 3.11.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import calibration  # noqa: E402  (same directory)
import oracles  # noqa: E402
import paired  # noqa: E402  (the first run: its prompt assembly, majority rule and collector are reused, never its items or scoring)
import prompts  # noqa: E402

MIN_PYTHON = (3, 11)
SET = calibration.FIXTURES / "paired-v2"
N_ITEMS = 16
REPEATS = paired.REPEATS          # 5
MAJORITY = paired.MAJORITY        # 3
THRESHOLD = 0.7
TREE = paired.TREE
RUBRIC_ID = "andon-wire@2"
WORKFLOW = HERE / "paired_v2_workflow.js"
ERRATA = SET / "results" / "key-errata.json"
DECISION_RULE = "keep the tribunal iff arm B has more false passes, or a lower record, than arm A"

ARM_B_HEAD = (
    "Judge this wire against its contract. You are its only judge. Decide each criterion from "
    "evidence you find yourself in the working tree at {TREE}: read it, and run whatever checks "
    "you need from inside it, but change nothing in it.\n\n"
    "Rubric andon-wire@2, threshold 0.7. For every criterion give a score from 0.0 to 1.0 for how "
    "strongly the evidence shows it holds, pass true or false, and evidence naming a file:line or "
    "a command and what it printed. If one criterion cannot be decided from evidence available in "
    "this environment, do not guess: give it score null and pass null, and say in its evidence what "
    "would decide it. Decide every other criterion as usual. Set abstain to true only if you cannot "
    "judge the item at all.\n\n"
    "Report item {ITEM}."
)


def items(errata: dict | None = None) -> list[dict]:
    """The sealed items; with ``errata``, each corrected item carries its corrected key."""
    answers = calibration.load_json(SET / "answers.json")
    fix = {cid: e["corrected"] for cid, e in (errata or {}).items()}
    return [{"id": f"paired-v2/{cid}", "dir": SET / "cases" / cid, "oracle": SET / "oracle" / f"{cid}.json",
             "expected": fix.get(cid, a)["expected"], "native": fix.get(cid, a)["nativeExpected"]}
            for cid, a in sorted(answers.items())]


def check_errata(errata: dict) -> list[str]:
    """Every erratum names a sealed item, matches the sealed key it corrects, and its probe
    fails the staged tree with an AssertionError (exit 1), never as root."""
    if os.geteuid() == 0:
        return ["the key errata cannot be checked as root: root reads a mode-000 directory"]
    probs = []
    answers = calibration.load_json(SET / "answers.json")
    for cid, e in sorted(errata.items()):
        if cid not in answers:
            probs.append(f"erratum {cid} names no sealed item")
            continue
        if e["sealed"] != {k: answers[cid][k] for k in ("expected", "nativeExpected")}:
            probs.append(f"erratum {cid}: its sealed key is not the one answers.json holds")
        if paired.OUTCOME_OF[e["corrected"]["nativeExpected"]] != e["corrected"]["expected"]:
            probs.append(f"erratum {cid}: corrected expected and nativeExpected disagree")
        with tempfile.TemporaryDirectory() as td:
            oracles.write_tree(Path(td), oracles._tree_of(SET / "cases" / cid / "tree"))
            r = subprocess.run([sys.executable, "-B", "-c", e["probe"]], cwd=td, capture_output=True, text=True,
                               env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": td}, check=False)
        if r.returncode != 1 or "AssertionError" not in r.stderr:
            probs.append(f"erratum {cid}: its probe does not reproduce the defect (exit {r.returncode}, "
                         f"{(r.stderr.strip().splitlines() or [''])[-1][:80]!r})")
    return probs


def rubric(contract: dict) -> dict:
    return {"id": RUBRIC_ID, "threshold": THRESHOLD,
            "criteria": [{"id": c["id"], "question": c["text"]} for c in contract["criteria"]]}


def templates(item: dict, key: str) -> dict[str, Any]:
    """The first run's prompts for this item, with arm B's head replaced by verdict@2's."""
    t = paired.templates(item, key)
    body = t["defender"].split("\n\n", 1)[1]
    return {**t, "armB": ARM_B_HEAD.replace("{ITEM}", key) + "\n\n" + body}


def _block(text: str, version: str) -> str:
    return text[text.index(f"// judge-contract:start {version}"):text.index("// judge-contract:end")]


def _old_trees() -> set[str]:
    """Every file body the first run (and the tribunal calibration it reused) ever staged."""
    out = set()
    for judge in ("paired", "tribunal"):
        for p in (calibration.FIXTURES / judge / "cases").rglob("*"):
            if p.is_file() and "tree" in p.parts:
                out.add(p.read_text(encoding="utf-8"))
    return out


def check() -> list[str]:
    probs = []
    its = items()
    if len(its) != N_ITEMS:
        probs.append(f"{len(its)} items, the design says {N_ITEMS}")
    exp = [i["expected"] for i in its]
    for o in calibration.OUTCOMES:
        if exp.count(o) / max(len(exp), 1) > 0.5:
            probs.append(f"known-{o} is more than half the items")
    old = _old_trees()
    for i in its:
        cid = i["id"].split("/", 1)[1]
        contract = calibration.load_json(i["dir"] / "contract.json")
        orc = calibration.load_json(i["oracle"])
        tree = oracles._tree_of(i["dir"] / "tree")
        if (i["dir"] / "fix.diff").read_text(encoding="utf-8") != oracles.udiff(orc["base"], tree):
            probs.append(f"{cid}: fix.diff is not the diff of the oracle's base and the staged tree")
        if sorted(orc["probes"]) != sorted(c["id"] for c in contract["criteria"]):
            probs.append(f"{cid}: probes do not cover exactly the contract's criteria")
            continue
        truth, codes = oracles.tribunal_truth(tree, orc["probes"])
        if truth != i["native"] or paired.OUTCOME_OF[truth] != i["expected"]:
            probs.append(f"{cid}: the probes say {truth} {codes}, answers.json says {i['native']}/{i['expected']}")
        if any(needle in body for body in tree.values() for needle in ("EXPECTED", "known-", "nativeExpected")):
            probs.append(f"{cid}: a staged file names the answer")
        if any(body in old for body in tree.values()):
            probs.append(f"{cid}: a staged file is one the first run already used")
        t = templates(i, "kX")
        if paired.js_verifier(t, "/s/tree", "D", "C") != prompts.verifier_prompt(contract, Path("/s/tree"), "D", "C"):
            probs.append(f"{cid}: the verifier's parts do not reassemble prompts.verifier_prompt")
        if paired.js_adjudicator(t, "D", "C", "V") != prompts.adjudicator_prompt(contract, "D", "C", "V"):
            probs.append(f"{cid}: the adjudicator's parts do not reassemble prompts.adjudicator_prompt")
        if TREE not in t["defender"] or TREE not in t["armB"] or "andon-wire@2" not in t["armB"]:
            probs.append(f"{cid}: a prompt does not carry the tree placeholder or the rubric")
        if any(w in t["armB"] for w in ("nativeExpected", "answers", "expected")):
            probs.append(f"{cid}: arm B's prompt names the answer")
    canon = (HERE.parent / "judge-contract" / "verdict.inline.js").read_text(encoding="utf-8")
    if _block(canon, "verdict@2") != _block(WORKFLOW.read_text(encoding="utf-8"), "verdict@2"):
        probs.append("paired_v2_workflow.js's verdict@2 block differs from tools/judge-contract/verdict.inline.js")
    res = SET / "results"
    if (res / "run.json").is_file():
        errata = calibration.load_json(ERRATA) if ERRATA.is_file() else None
        derived = [("score.json", None)] + ([("score-corrected.json", errata)] if errata else [])
        for name, err in derived:
            try:
                again = score(calibration.load_json(res / "run.json"), calibration.load_json(res / "map.json"), err)
            except ValueError as exc:
                probs.append(f"the committed run does not score: {exc}")
                continue
            if not (res / name).is_file() or again != calibration.load_json(res / name):
                probs.append(f"results/{name} differs from the score recomputed from results/run.json")
        if errata:
            probs += check_errata(errata)
    return probs


def stage(dest: Path, out: Path, map_file: Path) -> int:
    """paired.stage's layout for this set: one tree per (item, repeat, arm), prompts beside it."""
    roles = dest.parent / f"{dest.name}-roles"
    for d in (dest, roles):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    salt = hashlib.sha256(dest.as_posix().encode()).hexdigest()[:8]
    keys, mapping = [], {}
    for i in items():
        key = "w" + hashlib.sha256(f"{salt}:{i['id']}".encode()).hexdigest()[:8]
        mapping[key] = i["id"]
        keys.append(key)
        t = templates(i, key)
        for r in range(1, REPEATS + 1):
            for arm in ("a", "b"):
                run = f"{key}-{r}{arm}"
                tree = dest / run / "tree"
                shutil.copytree(i["dir"] / "tree", tree)
                rd = roles / run
                rd.mkdir()
                files = ({"judge": t["armB"]} if arm == "b" else {
                    "defender": t["defender"], "challenger": t["challenger"],
                    "verifier-head": t["verifierHead"] + "\n\n" + t["contractBlock"],
                    "adjudicator-head": t["adjudicatorHead"] + "\n\n" + t["contractBlock"]})
                for name, text in files.items():
                    (rd / f"{name}.txt").write_text(text.replace(TREE, tree.as_posix()), encoding="utf-8")
    out.write_text(json.dumps({"rolesRoot": roles.as_posix(), "repeats": REPEATS, "keys": keys}) + "\n", encoding="utf-8")
    map_file.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    print(f"staged {len(keys)} items x {REPEATS} repeats x 2 arms under {dest.as_posix()}; args {out.as_posix()}")
    return 0


def outcome_b(report: Any, contract: dict, key: str) -> tuple[str, dict]:
    v = calibration.judge_contract.decide(report, rubric(contract), item=key)
    return v["outcome"], v


def score(raw: dict, mapping: dict[str, str], errata: dict | None = None) -> dict:
    by_id = {i["id"]: i for i in items(errata)}
    per_item: dict[str, dict] = {}
    for run in raw["runs"]:
        iid = mapping[run["key"]]
        it = by_id[iid]
        rec = per_item.setdefault(iid, {"expected": it["expected"], "a": [], "b": [], "bVerdicts": []})
        if run["arm"] == "a":
            rec["a"].append(paired.outcome_a(run.get("adjudicator")))
        else:
            o, v = outcome_b(run.get("report"), calibration.load_json(it["dir"] / "contract.json"), run["key"])
            rec["b"].append(o)
            rec["bVerdicts"].append(v)
    probs = [f"{iid}: {len(r['a'])} arm-A and {len(r['b'])} arm-B runs, want {REPEATS} each"
             for iid, r in per_item.items() if len(r["a"]) != REPEATS or len(r["b"]) != REPEATS]
    if len(per_item) != len(by_id) or probs:
        raise ValueError("incomplete run: " + "; ".join(probs or [f"{len(per_item)}/{len(by_id)} items"]))
    out: dict[str, Any] = {"items": {}, "arms": {}}
    for arm in ("a", "b"):
        exp = {iid: r["expected"] for iid, r in per_item.items()}
        got = {iid: paired.majority(r[arm]) for iid, r in per_item.items()}
        m = calibration.metrics(calibration.confusion(exp, got))
        runs_exp = {f"{iid}#{k}": r["expected"] for iid, r in per_item.items() for k in range(REPEATS)}
        runs_got = {f"{iid}#{k}": r[arm][k] for iid, r in per_item.items() for k in range(REPEATS)}
        out["arms"][arm] = {"items": m, "record": calibration.derive_record(m, 0.8),
                            "runs": calibration.metrics(calibration.confusion(runs_exp, runs_got)),
                            "unanimousItems": sum(1 for r in per_item.values() if len(set(r[arm])) == 1)}
    b_only = sum(1 for r in per_item.values() if paired.majority(r["a"]) != r["expected"] == paired.majority(r["b"]))
    a_only = sum(1 for r in per_item.values() if paired.majority(r["b"]) != r["expected"] == paired.majority(r["a"]))
    out["discordant"] = {"onlyTribunalRight": a_only, "onlyContractJudgeRight": b_only,
                         "mcnemarExactP": paired.binom_two_sided(a_only, b_only)}
    A, B = out["arms"]["a"], out["arms"]["b"]
    keep = (B["items"]["falsePasses"] > A["items"]["falsePasses"]
            or B["record"]["agreement"] < A["record"]["agreement"])
    if errata:  # only a corrected score names its errata; the sealed score.json stays as committed
        out["keyErrata"] = sorted(errata)
    out["decision"] = {"rule": DECISION_RULE, "keepTribunal": keep,
                       "falsePasses": {"tribunal": A["items"]["falsePasses"], "contractJudge": B["items"]["falsePasses"]},
                       "record": {"tribunal": A["record"]["agreement"], "contractJudge": B["record"]["agreement"]}}
    # How often arm B used the new per-criterion undecidable, and how its abstains split: an
    # undecidable:<ids> abstain is verdict@2's; any other is a whole-item one, as under verdict@1.
    used = [v for r in per_item.values() for v in r["bVerdicts"] if any(c["pass"] is None for c in v["criteria"])]
    out["undecidableUse"] = {"runsWithAnUndecidableCriterion": len(used),
                             "ofWhichFail": sum(1 for v in used if v["outcome"] == "fail"),
                             "ofWhichAbstain": sum(1 for v in used if v["outcome"] == "abstain")}
    for iid, r in sorted(per_item.items()):
        out["items"][iid] = {"expected": r["expected"], "tribunal": r["a"], "contractJudge": r["b"],
                             "tribunalMajority": paired.majority(r["a"]), "contractJudgeMajority": paired.majority(r["b"]),
                             "contractJudgeAbstainReasons": sorted({v["abstainReason"] for v in r["bVerdicts"]
                                                                    if v["abstainReason"]})}
    return out


# ---------------------------------------------------------------------------- selftest

def _fake_raw(a_mode: str, b_mode: str) -> tuple[dict, dict]:
    """Fabricated runs. 'right' answers every item correctly (arm B through verdict@2's
    per-criterion nulls, exactly as the probes decide each criterion); 'v1' is arm B answering
    as a verdict@1 judge would, abstaining on the whole item whenever any criterion is
    undecidable; 'pass' always passes; 'cop-out' marks every criterion of every item undecidable."""
    word = {"pass": "green", "fail": "red", "abstain": "unknown"}
    mapping, runs = {}, []
    for n, it in enumerate(items()):
        key = f"w{n:02d}"
        mapping[key] = it["id"]
        orc = calibration.load_json(it["oracle"])
        _, codes = oracles.tribunal_truth(oracles._tree_of(it["dir"] / "tree"), orc["probes"])
        contract = calibration.load_json(it["dir"] / "contract.json")
        for _ in range(REPEATS):
            a = it["expected"] if a_mode == "right" else "pass"
            runs.append({"key": key, "arm": "a", "adjudicator": f"Overall: {word[a]}"})
            crit = []
            for c in contract["criteria"]:
                code = codes[c["id"]]
                if b_mode == "pass":
                    code = 0
                if b_mode == "cop-out" or code == 3:
                    crit.append({"id": c["id"], "score": None, "pass": None, "evidence": "needs production"})
                else:
                    crit.append({"id": c["id"], "score": 0.9 if code == 0 else 0.1, "pass": code == 0, "evidence": "probe"})
            report = {"item": key, "criteria": crit, "abstain": False, "abstainReason": None}
            if b_mode == "v1" and any(x["pass"] is None for x in crit):
                report = {"item": key, "criteria": [], "abstain": True, "abstainReason": "production only"}
            runs.append({"key": key, "arm": "b", "report": report})
    return {"runs": runs}, mapping


def selftest() -> int:
    bad = []
    rep = score(*_fake_raw("right", "right"))
    if rep["decision"]["keepTribunal"]:
        bad.append("two perfect arms kept the tribunal (a tie must collapse it)")
    if rep["arms"]["b"]["items"]["agreement"] != 1.0:
        bad.append("a verdict@2 judge reporting exactly what the probes show did not agree on every item")
    if rep["undecidableUse"]["ofWhichFail"] != 4 * REPEATS:
        bad.append(f"the four fail-beside-undecidable items did not decide fail: {rep['undecidableUse']}")
    rep = score(*_fake_raw("right", "v1"))
    if not rep["decision"]["keepTribunal"] or rep["arms"]["b"]["items"]["falsePasses"] != 0:
        bad.append("a verdict@1-shaped judge (whole-item abstain) did not lose on the fail-beside-undecidable items")
    rep = score(*_fake_raw("right", "pass"))
    if not rep["decision"]["keepTribunal"] or rep["arms"]["b"]["items"]["falsePasses"] == 0:
        bad.append("a contract judge that passes everything did not keep the tribunal")
    rep = score(*_fake_raw("right", "cop-out"))
    if not rep["decision"]["keepTribunal"] or rep["arms"]["b"]["items"]["falsePasses"] != 0:
        bad.append("a contract judge that marks everything undecidable (no false pass) did not keep the tribunal")
    rep = score(*_fake_raw("pass", "right"))
    if rep["decision"]["keepTribunal"]:
        bad.append("a tribunal that passes everything was kept over a perfect contract judge")
    raw, mp = _fake_raw("right", "right")
    raw["runs"].pop()
    try:
        score(raw, mp)
        bad.append("an incomplete run was scored")
    except ValueError:
        pass
    # check_errata refuses an erratum that reproduces nothing or corrects a key the seal never held.
    if ERRATA.is_file():
        real = calibration.load_json(ERRATA)
        cid, e = next(iter(real.items()))
        planted = {
            "a probe that exits 1 without an assertion": {cid: {**e, "probe": "raise SystemExit(1)"}},
            "a probe that passes the staged tree": {cid: {**e, "probe": "pass"}},
            "a sealed key answers.json does not hold": {cid: {**e, "sealed": {"expected": "pass", "nativeExpected": "green"}}},
            "an erratum for no sealed item": {"v2-99": e},
        }
        for name, errata in planted.items():
            if not check_errata(errata):
                bad.append(f"check_errata accepted {name}")
        if check_errata(real):
            bad.append(f"check_errata refused the committed errata: {check_errata(real)}")
    for b in bad:
        print(f"FAIL {b}")
    print(f"paired-v2 selftest: {len(bad)} failure(s)")
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
    s = sub.add_parser("collect")
    s.add_argument("--run-dir", type=Path, required=True)
    s.add_argument("--map", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--raw", type=Path, required=True)
    s.add_argument("--map", type=Path, required=True)
    s.add_argument("--write", type=Path)
    s.add_argument("--errata", type=Path, help="score under the corrected keys in this key-errata.json")
    a = p.parse_args(argv)
    if a.cmd == "check":
        probs = check()
        for x in probs:
            print(f"PAIRED-V2 {x}")
        print(f"paired-v2 measurement: {len(items())} items, {len(probs)} problem(s)")
        return 1 if probs else 0
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "stage":
        return stage(a.dest, a.out, a.map)
    if a.cmd == "collect":
        raw = paired.collect(a.run_dir, calibration.load_json(a.map))
        a.out.write_text(json.dumps(raw, indent=1) + "\n", encoding="utf-8")
        print(f"collected {len(raw['runs'])} runs into {a.out.as_posix()}")
        return 0
    rep = score(calibration.load_json(a.raw), calibration.load_json(a.map),
                calibration.load_json(a.errata) if a.errata else None)
    if a.write:
        a.write.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("decision", "discordant", "undecidableUse")}, indent=2))
    for arm, name in (("a", "tribunal"), ("b", "contract judge")):
        m = rep["arms"][arm]["items"]
        print(f"{name}: per-item agreement {m['agreement']:.2f}, false passes {m['falsePasses']}, "
              f"record {rep['arms'][arm]['record']['agreement']}, per-run agreement {rep['arms'][arm]['runs']['agreement']:.2f}, "
              f"unanimous items {rep['arms'][arm]['unanimousItems']}/{N_ITEMS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
