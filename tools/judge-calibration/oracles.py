"""Command oracles: for every fixture, a program that DERIVES the known answer.

An answer key written from intuition is an uncalibrated oracle. So ``answers.json`` is never
trusted on its own: ``check_oracle`` recomputes each case's expected outcome from the case's
own files and fails when the two differ. The recomputation runs commands (the referee's
acceptance checks, a CSS parse, the tribunal's probes) the way ``test/plugins/
verify-contested-fixture.py`` proves its fixture is still contested.

  referee   apply the candidate to a copy of the base tree, run each acceptance command.
            All exit 0 -> pass. Any non-zero -> fail. A case marked with ``variants`` is one
            whose acceptance outcome depends on a file the diff does not show: the commands
            are run against each variant of that file, and the case is an abstain exactly when
            the variants disagree (the diff alone cannot decide it).
  decode    resolve the cited location in the staged reference, re-measure it, compare the
            values and then the stated relation. The ladder is the agent's own.
  tribunal  run a probe per contract criterion inside the post-fix tree. Exit 0 = holds,
            1 = violated, 3 = cannot be decided in this environment. Any 1 -> red; else any
            3 -> unknown; else green.

``selftest_problems`` sabotages each oracle (breaks the candidate, edits a measured value,
breaks a fix) and requires the verdict to change, so an oracle that always says pass is caught.
"""

from __future__ import annotations

import copy
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURES = ROOT / "test" / "judge-calibration"
TIMEOUT = 30


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def udiff(base: dict[str, str], cand: dict[str, str]) -> str:
    out = []
    for path in sorted(set(base) | set(cand)):
        a, b = base.get(path), cand.get(path)
        if a == b:
            continue
        body = list(difflib.unified_diff(
            (a or "").splitlines(keepends=True), (b or "").splitlines(keepends=True),
            f"a/{path}" if a is not None else "/dev/null", f"b/{path}" if b is not None else "/dev/null", n=200))
        out.append(f"diff --git a/{path} b/{path}\n" + "".join(body))
    return "".join(out)


def write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def run(cmd: str | list[str], cwd: Path) -> int:
    """Exit code of ``cmd`` run in ``cwd``. A string goes through ``sh -c`` (the referee's
    acceptance commands are shell commands); a list is exec'd directly, so a multi-line
    Python snippet reaches the interpreter with its newlines intact."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": cwd.as_posix()}
    argv = ["sh", "-c", cmd] if isinstance(cmd, str) else cmd
    try:
        r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return 124
    return r.returncode


# ------------------------------------------------------------------------------ referee

def referee_truth(base: dict[str, str], cand: dict[str, str], acceptance: list[dict],
                  variants: list[dict[str, str]]) -> str:
    def exits(tree_files: dict[str, str]) -> list[int]:
        with tempfile.TemporaryDirectory() as td:
            write_tree(Path(td), tree_files)
            return [run(c["check"], Path(td)) for c in acceptance]

    if variants:
        runs = [exits({**cand, **v}) for v in variants]
        if any(r != runs[0] for r in runs[1:]):
            return "abstain"
        raise ValueError("a case with variants whose acceptance outcome does not depend on them")
    return "pass" if all(x == 0 for x in exits(cand)) else "fail"


def _check_referee(answers: dict[str, dict]) -> list[str]:
    probs = []
    for cid, a in sorted(answers.items()):
        d = FIXTURES / "referee"
        case = load_json(d / "cases" / cid / "case.json")
        orc = load_json(d / "oracle" / f"{cid}.json")
        if case["diff"] != udiff(orc["base"], orc["candidate"]):
            probs.append(f"{cid}: case.json diff is not the diff of the oracle's base and candidate")
        touched = sorted(p for p in set(orc["base"]) | set(orc["candidate"]) if orc["base"].get(p) != orc["candidate"].get(p))
        if case["filesTouched"] != touched:
            probs.append(f"{cid}: filesTouched {case['filesTouched']} is not {touched}")
        for k in case["checks"]:
            crit = next((c for c in case["acceptance"] if c["id"] == k["id"]), None)
            if crit is None or crit["check"] != k["command"]:
                probs.append(f"{cid}: reported check {k['id']} is not the criterion's own command")
        try:
            truth = referee_truth(orc["base"], orc["candidate"], case["acceptance"], orc["variants"])
        except ValueError as exc:
            probs.append(f"{cid}: {exc}")
            continue
        if truth != a["expected"]:
            probs.append(f"{cid}: the commands say {truth}, answers.json says {a['expected']}")
    return probs


# ------------------------------------------------------------------------------ decode

REM = 16.0


def prose(claim: dict) -> dict[str, str]:
    """The card text a decoder would have written, derived from the structured claim so the two
    cannot drift. Items are (selector, property, value, unit)."""
    items = claim["items"]
    sels = " ".join(dict.fromkeys(i["selector"] for i in items))
    props = ", ".join(dict.fromkeys(i["property"] for i in items))
    a, b = claim["lines"]
    rel = claim["relation"]
    if rel["kind"] == "ratio":
        rtext = f"modular scale: each step is {rel['value']} times the one before it"
    else:
        rtext = f"{rel['value']:g}px base grid: every value is a multiple of {rel['value']:g}px"
    return {
        "source": f"{{ROOT}}/{claim['file']}, selectors {sels}, property {props}, lines {a}-{b}",
        "measured": "; ".join(f"{i['selector']} {i['property']}: {i['value']:g}{i['unit']}" for i in items),
        "relation": rtext,
        "reliability": claim["reliability"],
    }


def _to_px(value: float, unit: str) -> float:
    return value * REM if unit == "rem" else value


def _blocks(css: str) -> list[tuple[str, int, dict[str, str]]]:
    """(selector, line of the selector, {property: raw value}) for each flat rule."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel = m.group(1).strip()
        line = css.count("\n", 0, m.start(1) + (len(m.group(1)) - len(m.group(1).lstrip()))) + 1
        props = {}
        for decl in m.group(2).split(";"):
            if ":" in decl:
                k, v = decl.split(":", 1)
                props.setdefault(k.strip(), v.strip())
        out.append((sel, line, props))
    return out


