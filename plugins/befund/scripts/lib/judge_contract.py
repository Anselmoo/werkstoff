#!/usr/bin/env python3
"""One LLM-as-judge verdict contract (verdict@1): the judge reports, code decides.

A judge returns only ``{item, criteria, abstain, abstainReason}``. Everything that
gates -- ``score``, ``outcome``, ``calibrated`` -- is derived here, deterministically,
so no model ever states its own pass. This file is the canonical Python side; the
canonical JS side is the block in ``verdict.inline.js`` beside it, and the two are
held to identical results by ``test_parity.py``. The file is vendored byte-identical
into plugins, so it reads nothing relative to itself and names no plugin.

Semantics of ``decide(raw, rubric)``, in the order the checks run:

    outcome "abstain"  raw is not an object (null, missing, a string) -- verdict-missing
                       no item, or an item that is not the one asked about
                       ``abstain`` is not a boolean, or is true (the judge abstained)
                       ``criteria`` is not a list; an entry is not an object or has
                       no string id; an id is duplicated or not in the rubric
                       a score that is not a finite number in [0, 1] (a bool is
                       NOT a number here, though Python says it is an int)
                       a ``pass`` that is not a boolean; evidence that is not a
                       non-empty string; a rubric criterion with no entry
    outcome "fail"     well-formed, and any criterion has pass false, or the
                       MINIMUM criterion score is below the rubric threshold
    outcome "pass"     everything else

``score`` is the minimum of the criterion scores, never an average: a verdict that
passes three criteria and fails a fourth is a fail. An abstain carries score 0.0 and
no criteria, and is never a pass -- fail-closed. ``abstainReason`` is a fixed code
(``missing-criterion:<id>``) for anything code detected, or ``judge:<text>`` when the
judge abstained itself, so the Python and JS sides emit the same string.

``calibrated`` is true only when the rubric carries a ``calibration`` record showing
a sealed known-answer set that the judge's agreement cleared. It is derived from that
record, never declared: a rubric with no record is uncalibrated. A bare
``"calibrated": true`` key on a rubric is ignored.

A malformed RUBRIC raises ``ValueError``: that is an author's bug, not a judge's
failure, and must not be hidden inside an abstain.

Usage:
    judge_contract.py --selftest
    judge_contract.py --decide RAW.json --rubric RUBRIC.json [--item ID] [--decided-by command]
    judge_contract.py --validate VERDICT.json
    judge_contract.py --spot-check VERDICTS.json [--k 3]

Exit 0 ok / pass; 1 a finding (selftest red, invalid verdict); 2 could not run
(unreadable input, malformed rubric). STDLIB ONLY. Python >= 3.11.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

MIN_PYTHON = (3, 11)
CONTRACT = "verdict@1"

# What a rubric looks like. ``calibration`` is optional and absent on every rubric
# today; ``sealed`` is the size of the known-answer set the judge never tuned on.
RUBRIC_SHAPE = {
    "id": "<plugin>-<name>@<int>",
    "threshold": "number in [0, 1]",
    "criteria": [{"id": "kebab-case id", "question": "what the judge answers"}],
    "calibration": {"sealed": "int > 0", "agreement": "number in [0, 1]", "floor": "number in [0, 1]"},
}
RUBRIC_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+@(?:0|[1-9][0-9]*)")
CRITERION_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
VERDICT_KEYS = (
    "item", "rubric", "decidedBy", "criteria", "abstain", "abstainReason",
    "threshold", "score", "outcome", "calibrated",
)
CRITERION_KEYS = ("id", "score", "pass", "evidence")
DECIDERS = ("judge", "command")
OUTCOMES = ("pass", "fail", "abstain")


def _is_number(v: Any) -> bool:
    # No separate finiteness test: NaN and inf already fail every range check
    # below (0 <= nan is False; inf.is_integer() is False), and a branch that can
    # never decide anything is one test_parity.py cannot show going red.
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_unit(v: Any) -> bool:
    return _is_number(v) and 0 <= v <= 1


def check_rubric(rubric: Any) -> list[str]:
    """Every way ``rubric`` is not a usable rubric; empty when it is."""
    if not isinstance(rubric, dict):
        return ["rubric is not an object"]
    errs = []
    rid = rubric.get("id")
    if not isinstance(rid, str) or not RUBRIC_ID.fullmatch(rid):
        errs.append(f"rubric id {rid!r} is not <plugin>-<name>@<int>")
    if not _is_unit(rubric.get("threshold")):
        errs.append("rubric threshold is not a number in [0, 1]")
    crit = rubric.get("criteria")
    if not isinstance(crit, list) or not crit:
        errs.append("rubric criteria is not a non-empty list")
    else:
        seen = set()
        for i, c in enumerate(crit):
            cid = c.get("id") if isinstance(c, dict) else None
            if not isinstance(cid, str) or not CRITERION_ID.fullmatch(cid):
                errs.append(f"rubric criterion {i} has no kebab-case id")
            elif cid in seen:
                errs.append(f"rubric criterion {cid} is duplicated")
            else:
                seen.add(cid)
            q = c.get("question") if isinstance(c, dict) else None
            if not isinstance(q, str) or not q.strip():
                errs.append(f"rubric criterion {i} has no question")
    cal = rubric.get("calibration")
    if cal is not None:
        # An integral float (12.0) counts, as Number.isInteger does on the JS side.
        ok = (isinstance(cal, dict) and _is_number(cal.get("sealed"))
              and float(cal["sealed"]).is_integer() and cal["sealed"] >= 0
              and _is_unit(cal.get("agreement")) and _is_unit(cal.get("floor")))
        if not ok:
            errs.append("rubric calibration is not {sealed: int >= 0, agreement: [0,1], floor: [0,1]}")
    return errs


def is_calibrated(rubric: dict) -> bool:
    """True only when a calibration record shows a sealed set the judge cleared."""
    cal = rubric.get("calibration")
    if not isinstance(cal, dict):
        return False
    return cal["sealed"] > 0 and cal["agreement"] >= cal["floor"]


def _first_defect(raw: Any, rubric: dict, item: str | None) -> tuple[str, str, list[dict]]:
    """(item, abstain reason or "", normalized criteria in rubric order)."""
    if not isinstance(raw, dict):
        return (item or "", "verdict-missing", [])
    raw_item = raw.get("item")
    if item is None:
        item = raw_item if isinstance(raw_item, str) else ""
    if not item:
        return ("", "missing-item", [])
    if raw_item != item:
        return (item, "item-mismatch", [])
    if not isinstance(raw.get("abstain"), bool):
        return (item, "malformed:abstain", [])
    if raw["abstain"]:
        why = raw.get("abstainReason")
        return (item, "judge:" + (why.strip() if isinstance(why, str) and why.strip() else "no reason given"), [])
    entries = raw.get("criteria")
    if not isinstance(entries, list):
        return (item, "malformed:criteria", [])
    wanted = [c["id"] for c in rubric["criteria"]]
    got: dict[str, dict] = {}
    for i, e in enumerate(entries):
        cid = e.get("id") if isinstance(e, dict) else None
        if not isinstance(cid, str):
            return (item, f"malformed-criterion:{i}", [])
        if cid in got:
            return (item, f"duplicate-criterion:{cid}", [])
        if cid not in wanted:
            return (item, f"unknown-criterion:{cid}", [])
        if not _is_unit(e.get("score")):
            return (item, f"bad-score:{cid}", [])
        if not isinstance(e.get("pass"), bool):
            return (item, f"bad-pass:{cid}", [])
        ev = e.get("evidence")
        if not isinstance(ev, str) or not ev.strip():
            return (item, f"bad-evidence:{cid}", [])
        got[cid] = {"id": cid, "score": e["score"], "pass": e["pass"], "evidence": ev}
    for cid in wanted:
        if cid not in got:
            return (item, f"missing-criterion:{cid}", [])
    return (item, "", [got[cid] for cid in wanted])


def decide(raw: Any, rubric: dict, *, item: str | None = None, decided_by: str = "judge") -> dict:
    """The full verdict for one judge (or command) report. Never returns a pass it cannot show.

    ``item`` is the id the caller asked about; when given, a report about any
    other item abstains. ``decided_by="command"`` marks a verdict whose criteria a
    command produced (score 1.0/0.0 from an exit code); it goes through the same
    checks, because a malformed command report is no more a pass than a judge's.
    """
    errs = check_rubric(rubric)
    if errs:
        raise ValueError("malformed rubric: " + "; ".join(errs))
    if decided_by not in DECIDERS:
        raise ValueError(f"decided_by must be one of {DECIDERS}, not {decided_by!r}")
    threshold = rubric["threshold"]
    item_id, reason, criteria = _first_defect(raw, rubric, item)
    if reason:
        outcome, score, criteria = "abstain", 0.0, []
    else:
        min_score = min(c["score"] for c in criteria)
        score = min_score
        outcome = "pass"
        if min_score < threshold:
            outcome = "fail"
        if not all(c["pass"] for c in criteria):
            outcome = "fail"
    return {
        "item": item_id,
        "rubric": rubric["id"],
        "decidedBy": decided_by,
        "criteria": criteria,
        "abstain": outcome == "abstain",
        "abstainReason": reason or None,
        "threshold": threshold,
        "score": score,
        "outcome": outcome,
        "calibrated": is_calibrated(rubric),
    }


def validate(verdict: Any) -> list[str]:
    """Every way ``verdict`` is not a well-formed, self-consistent verdict@1."""
    if not isinstance(verdict, dict):
        return ["verdict is not an object"]
    errs = []
    if set(verdict) != set(VERDICT_KEYS):
        missing = sorted(set(VERDICT_KEYS) - set(verdict))
        extra = sorted(set(verdict) - set(VERDICT_KEYS))
        errs.append(f"keys differ from verdict@1 (missing {missing}, extra {extra})")
        return errs
    v = verdict
    # Empty only on an abstain: a report with no item cannot name one.
    if not isinstance(v["item"], str) or (not v["item"] and v["outcome"] != "abstain"):
        errs.append("item is not a non-empty string")
    if not isinstance(v["rubric"], str) or not RUBRIC_ID.fullmatch(v["rubric"]):
        errs.append("rubric is not <plugin>-<name>@<int>")
    if v["decidedBy"] not in DECIDERS:
        errs.append(f"decidedBy is not one of {DECIDERS}")
    if v["outcome"] not in OUTCOMES:
        errs.append(f"outcome is not one of {OUTCOMES}")
    for k in ("abstain", "calibrated"):
        if not isinstance(v[k], bool):
            errs.append(f"{k} is not a boolean")
    for k in ("threshold", "score"):
        if not _is_unit(v[k]):
            errs.append(f"{k} is not a number in [0, 1]")
    crit = v["criteria"]
    ok_crit = isinstance(crit, list)
    if not ok_crit:
        errs.append("criteria is not a list")
    else:
        ids = set()
        for i, c in enumerate(crit):
            if (not isinstance(c, dict) or set(c) != set(CRITERION_KEYS)
                    or not isinstance(c["id"], str) or not _is_unit(c["score"])
                    or not isinstance(c["pass"], bool)
                    or not isinstance(c["evidence"], str) or not c["evidence"].strip()):
                errs.append(f"criterion {i} is not {{id, score in [0,1], pass: bool, evidence}}")
                ok_crit = False
            elif c["id"] in ids:
                errs.append(f"criterion {c['id']} is duplicated")
                ok_crit = False
            else:
                ids.add(c["id"])
    if errs:
        return errs
    if v["abstain"] != (v["outcome"] == "abstain"):
        errs.append("abstain disagrees with outcome")
    if v["abstain"]:
        if not isinstance(v["abstainReason"], str) or not v["abstainReason"]:
            errs.append("an abstain carries no abstainReason")
        if crit or v["score"] != 0:
            errs.append("an abstain carries criteria or a non-zero score")
        return errs
    if v["abstainReason"] is not None:
        errs.append("abstainReason is set on a verdict that did not abstain")
    if not crit:
        errs.append("a decided verdict has no criteria")
        return errs
    if ok_crit and v["score"] != min(c["score"] for c in crit):
        errs.append("score is not the minimum criterion score")
    should_pass = all(c["pass"] for c in crit) and v["score"] >= v["threshold"]
    if (v["outcome"] == "pass") != should_pass:
        errs.append(f"outcome {v['outcome']} does not follow from the criteria and threshold")
    return errs


def spot_check(verdicts: list[dict], k: int = 3) -> list[dict]:
    """A deterministic sample of ``k`` verdicts for a human to read: never random.

    Sorted by item id (stable), then a stride from first to last -- k=3 gives the
    first, the middle and the last. Fewer than ``k`` verdicts returns them all.
    """
    if not isinstance(k, int) or isinstance(k, bool) or k < 0:
        raise ValueError("k must be an int >= 0")
    ordered = sorted(verdicts, key=lambda v: v["item"])
    n = len(ordered)
    if n <= k:
        return ordered
    if k == 0:
        return []
    if k == 1:
        return [ordered[0]]
    return [ordered[(i * (n - 1)) // (k - 1)] for i in range(k)]


# --- selftest -----------------------------------------------------------------
# Each case is aimed at ONE branch: blank that branch and its case flips to a
# different outcome. In particular every malformed case has its present
# criteria all passing, so a missed defect turns it into a "pass" -- not into a
# "fail" that would hide the miss.

RUBRIC = {
    "id": "selftest-demo@1",
    "threshold": 0.7,
    "criteria": [
        {"id": "grounded", "question": "Does the cited location contain the claimed logic?"},
        {"id": "relevant", "question": "Does the claim bear on the item asked about?"},
    ],
}


def _crit(cid: str, score: Any = 0.9, ok: Any = True, evidence: Any = "file.py:12 shows it") -> dict:
    return {"id": cid, "score": score, "pass": ok, "evidence": evidence}


def _raw(*criteria: dict, item: Any = "item-a", abstain: Any = False, reason: Any = None) -> dict:
    return {"item": item, "criteria": list(criteria), "abstain": abstain, "abstainReason": reason}


G, R = "grounded", "relevant"
# (name, raw, item asked about, expected outcome, expected abstainReason)
CASES: list[tuple[str, Any, str | None, str, str | None]] = [
    ("all criteria pass", _raw(_crit(G), _crit(R)), "item-a", "pass", None),
    ("score exactly at threshold passes", _raw(_crit(G, 0.7), _crit(R)), "item-a", "pass", None),
    ("integer scores are numbers", _raw(_crit(G, 1), _crit(R, 1)), "item-a", "pass", None),
    ("min score below threshold fails", _raw(_crit(G, 0.69), _crit(R)), "item-a", "fail", None),
    ("a pass:false with a high score fails", _raw(_crit(G, 1.0, False), _crit(R)), "item-a", "fail", None),
    ("null verdict abstains", None, "item-a", "abstain", "verdict-missing"),
    ("a string verdict abstains", "pass", "item-a", "abstain", "verdict-missing"),
    ("no item anywhere abstains", _raw(_crit(G), _crit(R), item=None), None, "abstain", "missing-item"),
    ("a report about another item abstains", _raw(_crit(G), _crit(R), item="item-b"), "item-a", "abstain", "item-mismatch"),
    ("abstain that is not a boolean abstains", _raw(_crit(G), _crit(R), abstain="no"), "item-a", "abstain", "malformed:abstain"),
    ("the judge abstaining abstains", _raw(abstain=True, reason="cannot read file"), "item-a", "abstain", "judge:cannot read file"),
    ("criteria that is not a list abstains", {**_raw(), "criteria": "all good"}, "item-a", "abstain", "malformed:criteria"),
    ("a criterion with no id abstains", _raw(_crit(G), {"score": 0.9, "pass": True, "evidence": "x"}), "item-a", "abstain", "malformed-criterion:1"),
    ("a duplicated criterion abstains", _raw(_crit(G), _crit(G), _crit(R)), "item-a", "abstain", "duplicate-criterion:grounded"),
    ("an unknown criterion abstains", _raw(_crit(G), _crit(R), _crit("vibes")), "item-a", "abstain", "unknown-criterion:vibes"),
    ("a missing criterion abstains", _raw(_crit(G)), "item-a", "abstain", "missing-criterion:relevant"),
    ('score "0.9" (a string) abstains', _raw(_crit(G, "0.9"), _crit(R)), "item-a", "abstain", "bad-score:grounded"),
    ("score true (a bool) abstains", _raw(_crit(G, True), _crit(R)), "item-a", "abstain", "bad-score:grounded"),
    ("score above 1 abstains", _raw(_crit(G, 1.5), _crit(R)), "item-a", "abstain", "bad-score:grounded"),
    ('pass "no" (a string) abstains', _raw(_crit(G, 0.9, "no"), _crit(R)), "item-a", "abstain", "bad-pass:grounded"),
    ("pass 1 (an int) abstains", _raw(_crit(G, 0.9, 1), _crit(R)), "item-a", "abstain", "bad-pass:grounded"),
    ("empty evidence abstains", _raw(_crit(G, evidence="  "), _crit(R)), "item-a", "abstain", "bad-evidence:grounded"),
]


def _selftest_cases() -> list[str]:
    bad = []
    for name, raw, item, outcome, reason in CASES:
        got = decide(raw, RUBRIC, item=item)
        if got["outcome"] != outcome or got["abstainReason"] != reason:
            bad.append(f"{name}: expected {outcome}/{reason}, got {got['outcome']}/{got['abstainReason']}")
        problems = validate(got)
        if problems:
            bad.append(f"{name}: decide() produced an invalid verdict: {problems}")
    return bad


def _selftest_extras() -> list[str]:
    bad = []
    # score is the minimum, not an average (0.95 and 0.71 average 0.83).
    v = decide(_raw(_crit(G, 0.95), _crit(R, 0.71)), RUBRIC, item="item-a")
    if v["score"] != 0.71:
        bad.append(f"score is not the minimum criterion score: {v['score']}")
    # NaN parses from JSON in Python; it is not a number in [0, 1].
    if decide(_raw(_crit(G, float("nan")), _crit(R)), RUBRIC, item="item-a")["outcome"] != "abstain":
        bad.append("a NaN score did not abstain")
    # calibrated: derived from a record, never declared.
    if decide(_raw(_crit(G), _crit(R)), {**RUBRIC, "calibrated": True}, item="item-a")["calibrated"]:
        bad.append("a bare calibrated:true on the rubric was believed")
    cleared = {**RUBRIC, "calibration": {"sealed": 12, "agreement": 0.9, "floor": 0.8}}
    if not decide(_raw(_crit(G), _crit(R)), cleared, item="item-a")["calibrated"]:
        bad.append("a rubric that cleared its sealed floor is not calibrated")
    missed = {**RUBRIC, "calibration": {"sealed": 12, "agreement": 0.7, "floor": 0.8}}
    if decide(_raw(_crit(G), _crit(R)), missed, item="item-a")["calibrated"]:
        bad.append("a rubric below its sealed floor is calibrated")
    empty = {**RUBRIC, "calibration": {"sealed": 0, "agreement": 1.0, "floor": 0.8}}
    if decide(_raw(_crit(G), _crit(R)), empty, item="item-a")["calibrated"]:
        bad.append("a rubric with an empty sealed set is calibrated")
    # A malformed rubric is the author's bug: it raises, never abstains.
    for broken in ({**RUBRIC, "id": "nohyphen@1"}, {**RUBRIC, "threshold": "0.7"},
                   {**RUBRIC, "criteria": []}, {**RUBRIC, "threshold": True}):
        try:
            decide(_raw(_crit(G), _crit(R)), broken, item="item-a")
            bad.append(f"malformed rubric accepted: {broken}")
        except ValueError:
            pass
    # validate catches a verdict whose pass is not derived from its criteria.
    forged = {**decide(_raw(_crit(G, 0.5), _crit(R)), RUBRIC, item="item-a"), "outcome": "pass"}
    if not validate(forged):
        bad.append("validate accepted an outcome the threshold contradicts")
    averaged = {**decide(_raw(_crit(G, 0.95), _crit(R, 0.75)), RUBRIC, item="item-a"), "score": 0.85}
    if not validate(averaged):
        bad.append("validate accepted an averaged score")
    if not validate({**decide(None, RUBRIC, item="item-a"), "outcome": "pass", "abstain": False}):
        bad.append("validate accepted an abstain relabelled as pass")
    # spot_check: deterministic, first/middle/last by item id, independent of input order.
    vs = [decide(_raw(_crit(G), _crit(R), item=f"i{n:02d}"), RUBRIC) for n in (7, 3, 9, 1, 5)]
    picked = [v["item"] for v in spot_check(vs)]
    if picked != ["i01", "i05", "i09"]:
        bad.append(f"spot_check picked {picked}, expected first/middle/last [i01, i05, i09]")
    if [v["item"] for v in spot_check(list(reversed(vs)))] != picked:
        bad.append("spot_check depends on input order")
    if len(spot_check(vs[:2])) != 2 or spot_check(vs, 0) != []:
        bad.append("spot_check mishandles fewer than k or k=0")
    return bad


def selftest() -> int:
    bad = _selftest_cases() + _selftest_extras()
    for b in bad:
        print(f"FAIL {b}")
    print(f"judge_contract selftest: {len(CASES)} cases + extras, {len(bad)} failure(s)")
    return 1 if bad else 0


def _load(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: cannot read {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"ERROR: needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(description=(__doc__ or "judge verdict contract").splitlines()[0])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true", help="run the planted cases")
    mode.add_argument("--decide", metavar="RAW", help="decide a judge report (JSON file)")
    mode.add_argument("--validate", metavar="VERDICT", help="validate a decided verdict (JSON file)")
    mode.add_argument("--spot-check", metavar="VERDICTS", help="sample a JSON list of verdicts")
    p.add_argument("--rubric", help="rubric JSON file (with --decide)")
    p.add_argument("--item", help="the item id that was asked about (with --decide)")
    p.add_argument("--decided-by", choices=DECIDERS, default="judge")
    p.add_argument("--k", type=int, default=3)
    a = p.parse_args(argv)
    if a.selftest:
        return selftest()
    try:
        if a.decide:
            if not a.rubric:
                print("ERROR: --decide needs --rubric", file=sys.stderr)
                return 2
            v = decide(_load(a.decide), _load(a.rubric), item=a.item, decided_by=a.decided_by)
            print(json.dumps(v, indent=2))
            return 0 if v["outcome"] == "pass" else 1
        if a.validate:
            errs = validate(_load(a.validate))
            for e in errs:
                print(f"INVALID {e}")
            return 1 if errs else 0
        print(json.dumps(spot_check(_load(a.spot_check), a.k), indent=2))
        return 0
    except (ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
