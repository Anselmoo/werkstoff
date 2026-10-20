"""The prompts each judge is measured with: the workflow's OWN text, not a paraphrase.

The arbeitsplan referee prompt is the array literal in ``plugins/arbeitsplan/workflows/run.js``
(phase kind ``fanout-blind``); the matrize decode-referee prompt is the template literal in
``plugins/matrize/workflows/decode.js`` (the Referee phase). Both are EXTRACTED from the
workflow file at render time and their placeholders filled from the case. A workflow edit
that changes the prompt therefore changes what is measured, and an edit this module does not
understand (a new placeholder, a moved array) raises instead of rendering something close.

The tribunal has no workflow: ``andon-verify`` runs it from prose
(``references/tribunal-protocol.md``), so its role prompts are the harness's own, built
from exactly the inputs the protocol allows -- the wire's contract and the fix's
diff and files, fenced with andon's own ``fence()``. The harness writes no argument for a
verdict into any of them.

The only addition to the referees' prompts is a return-format footer: the workflows pass a
JSON schema to ``agent()``, the Agent tool used for the measurement has none, so the same
schema is stated in words. It is identical for every case and recorded with the results.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN_JS = ROOT / "plugins" / "arbeitsplan" / "workflows" / "run.js"
DECODE_JS = ROOT / "plugins" / "matrize" / "workflows" / "decode.js"
ANDON_CORE = ROOT / "plugins" / "andon" / "scripts" / "andon_core.py"

REFEREE_FOOTER = (
    "\n\nReturn ONLY one JSON object, no prose around it, with exactly these keys: "
    '"candidateId" (string), "verdict" (one of "accepted", "accepted_different_approach", '
    '"rejected", "cannot_judge"), "perCriterion" (array of {"id": string, "met": boolean, '
    '"evidence": string}), "rationaleLeaked" (boolean), "note" (string or null).'
)
DECODE_FOOTER = (
    "\n\nReturn ONLY one JSON object, no prose around it, with exactly these keys: "
    '"cardId" (string), "verdict" (one of "reproduced", "reproduced_different_relation", '
    '"not_reproduced", "cannot_reproduce"), "remeasured" (string), "note" (string).'
)


def _js_string(line: str) -> str | None:
    """The text of a one-line JS backtick literal (trailing comma allowed), else None."""
    m = re.fullmatch(r"\s*`(.*)`,?\s*", line)
    return m.group(1) if m else None


def _relayed(js: str) -> str:
    m = re.search(r"^const RELAYED = '(.*)'$", js, re.M)
    if not m:
        raise ValueError("const RELAYED not found in the workflow")
    return m.group(1)


def referee_template() -> list[str]:
    """The lines of the ``fanout-blind`` referee prompt array in run.js, placeholders kept."""
    js = RUN_JS.read_text(encoding="utf-8")
    start = js.index("`Judge ONE candidate against the acceptance criteria below.`")
    open_at = js.rindex("[", 0, start)
    end = js.index("].join('\\n')", start)
    lines = js[open_at + 1:end].strip("\n").split("\n")
    if "".join(lines).count("RELAYED") != 1:
        raise ValueError("run.js referee prompt no longer ends in ${RELAYED}")
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith('//')]


def referee_prompt(case: dict) -> str:
    """Render the run.js referee prompt for one case (``case.json``)."""
    js = RUN_JS.read_text(encoding="utf-8")
    relayed = _relayed(js)

    def criteria_text(acceptance: list[dict]) -> str:
        out = []
        for c in acceptance:
            check = c.get("check")
            cmds = check if isinstance(check, list) else ([check] if check else [])
            header = f"- [{c['id']}] {c['criterion']}"
            out.append("\n".join([header, "  ```", *[f"  {x}" for x in cmds], "  ```"]) if cmds else header)
        return "\n".join(out)

    def checks_reported(checks: list[dict]) -> str:
        if not checks:
            return "- none reported"
        return "\n".join("\n".join([f"- {k['id']} (exit {k['exit']}):", "  ```", f"  {k['command']}", "  ```"])
                         for k in checks)

    exprs = {
        "criteriaText(acceptance()),": criteria_text(case["acceptance"]),
        "checksReportedText(c.checks),": checks_reported(case["checks"]),
        "c.diff || '(none)',": case["diff"] or "(none)",
    }
    out = []
    for line in referee_template():
        lit = _js_string(line)
        if lit is not None:
            lit = lit.replace("${c.candidateId}", case["candidateId"])
            lit = lit.replace("${(c.filesTouched || []).join(', ') || 'none'}",
                              ", ".join(case["filesTouched"]) or "none")
            lit = lit.replace("${RELAYED}", relayed)
            if "${" in lit:
                raise ValueError(f"run.js referee prompt has a placeholder this harness does not fill: {lit!r}")
            out.append(lit)
        elif line in exprs:
            out.append(exprs[line])
        else:
            raise ValueError(f"run.js referee prompt has a line this harness does not understand: {line!r}")
    return "\n".join(out) + REFEREE_FOOTER


def decode_template() -> str:
    """The Referee-phase template literal in decode.js, with placeholders kept."""
    js = DECODE_JS.read_text(encoding="utf-8")
    start = js.index("`Re-derive this measurement from the source it cites.")
    end = js.index("`,\n      {\n        label: `referee:", start)
    return js[start + 1:end]


def decode_prompt(case: dict, ref_root: str) -> str:
    relayed = _relayed(DECODE_JS.read_text(encoding="utf-8"))
    text = decode_template()
    fills = {
        "${card.source}": case["source"].replace("{ROOT}", ref_root),
        "${card.measured}": case["measured"],
        "${card.relation}": case["relation"],
        "${card.reliability}": case["reliability"],
        "${RELAYED}": relayed,
    }
    for k, v in fills.items():
        text = text.replace(k, v)
    if "${" in text:
        raise ValueError("decode.js referee prompt has a placeholder this harness does not fill")
    return text + DECODE_FOOTER


def _fence():
    spec = importlib.util.spec_from_file_location("andon_core_for_calibration", ANDON_CORE)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load andon_core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.fence


def _files_block(tree: Path) -> str:
    fence = _fence()
    parts = []
    for p in sorted(x for x in tree.rglob("*") if x.is_file() and "__pycache__" not in x.parts):
        rel = p.relative_to(tree).as_posix()
        parts.append(f"File {rel}:\n" + fence(p.read_text(encoding="utf-8")))
    return "\n\n".join(parts)


def _contract_block(contract: dict) -> str:
    return "\n".join([f"Wire: {contract['wire']}", "Contract criteria:",
                      *[f"{i}. [{c['id']}] {c['text']}" for i, c in enumerate(contract["criteria"], 1)]])


def tribunal_prompts(contract: dict, case_src: Path, tree: Path) -> dict[str, str]:
    """Defender and challenger prompts: the contract, the fix's diff and the fixed files, nothing else."""
    fence = _fence()
    diff = (case_src / "fix.diff").read_text(encoding="utf-8")
    body = "\n\n".join([
        _contract_block(contract),
        "The fix under review, as a diff:\n" + fence(diff),
        f"The files as they stand after the fix (the working tree is at {tree.as_posix()}):\n" + _files_block(tree),
    ])
    return {
        "defender": ("Make your case for this wire, criterion by criterion.\n\n" + body),
        "challenger": ("Make your case against this wire, criterion by criterion.\n\n" + body),
    }


