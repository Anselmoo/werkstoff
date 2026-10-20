#!/usr/bin/env python3
"""Known-answer calibration for the judges docs/plugin-authoring/references/judge-contract.md
marks kept-unmeasured: the arbeitsplan candidate-referee, the matrize decode-referee and
the andon tribunal.

A judge is only as good as its measured agreement with answers a command established. This
file holds the part that must not be eyeballed:

  * the mapping from each judge's native verdict to pass / fail / abstain, which mirrors
    what the calling workflow actually ACTS on (not what the agent's prose says);
  * the confusion matrix and the five figures a record is derived from;
  * the derivation of the rubric's ``calibration`` record ({sealed, agreement, floor}) and
    the refusal to derive one from an incomplete run;
  * the stale-record and drift checks CI runs.

The record's ``agreement`` is the WEAKEST of five figures, not the plain fraction of
matches: overall agreement, one minus the false-pass rate, and the precision and recall
of the pass and fail classes. ``judge_contract.is_calibrated`` reads only that one
number against the floor, and the plain fraction can be cleared by a judge that passes
everything when most cases are passes (judge-contract.md section 4 says so). Taking the
minimum makes the existing gate carry the precision requirement without changing the
vendored contract.

Usage:
    calibration.py selftest
    calibration.py check [--judge J]         CI gate: fixtures, oracles, drift, stale, records
    calibration.py report [--judge J]        agreement per judge, from committed results
    calibration.py stage --judge J --phase tune|sealed --dest DIR --map FILE
    calibration.py score --judge J --phase tune|sealed [--results FILE]
    calibration.py collect --judge J --phase P --raw-dir DIR --date D   raw outputs -> results/P.json
    calibration.py tribunal-prompt --case C --stage-dir D --role verifier|adjudicator ...
    calibration.py record --judge J          write the sealed record into rubric.json

Exit 0 ok; 1 a finding; 2 could not run. STDLIB ONLY. Python >= 3.11.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

MIN_PYTHON = (3, 11)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURES = ROOT / "test" / "judge-calibration"
JUDGES = ("referee", "decode", "tribunal")
OUTCOMES = ("pass", "fail", "abstain")



def _load_judge_contract():
    """The canonical tools/judge-contract/judge_contract.py: its is_calibrated() and check_rubric()
    are the gate this file derives records for, so they are loaded, never re-implemented."""
    spec = importlib.util.spec_from_file_location("judge_contract", ROOT / "tools" / "judge-contract" / "judge_contract.py")
    if spec is None or spec.loader is None:
        raise SystemExit("ERROR: cannot load tools/judge-contract/judge_contract.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


judge_contract = _load_judge_contract()


# --------------------------------------------------------------------------------------
# Native verdict -> pass / fail / abstain
# --------------------------------------------------------------------------------------

def map_referee(native: Any) -> tuple[str, dict]:
    """arbeitsplan candidate-referee, as ``workflows/run.js`` acts on it.

    A candidate lands only when ``LANDS.has(verdict)`` (``accepted`` alone) AND
    ``perCriterion`` is non-empty with at least ONE met criterion (``withEvidence``). So an
    ``accepted`` verdict with an unmet criterion still lands. ``strict`` records whether
    every criterion was met, which is what the agent's own definition of ``accepted`` says.
    ``cannot_judge`` and a dead referee (no report) are an abstain: the workflow emits
    ``doubt`` / ``unmeasured`` for them and lands nothing.
    """
    if not isinstance(native, dict) or native.get("verdict") not in (
            "accepted", "accepted_different_approach", "rejected", "cannot_judge"):
        return "abstain", {"why": "no-report"}
    verdict = native["verdict"]
    per = native.get("perCriterion")
    per = per if isinstance(per, list) else []
    met = [bool(p.get("met")) for p in per if isinstance(p, dict)]
    extras = {"native": verdict, "strictAllMet": bool(met) and all(met),
              "differentApproach": verdict == "accepted_different_approach"}
    if verdict == "cannot_judge":
        return "abstain", extras
    if verdict == "accepted" and any(met):
        extras["gateGap"] = not all(met)
        return "pass", extras
    return "fail", extras


def map_decode(native: Any) -> tuple[str, dict]:
    """matrize decode-referee, as ``workflows/decode.js`` acts on it: ``confirmed`` is an
    allowlist of ``reproduced`` alone. ``cannot_reproduce`` is an abstain; a referee that
    returned nothing never confirms a card, and is likewise an abstain."""
    verdict = native.get("verdict") if isinstance(native, dict) else None
    table = {"reproduced": "pass", "reproduced_different_relation": "fail",
             "not_reproduced": "fail", "cannot_reproduce": "abstain"}
    if verdict not in table:
        return "abstain", {"why": "no-report"}
    return table[verdict], {"native": verdict}


def map_tribunal(native: Any) -> tuple[str, dict]:
    """andon tribunal: the adjudicator's overall wire verdict. green only if every criterion
    passed, red if any failed, unknown if the only non-passes are ``neither``
    (tribunal-protocol.md, Verdict mapping)."""
    overall = native.get("overall") if isinstance(native, dict) else None
    table = {"green": "pass", "red": "fail", "unknown": "abstain"}
    if overall not in table:
        return "abstain", {"why": "no-report"}
    return table[overall], {"native": overall}


MAPPERS = {"referee": map_referee, "decode": map_decode, "tribunal": map_tribunal}

# The exact native verdict each case is expected to produce, per judge. Agreement is
# measured on the mapped outcome; the native match is reported beside it.
NATIVE_OF = {
    "referee": {"pass": "accepted", "fail": "rejected", "abstain": "cannot_judge"},
    "decode": {"pass": "reproduced", "abstain": "cannot_reproduce"},
    "tribunal": {"pass": "green", "fail": "red", "abstain": "unknown"},
}


# --------------------------------------------------------------------------------------
# Confusion matrix, metrics, record
# --------------------------------------------------------------------------------------

def confusion(expected: dict[str, str], got: dict[str, str]) -> dict[str, dict[str, int]]:
    """rows = expected outcome, columns = the judge's mapped outcome."""
    m: dict[str, dict[str, int]] = {e: dict.fromkeys(OUTCOMES, 0) for e in OUTCOMES}
    for cid, e in expected.items():
        m[e][got[cid]] += 1
    return m


