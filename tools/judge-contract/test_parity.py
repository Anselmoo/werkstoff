#!/usr/bin/env python3
"""Hold the JS block (verdict.inline.js) and judge_contract.py to identical verdicts.

Three parts, all run every time -- an instrument that is never shown to fail is
not trusted here:

1. PARITY. Every case is decided by ``judge_contract.decide`` and by the JS
   ``decideVerdict`` evaluated the way the Workflow runtime evaluates a script
   body (an async function body; ``require``/``process``/``module`` shadowed;
   ``Math.random`` and ``Date.now`` poisoned so the block cannot use them). The
   full verdict objects are compared as parsed JSON, so JS ``1`` equals Python
   ``1.0`` but every other difference is a mismatch. ``spotCheck`` is compared
   the same way over lists of 0..7 verdicts and k in 0..5.
2. PARITY CAN FAIL. The threshold comparison is flipped (``<`` to ``<=``) on the
   JS side, then on the Python side, plus every other JS decision branch blanked,
   verdict@2's undecidable branches included; each sabotaged copy must produce a
   mismatch. The case set includes a score exactly at threshold, which is the only
   case that tells ``<`` from ``<=``, and an undecidable criterion whose keys are
   absent rather than null, which is the only case that tells ``=== null`` from
   ``== null``.
3. THE PYTHON SELFTEST CAN FAIL. Each decision branch of judge_contract.py is
   blanked on a scratch copy and ``--selftest`` must exit non-zero.

A sabotage whose target text is not found exactly once exits 2: a replace that
hits nothing measures nothing.

Exit 0 all hold; 1 a mismatch or an undetected sabotage; 2 could not run.
Needs ``node`` on PATH. STDLIB ONLY.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

MIN_PYTHON = (3, 11)
HERE = Path(__file__).resolve().parent
PY_SRC = HERE / "judge_contract.py"
JS_SRC = HERE / "verdict.inline.js"
SCHEMA = HERE / "verdict.schema.json"
START = "// judge-contract:start verdict@2"
END = "// judge-contract:end"

# Values arrive on stdin, never interpolated into the script.
NODE = r"""
const fs = require('fs')
const input = JSON.parse(fs.readFileSync(0, 'utf8'))
Math.random = () => { throw new Error('Math.random is forbidden in a workflow') }
Date.now = () => { throw new Error('Date.now is forbidden in a workflow') }
const AsyncFunction = (async () => {}).constructor
const body = input.block + '\nreturn { decideVerdict, spotCheck, JUDGE_VERDICT_SCHEMA }'
new AsyncFunction('require', 'process', 'module', 'exports', 'Buffer', body)()
  .then((api) => {
    const decided = input.cases.map((c) => {
      try { return api.decideVerdict(c.raw, c.rubric, c.opts) } catch (e) { return { error: true } }
    })
    const spot = input.spot.map((s) => {
      try { return api.spotCheck(s.verdicts, s.k).map((v) => v.item) } catch (e) { return { error: true } }
    })
    process.stdout.write(JSON.stringify({ decided, spot, schema: api.JUDGE_VERDICT_SCHEMA }))
  })
  .catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(2) })