def verifier_prompt(contract: dict, tree: Path, defender: str, challenger: str) -> str:
    fence = _fence()
    return "\n\n".join([
        "Convert the two cases below into reproduced facts. Check each concrete claim and report "
        f"what you ran and what it printed. The working tree is at {tree.as_posix()}; run checks "
        "from inside it and change nothing in it.",
        _contract_block(contract),
        "Defender's case:\n" + fence(defender),
        "Challenger's case:\n" + fence(challenger),
    ])


def adjudicator_prompt(contract: dict, defender: str, challenger: str, verifier: str) -> str:
    fence = _fence()
    return "\n\n".join([
        "Decide each criterion of the wire's contract (pass, fail or neither), then the overall wire verdict.",
        _contract_block(contract),
        "Defender's case:\n" + fence(defender),
        "Challenger's case:\n" + fence(challenger),
        "Verifier's facts:\n" + fence(verifier),
    ])


# --------------------------------------------------------------------------------------

def template_sha(judge: str) -> str:
    """Hash of everything the prompt is made of that is not the case itself."""
    if judge == "referee":
        text = "\n".join(referee_template()) + REFEREE_FOOTER
    elif judge == "decode":
        text = decode_template() + DECODE_FOOTER
    else:
        text = "".join(inspect.getsource(f) for f in (_contract_block, tribunal_prompts, verifier_prompt, adjudicator_prompt))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_templates(judge: str) -> list[str]:
    """Render each template once against a stub case; a workflow edit this module cannot
    follow is a finding, not a silent drift."""
    try:
        if judge == "referee":
            referee_prompt({"candidateId": "c1", "acceptance": [{"id": "a1", "criterion": "x", "check": "true"}],
                            "checks": [{"id": "a1", "command": "true", "exit": 0}], "filesTouched": ["f"], "diff": "d"})
        elif judge == "decode":
            decode_prompt({"source": "s", "measured": "m", "relation": "r", "reliability": "B"}, "/r")
    except (ValueError, OSError) as exc:
        return [f"prompt template no longer follows the workflow: {exc}"]
    return []