def _ratio(num: int, den: int) -> float:
    """num/den, with an empty denominator counted as 0.0: a class the judge never
    predicted has no precision, and 'no evidence' must not read as 'perfect'."""
    return num / den if den else 0.0


def metrics(conf: dict[str, dict[str, int]]) -> dict[str, Any]:
    n = sum(sum(r.values()) for r in conf.values())
    hits = sum(conf[o][o] for o in OUTCOMES)
    exp = {o: sum(conf[o].values()) for o in OUTCOMES}
    got = {o: sum(conf[e][o] for e in OUTCOMES) for o in OUTCOMES}
    not_pass = n - exp["pass"]
    false_pass = got["pass"] - conf["pass"]["pass"]
    false_fail = conf["pass"]["fail"]
    out = {
        "n": n,
        "agreement": _ratio(hits, n),
        "falsePasses": false_pass,
        "falsePassRate": _ratio(false_pass, not_pass),
        "falseFails": false_fail,
        "falseFailRate": _ratio(false_fail, exp["pass"]),
        "precision": {o: _ratio(conf[o][o], got[o]) for o in OUTCOMES},
        "recall": {o: _ratio(conf[o][o], exp[o]) for o in OUTCOMES},
    }
    out["terms"] = {"agreement": out["agreement"], "no-false-pass": 1.0 - out["falsePassRate"],
                    "precision-pass": out["precision"]["pass"], "precision-fail": out["precision"]["fail"],
                    "recall-pass": out["recall"]["pass"], "recall-fail": out["recall"]["fail"]}
    out["weakestTerm"] = min(out["terms"], key=lambda k: out["terms"][k])
    out["weakest"] = out["terms"][out["weakestTerm"]]
    return out


def derive_record(m: dict[str, Any], floor: float) -> dict[str, Any]:
    """The rubric's ``calibration`` block. ``agreement`` is the weakest of the five figures
    (see the module docstring), rounded DOWN to four places so rounding can never lift a
    figure over the floor."""
    return {"sealed": m["n"], "agreement": int(m["weakest"] * 10000) / 10000, "floor": floor}


# --------------------------------------------------------------------------------------
# Fixtures and results
# --------------------------------------------------------------------------------------

