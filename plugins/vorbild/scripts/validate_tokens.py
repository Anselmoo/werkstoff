#!/usr/bin/env python3
"""Validate a DTCG token file against vorbild's profile — including the rules with teeth.

Why this is a script
--------------------
Three of the checks below are the mechanical form of rules that would otherwise be
prose a model can be talked out of:

  * a token whose sole provenance is a grade-C card is REJECTED. That is
    "a value supported solely by a screenshot is not a token", made non-negotiable.
  * a colour token in a text-bearing role must carry a COMPUTED contrast block.
    Contrast is arithmetic; asserting it is how a system ships an unreadable button.
  * every token names the Design Card it came from. A token with no provenance is
    indistinguishable from one somebody made up.

Usage:
    validate_tokens.py <tokens.json>
    validate_tokens.py <tokens.json> --json      # machine-readable findings
    validate_tokens.py --selftest                # the validator asserts itself
Exit: 0 clean, 1 findings, 2 the file could not be read or parsed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXT = "com.werkstoff.vorbild"
REF = re.compile(r"^\{([A-Za-z0-9_.-]+)\}$")

# Value shape per $type, as the 2025.10 profile defines it. A type absent here is a type
# this plugin does not emit -- reported rather than silently accepted, because a token
# nothing can format is a token that will vanish at emit time.
SHAPES: dict[str, str] = {
    "color": "object with colorSpace and components",
    "dimension": "object with value and unit",
    "duration": "object with value and unit ms|s",
    "cubicBezier": "array of four numbers",
    "transition": "object with duration, delay, timingFunction",
    "gradient": "array of stops with color and position",
    "shadow": "object or array of shadow objects",
    "fontWeight": "number 1-1000 or a keyword",
    "fontFamily": "string or array of strings",
    "number": "number",
    "strokeStyle": "string or object",
    "border": "object with color, width, style",
    "typography": "object with fontFamily, fontSize, fontWeight, lineHeight",
}

# Roles whose colour can end up behind text, so a contrast figure is mandatory.
TEXT_BEARING = {"ink", "text", "muted", "dominant-action", "quiet-action", "alert", "link"}


class Finding:
    def __init__(self, rule: str, path: str, message: str, severity: str = "major") -> None:
        self.rule, self.path, self.message, self.severity = rule, path, message, severity

    def as_dict(self) -> dict:
        return {"rule": self.rule, "path": self.path, "message": self.message,
                "severity": self.severity}

    def __str__(self) -> str:
        return f"- [{self.severity}] {self.rule}  {self.path}\n    {self.message}"


def walk(node: dict, prefix: str = "") -> list[tuple[str, dict]]:
    """Yield (dotted-path, token) for every token. A token is a dict carrying $value."""
    found: list[tuple[str, dict]] = []
    for key, value in node.items():
        if key.startswith("$"):
            continue
        if not isinstance(value, dict):
            continue
        path = f"{prefix}.{key}" if prefix else key
        if "$value" in value:
            found.append((path, value))
        else:
            found.extend(walk(value, path))
    return found


def inherited_type(node: dict, parts: list[str]) -> str | None:
    """$type may be declared on a group and inherited. Resolve it down the path."""
    current, found = node, None
    for part in parts:
        if isinstance(current, dict):
            if "$type" in current:
                found = current["$type"]
            current = current.get(part, {})
    if isinstance(current, dict) and "$type" in current:
        found = current["$type"]
    return found


def check_shape(kind: str, value) -> str | None:
    if kind == "color":
        if not isinstance(value, dict) or "colorSpace" not in value or "components" not in value:
            return "expected an object with colorSpace and components"
    elif kind in ("dimension", "duration"):
        if not isinstance(value, dict) or "value" not in value or "unit" not in value:
            return "expected an object with value and unit"
        if kind == "duration" and value.get("unit") not in ("ms", "s"):
            return f"duration unit must be ms or s, got {value.get('unit')!r}"
    elif kind == "cubicBezier":
        if not isinstance(value, list) or len(value) != 4:
            return "expected an array of four numbers"
    elif kind == "gradient":
        if not isinstance(value, list) or not value:
            return "expected a non-empty array of stops"
    elif kind == "transition":
        if not isinstance(value, dict) or "duration" not in value:
            return "expected an object carrying at least duration"
    return None


def validate(doc: dict) -> list[Finding]:
    findings: list[Finding] = []
    tokens = walk(doc)
    if not tokens:
        findings.append(Finding("V-EMPTY", "(root)", "no tokens found", "blocker"))
        return findings

    names = {path for path, _ in tokens}

    for path, token in tokens:
        kind = token.get("$type") or inherited_type(doc, path.split("."))
        ext = (token.get("$extensions") or {}).get(EXT) or {}
        value = token["$value"]

        # 1. type present and known
        if not kind:
            findings.append(Finding("V-TYPE-MISSING", path,
                                    "no $type, and no group $type to inherit"))
        elif kind not in SHAPES:
            findings.append(Finding("V-TYPE-UNKNOWN", path,
                                    f"$type {kind!r} is outside vorbild's DTCG profile; "
                                    f"no formatter will emit it"))

        # 2. value shape, or an alias that resolves
        alias = REF.match(value) if isinstance(value, str) else None
        if alias is not None:
            target = alias.group(1)
            if target not in names:
                findings.append(Finding("V-REF-DANGLING", path,
                                        f"references {{{target}}}, which is not a token"))
            elif target == path:
                findings.append(Finding("V-REF-SELF", path, "references itself"))
        elif kind in SHAPES:
            problem = check_shape(kind, value)
            if problem:
                findings.append(Finding("V-VALUE-SHAPE", path, f"{problem} (for $type {kind})"))

        # 3. provenance
        if not ext.get("card"):
            findings.append(Finding("V-NO-CARD", path,
                                    "no com.werkstoff.vorbild.card: a token with no Design "
                                    "Card behind it cannot be told apart from an invention"))
        reliability = ext.get("reliability")
        if reliability not in ("A", "B", "C"):
            findings.append(Finding("V-NO-RELIABILITY", path,
                                    f"reliability is {reliability!r}, expected A, B or C"))
        if ext.get("rights") not in ("R1", "R2", "R3"):
            findings.append(Finding("V-NO-RIGHTS", path,
                                    f"rights is {ext.get('rights')!r}, expected R1, R2 or R3"))

        # 4. THE RULE WITH TEETH -- grade C alone cannot set a token
        if reliability == "C" and not ext.get("corroboratedBy"):
            findings.append(Finding(
                "V-GRADE-C-ALONE", path,
                "sole provenance is a grade-C card (screenshot or visual estimate). A value "
                "supported solely by a screenshot is not a token. Corroborate it with an "
                "A/B source via corroboratedBy, or surface it as an open question.",
                "blocker"))

        # 5. contrast is computed, never asserted
        if kind == "color" and ext.get("role") in TEXT_BEARING:
            contrast = ext.get("contrast")
            if not isinstance(contrast, dict) or "ratio" not in contrast:
                findings.append(Finding(
                    "V-NO-CONTRAST", path,
                    f"role {ext.get('role')!r} can carry text but has no computed contrast "
                    f"block; run scripts/contrast.py rather than asserting it"))

        # 6. a rule needs its anti-rule, or it is decoration
        if ext.get("rule") and not ext.get("antiRule"):
            findings.append(Finding("V-NO-ANTIRULE", path,
                                    "has a rule but no antiRule; a rule with no stated "
                                    "failure case is decoration and is not emitted"))
    return findings


SELFTEST_CLEAN = {
    "color": {
        "action": {
            "$type": "color",
            "$value": {"colorSpace": "srgb", "components": [0.98, 0.18, 0.10], "hex": "#FA2E1A"},
            "$description": "The single dominant action colour.",
            "$extensions": {EXT: {
                "role": "dominant-action", "card": "CARD-007",
                "reliability": "A", "rights": "R1",
                "rule": "Exactly one dominant action colour per view.",
                "antiRule": "Two dominants and neither reads as the action.",
                "contrast": {"ratio": 3.84, "passesAA": False, "passesAALarge": True},
            }},
        }
    }
}


def selftest() -> int:
    """Plant one defect per rule and confirm each is caught.

    A validator nobody has seen fail is an unverified claim. Every rule below is
    exercised by breaking the clean document in exactly one place.
    """
    import copy

    def mutate(fn):
        doc = copy.deepcopy(SELFTEST_CLEAN)
        fn(doc["color"]["action"])
        return doc

    def ext(tok):
        return tok["$extensions"][EXT]

    cases = [
        ("clean document is silent", SELFTEST_CLEAN, None),
        ("V-GRADE-C-ALONE", mutate(lambda t: ext(t).__setitem__("reliability", "C")),
         "V-GRADE-C-ALONE"),
        ("V-NO-CARD", mutate(lambda t: ext(t).pop("card")), "V-NO-CARD"),
        ("V-NO-RIGHTS", mutate(lambda t: ext(t).pop("rights")), "V-NO-RIGHTS"),
        ("V-NO-ANTIRULE", mutate(lambda t: ext(t).pop("antiRule")), "V-NO-ANTIRULE"),
        ("V-NO-CONTRAST", mutate(lambda t: ext(t).pop("contrast")), "V-NO-CONTRAST"),
        ("V-TYPE-UNKNOWN", mutate(lambda t: t.__setitem__("$type", "vibe")), "V-TYPE-UNKNOWN"),
        ("V-VALUE-SHAPE", mutate(lambda t: t.__setitem__("$value", "#FA2E1A")), "V-VALUE-SHAPE"),
        ("V-REF-DANGLING", mutate(lambda t: t.__setitem__("$value", "{color.nope}")),
         "V-REF-DANGLING"),
    ]

    failures = 0
    for label, doc, expected in cases:
        rules = {f.rule for f in validate(doc)}
        ok = (not rules) if expected is None else (expected in rules)
        print(f"  {label:<26} {'ok' if ok else 'FAIL'}"
              f"{'' if ok else '  got ' + (str(sorted(rules)) or 'nothing')}")
        failures += 0 if ok else 1

    # A grade-C token WITH corroboration must pass, or the rule is just "reject C".
    import copy as _c
    corroborated = _c.deepcopy(SELFTEST_CLEAN)
    e = corroborated["color"]["action"]["$extensions"][EXT]
    e["reliability"], e["corroboratedBy"] = "C", "CARD-012"
    if any(f.rule == "V-GRADE-C-ALONE" for f in validate(corroborated)):
        print("  corroborated grade C passes  FAIL")
        failures += 1
    else:
        print("  corroborated grade C passes  ok")

    print(f"\n{len(cases) + 1} case(s), {failures} failure(s)")
    print("RED" if failures else "GREEN")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("tokens", nargs="?", help="path to tokens.json")
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.tokens:
        ap.print_help()
        return 2

    try:
        doc = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"validate_tokens.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    findings = validate(doc)
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    else:
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.rule] = counts.get(f.rule, 0) + 1
        for rule, n in sorted(counts.items()):
            print(f"  {n:>4}  {rule}")
        for f in findings:
            print(f)
        if not findings:
            print(f"{args.tokens}: valid against the vorbild DTCG profile")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