def _resolve(raw: str, root_vars: dict[str, str]) -> tuple[float, str] | None:
    raw = raw.strip()
    m = re.fullmatch(r"var\((--[\w-]+)\)", raw)
    if m:
        if m.group(1) not in root_vars:
            return None
        raw = root_vars[m.group(1)]
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)(px|rem)", raw)
    return (float(m.group(1)), m.group(2)) if m else None


def decode_truth(claim: dict, files: dict[str, str]) -> str:
    """The decode-referee's own ladder: does the citation resolve, do the values reproduce,
    does the stated relation follow."""
    css = files.get(claim["file"])
    a, b = claim["lines"]
    if css is None or len(css.splitlines()) < b:
        return "cannot_reproduce"
    blocks = _blocks(css)
    root_vars: dict[str, str] = {}
    for sel, _, props in blocks:
        if sel == ":root":
            root_vars.update({k: v for k, v in props.items() if k.startswith("--")})
    measured = []
    for it in claim["items"]:
        hit = next((p for s, ln, p in blocks if s == it["selector"] and a <= ln <= b), None)
        if hit is None or it["property"] not in hit:
            return "cannot_reproduce"
        got = _resolve(hit[it["property"]], root_vars)
        if got is None:
            return "cannot_reproduce"
        measured.append(_to_px(*got))
    claimed = [_to_px(i["value"], i["unit"]) for i in claim["items"]]
    if any(abs(m - c) > 0.05 for m, c in zip(measured, claimed, strict=True)):
        return "not_reproduced"
    rel = claim["relation"]
    if rel["kind"] == "ratio":
        pairs = list(zip(measured, measured[1:], strict=False))
        ok = all(abs(max(x, y) / min(x, y) - rel["value"]) / rel["value"] <= 0.03 for x, y in pairs)
    else:
        ok = all(abs(m / rel["value"] - round(m / rel["value"])) < 1e-6 for m in measured)
    return "reproduced" if ok else "reproduced_different_relation"


def _check_decode(answers: dict[str, dict]) -> list[str]:
    probs = []
    d = FIXTURES / "decode"
    for cid, a in sorted(answers.items()):
        case = load_json(d / "cases" / cid / "case.json")
        claim = load_json(d / "oracle" / f"{cid}.json")
        files = {p.relative_to(d / "cases" / cid / "ref").as_posix(): p.read_text(encoding="utf-8")
                 for p in (d / "cases" / cid / "ref").rglob("*") if p.is_file()}
        want = prose(claim)
        for k in ("source", "measured", "relation", "reliability"):
            if case[k] != want[k]:
                probs.append(f"{cid}: case.json {k} is not derived from the structured claim")
        truth = decode_truth(claim, files)
        if truth != a["nativeExpected"]:
            probs.append(f"{cid}: the measurement says {truth}, answers.json says {a['nativeExpected']}")
        mapped = {"reproduced": "pass", "cannot_reproduce": "abstain"}.get(truth, "fail")
        if mapped != a["expected"]:
            probs.append(f"{cid}: mapped outcome {mapped} differs from expected {a['expected']}")
    return probs


# ------------------------------------------------------------------------------ tribunal

def tribunal_truth(tree: dict[str, str], probes: dict[str, str]) -> tuple[str, dict[str, int]]:
    codes = {}
    with tempfile.TemporaryDirectory() as td:
        write_tree(Path(td), tree)
        for cid, snippet in probes.items():
            codes[cid] = run([sys.executable, "-B", "-c", snippet], Path(td))
    if any(c not in (0, 3) for c in codes.values()):
        return "red", codes
    if any(c == 3 for c in codes.values()):
        return "unknown", codes
    return "green", codes