def jdir(judge: str) -> Path:
    return FIXTURES / judge


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: cannot read {path.as_posix()}: {exc}") from exc


def load_spec(judge: str) -> dict:
    return load_json(jdir(judge) / "judge.json")


def load_answers(judge: str) -> dict[str, dict]:
    return load_json(jdir(judge) / "answers.json")


def cases_in(answers: dict[str, dict], phase: str) -> list[str]:
    return sorted(c for c, a in answers.items() if a["split"] == phase)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instrument(judge: str) -> dict[str, str]:
    """What the measurement depends on: the judge's own definition files and the prompt
    template. A record taken before any of these changed no longer describes the judge."""
    spec = load_spec(judge)
    out = {p: sha256_file(ROOT / p) for p in spec["instrumentFiles"]}
    import prompts  # local module, imported late so selftests of this file stand alone
    out["prompt-template"] = prompts.template_sha(judge)
    return out


def read_results(judge: str, phase: str, path: Path | None = None) -> dict:
    return load_json(path or jdir(judge) / "results" / f"{phase}.json")


def score_results(judge: str, phase: str, results: dict) -> dict[str, Any]:
    """Score ``results`` ({meta, results:[{case, native}]}) against the committed answers.
    Every case in the phase must have exactly one result: a missing result is a run that
    did not happen, and is refused rather than counted as an abstain."""
    answers = load_answers(judge)
    want = cases_in(answers, phase)
    by_case: dict[str, Any] = {}
    for r in results.get("results", []):
        if r["case"] in by_case:
            raise ValueError(f"{judge} {phase}: case {r['case']} has two results")
        by_case[r["case"]] = r
    missing = [c for c in want if c not in by_case]
    extra = sorted(set(by_case) - set(want))
    if missing or extra:
        raise ValueError(f"{judge} {phase}: results are not the {len(want)} {phase} cases "
                         f"(missing {missing}, unexpected {extra})")
    mapper = MAPPERS[judge]
    expected = {c: answers[c]["expected"] for c in want}
    got: dict[str, str] = {}
    extras: dict[str, dict] = {}
    for c in want:
        got[c], extras[c] = mapper(by_case[c].get("native"))
    conf = confusion(expected, got)
    m = metrics(conf)
    exact_native = sum(1 for c in want if extras[c].get("native") == (
        answers[c].get("nativeExpected") or NATIVE_OF[judge].get(expected[c])))
    return {"judge": judge, "phase": phase, "confusion": conf, "metrics": m, "cases": {
        c: {"expected": expected[c], "got": got[c], **extras[c]} for c in want},
        "nativeExact": exact_native,
        "disagreements": [c for c in want if expected[c] != got[c]]}


# --------------------------------------------------------------------------------------
# Class balance of a fixture set (a set a constant judge can clear is not a calibration)
# --------------------------------------------------------------------------------------

MIN_PER_CLASS = {"pass": 3, "fail": 3, "abstain": 1}
MAX_SHARE = 0.5


def balance_problems(answers: dict[str, dict], phase: str) -> list[str]:
    ids = cases_in(answers, phase)
    probs = []
    for o in OUTCOMES:
        k = sum(1 for c in ids if answers[c]["expected"] == o)
        floor_k = MIN_PER_CLASS[o] if phase == "sealed" else 1
        if k < floor_k:
            probs.append(f"{phase}: {k} known-{o} cases, need at least {floor_k}")
        if ids and k / len(ids) > MAX_SHARE:
            probs.append(f"{phase}: known-{o} is {k}/{len(ids)} of the set; a judge that always says {o} "
                         f"would clear {k / len(ids):.0%}")
    return probs


# --------------------------------------------------------------------------------------
# Stage: one case per directory, no answer key anywhere inside it
# --------------------------------------------------------------------------------------

def opaque(judge: str, case: str, salt: str) -> str:
    return "k" + hashlib.sha256(f"{salt}:{judge}:{case}".encode()).hexdigest()[:8]


