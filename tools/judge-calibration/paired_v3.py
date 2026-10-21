#!/usr/bin/env python3
"""The third paired tribunal measurement: andon's four-role tribunal (arm A) against one
verdict@2 contract judge (arm B), on 16 new items built to test the second run's margin as a
pattern rather than a single case.

The second measurement (paired_v2.py, wf_8cbe77db-baa) kept the tribunal by one item, v2-16:
its challenger found that Path.rglob silently skips an unreadable directory, in all five runs,
and the single judge never did. One item cannot say whether adversarial search reliably finds
a subtle defect a single judge misses. This run asks that, on purpose-built items.

Everything that decides the result is fixed here, and committed, BEFORE the run:

  * the items: test/judge-calibration/paired-v3/, 16 cases in 8 matched pairs, one pair per
    defect class an adversary looks for (a swallowed worker error, a permission path, an
    encoding path, a whitespace-only field, the precision of a huge input, a crash part way
    through a write, a boundary, an ordering assumption). In each pair the red item passes its
    happy path and fails one criterion on the class's edge case; the green item has the same
    criterion shape, a tempting non-defect from the same class, and holds. 8 red, 8 green.
  * every probe calibrated both ways: each criterion's probe fails some tree and passes
    another among the staged tree and the item's recorded controls (the fix for a red, the
    tempting defect made real for a green, one break per other criterion), every failure is an
    AssertionError, and each red's failing criterion has a happy-path probe the staged tree
    passes. ``check`` re-runs all of it.
  * the pre-seal key audit (paired-v3/key-audit.json): adversarial agents tried to prove each key
    wrong, in three rounds, the last capped by a stop rule written before it ran. Each key error
    or ambiguity was fixed by scoping the criterion in the same words for both twins or making
    the green hold, never by flipping a key or by making a red more or less subtle; round 3's
    fixes are unaudited residuals. Every implementation an auditor showed passing a probe is
    kept as an oracle ``mutant`` that its probe must fail.
  * both arms exactly as the second run dispatched them: arm A the same role prompts and
    order, arm B paired_v2.ARM_B_HEAD and rubric andon-wire@2, imported, not copied, and
    paired_v3_workflow.js byte-identical to paired_v2_workflow.js below its meta.
  * the per-item outcome (at least 3 of the 5 repeats agree, else no-majority, scored as an
    abstain) and DECISION_RULE, word for word the first two runs'.
  * CONTAMINATION: a run any of whose agents named or was shown a path holding the key (the
    tool inputs and tool results in its transcript) is scored as abstain for its arm, which is
    wrong on every item of this set. Symmetric, and decided before the run.
  * PATTERN_RULE: how the readout on the pattern question is stated (below).
  * seal.json: a fingerprint of every item's prompts, contract, tree and oracle, and of the
    rule, so a later edit to any instrument this run depends on is caught.

Usage:
    paired_v3.py check [--repeat N]
    paired_v3.py selftest
    paired_v3.py seal                     # writes seal.json; only before the run
    paired_v3.py stage --dest DIR --out ARGS.json --map MAP.json
    paired_v3.py collect --run-dir DIR --map MAP.json --out RAW.json
    paired_v3.py score --raw RAW.json --map MAP.json [--write OUT.json] [--errata ERRATA.json]
                       [--instrument INSTRUMENT.json]

KEY ERRATA work as in paired_v2.py: a sealed key later shown wrong is never edited;
results/key-errata.json records the correction with a probe that reproduces it, and
results/score-corrected.json is the same raw run scored under the corrected keys.

INSTRUMENT ERRATA are the same idea for a pre-registered rule that misfired: the sealed rule
and results/score.json stay as committed; results/instrument-errata.json may only DROP
alternatives of the sealed CONTAMINATION pattern, names them, and says why, with the evidence;
results/score-instrument.json is the raw run scored with them dropped, in both arms alike, and
score-corrected.json applies both layers. check recomputes every layer present.

STDLIB ONLY. Python >= 3.11. POSIX, not as root (the permission probes need a mode-000
directory to be unreadable).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
import paired  # noqa: E402  (majority, outcome_a, McNemar, collect, prompt reassembly)
import paired_v2  # noqa: E402  (arm B's head and rubric, the decision rule, the dispatch; never its items)
import prompts  # noqa: E402

MIN_PYTHON = (3, 11)
SET = calibration.FIXTURES / "paired-v3"
N_ITEMS = 16
REPEATS = paired.REPEATS          # 5
MAJORITY = paired.MAJORITY        # 3
THRESHOLD = paired_v2.THRESHOLD   # 0.7
TREE = paired.TREE
RUBRIC_ID = paired_v2.RUBRIC_ID   # andon-wire@2
ARM_B_HEAD = paired_v2.ARM_B_HEAD
DECISION_RULE = paired_v2.DECISION_RULE
WORKFLOW = HERE / "paired_v3_workflow.js"
SEAL = SET / "seal.json"
ERRATA = SET / "results" / "key-errata.json"
INSTRUMENT = SET / "results" / "instrument-errata.json"
PROBE_TIMEOUT = 60
CLASSES = ("concurrency", "crash-consistency", "permission", "encoding", "whitespace", "precision", "boundary", "ordering")

# A tool input or tool result naming one of these is a run that could have read the key.
CONTAMINATION = re.compile(r"test/judge-calibration|tools/judge-calibration|docs/plugin-authoring|answers\.json|key-errata"
                           r"|seal\.json|key-audit|keyaudit|build_v3|scratchpad|/tasks/|\.claude/projects")

PATTERN_RULE = (
    "On the 8 red items, count the items only the tribunal's majority calls red (b) and only the "
    "contract judge's majority calls red (c), and how many reds each majority calls red. Read in this order: "
    "SUPPORTED if b >= 6 and c == 0 (exact McNemar p <= 0.031) and the tribunal's majority calls at most 1 "
    "green item red. CEILING if both majorities call at least 7 of the 8 reds red: the items did not "
    "discriminate, which says nothing about the second run's finding. FLOOR if both call at most 1 red red: "
    "the defects were too subtle for either arm. NO DETECTION ADVANTAGE if b <= c. Otherwise NOT SETTLED. "
    "Per-run red detection on the 40 red runs per arm, and per class, is reported beside it and decides nothing."
)
SUPPORT_MIN_B = 6
SUPPORT_MAX_FALSE_RED = 1
CEILING_MIN = 7
FLOOR_MAX = 1


# ------------------------------------------------------------------------------ items

def items(errata: dict | None = None) -> list[dict]:
    """The sealed items; with ``errata``, each corrected item carries its corrected key."""
    answers = calibration.load_json(SET / "answers.json")
    fix = {cid: e["corrected"] for cid, e in (errata or {}).items()}
    return [{"id": f"paired-v3/{cid}", "dir": SET / "cases" / cid, "oracle": SET / "oracle" / f"{cid}.json",
             "expected": fix.get(cid, a)["expected"], "native": fix.get(cid, a)["nativeExpected"],
             "class": a["class"], "pair": a["pair"]}
            for cid, a in sorted(answers.items())]


def templates(item: dict, key: str) -> dict[str, Any]:
    """The second run's prompts for this item, built by the same code."""
    return paired_v2.templates(item, key)


