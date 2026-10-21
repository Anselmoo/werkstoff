"""Confirm a P0 business rule with ONE contract judge, decided by code.

This module used to run a two-judge panel: it collected ``{judge_id, confirms}``
votes and called a rule confirmed when two distinct ids all voted truthy. That
shape had two defects the contract removes by construction -- a vote of ``"no"``
is truthy, and a repeated ``judge_id`` overwrote the first vote, so one judge
could stand in for the panel.

Now a single judge reports per-criterion scores for the rubric below, and
``judge_contract.decide`` (vendored byte-identical from ``tools/judge-contract/``)
turns that report into the verdict. The judge never states the outcome. A P0
rule is confirmed only when the decided verdict's ``outcome`` is ``"pass"``;
a fail, an abstain, a missing report and a malformed report all leave it
unconfirmed. The rubric's prose home is ``references/judge-rubrics.md`` and
``test_p0_panel.py`` fails if that file and ``P0_RUBRIC`` disagree.

The rubric carries no ``calibration`` record, so every verdict says
``calibrated: false``: nobody has measured this judge against known answers.
"""
from __future__ import annotations

from lib import judge_contract
from lib.errors import SelfAssessError

RUBRIC_ID = "befund-p0-rule@1"

P0_RUBRIC = {
    "id": RUBRIC_ID,
    "threshold": 0.7,
    "criteria": [
        {
            "id": "citation-contains-logic",
            "question": "Does the cited `file:line` contain the logic the rule claims?",
        },
        {
            "id": "logic-executes",
            "question": "Is that logic executing code, and not only a comment or docstring?",
        },
        {
            "id": "rule-faithful",
            "question": "Does the rule statement stay within what the code does, "
            "without over-generalising it?",
        },
    ],
}


def _rule_item(rule) -> str:
    """The id the judge was asked about. A rule with no id cannot be judged."""
    rule_id = rule.get("id") if isinstance(rule, dict) else None
    if not isinstance(rule_id, str) or not rule_id.strip():
        # Never take the item from the judge's own report: a report that names
        # whatever item it likes would then confirm whatever rule it likes.
        raise SelfAssessError("p0-confirm: the rule has no string 'id' to judge against.")
    return rule_id


def decide_p0_rule(rule, raw_verdict) -> dict:
    """The decided verdict for one P0 rule and ONE raw judge report (or None)."""
    return judge_contract.decide(raw_verdict, P0_RUBRIC, item=_rule_item(rule))


def downgrade_reason(verdict) -> str | None:
    """Why a verdict did not confirm, for the 'Unconfirmed rules' section.

    ``None`` for a pass. For an abstain, its ``abstainReason`` code. For a fail,
    the evidence of every criterion that failed or scored below the threshold.
    """
    if verdict.get("outcome") == "pass":
        return None
    if verdict.get("outcome") == "abstain":
        return f"abstain: {verdict.get('abstainReason')}"
    threshold = verdict.get("threshold", P0_RUBRIC["threshold"])
    failing = [
        f"{c['id']} ({c['score']}): {c['evidence']}"
        for c in verdict.get("criteria", [])
        if not c["pass"] or c["score"] < threshold
    ]
    return "fail: " + "; ".join(failing) if failing else "fail"


def refusal(rule) -> str | None:
    """Why ``rule``'s ``p0_verdict`` does not confirm it, or None when it does.

    The single gate shared by ``confirm_p0_rule`` and
    ``validators.validate_business_rules_summary``: well-formed per
    ``judge_contract.validate``, from THIS rubric, about THIS rule, and a pass.
    """
    verdict = rule.get("p0_verdict") if isinstance(rule, dict) else None
    if verdict is None:
        return "it carries no p0_verdict (panel_confirmed is no longer honoured)"
    problems = judge_contract.validate(verdict)
    if problems:
        return "its p0_verdict is not a well-formed verdict@1: " + "; ".join(problems)
    if verdict["rubric"] != RUBRIC_ID:
        return f"its p0_verdict is from rubric {verdict['rubric']!r}, not {RUBRIC_ID!r}"
    if verdict["item"] != rule.get("id"):
        return f"its p0_verdict is about {verdict['item']!r}, not this rule"
    if verdict["outcome"] != "pass":
        return f"its p0_verdict outcome is {verdict['outcome']!r}, not 'pass'"
    # validate() proves only self-consistency, so a hand-written verdict (threshold
    # 0.0, an invented criterion id, calibrated: true) passes every check above.
    # Re-derive the verdict from its own criteria under THIS code's rubric and
    # require exact equality: the stored threshold, criterion set and calibrated
    # flag must be what decide() produces, not what the record claims.
    rule_id = rule.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        return "the rule has no string 'id' to re-derive its p0_verdict against"
    raw = {
        "item": rule_id,
        "criteria": [
            {k: c.get(k) for k in ("id", "score", "pass", "evidence")}
            for c in verdict["criteria"]
        ],
        "abstain": False,
        "abstainReason": None,
    }
    if judge_contract.decide(raw, P0_RUBRIC, item=rule_id) != verdict:
        return (
            "its p0_verdict is not what judge_contract.decide produces from its own "
            f"criteria under rubric {RUBRIC_ID!r} (a forged or hand-edited threshold, "
            "criterion set or calibrated flag)"
        )
    return None


def confirm_p0_rule(rule, raw_verdict) -> dict:
    """Judge ONE P0 rule from ONE raw report; ``confirmed`` only on a pass.

    Returns ``{rule, confirmed, downgrade_reason}`` where ``rule`` is a copy of
    the input carrying the decided ``p0_verdict`` (replacing any the input
    already had, and dropping a stale ``panel_confirmed``).
    """
    verdict = decide_p0_rule(rule, raw_verdict)
    decided = {k: v for k, v in rule.items() if k not in ("panel_confirmed", "p0_verdict")}
    decided["p0_verdict"] = verdict
    return {
        "rule": decided,
        "confirmed": refusal(decided) is None,
        "downgrade_reason": downgrade_reason(verdict),
    }


def spot_check_verdicts(rules, k: int = 3) -> dict:
    """A deterministic sample of the P0 verdicts for the user to read each run.

    Every verdict is sampled whatever its outcome -- a pass is the one most worth
    reading -- and ``calibrated`` is true only if every verdict says so.
    """
    verdicts = [
        r["p0_verdict"]
        for r in rules
        if isinstance(r, dict)
        and isinstance(r.get("p0_verdict"), dict)
        and isinstance(r["p0_verdict"].get("item"), str)
    ]
    return {
        "sampled": judge_contract.spot_check(verdicts, k),
        "of": len(verdicts),
        "calibrated": bool(verdicts) and all(v.get("calibrated") is True for v in verdicts),
    }