def stage(judge: str, phase: str, dest: Path, map_file: Path) -> int:
    import prompts
    answers = load_answers(judge)
    ids = cases_in(answers, phase)
    salt = sha256_text(str(dest))[:8]
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    mapping = {}
    for cid in ids:
        key = opaque(judge, cid, salt)
        cdir = dest / key
        cdir.mkdir()
        mapping[key] = cid
        src = jdir(judge) / "cases" / cid
        if judge == "referee":
            case = load_json(src / "case.json")
            (cdir / "prompt.txt").write_text(prompts.referee_prompt(case), encoding="utf-8")
        elif judge == "decode":
            shutil.copytree(src / "ref", cdir / "ref")
            case = load_json(src / "case.json")
            (cdir / "prompt.txt").write_text(prompts.decode_prompt(case, (cdir / "ref").as_posix()), encoding="utf-8")
        else:
            shutil.copytree(src / "tree", cdir / "tree")
            contract = load_json(src / "contract.json")
            for role, text in prompts.tribunal_prompts(contract, src, cdir / "tree").items():
                (cdir / f"{role}.txt").write_text(text, encoding="utf-8")
    map_file.parent.mkdir(parents=True, exist_ok=True)
    map_file.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    print(f"staged {len(ids)} {judge} {phase} case(s) under {dest.as_posix()} (key map: {map_file.as_posix()})")
    return 0


# --------------------------------------------------------------------------------------
# check (CI)
# --------------------------------------------------------------------------------------

def check_judge(judge: str) -> list[str]:
    import oracles
    import prompts
    probs: list[str] = []
    d = jdir(judge)
    for need in ("judge.json", "answers.json", "rubric.json"):
        if not (d / need).is_file():
            return [f"{judge}: {need} is missing"]
    spec, answers = load_spec(judge), load_answers(judge)
    rubric = load_json(d / "rubric.json")
    for e in judge_contract.check_rubric(rubric):
        probs.append(f"{judge}: rubric.json: {e}")
    on_disk = sorted(p.name for p in (d / "cases").iterdir() if p.is_dir())
    if on_disk != sorted(answers):
        probs.append(f"{judge}: cases on disk {on_disk} differ from answers.json {sorted(answers)}")
    for cid, a in answers.items():
        want = "sealed" if cid.startswith("sealed") else "tune"
        if a["split"] != want:
            probs.append(f"{judge}: {cid} is split {a['split']!r} but its name says {want}")
        if a["expected"] not in OUTCOMES:
            probs.append(f"{judge}: {cid} expects {a['expected']!r}")
    for phase in ("tune", "sealed"):
        probs += [f"{judge}: {p}" for p in balance_problems(answers, phase)]
    probs += [f"{judge}: {p}" for p in oracles.check_oracle(judge, answers)]
    probs += [f"{judge}: {p}" for p in prompts.check_templates(judge)]
    if rubric.get("calibration", {}).get("floor", spec["floor"]) != spec["floor"]:
        probs.append(f"{judge}: rubric floor differs from judge.json floor {spec['floor']}")
    sealed_file = d / "results" / "sealed.json"
    cal = rubric.get("calibration")
    if cal is None:
        if sealed_file.is_file():
            probs.append(f"{judge}: results/sealed.json exists but rubric.json has no calibration record; "
                         f"run 'calibration.py record --judge {judge}'")
        return probs
    if not sealed_file.is_file():
        probs.append(f"{judge}: rubric.json carries a calibration record but results/sealed.json is missing")
        return probs
    res = read_results(judge, "sealed")
    try:
        rep = score_results(judge, "sealed", res)
    except ValueError as exc:
        return probs + [f"{judge}: {exc}"]
    want_rec = derive_record(rep["metrics"], spec["floor"])
    if cal != want_rec:
        probs.append(f"{judge}: rubric record {cal} differs from the one recomputed from the committed "
                     f"results {want_rec}; records are derived, never edited")
    now = instrument(judge)
    then = res.get("meta", {}).get("instrument", {})
    stale = sorted(k for k in set(now) | set(then) if now.get(k) != then.get(k))
    if stale:
        probs.append(f"{judge}: the record is stale; these changed since it was measured: {stale}. "
                     f"Re-measure with a new sealed set, or remove the record")
    return probs


def cmd_check(judges: tuple[str, ...]) -> int:
    probs = []
    for j in judges:
        probs += check_judge(j)
    for p in probs:
        print(f"CAL {p}")
    print(f"judge calibration: {len(judges)} judge(s), {len(probs)} problem(s)")
    return 1 if probs else 0


