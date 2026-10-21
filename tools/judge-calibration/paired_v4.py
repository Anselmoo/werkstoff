#!/usr/bin/env python3
"""The fourth paired tribunal measurement: andon's four-role tribunal (arm A) against one
verdict@2 contract judge (arm B), on items whose defects nobody in this repo planted.

Runs 2 and 3 (paired_v2.py, paired_v3.py) were each kept by one defect the item author left in
a green (v2-16, v3-10), and run 3's planted defects hit the CEILING in both arms. Whether
adversarial search reliably finds defects nobody planted cannot be asked of items whose author
also wrote the key. Here every item is a real bug from a public Python repository, keyed by its
own fix commit: the file at the fix's parent is a red, the file at the fix commit its green twin.

Everything that decides the result is fixed here, and committed, BEFORE the run:

  * how the items were chosen: paired-v4/selection.json, committed (a5954d6) before any candidate
    was examined. An admissibility filter, a scan order (newest author date first, inside a
    window after the model's training cutoff, so neither arm can recall a fix), and a log of
    every candidate examined (selection-log.json) with the first rule it failed. The first 8
    admitted are the 8 pairs. How subtle a defect looks was never looked at.
  * the items: paired-v4/cases/, 16 cases in 8 matched pairs. The twins of a pair share one
    contract word for word and one base (the parent with the contract's callables stubbed), so
    the diff an arm is shown is the implementation, never the fix. Their trees are the upstream
    files under a recorded, mechanical transform (a neutral module name, the project's name,
    issue numbers and URLs replaced), which check re-applies to the committed upstream originals
    (paired-v4/upstream/, never staged) whose git blob ids are recorded.
  * the keys and probes: c1's probe is the fix commit's own regression test, transcribed; the
    other criteria's probes are upstream tests that already existed at the parent. Each twin is
    the other's control, so c1 is calibrated both ways by history alone. paired_v3.calibrate runs
    every probe, control and mutant, unchanged.
  * both arms exactly as runs 2 and 3 dispatched them: paired_v2.ARM_B_HEAD, rubric andon-wire@2,
    the same role prompts, and paired_v4_workflow.js byte-identical to paired_v2_workflow.js
    below its meta.
  * the per-item outcome (at least 3 of the 5 repeats agree) and DECISION_RULE, word for word.
  * CONTAMINATION, rebuilt for public history and for the harness run 3 met:
      - a tool input or result naming a path or file that holds the key (as before, minus the
        alternatives that matched the harness's own subagent work area), the upstream repo, its
        package, or the fix or parent commit;
      - any web or MCP tool call: arm B is a general-purpose agent and can reach the upstream
        fix, arm A's roles cannot, so the asymmetry is reported beside the rule;
      - a Bash command that reaches the network or a package index;
      - a tool input naming another run's staged directory (the shared-scratch risk run 3 could
        not exclude; the workflow body stays byte-identical, so no per-run work directory).
    check proves the pattern matches nothing stage() writes and no path of the harness's own
    work area.
  * PATTERN_RULE (paired_v3's, imported verbatim) read on the 8 historic reds under the sealed
    key; the GREEN-CLAIMS readout on the greens; DECISION_RULE on the final layer (LAYERS).
  * seal.json: a fingerprint of every item, its provenance, the selection record and every rule.

Usage:
    paired_v4.py check [--repeat N]
    paired_v4.py selftest
    paired_v4.py estimate                 # staged bytes per run against run 3's, and the cost
    paired_v4.py seal                     # writes seal.json; only before the run
    paired_v4.py stage --dest DIR --out ARGS.json --map MAP.json
    paired_v4.py collect --run-dir DIR --map MAP.json --out RAW.json
    paired_v4.py score --raw RAW.json --map MAP.json [--write OUT.json] [--errata ERRATA.json]
                       [--instrument INSTRUMENT.json]

KEY ERRATA and INSTRUMENT ERRATA are paired_v3's layers. A key erratum here can only come from
the GREEN-CLAIMS procedure in selection.json, and must carry a control.

STDLIB ONLY. Python >= 3.11. POSIX, not as root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import calibration  # noqa: E402  (same directory)
import oracles  # noqa: E402
import paired  # noqa: E402
import paired_v2  # noqa: E402  (arm B's head and rubric, the decision rule, the dispatch)
import paired_v3  # noqa: E402  (calibrate, run_probe, jsonl, _report, score_core, pattern, PATTERN_RULE)
import prompts  # noqa: E402

MIN_PYTHON = (3, 11)
SET = calibration.FIXTURES / "paired-v4"
UPSTREAM = SET / "upstream"
SELECTION = SET / "selection.json"
SELECTION_LOG = SET / "selection-log.json"
N_PAIRS = 8
N_ITEMS = 2 * N_PAIRS
REPEATS = paired.REPEATS          # 5
MAJORITY = paired.MAJORITY        # 3
THRESHOLD = paired_v2.THRESHOLD   # 0.7
TREE = paired.TREE
RUBRIC_ID = paired_v2.RUBRIC_ID   # andon-wire@2
ARM_B_HEAD = paired_v2.ARM_B_HEAD
DECISION_RULE = paired_v2.DECISION_RULE
PATTERN_RULE = paired_v3.PATTERN_RULE
WORKFLOW = HERE / "paired_v4_workflow.js"
SEAL = SET / "seal.json"
ERRATA = SET / "results" / "key-errata.json"
INSTRUMENT = SET / "results" / "instrument-errata.json"
CLASSES = paired_v3.CLASSES
MAX_PER_CLASS = 2
MAX_PER_REPO = 3
MAX_TREE_LINES = 600

LAYERS = ("PATTERN_RULE is read on the 8 historic reds under the sealed key. GREEN-CLAIMS is read on the "
          "8 greens: every green any run of either arm called red is a claim, upheld only as a key erratum "
          "with a probe and a control (selection.json), else a false red for the arm that made it. "
          "DECISION_RULE is read on the final layer: the sealed key, then the upheld GREEN-CLAIMS errata, "
          "then any instrument errata. Every layer is reported.")

# --------------------------------------------------------------------- contamination
# Run 3's pattern without the three alternatives that name the harness rather than the key:
# 'scratchpad' (every subagent's work area, the instrument erratum of run 3), '/tasks/' (too
# broad: it is a directory name any agent may create) and 'build_v3'. Reading another agent's
# task output is kept, narrowly. Added: this run's own key files, and the upstream origin.
KEY_PATHS = (r"test/judge-calibration", r"tools/judge-calibration", r"docs/plugin-authoring", r"answers\.json",
             r"key-errata", r"seal\.json", r"key-audit", r"keyaudit", r"selection(?:-log)?\.json",
             r"provenance\.json", r"/tasks/[A-Za-z0-9_-]+\.output", r"\.claude/projects")
ORIGIN = (r"github\.com", r"githubusercontent", r"pypi\.org", r"pythonhosted\.org")
WEB_TOOLS = ("WebSearch", "WebFetch")
NETWORK_BASH = re.compile(
    r"(?:^|[\s;&|(`])(?:curl|wget|pip3?|pipx|uvx?|gh|conda|poetry)(?=\s)|\bgit\s+(?:clone|fetch|pull|ls-remote|remote|submodule)\b"
    r"|\bpython[0-9.]*\s+-m\s+pip\b|urlopen\(|http\.client|socket\.create_connection|requests\.(?:get|post|head)\(")
RUN_NAME = re.compile(r"\bw[0-9a-f]{8}-[1-5][ab]\b")
# What the run-3 harness handed every subagent as its work area. The pattern must never match it.
HARNESS_PATHS = (
    "/private/tmp/claude-502/-Users-hahn-LocalDocuments-GitHub-Forks-werkstoff--claude-worktrees-busy-chatterjee-45a1e4"
    "/4471e75e-2c2b-4a29-acd0-c549860ef9b6/scratchpad/v/check.py",
    "/tmp/claude-1001/-home-runner-work-werkstoff-werkstoff/0b5e/scratchpad/chk.py",
    "/private/tmp/claude-502/-Users-hahn-x/4471e75e/scratchpad/tasks/notes.txt",
)


def provenances() -> list[dict]:
    """Every pair's upstream record, in pair order."""
    return [calibration.load_json(p) for p in sorted(UPSTREAM.glob("*/provenance.json"))]