def _tree_of(path: Path) -> dict[str, str]:
    return {p.relative_to(path).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(path.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def _check_tribunal(answers: dict[str, dict]) -> list[str]:
    probs = []
    d = FIXTURES / "tribunal"
    for cid, a in sorted(answers.items()):
        src = d / "cases" / cid
        contract = load_json(src / "contract.json")
        orc = load_json(d / "oracle" / f"{cid}.json")
        tree = _tree_of(src / "tree")
        if (src / "fix.diff").read_text(encoding="utf-8") != udiff(orc["base"], tree):
            probs.append(f"{cid}: fix.diff is not the diff of the oracle's base and the staged tree")
        if sorted(orc["probes"]) != sorted(c["id"] for c in contract["criteria"]):
            probs.append(f"{cid}: probes do not cover exactly the contract's criteria")
            continue
        truth, codes = tribunal_truth(tree, orc["probes"])
        want = {"green": "pass", "red": "fail", "unknown": "abstain"}[truth]
        if want != a["expected"] or truth != a["nativeExpected"]:
            probs.append(f"{cid}: the probes say {truth} {codes}, answers.json says "
                         f"{a['nativeExpected']}/{a['expected']}")
        for needle in ("expected", "answer", "EXPECTED", "known-"):
            if any(needle in t for t in tree.values()) and needle in ("EXPECTED", "known-"):
                probs.append(f"{cid}: a staged file names the answer ({needle!r})")
    return probs


def check_oracle(judge: str, answers: dict[str, dict]) -> list[str]:
    return {"referee": _check_referee, "decode": _check_decode, "tribunal": _check_tribunal}[judge](answers)


# ------------------------------------------------------------------------------ sabotage

def selftest_problems() -> list[str]:
    """Each oracle must change its mind when the thing it measures is broken."""
    bad = []
    d = FIXTURES
    # referee: break a passing candidate -> fail; make a failing candidate right -> pass.
    orc = load_json(d / "referee" / "oracle" / "tune-01.json")
    case = load_json(d / "referee" / "cases" / "tune-01" / "case.json")
    if referee_truth(orc["base"], orc["candidate"], case["acceptance"], []) != "pass":
        bad.append("referee oracle: tune-01 is not a pass before sabotage")
    broken = copy.deepcopy(orc["candidate"])
    broken["util.py"] = broken["util.py"].replace("max(lo, min(x, hi))", "min(lo, max(x, hi))")
    if referee_truth(orc["base"], broken, case["acceptance"], []) != "fail":
        bad.append("referee oracle: a broken clamp still passed")
    # abstain: collapse the two variants into one -> the oracle must refuse, not say abstain.
    orc9 = load_json(d / "referee" / "oracle" / "sealed-09.json")
    case9 = load_json(d / "referee" / "cases" / "sealed-09" / "case.json")
    try:
        referee_truth(orc9["base"], orc9["candidate"], case9["acceptance"], [orc9["variants"][0], orc9["variants"][0]])
        bad.append("referee oracle: identical variants were called an abstain")
    except ValueError:
        pass
    # decode: change a measured value -> not_reproduced; remove the cited selector -> cannot_reproduce.
    claim = load_json(d / "decode" / "oracle" / "tune-01.json")
    files = {p.relative_to(d / "decode" / "cases" / "tune-01" / "ref").as_posix(): p.read_text(encoding="utf-8")
             for p in (d / "decode" / "cases" / "tune-01" / "ref").rglob("*") if p.is_file()}
    if decode_truth(claim, files) != "reproduced":
        bad.append("decode oracle: tune-01 does not reproduce before sabotage")
    f = {k: re.sub(r"(\d+(?:\.\d+)?)(rem|px)", lambda m: f"{float(m.group(1)) + 1:g}{m.group(2)}", v, count=1)
         for k, v in files.items()}
    if decode_truth(claim, f) == "reproduced":
        bad.append("decode oracle: a changed value still reproduced")
    g = {k: v.replace(claim["items"][0]["selector"], ".gone") for k, v in files.items()}
    if decode_truth(claim, g) != "cannot_reproduce":
        bad.append("decode oracle: a missing selector did not cannot_reproduce")
    # tribunal: break a green case -> red.
    src = d / "tribunal" / "cases" / "tune-02"
    orc_t = load_json(d / "tribunal" / "oracle" / "tune-02.json")
    tree = _tree_of(src / "tree")
    if tribunal_truth(tree, orc_t["probes"])[0] != "green":
        bad.append("tribunal oracle: tune-02 is not green before sabotage")
    first = next(iter(sorted(p for p in tree if p.endswith(".py"))))
    spoiled = {**tree, first: tree[first] + "\nraise RuntimeError('sabotage')\n"}
    if tribunal_truth(spoiled, orc_t["probes"])[0] != "red":
        bad.append("tribunal oracle: a sabotaged fix stayed green")
    return bad