def fmt_report(judge: str, phase: str, rep: dict) -> str:
    m, c = rep["metrics"], rep["confusion"]
    lines = [f"{judge} {phase}: n={m['n']}  agreement {m['agreement']:.2f}  "
             f"false passes {m['falsePasses']} (rate {m['falsePassRate']:.2f})  "
             f"false fails {m['falseFails']} (rate {m['falseFailRate']:.2f})",
             f"  precision pass {m['precision']['pass']:.2f} fail {m['precision']['fail']:.2f}   "
             f"recall pass {m['recall']['pass']:.2f} fail {m['recall']['fail']:.2f} abstain {m['recall']['abstain']:.2f}",
             "  expected\\got   pass fail abstain"]
    for e in OUTCOMES:
        lines.append(f"  {e:<13} {c[e]['pass']:>4} {c[e]['fail']:>4} {c[e]['abstain']:>7}")
    lines.append(f"  native-exact {rep['nativeExact']}/{m['n']}   weakest figure {m['weakest']:.4f}")
    if rep["disagreements"]:
        lines.append("  disagreements: " + ", ".join(
            f"{k} (expected {rep['cases'][k]['expected']}, got {rep['cases'][k]['got']})" for k in rep["disagreements"]))
    return "\n".join(lines)


def cmd_report(judges: tuple[str, ...]) -> int:
    for j in judges:
        spec = load_spec(j)
        rubric = load_json(jdir(j) / "rubric.json")
        for phase in ("tune", "sealed"):
            f = jdir(j) / "results" / f"{phase}.json"
            if not f.is_file():
                print(f"{j} {phase}: not measured")
                continue
            print(fmt_report(j, phase, score_results(j, phase, read_results(j, phase))))
        cal = rubric.get("calibration")
        state = ("calibrated" if judge_contract.is_calibrated(rubric) else "below floor") if cal else "no record"
        print(f"{j}: floor {spec['floor']}, record {cal}, {state}\n")
    return 0


def cmd_record(judge: str, force: bool) -> int:
    spec = load_spec(judge)
    path = jdir(judge) / "rubric.json"
    rubric = load_json(path)
    if "calibration" in rubric and not force:
        print(f"ERROR: {judge} already has a calibration record. The sealed set is measured once; a "
              f"second record needs --remeasure and a new sealed set.", file=sys.stderr)
        return 2
    res = read_results(judge, "sealed")
    rep = score_results(judge, "sealed", res)
    res.setdefault("meta", {})["instrument"] = res["meta"].get("instrument") or instrument(judge)
    rubric["calibration"] = derive_record(rep["metrics"], spec["floor"])
    path.write_text(json.dumps(rubric, indent=2) + "\n", encoding="utf-8")
    print(fmt_report(judge, "sealed", rep))
    print(f"wrote {rubric['calibration']} to {path.as_posix()}; calibrated: {judge_contract.is_calibrated(rubric)}")
    return 0


# --------------------------------------------------------------------------------------
# collect: raw agent outputs (one verbatim text file per case) -> results/<phase>.json
# --------------------------------------------------------------------------------------

ADJUDICATOR_OVERALL = re.compile(r"overall[^a-z]{0,12}(green|red|unknown)", re.I)