"""


class CannotRun(Exception):
    pass


def load_module(source: str, name: str = "judge_contract_under_test") -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__file__ = str(PY_SRC)
    sys.modules[name] = mod  # dataclass/typing lookups resolve through sys.modules
    exec(compile(source, str(PY_SRC), "exec"), mod.__dict__)
    return mod


def extract_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if ln.rstrip("\r\n") == START]
    ends = [i for i, ln in enumerate(lines) if ln.rstrip("\r\n") == END]
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        raise CannotRun(f"{JS_SRC.name}: need exactly one {START!r} ... {END!r} block")
    return "".join(lines[starts[0]: ends[0] + 1])


def sabotage(text: str, old: str, new: str, where: str) -> str:
    n = text.count(old)
    if n != 1:
        raise CannotRun(f"sabotage target in {where} found {n} times, not once: {old!r}")
    return text.replace(old, new)


def build_cases(jc: types.ModuleType) -> tuple[list[dict], list[dict]]:
    rubric = jc.RUBRIC
    cases = [{"raw": raw, "rubric": rubric, "opts": {"item": item}} for _, raw, item, _, _ in jc.CASES]
    crit, raw_of = jc._crit, jc._raw
    ok = raw_of(crit("grounded"), crit("relevant"))
    cases += [
        {"raw": raw_of(crit("grounded", 0.95), crit("relevant", 0.71)), "rubric": rubric, "opts": {"item": "item-a"}},
        {"raw": ok, "rubric": rubric, "opts": {}},  # item taken from the report
        {"raw": ok, "rubric": rubric, "opts": {"item": "item-a", "decidedBy": "command"}},
        {"raw": ok, "rubric": rubric, "opts": {"item": "item-a", "decidedBy": "model"}},  # raises
        {"raw": raw_of(abstain=True, reason="   "), "rubric": rubric, "opts": {"item": "item-a"}},
        {"raw": {**ok, "criteria": [crit("grounded"), "x"]}, "rubric": rubric, "opts": {"item": "item-a"}},
        {"raw": [ok], "rubric": rubric, "opts": {"item": "item-a"}},
        {"raw": ok, "rubric": {**rubric, "threshold": 0.9}, "opts": {"item": "item-a"}},
        {"raw": ok, "rubric": {**rubric, "threshold": 0.91}, "opts": {"item": "item-a"}},
        {"raw": ok, "rubric": {**rubric, "calibrated": True}, "opts": {"item": "item-a"}},
        # verdict@2: a fail's score over two decided criteria beside an undecidable;
        # a JS-only undefined (the key absent) is not a null.
        {"raw": raw_of(crit("grounded", 0.9), crit("relevant", 0.3, False)), "rubric": rubric, "opts": {"item": "item-a"}},
        {"raw": raw_of(crit("grounded"), {"id": "relevant", "score": None, "evidence": "x"}), "rubric": rubric,
         "opts": {"item": "item-a"}},
        {"raw": raw_of(crit("grounded"), {"id": "relevant", "pass": None, "evidence": "x"}), "rubric": rubric,
         "opts": {"item": "item-a"}},
    ]
    for cal in ({"sealed": 12, "agreement": 0.9, "floor": 0.8}, {"sealed": 12, "agreement": 0.7, "floor": 0.8},
                {"sealed": 0, "agreement": 1.0, "floor": 0.8}, {"sealed": 12.0, "agreement": 0.8, "floor": 0.8},
                {"sealed": 1.5, "agreement": 0.9, "floor": 0.8}, {"sealed": True, "agreement": 0.9, "floor": 0.8}):
        cases.append({"raw": ok, "rubric": {**rubric, "calibration": cal}, "opts": {"item": "item-a"}})
    for broken in ({**rubric, "id": "nohyphen@1"}, {**rubric, "id": "a-b@01"}, {**rubric, "threshold": "0.7"},
                   {**rubric, "threshold": True}, {**rubric, "threshold": 1.2}, {**rubric, "criteria": []},
                   {**rubric, "criteria": [{"id": "Bad Id", "question": "q"}]},
                   {**rubric, "criteria": [{"id": "a", "question": "q"}, {"id": "a", "question": "q"}]},
                   {**rubric, "criteria": [{"id": "a", "question": " "}]}, None):
        cases.append({"raw": ok, "rubric": broken, "opts": {"item": "item-a"}})
    verdicts = [jc.decide(raw_of(crit("grounded"), crit("relevant"), item=f"i{n}"), rubric)
                for n in ("07", "03", "09", "01", "05", "02", "08")]
    spot = [{"verdicts": verdicts[:n], "k": k} for n in range(8) for k in range(6)]
    spot += [{"verdicts": verdicts, "k": -1}, {"verdicts": verdicts, "k": 1.5}]
    return cases, spot


def py_side(jc: types.ModuleType, cases: list[dict], spot: list[dict]) -> dict:
    decided = []
    for c in cases:
        try:
            decided.append(jc.decide(c["raw"], c["rubric"], item=c["opts"].get("item"),
                                     decided_by=c["opts"].get("decidedBy", "judge")))
        except ValueError:
            decided.append({"error": True})
    picks = []
    for s in spot:
        try:
            picks.append([v["item"] for v in jc.spot_check(s["verdicts"], s["k"])])
        except ValueError:
            picks.append({"error": True})
    return json.loads(json.dumps({"decided": decided, "spot": picks}))


def js_side(block: str, cases: list[dict], spot: list[dict]) -> dict:
    node = shutil.which("node")
    if not node:
        raise CannotRun("node is not on PATH; the JS side cannot be evaluated")
    payload = json.dumps({"block": block, "cases": cases, "spot": spot})
    r = subprocess.run([node, "-e", NODE], input=payload, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise CannotRun(f"node exited {r.returncode}: {r.stderr.strip()[:500]}")
    return json.loads(r.stdout)


def mismatches(py: dict, js: dict, cases: list[dict]) -> list[str]:
    out = []
    for i, (a, b) in enumerate(zip(py["decided"], js["decided"], strict=True)):
        if a != b:
            out.append(f"decide case {i} ({json.dumps(cases[i]['raw'])[:80]}): python {a} != js {b}")
    for i, (a, b) in enumerate(zip(py["spot"], js["spot"], strict=True)):
        if a != b:
            out.append(f"spot case {i}: python {a} != js {b}")
    return out


def check_schema_shapes(jc: types.ModuleType, js_schema: dict) -> list[str]:
    """verdict.schema.json and the judge schema must name the keys judge_contract uses."""
    bad = []
    full = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if sorted(full.get("required", [])) != sorted(jc.VERDICT_KEYS):
        bad.append(f"{SCHEMA.name} required {full.get('required')} != VERDICT_KEYS {list(jc.VERDICT_KEYS)}")
    if sorted(full.get("properties", {})) != sorted(jc.VERDICT_KEYS):
        bad.append(f"{SCHEMA.name} properties differ from VERDICT_KEYS")
    item_schema = full.get("properties", {}).get("criteria", {}).get("items", {})
    if sorted(item_schema.get("required", [])) != sorted(jc.CRITERION_KEYS):
        bad.append(f"{SCHEMA.name} criterion required differs from CRITERION_KEYS")
    judge_keys = {"item", "criteria", "abstain", "abstainReason"}
    if set(js_schema.get("required", [])) != judge_keys or set(js_schema.get("properties", {})) != judge_keys:
        bad.append("JUDGE_VERDICT_SCHEMA does not require exactly {item, criteria, abstain, abstainReason}")
    js_item = js_schema.get("properties", {}).get("criteria", {}).get("items", {})
    if sorted(js_item.get("required", [])) != sorted(jc.CRITERION_KEYS):
        bad.append("JUDGE_VERDICT_SCHEMA criterion required differs from CRITERION_KEYS")
    return bad


# (where, old, new): each blanks one branch of the JS block; parity must catch it.
JS_SABOTAGE = [
    ("threshold comparison flipped", "c.score < threshold)", "c.score <= threshold)"),
    ("pass false ignored", "decided.some((c) => !c.pass || c.score", "decided.some((c) => c.score"),
    ("fail does not dominate an undecidable", "if (failed) {", "if (failed && !undecided.length) {"),
    ("undecidable branch removed", "const undecidable = e.score === null && e.pass === null", "const undecidable = false"),
    ("a half-null read as undecidable", "e.score === null && e.pass === null", "(e.score === null || e.pass === null)"),
    ("an absent key read as undecidable", "e.score === null && e.pass === null", "e.score == null && e.pass == null"),
    ("undecidable ids out of rubric order", "filter((c) => c.pass === null).map((c) => c.id)",
     "filter((c) => c.pass === null).map((c) => c.id).reverse()"),
    ("fail scored over every criterion", "outcome = 'fail'\n      score = Math.min(...decided.map",
     "outcome = 'fail'\n      score = Math.min(...criteria.map"),
    ("bool score accepted", "const isNum = (v) => typeof v === 'number'", "const isNum = (v) => typeof v === 'number' || typeof v === 'boolean'"),
    ("unknown criterion accepted", "if (!wanted.includes(cid)) return", "if (false) return"),
    ("missing criterion accepted", "if (!got.has(cid)) return [item, `missing", "if (false) return [item, `missing"),
    ("average instead of minimum", "outcome = 'pass'\n      score = Math.min(...decided.map((c) => c.score))",
     "outcome = 'pass'\n      score = decided.reduce((s, c) => s + c.score, 0) / decided.length"),
    ("spot-check stride removed", "return Array.from({ length: k }, (_, i) => ordered[Math.floor((i * (n - 1)) / (k - 1))])",
     "return ordered.slice(0, k)"),
]
PY_SABOTAGE = [
    ("threshold comparison flipped", 'c["score"] < threshold for c in decided', 'c["score"] <= threshold for c in decided'),
    ("fail does not dominate an undecidable", "        if failed:\n", "        if failed and not undecided:\n"),
]

# Each blanks one decision branch of judge_contract.py; --selftest must go red.
SELFTEST_SABOTAGE = [
    ("verdict-missing", "    if not isinstance(raw, dict):\n        return (item or", "    if False:\n        return (item or"),
    ("missing-item", "    if not item:\n", "    if False:\n"),
    ("item-mismatch", "if raw_item != item:", "if False:"),
    ("malformed:abstain", 'if not isinstance(raw.get("abstain"), bool):', "if False:"),
    ("judge abstained", '    if raw["abstain"]:', "    if False:"),
    ("malformed:criteria", "if not isinstance(entries, list):", "if False:"),
    ("malformed-criterion", "if not isinstance(cid, str):\n            return", "if False:\n            return"),
    ("duplicate-criterion", "if cid in got:", "if False:"),
    ("unknown-criterion", "if cid not in wanted:", "if False:"),
    ("bad-score", 'if not undecidable and not _is_unit(e.get("score")):', "if False:"),
    ("bad-pass", 'if not undecidable and not isinstance(e.get("pass"), bool):', "if False:"),
    ("bad-evidence", "if not isinstance(ev, str) or not ev.strip():", "if False:"),
    ("missing-criterion", "        if cid not in got:", "        if False:"),
    ("below threshold", 'failed = any(not c["pass"] or c["score"] < threshold for c in decided)',
     'failed = any(not c["pass"] for c in decided)'),
    ("pass false", 'failed = any(not c["pass"] or c["score"] < threshold for c in decided)',
     'failed = any(c["score"] < threshold for c in decided)'),
    ("minimum, not average", 'outcome, score = "pass", min(c["score"] for c in decided)',
     'outcome, score = "pass", sum(c["score"] for c in decided) / len(decided)'),
    ("fail scored at its minimum", 'outcome, score = "fail", min(c["score"] for c in decided)',
     'outcome, score = "fail", max(c["score"] for c in decided)'),
    ("fail dominates an undecidable", "        if failed:\n", "        if failed and not undecided:\n"),
    ("undecidable branch", 'undecidable = "score" in e and "pass" in e and e["score"] is None and e["pass"] is None',
     "undecidable = False"),
    ("undecidable needs both nulls", 'e["score"] is None and e["pass"] is None', '(e["score"] is None or e["pass"] is None)'),
    ("undecidable needs both keys", 'undecidable = "score" in e and "pass" in e and e["score"] is None and e["pass"] is None',
     'undecidable = e.get("score") is None and e.get("pass") is None'),
    ("undecidable ids in rubric order", 'undecided = [c["id"] for c in criteria if c["pass"] is None]',
     'undecided = [c["id"] for c in criteria if c["pass"] is None][::-1]'),
    ("undecidable abstain keeps its criteria", 'outcome, score, reason = "abstain", 0.0, "undecidable:" + ",".join(undecided)',
     'outcome, score, reason, criteria = "abstain", 0.0, "undecidable:" + ",".join(undecided), []'),
    ("bool is not a number", "isinstance(v, (int, float)) and not isinstance(v, bool)", "isinstance(v, (int, float))"),
    ("unit range", "_is_number(v) and 0 <= v <= 1", "_is_number(v)"),
    ("calibration derived", 'return cal["sealed"] > 0 and cal["agreement"] >= cal["floor"]', "return True"),
    ("spot-check stride", "return [ordered[(i * (n - 1)) // (k - 1)] for i in range(k)]", "return ordered[:k]"),
    ("spot-check sort", 'sorted(verdicts, key=lambda v: v["item"])', "list(verdicts)"),
    ("validate threshold", 'failing = any(not c["pass"] or c["score"] < v["threshold"] for c in decided)',
     'failing = any(not c["pass"] for c in decided)'),
    ("validate minimum", 'if ok_crit and v["score"] != min(c["score"] for c in decided):', "if False:"),
    ("validate undecidable shape", '(c["score"] is None and c["pass"] is None)', '(c["score"] is None or c["pass"] is None)'),
    ("validate fail dominates", "            if failing:\n                errs.append(\"an abstain whose", "            if False:\n                errs.append(\"an abstain whose"),
    ("validate undecidable needs a null", "            if not nulls:\n", "            if False:\n"),
    ("validate undecidable names the nulls", 'elif why != "undecidable:" + ",".join(nulls):', "elif False:"),
    ("validate report abstain has no criteria", "        elif crit:\n", "        elif False:\n"),
    ("validate abstain score", '        if v["score"] != 0:\n', "        if False:\n"),
    ("validate pass has no null", 'if v["outcome"] == "pass" and (nulls or failing):', 'if v["outcome"] == "pass" and failing:'),
    ("validate fail has a failure", 'if v["outcome"] == "fail" and not failing:', "if False:"),
    ("validate needs a decided criterion", "    if not decided:\n        errs.append", "    if False:\n        errs.append"),
]


def selftest_goes_red(py_text: str) -> list[str]:
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "judge_contract.py"
        for name, old, new in SELFTEST_SABOTAGE:
            target.write_text(sabotage(py_text, old, new, PY_SRC.name), encoding="utf-8")
            r = subprocess.run([sys.executable, "-I", str(target), "--selftest"],
                               capture_output=True, text=True, check=False)
            if r.returncode == 0:
                bad.append(f"selftest stayed green with branch blanked: {name}")
    return bad


def main() -> int:
    try:
        py_text = PY_SRC.read_text(encoding="utf-8")
        block = extract_block(JS_SRC.read_text(encoding="utf-8"))
        jc = load_module(py_text)
        cases, spot = build_cases(jc)
        py = py_side(jc, cases, spot)
        js = js_side(block, cases, spot)
        failures = mismatches(py, js, cases) + check_schema_shapes(jc, js["schema"])
        print(f"parity: {len(cases)} decide cases, {len(spot)} spot-check cases, {len(failures)} failure(s)")

        caught = 0
        for name, old, new in JS_SABOTAGE:
            if mismatches(py, js_side(sabotage(block, old, new, JS_SRC.name), cases, spot), cases):
                caught += 1
            else:
                failures.append(f"JS sabotage not detected by parity: {name}")
        for name, old, new in PY_SABOTAGE:
            broken = load_module(sabotage(py_text, old, new, PY_SRC.name), "judge_contract_sabotaged")
            if mismatches(py_side(broken, cases, spot), js, cases):
                caught += 1
            else:
                failures.append(f"Python sabotage not detected by parity: {name}")
        print(f"parity sabotage: {caught}/{len(JS_SABOTAGE) + len(PY_SABOTAGE)} detected")

        red = selftest_goes_red(py_text)
        failures += red
        print(f"selftest sabotage: {len(SELFTEST_SABOTAGE) - len(red)}/{len(SELFTEST_SABOTAGE)} branches go red when blanked")
    except (CannotRun, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for f in failures:
        print(f"FAIL {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    if sys.version_info < MIN_PYTHON:
        print(f"ERROR: needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}", file=sys.stderr)
        sys.exit(2)
    sys.exit(main())