# ------------------------------------------------------------------------- calibration

def run_probe(snippet: str, files: dict[str, str]) -> tuple[int, str]:
    """(exit code, last stderr line) of one probe run inside a fresh copy of ``files``."""
    with tempfile.TemporaryDirectory() as td:
        oracles.write_tree(Path(td), files)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": td}
        try:
            r = subprocess.run([sys.executable, "-B", "-c", snippet], cwd=td, env=env, capture_output=True,
                               text=True, timeout=PROBE_TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            return 124, "timeout"
    return r.returncode, (r.stderr.strip().splitlines() or [""])[-1]


def _codes(probes: dict[str, str], files: dict[str, str]) -> tuple[dict[str, int], list[str]]:
    codes, bad = {}, []
    for cid, snippet in sorted(probes.items()):
        code, last = run_probe(snippet, files)
        codes[cid] = code
        if code not in (0, 1):
            bad.append(f"{cid} exits {code} ({last[:80]!r})")
        elif code == 1 and not last.startswith("AssertionError"):
            bad.append(f"{cid} fails without an assertion ({last[:80]!r})")
    return codes, bad


def calibrate(item: dict) -> list[str]:
    """Every probe decides the key on the staged tree and is shown to discriminate: it passes
    one tree and fails another among the staged tree and the recorded controls."""
    cid = item["id"].split("/", 1)[1]
    orc = calibration.load_json(item["oracle"])
    tree = oracles._tree_of(item["dir"] / "tree")
    probs = []
    codes, bad = _codes(orc["probes"], tree)
    probs += [f"{cid} staged: {b}" for b in bad]
    truth = "red" if 1 in codes.values() else "green"
    if truth != item["native"]:
        probs.append(f"{cid}: the probes say {truth} {codes} on the staged tree, answers.json says {item['native']}")
    seen = {c: {code} for c, code in codes.items()}
    for c, snippet in sorted(orc.get("happy", {}).items()):
        code, last = run_probe(snippet, tree)
        if codes.get(c) != 1:
            probs.append(f"{cid}: a happy-path probe for {c}, which does not fail the staged tree")
        if code != 0:
            probs.append(f"{cid}: the happy path of {c} fails the staged tree (exit {code}, {last[:80]!r})")
    if item["native"] == "red" and not any(codes[c] == 1 for c in orc.get("happy", {})):
        probs.append(f"{cid}: no happy-path probe for the criterion the staged tree fails")
    for ctl in orc["controls"]:
        files = {**tree, **ctl["files"]}
        if files == tree:
            probs.append(f"{cid} control {ctl['name']}: it is the staged tree")
            continue
        got, bad = _codes(orc["probes"], files)
        probs += [f"{cid} control {ctl['name']}: {b}" for b in bad]
        if got != ctl["expect"]:
            probs.append(f"{cid} control {ctl['name']}: the probes say {got}, the control records {ctl['expect']}")
        for c, code in got.items():
            seen[c].add(code)
    for c, codes_seen in sorted(seen.items()):
        if not {0, 1} <= codes_seen:
            probs.append(f"{cid}: the probe for {c} is not calibrated both ways (exits seen: {sorted(codes_seen)})")
    # Mutants: implementations the pre-seal key audit showed passing the probes as first written.
    for m in orc.get("mutants", []):
        files = {**tree, **m["files"]}
        code, last = run_probe(orc["probes"][m["breaks"]], files)
        if files == tree or code != 1 or not last.startswith("AssertionError"):
            probs.append(f"{cid} mutant {m['name']}: the probe for {m['breaks']} does not catch it (exit {code}, {last[:80]!r})")
    if item["native"] == "red" and not any(all(v == 0 for v in ctl["expect"].values()) for ctl in orc["controls"]):
        probs.append(f"{cid}: no fixed control that every probe passes")
    return probs


def _old_trees() -> set[str]:
    """Every file body an earlier run (or the tribunal calibration they reused) ever staged."""
    out = set()
    for judge in ("paired", "tribunal", "paired-v2"):
        for p in (calibration.FIXTURES / judge / "cases").rglob("*"):
            if p.is_file() and "tree" in p.parts:
                out.add(p.read_text(encoding="utf-8"))
    return out


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def fingerprint() -> dict[str, Any]:
    """What the seal holds: the rule, both arms' instruments, and per item everything a run reads."""
    per_item = {}
    for i in items():
        cid = i["id"].split("/", 1)[1]
        per_item[cid] = {
            "prompts": _sha(templates(i, "{ITEM}")),
            "contract": _sha(calibration.load_json(i["dir"] / "contract.json")),
            "tree": _sha(oracles._tree_of(i["dir"] / "tree")),
            "oracle": _sha(calibration.load_json(i["oracle"])),
            "answer": _sha(calibration.load_json(SET / "answers.json")[cid]),
        }
    wf = WORKFLOW.read_text(encoding="utf-8")
    return {"rubric": RUBRIC_ID, "threshold": THRESHOLD, "repeats": REPEATS, "majority": MAJORITY,
            "decisionRule": DECISION_RULE, "patternRule": PATTERN_RULE, "contamination": CONTAMINATION.pattern,
            "armBHead": hashlib.sha256(ARM_B_HEAD.encode()).hexdigest(),
            "workflow": hashlib.sha256(wf.encode()).hexdigest(), "items": per_item}


def _body(js: str) -> str:
    """A workflow script below its meta block."""
    return js[js.index("\n}\n") + 3:]


def check(repeat: int = 1) -> list[str]:
    if os.geteuid() == 0:
        return ["paired-v3 cannot be checked as root: root reads a mode-000 directory"]
    probs = []
    its = items()
    if len(its) != N_ITEMS:
        probs.append(f"{len(its)} items, the design says {N_ITEMS}")
    exp = [i["expected"] for i in its]
    if exp.count("pass") != N_ITEMS // 2 or exp.count("fail") != N_ITEMS // 2:
        probs.append(f"the design is {N_ITEMS // 2} red and {N_ITEMS // 2} green, the key has {exp.count('fail')} red")
    pairs: dict[str, list[dict]] = {}
    for i in its:
        pairs.setdefault(i["pair"], []).append(i)
    for p, two in sorted(pairs.items()):
        if sorted(x["expected"] for x in two) != ["fail", "pass"] or len({x["class"] for x in two}) != 1:
            probs.append(f"pair {p} is not one red and one green of one class")
    if sorted({i["class"] for i in its}) != sorted(CLASSES):
        probs.append(f"the classes are {sorted({i['class'] for i in its})}, the design says {sorted(CLASSES)}")
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
        for _ in range(repeat):
            probs += calibrate(i)
        if any(needle in body for body in tree.values() for needle in ("EXPECTED", "known-", "nativeExpected", "paired-v3")):
            probs.append(f"{cid}: a staged file names the answer")
        if any(body in old for body in tree.values()):
            probs.append(f"{cid}: a staged file is one an earlier run already used")
        stray = sorted(q.relative_to(i["dir"]).as_posix() for q in (i["dir"] / "tree").rglob("*")
                       if q.is_file() and q.relative_to(i["dir"] / "tree").as_posix() not in tree)
        if stray:
            probs.append(f"{cid}: stage would copy files the oracle never saw: {stray}")
        t = templates(i, "kX")
        if paired.js_verifier(t, "/s/tree", "D", "C") != prompts.verifier_prompt(contract, Path("/s/tree"), "D", "C"):
            probs.append(f"{cid}: the verifier's parts do not reassemble prompts.verifier_prompt")
        if paired.js_adjudicator(t, "D", "C", "V") != prompts.adjudicator_prompt(contract, "D", "C", "V"):
            probs.append(f"{cid}: the adjudicator's parts do not reassemble prompts.adjudicator_prompt")
        if TREE not in t["defender"] or TREE not in t["armB"] or RUBRIC_ID not in t["armB"]:
            probs.append(f"{cid}: a prompt does not carry the tree placeholder or the rubric")
        if any(w in t["armB"] or w in t["challenger"] for w in ("nativeExpected", "answers", "expected", "paired-v3")):
            probs.append(f"{cid}: a prompt names the answer")
    wf = WORKFLOW.read_text(encoding="utf-8")
    if _body(wf) != _body(paired_v2.WORKFLOW.read_text(encoding="utf-8")):
        probs.append("paired_v3_workflow.js differs from paired_v2_workflow.js below its meta")
    canon = (HERE.parent / "judge-contract" / "verdict.inline.js").read_text(encoding="utf-8")
    if paired_v2._block(canon, "verdict@2") != paired_v2._block(wf, "verdict@2"):
        probs.append("paired_v3_workflow.js's verdict@2 block differs from tools/judge-contract/verdict.inline.js")
    if not SEAL.is_file():
        probs.append("no seal.json: run `paired_v3.py seal` before staging")
    elif calibration.load_json(SEAL) != fingerprint():
        now, was = fingerprint(), calibration.load_json(SEAL)
        moved = sorted(k for k in now if now[k] != was.get(k)) + sorted(
            f"items.{c}.{f}" for c in now["items"] for f in now["items"][c] if was.get("items", {}).get(c, {}).get(f) != now["items"][c][f])
        probs.append(f"seal.json does not match what is committed now: {moved}")
    probs += v2_equivalence()
    res = SET / "results"
    if (res / "run.json").is_file():
        errata = calibration.load_json(ERRATA) if ERRATA.is_file() else None
        inst = calibration.load_json(INSTRUMENT) if INSTRUMENT.is_file() else None
        derived = ([("score.json", None, None)] + ([("score-instrument.json", None, inst)] if inst else [])
                   + ([("score-corrected.json", errata, inst)] if errata else []))
        for name, err, ins in derived:
            try:
                again = score(calibration.load_json(res / "run.json"), calibration.load_json(res / "map.json"),
                              errata=err, instrument=ins)
            except ValueError as exc:
                probs.append(f"the committed run does not score: {exc}")
                continue
            if not (res / name).is_file() or again != calibration.load_json(res / name):
                probs.append(f"results/{name} differs from the score recomputed from results/run.json")
        if errata:
            probs += check_errata(errata)
        if inst:
            probs += check_instrument(inst)
    return probs


def check_instrument(inst: dict) -> list[str]:
    """An instrument erratum may only drop alternatives the sealed CONTAMINATION pattern had, and
    it states the pattern it corrects verbatim, so it cannot quietly rewrite the rule."""
    c = inst.get("contamination", {})
    probs = []
    if c.get("sealedPattern") != CONTAMINATION.pattern:
        probs.append("instrument-errata.json: its sealedPattern is not the CONTAMINATION pattern the seal holds")
    alts = CONTAMINATION.pattern.split("|")
    for d in c.get("dropped", []):
        if d not in alts:
            probs.append(f"instrument-errata.json: it drops {d!r}, which is not an alternative of the sealed pattern")
    return probs


def v2_equivalence() -> list[str]:
    """This scorer, given the second run's raw run and items, reproduces its committed scores:
    the reuse is proven, not asserted."""
    res = paired_v2.SET / "results"
    if not (res / "run.json").is_file():
        return []
    raw, mp = calibration.load_json(res / "run.json"), calibration.load_json(res / "map.json")
    probs = []
    errata = calibration.load_json(paired_v2.ERRATA) if paired_v2.ERRATA.is_file() else None
    for name, err in [("score.json", None)] + ([("score-corrected.json", errata)] if errata else []):
        mine = score_core(raw, mp, paired_v2.items(err), err)
        if mine != calibration.load_json(res / name):
            probs.append(f"this scorer does not reproduce paired-v2/results/{name}")
    return probs


def check_errata(errata: dict) -> list[str]:
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
        code, last = run_probe(e["probe"], oracles._tree_of(SET / "cases" / cid / "tree"))
        want_fail = e["corrected"]["expected"] == "fail"
        if want_fail and (code != 1 or not last.startswith("AssertionError")):
            probs.append(f"erratum {cid}: its probe does not reproduce the defect (exit {code}, {last[:80]!r})")
        if not want_fail and code != 0:
            probs.append(f"erratum {cid}: its probe does not show the criterion holds (exit {code}, {last[:80]!r})")
        if "control" in e:
            files = {**oracles._tree_of(SET / "cases" / cid / "tree"), **e["control"]["files"]}
            ccode, clast = run_probe(e["probe"], files)
            if ccode != (0 if want_fail else 1):
                probs.append(f"erratum {cid}: its probe does not discriminate on its control (exit {ccode}, {clast[:80]!r})")
    return probs


def seal() -> int:
    probs = [p for p in check() if not p.startswith(("no seal.json", "seal.json does not match"))]
    if probs:
        for p in probs:
            print(f"PAIRED-V3 {p}")
        print("refusing to seal a set that does not check")
        return 1
    if (SET / "results").exists():
        print("refusing to re-seal: results/ exists, so the run has happened")
        return 1
    SEAL.write_text(json.dumps(fingerprint(), indent=2) + "\n", encoding="utf-8")
    print(f"sealed {N_ITEMS} items into {SEAL.as_posix()}")
    return 0


# ------------------------------------------------------------------------------ the run

def stage(dest: Path, out: Path, map_file: Path) -> int:
    """paired_v2.stage's layout for this set: one tree per (item, repeat, arm), prompts beside it."""
    if CONTAMINATION.search(dest.resolve().as_posix()):
        print(f"ERROR: {dest} would make every staged path look like contamination; stage elsewhere", file=sys.stderr)
        return 2
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


def jsonl(path: Path) -> list[Any]:
    """Every record of a JSON-lines file, split on '\\n' ONLY. str.splitlines() also splits on
    U+2028, U+2029, U+0085 and \\x1c-\\x1e, which JSON allows raw inside a string: an agent quoting
    v3-07's probe broke paired.collect's journal read, and its transcript reader would have
    dropped such a line silently (``except ValueError: continue``), turning a report into an
    abstain. A line that still does not parse is an error here, never a skipped line."""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError as exc:
                raise ValueError(f"{path}:{n} is not a JSON record: {exc}") from exc
    return out


def _report(transcript: Path) -> tuple[Any, dict[str, int]]:
    """paired._report over jsonl(): the input of the agent's StructuredOutput call when it had a
    schema, else its last text, and its token usage."""
    structured, text = None, None
    usage = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    for e in jsonl(transcript):
        msg = e.get("message") if isinstance(e, dict) else None
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        u = msg.get("usage") or {}
        usage["input"] += u.get("input_tokens", 0) or 0
        usage["output"] += u.get("output_tokens", 0) or 0
        usage["cacheRead"] += u.get("cache_read_input_tokens", 0) or 0
        usage["cacheWrite"] += u.get("cache_creation_input_tokens", 0) or 0
        for c in msg.get("content") if isinstance(msg.get("content"), list) else []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use" and c.get("name") == "StructuredOutput":
                structured = c.get("input")
            elif c.get("type") == "text" and c.get("text", "").strip():
                text = c["text"].strip()
    return (structured if structured is not None else text), usage


def contamination(transcript: Path) -> list[str]:
    """The key paths one agent's tool inputs or tool results named."""
    hits = set()
    for e in jsonl(transcript):
        msg = e.get("message") if isinstance(e, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        for c in content if isinstance(content, list) else []:
            if isinstance(c, dict) and c.get("type") in ("tool_use", "tool_result"):
                text = json.dumps(c.get("input") if c["type"] == "tool_use" else c.get("content"))
                hits.update(m.group(0) for m in CONTAMINATION.finditer(text))
    return sorted(hits)


def collect(run_dir: Path, mapping: dict[str, str]) -> dict:
    """paired.collect's rebuild of every run from the workflow journal (each agent's label names
    its role, item and repeat; its transcript holds its report), read through jsonl(), plus the
    contamination scan of every agent of every run."""
    labels = {e["agentId"]: e["label"] for e in jsonl(run_dir / "journal.jsonl")
              if e.get("type") == "started" and e.get("agentId")}
    runs: dict[tuple[str, int, str], dict] = {}
    for aid, label in labels.items():
        role, key, rep = label.rsplit(" ", 2)
        arm = "b" if role == "contract judge" else "a"
        t = run_dir / f"agent-{aid}.jsonl"
        report, usage = _report(t) if t.is_file() else (None, {})
        run = runs.setdefault((key, int(rep.lstrip("r")), arm),
                              {"key": key, "r": int(rep.lstrip("r")), "arm": arm, "roles": {}, "usage": {},
                               "agents": 0, "contaminated": set()})
        run["agents"] += 1
        run["usage"] = {k: run["usage"].get(k, 0) + v for k, v in usage.items()}
        run["contaminated"].update(contamination(t) if t.is_file() else [])
        if arm == "b":
            run["report"] = report
        else:
            run["roles"][role] = report
            if role == "adjudicator":
                run["adjudicator"] = report
    unknown = sorted({k for k, _, _ in runs} - set(mapping))
    if unknown:
        raise ValueError(f"journal names items the map does not: {unknown}")
    out = [runs[k] for k in sorted(runs)]
    for run in out:
        run["contaminated"] = sorted(run["contaminated"])
    return {"runs": out}


# ---------------------------------------------------------------------------- scoring

def score_core(raw: dict, mapping: dict[str, str], its: list[dict], errata: dict | None = None) -> dict:
    """paired_v2.score's computation over any item list, with one addition: a run marked
    contaminated scores as abstain for its arm. Runs without the mark score exactly as there,
    which v2_equivalence proves on the second run's committed results."""
    by_id = {i["id"]: i for i in its}
    per_item: dict[str, dict] = {}
    for run in raw["runs"]:
        iid = mapping[run["key"]]
        it = by_id[iid]
        rec = per_item.setdefault(iid, {"expected": it["expected"], "a": [], "b": [], "bVerdicts": []})
        if run["arm"] == "a":
            rec["a"].append("abstain" if run.get("contaminated") else paired.outcome_a(run.get("adjudicator")))
        else:
            o, v = paired_v2.outcome_b(run.get("report"), calibration.load_json(it["dir"] / "contract.json"), run["key"])
            rec["b"].append("abstain" if run.get("contaminated") else o)
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
    if errata:
        out["keyErrata"] = sorted(errata)
    out["decision"] = {"rule": DECISION_RULE, "keepTribunal": keep,
                       "falsePasses": {"tribunal": A["items"]["falsePasses"], "contractJudge": B["items"]["falsePasses"]},
                       "record": {"tribunal": A["record"]["agreement"], "contractJudge": B["record"]["agreement"]}}
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


def pattern(core: dict, its: list[dict]) -> dict:
    """PATTERN_RULE applied to a scored run."""
    cls = {i["id"]: i["class"] for i in its}
    reds = {iid: r for iid, r in core["items"].items() if r["expected"] == "fail"}
    greens = {iid: r for iid, r in core["items"].items() if r["expected"] == "pass"}
    b = sum(1 for r in reds.values() if r["tribunalMajority"] == "fail" != r["contractJudgeMajority"])
    c = sum(1 for r in reds.values() if r["contractJudgeMajority"] == "fail" != r["tribunalMajority"])
    false_red = sum(1 for r in greens.values() if r["tribunalMajority"] == "fail")
    found = {arm: sum(1 for r in reds.values() if r[f"{arm}Majority"] == "fail") for arm in ("tribunal", "contractJudge")}
    if b >= SUPPORT_MIN_B and c == 0 and false_red <= SUPPORT_MAX_FALSE_RED:
        verdict = "SUPPORTED"
    elif min(found.values()) >= CEILING_MIN:
        verdict = "CEILING"
    elif max(found.values()) <= FLOOR_MAX:
        verdict = "FLOOR"
    elif b <= c:
        verdict = "NO DETECTION ADVANTAGE"
    else:
        verdict = "NOT SETTLED"
    detect = {arm: sum(r[name].count("fail") for r in reds.values())
              for arm, name in (("tribunal", "tribunal"), ("contractJudge", "contractJudge"))}
    per_class = {cls[iid]: {"tribunal": r["tribunal"].count("fail"), "contractJudge": r["contractJudge"].count("fail")}
                 for iid, r in sorted(reds.items())}
    return {"rule": PATTERN_RULE, "verdict": verdict, "onlyTribunalFoundRed": b, "onlyContractJudgeFoundRed": c,
            "mcnemarExactPOnReds": paired.binom_two_sided(b, c), "tribunalFalseRedGreens": false_red,
            "redItemsCalledRed": {k: f"{v}/{len(reds)}" for k, v in found.items()},
            "redRunsCalledRed": {k: f"{v}/{len(reds) * REPEATS}" for k, v in detect.items()},
            "redRunsCalledRedPerClass": per_class}


def score(raw: dict, mapping: dict[str, str], errata: dict | None = None, instrument: dict | None = None) -> dict:
    """The sealed score; with ``instrument``, a run's contamination hits on the alternatives the
    instrument erratum drops no longer count, in both arms alike."""
    if instrument:
        drop = set(instrument["contamination"]["dropped"])
        raw = {**raw, "runs": [{**r, "contaminated": [h for h in r.get("contaminated", []) if h not in drop]}
                               for r in raw["runs"]]}
    its = items(errata)
    core = score_core(raw, mapping, its, errata)
    if instrument:
        core["instrumentErrata"] = sorted(instrument)
    core["contaminatedRuns"] = sorted(f"{mapping[r['key']]} r{r['r']} arm {r['arm']}: {', '.join(r['contaminated'])}"
                                      for r in raw["runs"] if r.get("contaminated"))
    core["pattern"] = pattern(core, its)
    return core


# ---------------------------------------------------------------------------- selftest

def _fake_raw(a_mode: str, b_mode: str) -> tuple[dict, dict]:
    """Fabricated runs. 'right' answers every item by its key; 'pass' always passes; 'hedge'
    answers unknown on the first green and right elsewhere; 'blind' passes every red (a judge
    that never finds the edge case) and is right on the greens; 'paranoid' fails every item."""
    word = {"pass": "green", "fail": "red", "abstain": "unknown"}
    mapping, runs = {}, []
    its = items()
    first_green = next(i["id"] for i in its if i["expected"] == "pass")
    for n, it in enumerate(its):
        key = f"w{n:02d}"
        mapping[key] = it["id"]
        contract = calibration.load_json(it["dir"] / "contract.json")

        def want(mode: str) -> str:
            return {"right": it["expected"], "pass": "pass", "paranoid": "fail",
                    "hedge": "abstain" if it["id"] == first_green else it["expected"],
                    "blind": "pass"}[mode]

        for r in range(1, REPEATS + 1):
            runs.append({"key": key, "r": r, "arm": "a", "adjudicator": f"Overall: {word[want(a_mode)]}"})
            o = want(b_mode)
            if o == "abstain":
                report = {"item": key, "criteria": [], "abstain": True, "abstainReason": "cannot tell"}
            else:
                crit = [{"id": c["id"], "score": 0.9, "pass": True, "evidence": "probe"} for c in contract["criteria"]]
                if o == "fail":
                    crit[0] = {**crit[0], "score": 0.1, "pass": False}
                report = {"item": key, "criteria": crit, "abstain": False, "abstainReason": None}
            runs.append({"key": key, "r": r, "arm": "b", "report": report})
    return {"runs": runs}, mapping


def selftest() -> int:
    bad = []
    rep = score(*_fake_raw("right", "right"))
    if rep["decision"]["keepTribunal"]:
        bad.append("two perfect arms kept the tribunal (a tie must collapse it)")
    if rep["arms"]["b"]["record"]["agreement"] != 1.0 or rep["arms"]["a"]["record"]["agreement"] != 1.0:
        bad.append("a perfect arm on an 8-red/8-green set did not get a record of 1.0 (a degenerate figure?)")
    if rep["pattern"]["verdict"] != "CEILING":
        bad.append(f"two perfect arms read as {rep['pattern']['verdict']}, not CEILING (the items did not discriminate)")
    rep = score(*_fake_raw("blind", "blind"))
    if rep["pattern"]["verdict"] != "FLOOR":
        bad.append(f"two arms that find no red read as {rep['pattern']['verdict']}, not FLOOR")
    rep = score(*_fake_raw("blind", "right"))
    if rep["pattern"]["verdict"] != "NO DETECTION ADVANTAGE":
        bad.append(f"a judge that finds every red beside a tribunal that finds none read as {rep['pattern']['verdict']}")
    rep = score(*_fake_raw("right", "hedge"))
    if not rep["decision"]["keepTribunal"]:
        bad.append("a contract judge hedging unknown on one green did not lose on the record")
    rep = score(*_fake_raw("right", "pass"))
    if not rep["decision"]["keepTribunal"] or rep["arms"]["b"]["items"]["falsePasses"] != N_ITEMS // 2:
        bad.append("a contract judge that passes everything did not keep the tribunal with 8 false passes")
    rep = score(*_fake_raw("right", "blind"))
    if rep["pattern"]["verdict"] != "SUPPORTED" or rep["pattern"]["onlyTribunalFoundRed"] != N_ITEMS // 2:
        bad.append(f"a tribunal that finds every red beside a judge that finds none read as {rep['pattern']}")
    rep = score(*_fake_raw("paranoid", "blind"))
    if rep["pattern"]["verdict"] != "NOT SETTLED":
        bad.append(f"a tribunal that calls every item red beside a blind judge read as {rep['pattern']['verdict']}, not NOT SETTLED")
    rep = score(*_fake_raw("paranoid", "right"))
    if rep["decision"]["keepTribunal"]:
        bad.append("a tribunal that invents reds on every green was kept over a perfect contract judge")
    raw, mp = _fake_raw("right", "right")
    for run in raw["runs"]:
        if run["arm"] == "a":
            run["contaminated"] = ["test/judge-calibration"]
    rep = score(raw, mp)
    if rep["arms"]["a"]["items"]["agreement"] != 0.0 or len(rep["contaminatedRuns"]) != N_ITEMS * REPEATS:
        bad.append("contaminated runs were not scored as abstain and listed")
    raw, mp = _fake_raw("right", "right")
    raw["runs"].pop()
    try:
        score(raw, mp)
        bad.append("an incomplete run was scored")
    except ValueError:
        pass
    # The calibration refuses a probe that decides nothing, a control that is the staged tree,
    # and a failure that is not an assertion.
    it = next(i for i in items() if i["expected"] == "fail")
    orc = calibration.load_json(it["oracle"])
    with tempfile.TemporaryDirectory() as td:
        planted = {
            "a probe that always passes": {**orc, "probes": dict.fromkeys(orc["probes"], "pass")},
            "a control equal to the staged tree": {**orc, "controls": [{**orc["controls"][0], "files": {}}]},
            "a probe that crashes instead of asserting": {**orc, "probes": {**orc["probes"], next(iter(orc["probes"])): "import nosuchmodule_x"}},
            "a red without its happy-path probe": {**orc, "happy": {}},
            "a mutant its probe does not catch": {**orc, "mutants": [
                {"name": "planted", "breaks": next(iter(orc["probes"])), "files": {}}]},
        }
        for name, o in planted.items():
            p = Path(td) / "o.json"
            p.write_text(json.dumps(o), encoding="utf-8")
            if not calibrate({**it, "oracle": p}):
                bad.append(f"calibrate accepted {name}")
    if calibrate(it):
        bad.append(f"calibrate refused a committed item: {calibrate(it)}")
    # The contamination scan sees a key path in a tool result as well as in a tool input.
    with tempfile.TemporaryDirectory() as td:
        t = Path(td) / "agent-x.jsonl"
        t.write_text("\n".join(json.dumps(x) for x in [
            {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Grep", "input": {"pattern": "latest"}}]}},
            {"message": {"role": "user", "content": [{"type": "tool_result", "content": "test/judge-calibration/x/answers.json:3"}]}},
        ]) + "\n", encoding="utf-8")
        if contamination(t) != ["answers.json", "test/judge-calibration"]:
            bad.append(f"the contamination scan missed a key path in a tool result: {contamination(t)}")
        t.write_text(json.dumps({"message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/stage/wab-1a/tree/rotate.py"}}]}}) + "\n", encoding="utf-8")
        if contamination(t):
            bad.append("the contamination scan flagged a read of the staged tree")
    # check_instrument refuses a correction that rewrites the rule instead of dropping from it.
    for name, inst in {"a sealed pattern that is not the seal's": {"contamination": {"sealedPattern": "x", "dropped": []}},
                       "a dropped alternative the seal never had": {"contamination": {"sealedPattern": CONTAMINATION.pattern,
                                                                                      "dropped": ["answers"]}}}.items():
        if not check_instrument(inst):
            bad.append(f"check_instrument accepted {name}")
    if check_instrument({"contamination": {"sealedPattern": CONTAMINATION.pattern, "dropped": ["scratchpad"]}}):
        bad.append("check_instrument refused dropping an alternative the seal has")
    raw, mp = _fake_raw("right", "right")
    for run in raw["runs"]:
        run["contaminated"] = ["scratchpad"] if run["arm"] == "a" else []
    inst = {"contamination": {"sealedPattern": CONTAMINATION.pattern, "dropped": ["scratchpad"]}}
    if score(raw, mp)["arms"]["a"]["items"]["agreement"] != 0.0 or score(raw, mp, instrument=inst)["arms"]["a"]["items"]["agreement"] != 1.0:
        bad.append("an instrument erratum did not lift exactly the contamination it drops")
    for b in bad:
        print(f"FAIL {b}")
    print(f"paired-v3 selftest: {len(bad)} failure(s)")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print("ERROR: needs Python >= 3.11", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("check")
    s.add_argument("--repeat", type=int, default=1, help="run every probe calibration this many times (determinism)")
    sub.add_parser("selftest")
    sub.add_parser("seal")
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
    s.add_argument("--instrument", type=Path, help="score under the instrument corrections in this instrument-errata.json")
    a = p.parse_args(argv)
    if a.cmd == "check":
        probs = check(a.repeat)
        for x in probs:
            print(f"PAIRED-V3 {x}")
        print(f"paired-v3 measurement: {len(items())} items, {len(probs)} problem(s)")
        return 1 if probs else 0
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "seal":
        return seal()
    if a.cmd == "stage":
        return stage(a.dest, a.out, a.map)
    if a.cmd == "collect":
        raw = collect(a.run_dir, calibration.load_json(a.map))
        a.out.write_text(json.dumps(raw, indent=1) + "\n", encoding="utf-8")
        print(f"collected {len(raw['runs'])} runs into {a.out.as_posix()}, "
              f"{sum(1 for r in raw['runs'] if r['contaminated'])} contaminated")
        return 0
    rep = score(calibration.load_json(a.raw), calibration.load_json(a.map),
                calibration.load_json(a.errata) if a.errata else None,
                calibration.load_json(a.instrument) if a.instrument else None)
    if a.write:
        a.write.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("decision", "discordant", "pattern", "contaminatedRuns")}, indent=2))
    for arm, name in (("a", "tribunal"), ("b", "contract judge")):
        m = rep["arms"][arm]["items"]
        print(f"{name}: per-item agreement {m['agreement']:.2f}, false passes {m['falsePasses']}, "
              f"record {rep['arms'][arm]['record']['agreement']}, per-run agreement {rep['arms'][arm]['runs']['agreement']:.2f}, "
              f"unanimous items {rep['arms'][arm]['unanimousItems']}/{N_ITEMS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