def parse_native(judge: str, raw: str) -> Any:
    """The judge's report from its raw text, or None when there is none to read. A report
    that cannot be parsed is a dead judge (an abstain), never a guess at what it meant."""
    if judge == "tribunal":
        hits = ADJUDICATOR_OVERALL.findall(raw)
        return {"overall": hits[-1].lower()} if hits else None
    want = "cardId" if judge == "decode" else "candidateId"
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", raw):
        try:
            obj, _ = dec.raw_decode(raw[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and want in obj and "verdict" in obj:
            return obj
    return None


def collect(judge: str, phase: str, raw_dir: Path, note: str, run_date: str) -> int:
    answers = load_answers(judge)
    out = []
    for cid in cases_in(answers, phase):
        f = raw_dir / f"{cid}.txt"
        if not f.is_file():
            print(f"ERROR: no raw output for {cid} at {f.as_posix()}; a run with holes is not recorded", file=sys.stderr)
            return 2
        raw = f.read_text(encoding="utf-8")
        out.append({"case": cid, "native": parse_native(judge, raw), "raw": raw})
    spec = load_spec(judge)
    results = {"meta": {"judge": judge, "phase": phase, "agentType": spec["agentType"], "runDate": run_date,
                        "delivery": spec["delivery"], "note": note, "instrument": instrument(judge)},
               "results": out}
    dest = jdir(judge) / "results" / f"{phase}.json"
    if phase == "sealed" and dest.exists():
        print(f"ERROR: {dest.as_posix()} exists. The sealed set is measured once.", file=sys.stderr)
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(fmt_report(judge, phase, score_results(judge, phase, results)))
    return 0


def tribunal_prompt(case_id: str, stage_dir: Path, role: str, outs: dict[str, Path]) -> int:
    import prompts
    contract = load_json(jdir("tribunal") / "cases" / case_id / "contract.json")
    text = {r: p.read_text(encoding="utf-8") for r, p in outs.items()}
    tree = stage_dir / "tree"
    if role == "verifier":
        body = prompts.verifier_prompt(contract, tree, text["defender"], text["challenger"])
    else:
        body = prompts.adjudicator_prompt(contract, text["defender"], text["challenger"], text["verifier"])
    (stage_dir / f"{role}.txt").write_text(body, encoding="utf-8")
    print(f"wrote {(stage_dir / f'{role}.txt').as_posix()}")
    return 0


# --------------------------------------------------------------------------------------
# Selftest: the scorer against fabricated judges whose right answer is known
# --------------------------------------------------------------------------------------

def _fab(expected: list[str], got: list[str]) -> dict[str, Any]:
    exp = {f"c{i}": e for i, e in enumerate(expected)}
    g = {f"c{i}": o for i, o in enumerate(got)}
    return metrics(confusion(exp, g))


BALANCED = ["pass"] * 4 + ["fail"] * 4 + ["abstain"] * 2


def _fabricated(judge: str, behave: str) -> dict:
    """A results file for ``judge`` whose native verdicts follow ``behave`` and nothing else:
    'oracle' gives every case its expected native verdict; 'pass', 'fail' and 'dead' give one answer."""
    answers = load_answers(judge)
    out = []
    for cid in cases_in(answers, "sealed"):
        a = answers[cid]
        if behave == "oracle":
            word = a.get("nativeExpected") or NATIVE_OF[judge][a["expected"]]
        elif behave == "pass":
            word = NATIVE_OF[judge]["pass"]
        elif behave == "fail":
            word = NATIVE_OF[judge].get("fail", "not_reproduced")
        else:
            word = None
        if word is None:
            native = None
        elif judge == "tribunal":
            native = {"overall": word}
        else:
            native = {"verdict": word, "perCriterion": [{"id": "a1", "met": word == "accepted"}]}
        out.append({"case": cid, "native": native})
    return {"meta": {}, "results": out}


def _selftest_on_fixtures() -> list[str]:
    """Fabricated judges scored against the committed fixtures: a perfect one clears, a constant
    one never does, a dead one never does, and a run with a hole is refused. This is the scorer
    calibrated on transcripts whose right answer is known, before it grades a real run."""
    import oracles
    bad = []
    for judge in JUDGES:
        floor = load_spec(judge)["floor"]
        perfect = score_results(judge, "sealed", _fabricated(judge, "oracle"))
        if derive_record(perfect["metrics"], floor)["agreement"] < floor or perfect["disagreements"]:
            bad.append(f"{judge}: a judge that returns every expected verdict did not clear the floor")
        for behave in ("pass", "fail", "dead"):
            rep = score_results(judge, "sealed", _fabricated(judge, behave))
            if derive_record(rep["metrics"], floor)["agreement"] >= floor:
                bad.append(f"{judge}: a judge that always answers {behave!r} cleared the floor")
        holed = _fabricated(judge, "oracle")
        holed["results"].pop()
        try:
            score_results(judge, "sealed", holed)
            bad.append(f"{judge}: a run with a missing case was scored")
        except ValueError:
            pass
        twice = _fabricated(judge, "oracle")
        twice["results"].append(twice["results"][0])
        try:
            score_results(judge, "sealed", twice)
            bad.append(f"{judge}: a case with two results was scored")
        except ValueError:
            pass
    bad += [f"oracle sabotage: {p}" for p in oracles.selftest_problems()]
    return bad


def selftest() -> int:
    bad: list[str] = []

    def expect(name: str, cond: bool) -> None:
        if not cond:
            bad.append(name)

    perfect = _fab(BALANCED, BALANCED)
    expect("a perfect judge scores 1.0", perfect["weakest"] == 1.0)
    expect("a perfect judge clears floor 0.8", derive_record(perfect, 0.8)["agreement"] >= 0.8)
    # The judge that passes everything: plain agreement 0.4, but it must not clear anything.
    all_pass = _fab(BALANCED, ["pass"] * 10)
    expect("pass-everything has falsePasses 6", all_pass["falsePasses"] == 6)
    expect("pass-everything is nowhere near the floor", all_pass["weakest"] < 0.5)
    all_fail = _fab(BALANCED, ["fail"] * 10)
    expect("fail-everything has recall(pass) 0", all_fail["recall"]["pass"] == 0.0)
    expect("fail-everything does not clear 0.8", all_fail["weakest"] < 0.8)
    all_abstain = _fab(BALANCED, ["abstain"] * 10)
    expect("abstain-everything scores 0 on pass precision (empty prediction is not perfect)",
           all_abstain["precision"]["pass"] == 0.0 and all_abstain["weakest"] == 0.0)
    # Each of the six terms must be able to be the one that decides: a term no matrix can
    # make the weakest is a branch nothing tests. (Found by search, then checked by hand.)
    isolated = {
        "agreement": [[200, 20, 1], [0, 200, 60], [60, 0, 20]],
        "no-false-pass": [[200, 2, 60], [5, 5, 0], [20, 0, 1]],
        "precision-pass": [[20, 0, 2], [60, 200, 20], [0, 0, 20]],
        "precision-fail": [[200, 0, 1], [0, 1, 0], [20, 5, 1]],
        "recall-pass": [[1, 60, 0], [5, 60, 1], [2, 20, 1]],
        "recall-fail": [[5, 5, 60], [60, 1, 1], [0, 2, 60]],
    }
    for term, rows in isolated.items():
        conf = {e: dict(zip(OUTCOMES, row, strict=True)) for e, row in zip(OUTCOMES, rows, strict=True)}
        expect(f"the {term} term can be the weakest", metrics(conf)["weakestTerm"] == term)
    # One false pass among six non-pass cases: overall agreement 0.9 clears 0.8, but the
    # fail class lost one of its four (recall 3/4), pass precision is 4/5 and the false-pass
    # rate is 1/6. The weakest of those is 0.75: below the floor.
    one_fp = _fab(BALANCED, ["pass"] * 4 + ["pass"] + ["fail"] * 3 + ["abstain"] * 2)
    expect("overall 0.9 with one false pass", abs(one_fp["agreement"] - 0.9) < 1e-9 and one_fp["falsePasses"] == 1)
    expect("the weakest figure sees the false pass, not the 0.9",
           one_fp["weakest"] < one_fp["agreement"] and abs(one_fp["weakest"] - 0.75) < 1e-9)
    # An abstain on a known-abstain case is agreement; a fail on it is a disagreement.
    ab = _fab(BALANCED, ["pass"] * 4 + ["fail"] * 4 + ["fail"] * 2)
    expect("a fail on a known-abstain is a disagreement", abs(ab["agreement"] - 0.8) < 1e-9)
    # Rounding never lifts a figure over the floor.
    expect("rounding down", derive_record({"n": 10, "weakest": 0.79999}, 0.8)["agreement"] == 0.7999)
    rec = derive_record(perfect, 0.8)
    expect("a derived record is accepted by the contract", not judge_contract.check_rubric(
        {"id": "x-y@1", "threshold": 0.5, "criteria": [{"id": "a", "question": "q"}], "calibration": rec}))
    expect("a cleared record calibrates", judge_contract.is_calibrated({"calibration": rec}))
    expect("a missed record does not", not judge_contract.is_calibrated(
        {"calibration": derive_record(all_pass, 0.8)}))
    # Mappers against the workflows' real gates.
    expect("referee: accepted + one met lands", map_referee(
        {"verdict": "accepted", "perCriterion": [{"id": "a", "met": True}, {"id": "b", "met": False}]})[0] == "pass")
    expect("referee: that landing is flagged as a gate gap", map_referee(
        {"verdict": "accepted", "perCriterion": [{"id": "a", "met": True}, {"id": "b", "met": False}]})[1]["gateGap"])
    expect("referee: accepted with no criteria does not land", map_referee(
        {"verdict": "accepted", "perCriterion": []})[0] == "fail")
    expect("referee: accepted_different_approach is not in LANDS", map_referee(
        {"verdict": "accepted_different_approach", "perCriterion": [{"id": "a", "met": True}]})[0] == "fail")
    expect("referee: cannot_judge abstains", map_referee({"verdict": "cannot_judge", "perCriterion": []})[0] == "abstain")
    expect("referee: a dead referee abstains", map_referee(None)[0] == "abstain")
    expect("decode: only reproduced passes", [map_decode({"verdict": v})[0] for v in (
        "reproduced", "reproduced_different_relation", "not_reproduced", "cannot_reproduce")] ==
        ["pass", "fail", "fail", "abstain"])
    expect("decode: an unknown verdict abstains", map_decode({"verdict": "looks-fine"})[0] == "abstain")
    expect("tribunal: green/red/unknown", [map_tribunal({"overall": v})[0] for v in ("green", "red", "unknown")] ==
           ["pass", "fail", "abstain"])
    # Balance lint: a set a constant judge can clear is refused.
    skew = {f"sealed-{i}": {"split": "sealed", "expected": "pass"} for i in range(8)}
    expect("a one-class sealed set is refused", len(balance_problems(skew, "sealed")) >= 3)
    ok = {f"sealed-{i:02d}": {"split": "sealed", "expected": e} for i, e in enumerate(BALANCED)}
    expect("the balanced set is accepted", not balance_problems(ok, "sealed"))
    bad += _selftest_on_fixtures()
    for b in bad:
        print(f"FAIL {b}")
    print(f"judge calibration selftest: {len(bad)} failure(s)")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"ERROR: needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}", file=sys.stderr)
        return 2
    sys.path.insert(0, str(HERE))
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    for name in ("check", "report"):
        s = sub.add_parser(name)
        s.add_argument("--judge", choices=JUDGES)
    s = sub.add_parser("stage")
    s.add_argument("--judge", choices=JUDGES, required=True)
    s.add_argument("--phase", choices=("tune", "sealed"), required=True)
    s.add_argument("--dest", type=Path, required=True)
    s.add_argument("--map", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--judge", choices=JUDGES, required=True)
    s.add_argument("--phase", choices=("tune", "sealed"), required=True)
    s.add_argument("--results", type=Path)
    s = sub.add_parser("record")
    s.add_argument("--judge", choices=JUDGES, required=True)
    s.add_argument("--remeasure", action="store_true")
    s = sub.add_parser("collect")
    s.add_argument("--judge", choices=JUDGES, required=True)
    s.add_argument("--phase", choices=("tune", "sealed"), required=True)
    s.add_argument("--raw-dir", type=Path, required=True)
    s.add_argument("--note", default="")
    s.add_argument("--date", required=True)
    s = sub.add_parser("tribunal-prompt")
    s.add_argument("--case", required=True)
    s.add_argument("--stage-dir", type=Path, required=True)
    s.add_argument("--role", choices=("verifier", "adjudicator"), required=True)
    s.add_argument("--defender", type=Path, required=True)
    s.add_argument("--challenger", type=Path, required=True)
    s.add_argument("--verifier", type=Path)
    a = p.parse_args(argv)
    try:
        if a.cmd == "selftest":
            return selftest()
        if a.cmd in ("check", "report"):
            js = (a.judge,) if a.judge else JUDGES
            return cmd_check(js) if a.cmd == "check" else cmd_report(js)
        if a.cmd == "stage":
            return stage(a.judge, a.phase, a.dest, a.map)
        if a.cmd == "score":
            print(fmt_report(a.judge, a.phase, score_results(a.judge, a.phase, read_results(a.judge, a.phase, a.results))))
            return 0
        if a.cmd == "collect":
            return collect(a.judge, a.phase, a.raw_dir, a.note, a.date)
        if a.cmd == "tribunal-prompt":
            outs = {"defender": a.defender, "challenger": a.challenger}
            if a.role == "adjudicator":
                if a.verifier is None:
                    print("ERROR: the adjudicator prompt needs --verifier", file=sys.stderr)
                    return 2
                outs["verifier"] = a.verifier
            return tribunal_prompt(a.case, a.stage_dir, a.role, outs)
        return cmd_record(a.judge, a.remeasure)
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