def origin_alternatives(provs: list[dict] | None = None) -> list[str]:
    """The upstream repos, packages and commits of the admitted pairs. A name that is also an
    ordinary word counts only after `import`/`from`, or as a path component."""
    out: list[str] = []
    for p in provs if provs is not None else provenances():
        out.append(re.escape(p["slug"]))
        out += [r"\b" + p[k][:10] for k in ("fix", "parent")]
        for n in p["names"]["plain"]:
            out.append(r"\b" + re.escape(n) + r"\b")
        for n in p["names"]["importOnly"]:
            out.append(r"(?:\bimport|\bfrom)\s+" + re.escape(n) + r"\b|/" + re.escape(n) + r"/")
    return sorted(set(out))


def alternatives() -> list[str]:
    return list(KEY_PATHS) + list(ORIGIN) + origin_alternatives()


CONTAMINATION = re.compile("|".join(f"(?:{a})" for a in alternatives()))


def scan_text(text: str, alts: list[str] | None = None) -> set[str]:
    """The ALTERNATIVES (their pattern source, not the matched text) that match ``text``, so an
    instrument erratum can drop exactly one of them."""
    return {a for a in (alts if alts is not None else alternatives()) if re.search(a, text)}


def contamination(transcript: Path, own: str, keys: set[str], alts: list[str] | None = None) -> list[str]:
    """Why one agent's run could have read the key: 'path:<alternative>' for a key path, the
    upstream origin or the commits in a tool input or result; 'web:<tool>' for a web or MCP tool;
    'net:<match>' for a Bash command that reaches the network; 'cross-run:<run>' for a tool input
    naming another run's staged directory."""
    hits: set[str] = set()
    for e in paired_v3.jsonl(transcript):
        msg = e.get("message") if isinstance(e, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        for c in content if isinstance(content, list) else []:
            if not isinstance(c, dict) or c.get("type") not in ("tool_use", "tool_result"):
                continue
            if c["type"] == "tool_use":
                name = str(c.get("name", ""))
                if name in WEB_TOOLS or name.startswith("mcp__"):
                    hits.add(f"web:{name}")
                inp = c.get("input")
                text = json.dumps(inp)
                if name == "Bash" and isinstance(inp, dict):
                    hits.update(f"net:{m.group(0).strip()}" for m in NETWORK_BASH.finditer(str(inp.get("command", ""))))
                hits.update(f"cross-run:{m.group(0)}" for m in RUN_NAME.finditer(text)
                            if m.group(0) != own and m.group(0).split("-")[0] in keys)
            else:
                text = json.dumps(c.get("content"))
            hits.update(f"path:{a}" for a in scan_text(text, alts))
    return sorted(hits)


def observations(transcript: Path, provs: list[dict]) -> dict[str, int]:
    """Reported beside the rule, deciding nothing: whether the agent named the upstream project in
    its own words (recognition), and whether it wrote into a shared scratch directory."""
    names = [n for p in provs for n in p["names"]["plain"] + p["names"]["importOnly"] + [p["slug"]]]
    named = re.compile("|".join(r"\b" + re.escape(n) + r"\b" for n in names)) if names else None
    out = {"namedUpstream": 0, "sharedScratchWrites": 0}
    for e in paired_v3.jsonl(transcript):
        msg = e.get("message") if isinstance(e, dict) else None
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        for c in msg.get("content") if isinstance(msg.get("content"), list) else []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text" and named and named.search(c.get("text", "")):
                out["namedUpstream"] = 1
            if c.get("type") == "tool_use" and "/scratchpad/" in json.dumps(c.get("input")) and c.get("name") in ("Write", "Edit", "Bash"):
                out["sharedScratchWrites"] += 1
    return out


# ------------------------------------------------------------------------------ items

def items(errata: dict | None = None) -> list[dict]:
    """The sealed items; with ``errata``, each corrected item carries its corrected key."""
    answers = calibration.load_json(SET / "answers.json")
    fix = {cid: e["corrected"] for cid, e in (errata or {}).items()}
    return [{"id": f"paired-v4/{cid}", "dir": SET / "cases" / cid, "oracle": SET / "oracle" / f"{cid}.json",
             "expected": fix.get(cid, a)["expected"], "native": fix.get(cid, a)["nativeExpected"],
             "class": a["class"], "pair": a["pair"], "twin": a["twin"]}
            for cid, a in sorted(answers.items())]


def templates(item: dict, key: str) -> dict[str, Any]:
    """The second and third runs' prompts for this item, built by the same code."""
    return paired_v2.templates(item, key)


def git_blob(data: bytes) -> str:
    """The git blob id of ``data``: anyone can compare it with `git rev-parse <sha>:<path>` upstream."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324  (git's id, not security)


def transformed(prov: dict, side: str) -> dict[str, str]:
    """The staged tree of one side ('parent' or 'fix'): the committed upstream originals under the
    pair's recorded transform. Replacements apply in order, to every file alike."""
    out = {}
    for up, staged in sorted(prov["files"].items()):
        text = (UPSTREAM / prov["pair"] / side / up).read_bytes().decode("utf-8")
        for old, new in prov["replace"]:
            text = text.replace(old, new)
        out[staged] = text
    return out


def check_pair(prov: dict, by_cid: dict[str, dict]) -> list[str]:
    """The pair is what its provenance says: the trees are the transformed upstream originals, the
    twins share a contract and a base, and nothing staged names the upstream."""
    pid = prov["pair"]
    probs = []
    red, green = by_cid.get(prov["redItem"]), by_cid.get(prov["greenItem"])
    if not red or not green:
        return [f"pair {pid}: names items answers.json does not hold"]
    if (red["expected"], green["expected"]) != ("fail", "pass") or red["pair"] != pid or green["pair"] != pid:
        probs.append(f"pair {pid}: {prov['redItem']} is not its red and {prov['greenItem']} its green")
    if red["twin"] != prov["greenItem"] or green["twin"] != prov["redItem"]:
        probs.append(f"pair {pid}: the twins do not name each other")
    for side in ("parent", "fix"):
        for up in prov["files"]:
            data = (UPSTREAM / pid / side / up).read_bytes()
            if git_blob(data) != prov["blobs"][side][up]:
                probs.append(f"pair {pid}: upstream/{side}/{up} is not the blob {prov['blobs'][side][up]}")
            if b"\r" in data:
                probs.append(f"pair {pid}: upstream/{side}/{up} has a carriage return; the tree reader would change it")
    for side, it in (("parent", red), ("fix", green)):
        if oracles._tree_of(it["dir"] / "tree") != transformed(prov, side):
            probs.append(f"pair {pid}: {it['id']}'s tree is not the transformed upstream {side}")
    if oracles._tree_of(red["dir"] / "tree") == oracles._tree_of(green["dir"] / "tree"):
        probs.append(f"pair {pid}: the twins' trees are the same")
    if calibration.load_json(red["dir"] / "contract.json") != calibration.load_json(green["dir"] / "contract.json"):
        probs.append(f"pair {pid}: the twins' contracts differ")
    rb, gb = (calibration.load_json(i["oracle"])["base"] for i in (red, green))
    if rb != gb:
        probs.append(f"pair {pid}: the twins' bases differ, so the diff shown would point at the fix")
    if rb in (oracles._tree_of(red["dir"] / "tree"), oracles._tree_of(green["dir"] / "tree")):
        probs.append(f"pair {pid}: the base is one of the trees")
    if set(rb) != set(prov["files"].values()):
        probs.append(f"pair {pid}: the base does not hold exactly the staged files")
    lines = sum(t.count("\n") for t in transformed(prov, "fix").values())
    if lines > MAX_TREE_LINES:
        probs.append(f"pair {pid}: {lines} lines, A4 allows {MAX_TREE_LINES}")
    leak = sorted({a for it in (red, green) for t in [*oracles._tree_of(it["dir"] / "tree").values(),
                                                         (it["dir"] / "fix.diff").read_text(encoding="utf-8"),
                                                         json.dumps(calibration.load_json(it["dir"] / "contract.json"))]
                   for a in scan_text(t, list(ORIGIN) + origin_alternatives([prov]))})
    if leak:
        probs.append(f"pair {pid}: a staged file or the contract names the upstream: {leak}")
    return probs


def check_selection(provs: list[dict]) -> list[str]:
    """The admitted pairs are the first 8 the pre-registered scan admitted, in its order, within
    its caps, and the log examined candidates in the order selection.json fixes."""
    sel, log = calibration.load_json(SELECTION), calibration.load_json(SELECTION_LOG)
    probs = []
    order = {r["slug"]: n for n, r in enumerate(sel["repos"])}
    seen = log["examined"]
    want = sorted(seen, key=lambda c: (c["authorDate"], -order.get(c["slug"], 99), c["sha"]), reverse=True)
    if [c["sha"] for c in seen] != [c["sha"] for c in want]:
        probs.append("selection-log.json did not examine candidates newest author date first")
    lo, hi = sel["window"]["authorDateFrom"], sel["window"]["authorDateTo"] + "T23:59:59Z"
    for c in seen:
        if not lo <= c["authorDate"] <= hi or c["slug"] not in order:
            probs.append(f"selection-log.json examined {c['sha'][:10]}, outside the window or the repo list")
        if c["outcome"] != "admitted" and not re.fullmatch(r"A[1-9]|cap:(class|repo)|not a candidate", c["outcome"]):
            probs.append(f"selection-log.json: {c['sha'][:10]}'s outcome {c['outcome']!r} names no rule")
    admitted = [c for c in seen if c["outcome"] == "admitted"]
    if len(admitted) != N_PAIRS or seen[-1]["outcome"] != "admitted":
        probs.append(f"the scan admitted {len(admitted)} and must stop at its {N_PAIRS}th admission")
    per_class: dict[str, int] = {}
    per_repo: dict[str, int] = {}
    for c in admitted:
        per_class[c["class"]] = per_class.get(c["class"], 0) + 1
        per_repo[c["slug"]] = per_repo.get(c["slug"], 0) + 1
    if any(v > MAX_PER_CLASS for v in per_class.values()) or any(v > MAX_PER_REPO for v in per_repo.values()):
        probs.append(f"the admitted set breaks a cap: {per_class} {per_repo}")
    if sorted(c["sha"] for c in admitted) != sorted(p["fix"] for p in provs):
        probs.append("the pairs are not exactly the candidates the scan admitted")
    for p in provs:
        c = next((c for c in admitted if c["sha"] == p["fix"]), None)
        if c and (c["slug"], c["parent"], c["class"], c["authorDate"]) != (p["slug"], p["parent"], p["class"], p["authorDate"]):
            probs.append(f"pair {p['pair']}: its provenance disagrees with the selection log")
        lic = {r["slug"]: r["license"] for r in sel["repos"]}.get(p["slug"])
        if p.get("license") != lic or not p.get("notice", "").strip():
            probs.append(f"pair {p['pair']}: no license notice, or not the license selection.json lists")
    return probs


# ------------------------------------------------------------------------------ check

def _old_trees() -> set[str]:
    """Every file body an earlier run, or the tribunal calibration they reused, ever staged."""
    out = set()
    for judge in ("paired", "tribunal", "paired-v2", "paired-v3"):
        for p in (calibration.FIXTURES / judge / "cases").rglob("*"):
            if p.is_file() and "tree" in p.parts:
                out.add(p.read_text(encoding="utf-8"))
    return out


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def fingerprint() -> dict[str, Any]:
    """What the seal holds: every rule, both arms' instruments, the selection, and per item
    everything a run reads and everything its key rests on."""
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
    upstream = {p.relative_to(UPSTREAM).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(UPSTREAM.rglob("*")) if p.is_file()}
    wf = WORKFLOW.read_text(encoding="utf-8")
    return {"rubric": RUBRIC_ID, "threshold": THRESHOLD, "repeats": REPEATS, "majority": MAJORITY,
            "decisionRule": DECISION_RULE, "patternRule": PATTERN_RULE, "layers": LAYERS,
            "contamination": {"alternatives": alternatives(), "webTools": list(WEB_TOOLS), "mcpPrefix": "mcp__",
                              "networkBash": NETWORK_BASH.pattern, "runName": RUN_NAME.pattern},
            "armBHead": hashlib.sha256(ARM_B_HEAD.encode()).hexdigest(),
            "workflow": hashlib.sha256(wf.encode()).hexdigest(),
            "selection": _sha(calibration.load_json(SELECTION)), "selectionLog": _sha(calibration.load_json(SELECTION_LOG)),
            "keyAudit": _sha(calibration.load_json(SET / "key-audit.json")),
            "upstream": upstream, "items": per_item}


def check_pattern_bounds() -> list[str]:
    """The contamination pattern cannot match the harness's own work area, nor anything stage()
    writes: every staged path and every staged file's text, for every item."""
    probs = [f"the contamination pattern matches the harness work area {p}: {sorted(scan_text(p))}"
             for p in HARNESS_PATHS if scan_text(p)]
    with tempfile.TemporaryDirectory(prefix="pv4-bounds-") as td:
        dest = Path(td) / "stage"
        if stage(dest, Path(td) / "args.json", Path(td) / "map.json", quiet=True) != 0:
            return [*probs, "stage() refused a clean temporary directory"]
        for p in sorted(Path(td).rglob("*")):
            hit = scan_text(p.as_posix()) | (scan_text(p.read_text(encoding="utf-8")) if p.is_file() and p.suffix != ".json" else set())
            if hit:
                probs.append(f"the contamination pattern matches what stage() wrote, {p.relative_to(td)}: {sorted(hit)}")
        keys = set(calibration.load_json(Path(td) / "map.json"))
        for run in sorted(q.name for q in dest.iterdir()):
            names = {m.group(0) for f in (dest.parent / f"{dest.name}-roles" / run).iterdir()
                     for m in RUN_NAME.finditer(f.read_text(encoding="utf-8"))}
            if names - {run} and {n.split("-")[0] for n in names - {run}} & keys:
                probs.append(f"run {run}'s prompts name another run's directory: {sorted(names - {run})}")
    return probs


def check(repeat: int = 1) -> list[str]:
    if os.geteuid() == 0:
        return ["paired-v4 cannot be checked as root"]
    probs = []
    its = items()
    by_cid = {i["id"].split("/", 1)[1]: i for i in its}
    if len(its) != N_ITEMS:
        probs.append(f"{len(its)} items, the design says {N_ITEMS}")
    exp = [i["expected"] for i in its]
    if exp.count("pass") != N_PAIRS or exp.count("fail") != N_PAIRS:
        probs.append(f"the design is {N_PAIRS} red and {N_PAIRS} green, the key has {exp.count('fail')} red")
    pairs: dict[str, list[dict]] = {}
    for i in its:
        pairs.setdefault(i["pair"], []).append(i)
    for p, two in sorted(pairs.items()):
        if sorted(x["expected"] for x in two) != ["fail", "pass"] or len({x["class"] for x in two}) != 1 or two[0]["class"] not in CLASSES:
            probs.append(f"pair {p} is not one red and one green of one of run 3's classes")
    provs = provenances()
    if sorted(p["pair"] for p in provs) != sorted(pairs):
        probs.append(f"the provenance records name pairs {sorted(p['pair'] for p in provs)}, the items {sorted(pairs)}")
    for prov in provs:
        probs += check_pair(prov, by_cid)
    probs += check_selection(provs)
    old = _old_trees()
    for i in its:
        cid = i["id"].split("/", 1)[1]
        contract = calibration.load_json(i["dir"] / "contract.json")
        orc = calibration.load_json(i["oracle"])
        tree = oracles._tree_of(i["dir"] / "tree")
        if (i["dir"] / "fix.diff").read_text(encoding="utf-8") != oracles.udiff(orc["base"], tree):
            probs.append(f"{cid}: fix.diff is not the diff of the shared base and the staged tree")
        if sorted(orc["probes"]) != sorted(c["id"] for c in contract["criteria"]):
            probs.append(f"{cid}: probes do not cover exactly the contract's criteria")
            continue
        twin = by_cid.get(i["twin"])
        if twin is None or not any(c["files"] == oracles._tree_of(twin["dir"] / "tree") for c in orc["controls"]):
            probs.append(f"{cid}: its twin's tree is not among its controls")
        for _ in range(repeat):
            probs += [f"{p}" for p in paired_v3.calibrate(i)]
        if any(needle in body for body in tree.values() for needle in ("EXPECTED", "known-", "nativeExpected", "paired-v4")):
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
        if any(w in t["armB"] or w in t["challenger"] for w in ("nativeExpected", "answers", "expected", "paired-v4")):
            probs.append(f"{cid}: a prompt names the answer")
    wf = WORKFLOW.read_text(encoding="utf-8")
    if paired_v3._body(wf) != paired_v3._body(paired_v2.WORKFLOW.read_text(encoding="utf-8")):
        probs.append("paired_v4_workflow.js differs from paired_v2_workflow.js below its meta")
    canon = (HERE.parent / "judge-contract" / "verdict.inline.js").read_text(encoding="utf-8")
    if paired_v2._block(canon, "verdict@2") != paired_v2._block(wf, "verdict@2"):
        probs.append("paired_v4_workflow.js's verdict@2 block differs from tools/judge-contract/verdict.inline.js")
    probs += check_pattern_bounds()
    if not SEAL.is_file():
        probs.append("no seal.json: run `paired_v4.py seal` before staging")
    elif calibration.load_json(SEAL) != fingerprint():
        now, was = fingerprint(), calibration.load_json(SEAL)
        moved = sorted(k for k in now if now[k] != was.get(k)) + sorted(
            f"items.{c}.{f}" for c in now["items"] for f in now["items"][c] if was.get("items", {}).get(c, {}).get(f) != now["items"][c][f])
        probs.append(f"seal.json does not match what is committed now: {moved}")
    probs += paired_v3.v2_equivalence()
    probs += v3_equivalence()
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
            seen: dict[str, list[str]] = {}
            probs += check_errata(errata, seen)
            print(f"paired-v4 key errata decided here: {seen['decided'] or 'none'}; "
                  f"skipped on this platform: {seen['skipped'] or 'none'}")
        if inst:
            probs += check_instrument(inst)
    return probs


def v3_equivalence() -> list[str]:
    """The functions this run scores with (paired_v3.score_core and paired_v3.pattern, through
    paired_v3.score) still reproduce every committed layer of the third run: the reuse is proven."""
    res = paired_v3.SET / "results"
    if not (res / "run.json").is_file():
        return []
    raw, mp = calibration.load_json(res / "run.json"), calibration.load_json(res / "map.json")
    err = calibration.load_json(paired_v3.ERRATA) if paired_v3.ERRATA.is_file() else None
    inst = calibration.load_json(paired_v3.INSTRUMENT) if paired_v3.INSTRUMENT.is_file() else None
    probs = []
    for name, e, i in [("score.json", None, None), ("score-instrument.json", None, inst), ("score-corrected.json", err, inst)]:
        if (res / name).is_file() and paired_v3.score(raw, mp, errata=e, instrument=i) != calibration.load_json(res / name):
            probs.append(f"paired_v3.score no longer reproduces paired-v3/results/{name}")
    return probs


def check_instrument(inst: dict) -> list[str]:
    """An instrument erratum may only drop alternatives or categories the sealed rule had, and it
    names the sealed rule verbatim."""
    c = inst.get("contamination", {})
    probs = []
    if c.get("sealedAlternatives") != alternatives():
        probs.append("instrument-errata.json: its sealedAlternatives are not the ones the seal holds")
    allowed = {f"path:{a}" for a in alternatives()} | {"web:", "net:", "cross-run:"}
    for d in c.get("dropped", []):
        if d not in allowed:
            probs.append(f"instrument-errata.json: it drops {d!r}, which the sealed rule does not have")
    return probs


def check_errata(errata: dict, seen: dict[str, list[str]] | None = None) -> list[str]:
    """A key erratum here is an upheld GREEN-CLAIMS claim: it names a green, its probe fails the
    staged tree with an assertion, and it carries a control that changes only the behaviour
    named, which the probe passes. Platform-bound errata are reported as skipped, never decided."""
    probs = []
    seen = seen if seen is not None else {}
    seen.setdefault("decided", [])
    seen.setdefault("skipped", [])
    answers = calibration.load_json(SET / "answers.json")
    for cid, e in sorted(errata.items()):
        if cid not in answers:
            probs.append(f"erratum {cid} names no sealed item")
            continue
        if e["sealed"] != {k: answers[cid][k] for k in ("expected", "nativeExpected")}:
            probs.append(f"erratum {cid}: its sealed key is not the one answers.json holds")
        if answers[cid]["expected"] != "pass" or e["corrected"] != {"expected": "fail", "nativeExpected": "red"}:
            probs.append(f"erratum {cid}: GREEN-CLAIMS only turns a sealed green red")
        if "control" not in e or not e.get("claims"):
            probs.append(f"erratum {cid}: no control, or no claim it upholds")
            continue
        if e.get("platform") and not sys.platform.startswith(e["platform"]):
            seen["skipped"].append(f"{cid} (needs {e['platform']})")
            continue
        seen["decided"].append(cid)
        tree = oracles._tree_of(SET / "cases" / cid / "tree")
        code, last = paired_v3.run_probe(e["probe"], tree)
        if code != 1 or not last.startswith("AssertionError"):
            probs.append(f"erratum {cid}: its probe does not reproduce the defect (exit {code}, {last[:80]!r})")
        files = {**tree, **e["control"]["files"]}
        ccode, clast = paired_v3.run_probe(e["probe"], files)
        if files == tree or ccode != 0:
            probs.append(f"erratum {cid}: its probe does not pass its control (exit {ccode}, {clast[:80]!r})")
    return probs


def seal() -> int:
    probs = [p for p in check() if not p.startswith(("no seal.json", "seal.json does not match"))]
    if probs:
        for p in probs:
            print(f"PAIRED-V4 {p}")
        print("refusing to seal a set that does not check")
        return 1
    if (SET / "results").exists():
        print("refusing to re-seal: results/ exists, so the run has happened")
        return 1
    SEAL.write_text(json.dumps(fingerprint(), indent=2) + "\n", encoding="utf-8")
    print(f"sealed {N_ITEMS} items into {SEAL.as_posix()}")
    return 0


# ------------------------------------------------------------------------------ the run

def scratch_like(dest: Path) -> bool:
    """A destination inside a harness scratch directory: run 3 staged there and its contamination
    rule then matched every staged path."""
    s = dest.resolve().as_posix()
    return "/scratchpad" in s or re.search(r"/claude-\d+/", s) is not None


def stage(dest: Path, out: Path, map_file: Path, quiet: bool = False) -> int:
    """paired_v3.stage's layout for this set: one tree per (item, repeat, arm), prompts beside it,
    refusing a destination the contamination rule or a harness scratch directory would cover."""
    if scan_text(dest.resolve().as_posix()) or scratch_like(dest):
        print(f"ERROR: {dest} is inside a scratch directory or names a key path; stage elsewhere", file=sys.stderr)
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
    if not quiet:
        print(f"staged {len(keys)} items x {REPEATS} repeats x 2 arms under {dest.as_posix()}; args {out.as_posix()}")
    return 0


def collect(run_dir: Path, mapping: dict[str, str]) -> dict:
    """paired_v3.collect's rebuild of every run from the workflow journal, read through jsonl(),
    with this run's contamination scan (which needs each agent's own run name) and the
    observations reported beside the rule."""
    labels = {e["agentId"]: e["label"] for e in paired_v3.jsonl(run_dir / "journal.jsonl")
              if e.get("type") == "started" and e.get("agentId")}
    keys, provs = set(mapping), provenances()
    alts = alternatives()
    runs: dict[tuple[str, int, str], dict] = {}
    for aid, label in labels.items():
        role, key, rep = label.rsplit(" ", 2)
        arm = "b" if role == "contract judge" else "a"
        r = int(rep.lstrip("r"))
        t = run_dir / f"agent-{aid}.jsonl"
        report, usage = paired_v3._report(t) if t.is_file() else (None, {})
        run = runs.setdefault((key, r, arm), {"key": key, "r": r, "arm": arm, "roles": {}, "usage": {}, "agents": 0,
                                              "contaminated": set(), "observed": {"namedUpstream": 0, "sharedScratchWrites": 0}})
        run["agents"] += 1
        run["usage"] = {k: run["usage"].get(k, 0) + v for k, v in usage.items()}
        if t.is_file():
            run["contaminated"].update(contamination(t, f"{key}-{r}{arm}", keys, alts))
            run["observed"] = {k: v + observations(t, provs)[k] for k, v in run["observed"].items()}
        if arm == "b":
            run["report"] = report
        else:
            run["roles"][role] = report
            if role == "adjudicator":
                run["adjudicator"] = report
    unknown = sorted({k for k, _, _ in runs} - keys)
    if unknown:
        raise ValueError(f"journal names items the map does not: {unknown}")
    out = [runs[k] for k in sorted(runs)]
    for run in out:
        run["contaminated"] = sorted(run["contaminated"])
    return {"runs": out}


# ---------------------------------------------------------------------------- scoring

def green_claims(core: dict, errata: dict | None) -> dict:
    """The GREEN-CLAIMS readout: per arm, the greens (under the sealed key) any run called red, how
    many of those claims an erratum upheld, and how many are false reds."""
    upheld = set(errata or {})
    out = {}
    for arm in ("tribunal", "contractJudge"):
        claimed = {iid.split("/", 1)[1]: r[arm].count("fail") for iid, r in core["items"].items()
                   if r.get("sealedExpected", r["expected"]) == "pass" and r[arm].count("fail")}
        majority = sorted(c for c in claimed if core["items"][f"paired-v4/{c}"][f"{arm}Majority"] == "fail")
        out[arm] = {"claims": claimed, "majorityRed": majority, "upheld": sorted(set(claimed) & upheld),
                    "falseRed": sorted(set(claimed) - upheld)}
    return {"rule": "selection.json greenClaims", **out}


def score(raw: dict, mapping: dict[str, str], errata: dict | None = None, instrument: dict | None = None) -> dict:
    """The sealed score, then each correction layer. The core and PATTERN_RULE are paired_v3's;
    PATTERN_RULE is read on the sealed key's reds whatever layer this is (LAYERS)."""
    if instrument:
        drop = set(instrument["contamination"]["dropped"])
        raw = {**raw, "runs": [{**r, "contaminated": [h for h in r.get("contaminated", [])
                                                      if h not in drop and not any(h.startswith(d) for d in drop if d.endswith(":"))]}
                               for r in raw["runs"]]}
    its = items(errata)
    core = paired_v3.score_core(raw, mapping, its, errata)
    sealed = {i["id"]: i["expected"] for i in items()}
    for iid, r in core["items"].items():
        r["sealedExpected"] = sealed[iid]
    if instrument:
        core["instrumentErrata"] = sorted(instrument)
    core["contaminatedRuns"] = sorted(f"{mapping[r['key']]} r{r['r']} arm {r['arm']}: {', '.join(r['contaminated'])}"
                                      for r in raw["runs"] if r.get("contaminated"))
    sealed_core = paired_v3.score_core(raw, mapping, items(), None) if errata else core
    core["pattern"] = paired_v3.pattern(sealed_core, items())
    core["greenClaims"] = green_claims(core, errata)
    core["layers"] = LAYERS
    obs: dict[str, dict[str, int]] = {"a": {}, "b": {}}
    for r in raw["runs"]:
        o = obs[r["arm"]]
        o["runs"] = o.get("runs", 0) + 1
        o["runsWithWebOrMcpTool"] = o.get("runsWithWebOrMcpTool", 0) + any(h.startswith("web:") for h in r.get("contaminated", []))
        for k, v in (r.get("observed") or {}).items():
            o[f"runsWith_{k}"] = o.get(f"runsWith_{k}", 0) + (1 if v else 0)
    core["observed"] = {"tribunal": obs["a"], "contractJudge": obs["b"]}
    return core


# ---------------------------------------------------------------------------- estimate

RUN3_SUBAGENT_TOKENS = 20_700_000   # wf_e4697e20-c20, judge-calibration.md
RUN3_OUTPUT_PER_RUN = {"a": 10_500, "b": 870}


def staged_bytes(module: Any) -> int:
    """The bytes of every role file plus every tree one full staging writes."""
    with tempfile.TemporaryDirectory(prefix="pv4-est-") as td:
        dest = Path(td) / "stage"
        if module is paired_v3:
            module.stage(dest, Path(td) / "a.json", Path(td) / "m.json")
        else:
            stage(dest, Path(td) / "a.json", Path(td) / "m.json", quiet=True)
        return sum(p.stat().st_size for p in Path(td).rglob("*") if p.is_file() and p.suffix == ".txt" or "tree" in p.parts)


def estimate() -> dict[str, Any]:
    """Run 4's expected subagent tokens: run 3's total scaled by the ratio of what one staging
    writes (each role reads its prompt and the tree), as an order of magnitude, not a quote."""
    v3, v4 = staged_bytes(paired_v3), staged_bytes(sys.modules[__name__])
    ratio = v4 / v3
    agents = N_ITEMS * REPEATS * 5
    return {"agents": agents, "stagedBytes": {"run3": v3, "run4": v4}, "ratio": round(ratio, 2),
            "subagentTokens": {"low": int(RUN3_SUBAGENT_TOKENS * min(1.0, ratio)), "scaled": int(RUN3_SUBAGENT_TOKENS * ratio)},
            "outputTokens": N_ITEMS * REPEATS * (RUN3_OUTPUT_PER_RUN["a"] + RUN3_OUTPUT_PER_RUN["b"])}


# ---------------------------------------------------------------------------- selftest

def _fake_raw(a_mode: str, b_mode: str) -> tuple[dict, dict]:
    """paired_v3._fake_raw's fabricated runs over this set's items."""
    word = {"pass": "green", "fail": "red", "abstain": "unknown"}
    mapping, runs = {}, []
    its = items()
    first_green = next(i["id"] for i in its if i["expected"] == "pass")
    for n, it in enumerate(its):
        key = f"w{n:02d}"
        mapping[key] = it["id"]
        contract = calibration.load_json(it["dir"] / "contract.json")
        want = {"right": it["expected"], "pass": "pass", "paranoid": "fail", "blind": "pass",
                "hedge": "abstain" if it["id"] == first_green else it["expected"]}
        for r in range(1, REPEATS + 1):
            runs.append({"key": key, "r": r, "arm": "a", "adjudicator": f"Overall: {word[want[a_mode]]}"})
            o = want[b_mode]
            if o == "abstain":
                report = {"item": key, "criteria": [], "abstain": True, "abstainReason": "cannot tell"}
            else:
                crit = [{"id": c["id"], "score": 0.9, "pass": True, "evidence": "probe"} for c in contract["criteria"]]
                if o == "fail":
                    crit[0] = {**crit[0], "score": 0.1, "pass": False}
                report = {"item": key, "criteria": crit, "abstain": False, "abstainReason": None}
            runs.append({"key": key, "r": r, "arm": "b", "report": report})
    return {"runs": runs}, mapping


def _transcript(td: str, entries: list[dict]) -> Path:
    t = Path(td) / f"agent-{len(list(Path(td).iterdir()))}.jsonl"
    t.write_text("\n".join(json.dumps(x) for x in entries) + "\n", encoding="utf-8")
    return t


def _use(name: str, inp: dict) -> dict:
    return {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": inp}]}}


def selftest() -> int:
    bad = []
    expect = {("right", "right"): "CEILING", ("blind", "blind"): "FLOOR", ("blind", "right"): "NO DETECTION ADVANTAGE",
              ("right", "blind"): "SUPPORTED", ("paranoid", "blind"): "NOT SETTLED"}
    for (a, b), verdict in expect.items():
        got = score(*_fake_raw(a, b))["pattern"]["verdict"]
        if got != verdict:
            bad.append(f"arms {a}/{b} read as {got}, not {verdict}")
    if score(*_fake_raw("right", "right"))["decision"]["keepTribunal"]:
        bad.append("two perfect arms kept the tribunal (a tie must collapse it)")
    if not score(*_fake_raw("right", "hedge"))["decision"]["keepTribunal"]:
        bad.append("a contract judge hedging unknown on one green did not lose on the record")
    rep = score(*_fake_raw("paranoid", "right"))
    if rep["decision"]["keepTribunal"] or len(rep["greenClaims"]["tribunal"]["falseRed"]) != N_PAIRS:
        bad.append("a tribunal inventing reds on every green was kept, or its claims were not all false reds")
    # An upheld claim moves the decision layer but never PATTERN_RULE, which reads the sealed key.
    raw, mp = _fake_raw("paranoid", "right")
    g = next(i for i in items() if i["expected"] == "pass")
    cid = g["id"].split("/", 1)[1]
    errata = {cid: {"corrected": {"expected": "fail", "nativeExpected": "red"}}}
    c = score(raw, mp, errata=errata)
    s = score(raw, mp)
    if c["pattern"] != s["pattern"] or c["greenClaims"]["tribunal"]["upheld"] != [cid]:
        bad.append("an upheld GREEN-CLAIMS erratum changed PATTERN_RULE or was not reported as upheld")
    if c["items"][g["id"]]["expected"] != "fail" or c["items"][g["id"]]["sealedExpected"] != "pass":
        bad.append("the corrected layer does not score the upheld green as red while recording its sealed key")
    raw, mp = _fake_raw("right", "right")
    raw["runs"].pop()
    try:
        score(raw, mp)
        bad.append("an incomplete run was scored")
    except ValueError:
        pass
    # The contamination scanner: what it must flag, and what it must not.
    keys = {"w0123abcd", "w89abcdef"}
    with tempfile.TemporaryDirectory() as td:
        cases = {
            "a key path in a tool result": ([{"message": {"role": "user", "content": [
                {"type": "tool_result", "content": "test/judge-calibration/paired-v4/answers.json:3"}]}}], "path:"),
            "WebSearch": ([_use("WebSearch", {"query": "dedupe fix"})], "web:WebSearch"),
            "an MCP tool": ([_use("mcp__github__get_commit", {"sha": "x"})], "web:mcp__github__get_commit"),
            "curl in Bash": ([_use("Bash", {"command": "cd /x && curl -s https://example.org"})], "net:curl"),
            "pip in Bash": ([_use("Bash", {"command": "python3 -m pip download x"})], "net:"),
            "git clone in Bash": ([_use("Bash", {"command": "git clone https://x/y"})], "net:git clone"),
            "another run's directory": ([_use("Read", {"file_path": "/stage/w89abcdef-2b/tree/x.py"})], "cross-run:w89abcdef-2b"),
            "a task output file": ([_use("Read", {"file_path": "/private/tmp/claude-502/p/s/tasks/a2e41adfa7c2b5a47.output"})], "path:"),
        }
        for name, (entries, want) in cases.items():
            got = contamination(_transcript(td, entries), "w0123abcd-1a", keys)
            if not any(h.startswith(want) for h in got):
                bad.append(f"the contamination scan missed {name}: {got}")
        clean = {
            "its own run's tree": [_use("Read", {"file_path": "/stage/w0123abcd-1a/tree/x.py"})],
            "the harness scratch area": [_use("Write", {"file_path": HARNESS_PATHS[0], "content": "print(1)"}),
                                         _use("Bash", {"command": f"python3 {HARNESS_PATHS[1]}"})],
            "a probe that tests a URL string": [_use("Bash", {"command": "python3 -c \"assert f('http://a/b')\""})],
            "a word like 'equip' or 'shipping'": [_use("Bash", {"command": "echo equip shipping | grep -c ship"})],
            "an unknown run-like name": [_use("Read", {"file_path": "/stage/wdeadbeef-3a/x"})],
        }
        for name, entries in clean.items():
            got = contamination(_transcript(td, entries), "w0123abcd-1a", keys)
            if got:
                bad.append(f"the contamination scan flagged {name}: {got}")
    for p in HARNESS_PATHS:
        if scan_text(p):
            bad.append(f"the pattern matches the harness work area {p}")
    with tempfile.TemporaryDirectory() as td:
        for d in (Path(td) / "claude-502" / "x" / "scratchpad" / "stage", Path(td) / "a" / "test" / "judge-calibration" / "s"):
            if stage(d, Path(td) / "o.json", Path(td) / "m.json", quiet=True) == 0:
                bad.append(f"stage() accepted the destination {d}")
    # An instrument erratum drops exactly what it names, and nothing the seal never had.
    raw, mp = _fake_raw("right", "right")
    for run in raw["runs"]:
        run["contaminated"] = ["web:WebSearch"] if run["arm"] == "b" else []
    inst = {"contamination": {"sealedAlternatives": alternatives(), "dropped": ["web:"]}}
    if score(raw, mp)["arms"]["b"]["items"]["agreement"] != 0.0 or score(raw, mp, instrument=inst)["arms"]["b"]["items"]["agreement"] != 1.0:
        bad.append("an instrument erratum did not lift exactly the contamination it drops")
    if score(raw, mp)["observed"]["contractJudge"].get("runsWithWebOrMcpTool") != N_ITEMS * REPEATS:
        bad.append("web-tool use was not reported per arm")
    for name, i in {"a rewritten rule": {"contamination": {"sealedAlternatives": ["x"], "dropped": []}},
                    "an alternative the seal never had": {"contamination": {"sealedAlternatives": alternatives(), "dropped": ["path:answers"]}}}.items():
        if not check_instrument(i):
            bad.append(f"check_instrument accepted {name}")
    # check_errata: only a green turned red, with a control, reproduced by an assertion.
    tree = oracles._tree_of(g["dir"] / "tree")
    path = next(iter(tree))
    base = {"sealed": {"expected": "pass", "nativeExpected": "green"}, "corrected": {"expected": "fail", "nativeExpected": "red"},
            "claims": ["planted"], "probe": f"import pathlib\nassert 'PLANTED' in pathlib.Path({path!r}).read_text(), 'defect'",
            "control": {"files": {path: tree[path] + "\n# PLANTED\n"}}}
    if check_errata({cid: base}):
        bad.append(f"check_errata refused a well-formed erratum: {check_errata({cid: base})}")
    red = next(i["id"].split("/", 1)[1] for i in items() if i["expected"] == "fail")
    for name, errata in {"a probe that passes the staged tree": {cid: {**base, "probe": "pass"}},
                         "a probe that fails its control too": {cid: {**base, "probe": "assert False, 'always'"}},
                         "no control": {cid: {k: v for k, v in base.items() if k != "control"}},
                         "a red turned green": {red: {**base, "sealed": {"expected": "fail", "nativeExpected": "red"},
                                                      "corrected": {"expected": "pass", "nativeExpected": "green"}}},
                         "an erratum for no item": {"v4-99": base}}.items():
        if not check_errata(errata):
            bad.append(f"check_errata accepted {name}")
    seen: dict[str, list[str]] = {}
    check_errata({cid: {**base, "platform": "no-such-platform"}}, seen)
    if seen["decided"] or not seen["skipped"]:
        bad.append(f"an erratum for another platform was not reported as skipped: {seen}")
    # The calibration it imports refuses what it refused for run 3.
    it = next(i for i in items() if i["expected"] == "fail")
    orc = calibration.load_json(it["oracle"])
    with tempfile.TemporaryDirectory() as td:
        planted = {
            "a probe that always passes": {**orc, "probes": dict.fromkeys(orc["probes"], "pass")},
            "a probe that crashes instead of asserting": {**orc, "probes": {**orc["probes"], next(iter(orc["probes"])): "import nosuchmodule_x"}},
            "a red without its happy-path probe": {**orc, "happy": {}},
        }
        for name, o in planted.items():
            p = Path(td) / "o.json"
            p.write_text(json.dumps(o), encoding="utf-8")
            if not paired_v3.calibrate({**it, "oracle": p}):
                bad.append(f"calibrate accepted {name}")
    # The blob id is git's.
    if git_blob(b"hello\n") != "ce013625030ba8dba906f756967f9e9ca394464a":
        bad.append("git_blob is not git's blob id")
    for b in bad:
        print(f"FAIL {b}")
    print(f"paired-v4 selftest: {len(bad)} failure(s)")
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
    sub.add_parser("estimate")
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
            print(f"PAIRED-V4 {x}")
        print(f"paired-v4 measurement: {len(items())} items, {len(probs)} problem(s)")
        return 1 if probs else 0
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "seal":
        return seal()
    if a.cmd == "estimate":
        print(json.dumps(estimate(), indent=2))
        return 0
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
    print(json.dumps({k: rep[k] for k in ("decision", "discordant", "pattern", "greenClaims", "observed", "contaminatedRuns")}, indent=2))
    for arm, name in (("a", "tribunal"), ("b", "contract judge")):
        m = rep["arms"][arm]["items"]
        print(f"{name}: per-item agreement {m['agreement']:.2f}, false passes {m['falsePasses']}, "
              f"record {rep['arms'][arm]['record']['agreement']}, per-run agreement {rep['arms'][arm]['runs']['agreement']:.2f}, "
              f"unanimous items {rep['arms'][arm]['unanimousItems']}/{N_ITEMS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
