#!/usr/bin/env python3
"""Validate a DTCG token file against matrize's profile — including the rules with teeth.

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
  * every token records the EDGE it arrived by, with that edge's own grade. Edges are
    written, never reconstructed: value-matching across files was tested against a real
    50-declaration token file and merged `--space-1` with `--radius-sm` (both 4px) and
    collapsed three roles that alias one source into a single node. A graph that is
    confidently wrong about "what depends on this" is worse than no graph.
  * a SECONDARY source -- a third party's description of someone else's system -- is
    capped at grade B and must name what it describes. Grading it A because it is
    published is the trap the cap exists for.
  * every token names the VOCABULARY TERM it instantiates, and the vocabulary decides
    whether it may be a token at all. `references/vocabulary/` calls `Padding` a `derived`
    term and `Stacking context` a `property`; either one sitting in tokens.json is a value
    that will drift from the thing it was derived from. This was prose in a SKILL.md, which
    this repository has measured as the weakest enforcement layer there is.

Failing closed on the registry
------------------------------
If `vocabulary.py` cannot build a registry, every vocabulary rule below would pass
vacuously and the file would go green with no vocabulary enforcement at all. That is
reported as `V-VOCAB-REGISTRY`, a blocker, rather than skipped.

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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vocabulary as vocablib  # noqa: E402

EXT = "com.werkstoff.matrize"
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

# color-system.md states this as a MANDATORY column, and says why: a table mixing light
# and dark pairs "looks complete and is not -- it is the shape of the error that hides a
# role behaving differently in the two modes".
APPEARANCE_MODES = ("light", "dark", "forced")

# A reference cannot be graded above its dimension's written ceiling. Higher letter = more
# trusted, so "better than the cap" is a smaller index here.
GRADE_ORDER = {"A": 0, "B": 1, "C": 2}

# How much of an asset class a design system may promise, per the taxonomy's Origin column.
DELIVERY = ("asset", "system", "rules")


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


def load_registry() -> tuple[object | None, str | None]:
    """(registry, why-not). Never swallows the failure -- see V-VOCAB-REGISTRY."""
    try:
        reg = vocablib.load()
    except (OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if reg.problems:
        return None, "; ".join(reg.problems[:3])
    return reg, None


def check_vocab(path: str, ext: dict, reg, findings: list[Finding]) -> str | None:
    """The vocabulary rules for one token. Returns the resolved term key, or None."""
    spec = ext.get("vocab")
    if not isinstance(spec, dict) or not spec.get("term"):
        findings.append(Finding(
            "V-VOCAB-MISSING", path,
            "no com.werkstoff.matrize.vocab.term: the token instantiates no named concept. "
            "references/vocabulary/ names 223 of them; a value that matches none of them "
            "is either a new concept (declare it) or a misunderstanding.",
            "blocker"))
        return None

    term_slug = vocablib.slug(spec["term"])
    term, why = reg.lookup(term_slug, spec.get("dimension"))
    if term is None:
        if spec.get("extends") and spec.get("declaredBy"):
            return None          # a declared extension: allowed, and reported by `status`
        findings.append(Finding(
            "V-VOCAB-UNKNOWN", path,
            f"{why}. If the project genuinely needs a concept the vocabulary lacks, say so "
            f"in vocab.extends and name the Design Card in vocab.declaredBy.",
            "blocker"))
        return None

    declared = spec.get("kind")
    if declared and term.kind and declared != term.kind:
        findings.append(Finding(
            "V-VOCAB-KIND-MISMATCH", path,
            f"declares kind {declared!r}, but {term.display!r} is {term.kind!r} in "
            f"{term.dimension}.md:{term.line}",
            "blocker"))

    if term.kind in ("derived", "property"):
        findings.append(Finding(
            "V-VOCAB-NOT-A-TOKEN", path,
            f"{term.display!r} is {term.kind!r} in {term.dimension}.md:{term.line}. A "
            f"'derived' term is computed from tokens and never stored separately; a "
            f"'property' is observed, not stored. Storing it makes a second copy that "
            f"drifts from the thing it was derived from.",
            "blocker"))

    if term.kind == "rule" and not ext.get("antiRule"):
        findings.append(Finding(
            "V-VOCAB-RULE-NO-ANTIRULE", path,
            f"{term.display!r} is a 'rule' term, and a rule with no stated failure case is "
            f"decoration. This fires on the KIND, so it catches an entry that omitted the "
            f"rule text as well as one that omitted the anti-rule.",
            "blocker"))

    if term.key in reg.ceilings:
        cap = reg.ceilings[term.key]
        grade = ext.get("reliability")
        if cap is None:
            findings.append(Finding(
                "V-VOCAB-GRADE-CEILING", path,
                f"{term.display!r} is not recoverable from a reference at any grade -- it "
                f"is a decision, not a measurement, and must be authored. See the ceilings "
                f"table in references/vocabulary/README.md.",
                "blocker"))
        elif grade in GRADE_ORDER and GRADE_ORDER[grade] < GRADE_ORDER[cap]:
            findings.append(Finding(
                "V-VOCAB-GRADE-CEILING", path,
                f"graded {grade} , but {term.dimension}.md caps {term.display!r} at "
                f"{cap}. Confidence is not evidence.",
                "blocker"))
    return term.key


def check_naming(tokens: list[tuple[str, dict]], terms: dict[str, str], reg,
                 findings: list[Finding]) -> None:
    """Two name-level collisions the vocabulary explicitly warns about."""
    by_leaf: dict[str, list[tuple[str, str]]] = {}
    for path, _ in tokens:
        key = terms.get(path)
        if key:
            by_leaf.setdefault(path.split(".")[-1], []).append((path, key))
    for leaf, entries in sorted(by_leaf.items()):
        distinct = {key for _, key in entries}
        if len(distinct) > 1:
            findings.append(Finding(
                "V-VOCAB-COLLISION", ", ".join(p for p, _ in entries),
                f"{len(entries)} tokens are all named {leaf!r} but instantiate different "
                f"concepts ({', '.join(sorted(distinct))}). The vocabulary names this case "
                f"outright: margin is both a page concept and a box concept -- if both "
                f"appear, rename one."))

    # A token named after the thing it is NOT: `vocab.term` is one half of a recorded
    # confused pair and the token's own leaf name is the other half.
    halves: dict[str, tuple[str, str]] = {}
    for a, b, heading in reg.pairs:
        halves.setdefault(a, (b, heading))
        halves.setdefault(b, (a, heading))
    for path, _ in tokens:
        key = terms.get(path)
        if not key:
            continue
        term_slug, leaf = key.split("/", 1)[1], vocablib.slug(path.split(".")[-1])
        other = halves.get(term_slug)
        if other and leaf == other[0]:
            findings.append(Finding(
                "V-VOCAB-CONFUSED-PAIR", path,
                f"instantiates {term_slug!r} but is named {leaf!r}, and the vocabulary "
                f"records those two as a confused pair ({other[1]!r}). Adopting the "
                f"near-synonym is how a lexicon invents a collision the vocabulary "
                f"already warns about."))


def check_assets(doc: dict, reg, findings: list[Finding]) -> None:
    """The asset inventory, bounded by the taxonomy's Origin column."""
    declared = ((doc.get("$extensions") or {}).get(EXT) or {}).get("assets")
    if not isinstance(declared, list):
        return                       # a token file need not carry an asset inventory
    present: set[str] = set()
    for entry in declared:
        if not isinstance(entry, dict):
            continue
        cls_slug = vocablib.slug(str(entry.get("class", "")))
        cls = reg.classes.get(cls_slug)
        if cls is None:
            findings.append(Finding(
                "V-ASSET-UNKNOWN", f"assets/{entry.get('class')}",
                f"{entry.get('class')!r} is not a class in visual-asset-taxonomy.md",
                "blocker"))
            continue
        present.add(cls_slug)
        if entry.get("delivered") == "asset" and not cls.deliverable_whole:
            findings.append(Finding(
                "V-ASSET-ORIGIN-OVERREACH", f"assets/{cls.display}",
                f"promised as a delivered asset, but its origin is {cls.origin_raw!r}. A "
                f"'drawn' class yields a system plus a seed set and a growth rule; "
                f"'captured' and 'shot' yield rules only. Promising the artwork is a "
                f"promise that cannot be kept.",
                "blocker"))
    for cls_slug in reg.mandatory:
        if cls_slug not in present:
            cls = reg.classes.get(cls_slug)
            findings.append(Finding(
                "V-COVERAGE-MANDATORY", "assets",
                f"{(cls.display if cls else cls_slug)!r} is not covered. The taxonomy names "
                f"it among the classes missing from almost every design system and almost "
                f"always needed in practice."))


def validate(doc: dict, reg=None) -> list[Finding]:
    findings: list[Finding] = []
    if reg is None:
        reg, why = load_registry()
        if reg is None:
            findings.append(Finding(
                "V-VOCAB-REGISTRY", "(root)",
                f"the vocabulary registry could not be built ({why}). Every vocabulary "
                f"rule would pass vacuously, so this fails closed instead. Run "
                f"scripts/vocabulary.py --selftest.",
                "blocker"))
    tokens = walk(doc)
    if not tokens:
        findings.append(Finding("V-EMPTY", "(root)", "no tokens found", "blocker"))
        return findings

    names = {path for path, _ in tokens}

    term_keys: dict[str, str] = {}
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
                                    f"$type {kind!r} is outside matrize's DTCG profile; "
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
                                    "no com.werkstoff.matrize.card: a token with no Design "
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

        # 4b. I8 -- the edge this token arrived by, with its own grade
        edge = ext.get("edge")
        if not isinstance(edge, dict) or not edge.get("from"):
            findings.append(Finding(
                "V-NO-EDGE", path,
                "no com.werkstoff.matrize.edge: the card -> token edge must be WRITTEN. "
                "Reconstructing it by matching values across files merges roles that "
                "happen to share a value -- tested and reproduced on real material.",
                "blocker"))
        elif edge.get("grade") not in ("A", "B", "C"):
            findings.append(Finding("V-EDGE-NO-GRADE", path,
                                    f"edge.grade is {edge.get('grade')!r}, expected A, B or C; "
                                    f"an edge without its own grade cannot be drawn dashed"))

        # 4c. a secondary source is capped at B and must say what it describes
        if ext.get("secondary"):
            if reliability == "A":
                findings.append(Finding(
                    "V-SECONDARY-GRADE-A", path,
                    "marked secondary but graded A. A third party's description of "
                    "someone else's system underwrites 'one documented interpretation', "
                    "not 'this is what that vendor does'. Ceiling is B.",
                    "blocker"))
            if not ext.get("describes"):
                findings.append(Finding("V-SECONDARY-NO-SUBJECT", path,
                                        "marked secondary but does not name what it describes, "
                                        "so the claim's real subject is invisible"))

        # 5. contrast is computed, never asserted
        if kind == "color" and ext.get("role") in TEXT_BEARING:
            contrast = ext.get("contrast")
            if not isinstance(contrast, dict) or "ratio" not in contrast:
                findings.append(Finding(
                    "V-NO-CONTRAST", path,
                    f"role {ext.get('role')!r} can carry text but has no computed contrast "
                    f"block; run scripts/contrast.py rather than asserting it"))
            elif contrast.get("mode") not in APPEARANCE_MODES:
                findings.append(Finding(
                    "V-CONTRAST-NO-MODE", path,
                    f"contrast block states no appearance mode (expected one of "
                    f"{', '.join(APPEARANCE_MODES)}). color-system.md makes the mode a "
                    f"mandatory column: a contrast record without one looks complete and "
                    f"is not -- it is the shape of the error that hides a role behaving "
                    f"differently in light and dark.",
                    "blocker"))

        # 6. a rule needs its anti-rule, or it is decoration
        if ext.get("rule") and not ext.get("antiRule"):
            findings.append(Finding("V-NO-ANTIRULE", path,
                                    "has a rule but no antiRule; a rule with no stated "
                                    "failure case is decoration and is not emitted"))

        # 7. the vocabulary decides whether this may be a token at all
        if reg is not None:
            key = check_vocab(path, ext, reg, findings)
            if key:
                term_keys[path] = key

    if reg is not None:
        check_naming(tokens, term_keys, reg, findings)
        check_assets(doc, reg, findings)
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
                "edge": {"from": "CARD-007", "grade": "A"},
                "vocab": {"term": "Action / interactive", "dimension": "color-system",
                          "kind": "token"},
                "rule": "Exactly one dominant action colour per view.",
                "antiRule": "Two dominants and neither reads as the action.",
                "contrast": {"ratio": 3.84, "passesAA": False, "passesAALarge": True,
                             "mode": "light"},
            }},
        }
    }
}


def _with(**over):
    """SELFTEST_CLEAN with the action token's matrize extension updated."""
    import copy
    doc = copy.deepcopy(SELFTEST_CLEAN)
    doc["color"]["action"]["$extensions"][EXT].update(over)
    return doc


def _twin(group: str, leaf: str, vocab: dict):
    """A second token at `<group>.<leaf>`, so the naming rules have two to compare."""
    import copy
    doc = copy.deepcopy(SELFTEST_CLEAN)
    twin = copy.deepcopy(doc["color"]["action"])
    twin["$extensions"][EXT]["vocab"] = vocab
    doc[group] = {leaf: twin}
    return doc


SELFTEST_ASSETS = {
    "$extensions": {EXT: {"assets": [
        {"class": "Empty state illustration", "delivered": "system"},
        {"class": "Error state illustration", "delivered": "system"},
        {"class": "Open Graph image", "delivered": "asset"},
    ]}},
    "color": SELFTEST_CLEAN["color"],
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

    def mutate_rule_term():
        """A `rule`-kind term with the anti-rule removed."""
        doc = copy.deepcopy(SELFTEST_CLEAN)
        e = doc["color"]["action"]["$extensions"][EXT]
        e["vocab"] = {"term": "Brand", "dimension": "color-system"}
        e.pop("antiRule")
        return doc

    def assets_with(entry):
        doc = copy.deepcopy(SELFTEST_ASSETS)
        doc["$extensions"][EXT]["assets"].append(entry)
        return doc

    def assets_without(display):
        doc = copy.deepcopy(SELFTEST_ASSETS)
        doc["$extensions"][EXT]["assets"] = [
            a for a in doc["$extensions"][EXT]["assets"] if a["class"] != display]
        return doc

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
        ("V-NO-EDGE", mutate(lambda t: ext(t).pop("edge")), "V-NO-EDGE"),
        ("V-EDGE-NO-GRADE", mutate(lambda t: ext(t)["edge"].pop("grade")),
         "V-EDGE-NO-GRADE"),
        ("V-SECONDARY-GRADE-A",
         mutate(lambda t: ext(t).update({"secondary": True, "describes": "Apple HIG"})),
         "V-SECONDARY-GRADE-A"),
        ("V-SECONDARY-NO-SUBJECT",
         mutate(lambda t: ext(t).update({"secondary": True, "reliability": "B"})),
         "V-SECONDARY-NO-SUBJECT"),

        # --- the vocabulary rules ---
        ("V-VOCAB-MISSING", mutate(lambda t: ext(t).pop("vocab")), "V-VOCAB-MISSING"),
        ("V-VOCAB-UNKNOWN",
         _with(vocab={"term": "Vibe", "dimension": "color-system"}), "V-VOCAB-UNKNOWN"),
        ("V-VOCAB-UNKNOWN (bare homonym)",
         _with(vocab={"term": "Opacity"}), "V-VOCAB-UNKNOWN"),
        ("V-VOCAB-KIND-MISMATCH",
         _with(vocab={"term": "Action / interactive", "dimension": "color-system",
                      "kind": "rule"}), "V-VOCAB-KIND-MISMATCH"),
        ("V-VOCAB-NOT-A-TOKEN (derived)",
         _with(vocab={"term": "Padding", "dimension": "grid-and-spacing"}),
         "V-VOCAB-NOT-A-TOKEN"),
        ("V-VOCAB-NOT-A-TOKEN (property)",
         _with(vocab={"term": "Stacking context", "dimension": "grid-and-spacing"}),
         "V-VOCAB-NOT-A-TOKEN"),
        ("V-VOCAB-RULE-NO-ANTIRULE", mutate_rule_term(), "V-VOCAB-RULE-NO-ANTIRULE"),
        ("V-VOCAB-GRADE-CEILING (capped at C)",
         _with(vocab={"term": "Baseline grid", "dimension": "grid-and-spacing"},
               reliability="A"), "V-VOCAB-GRADE-CEILING"),
        ("V-VOCAB-GRADE-CEILING (never recoverable)",
         _with(vocab={"term": "Growth rule", "dimension": "icon-system"}),
         "V-VOCAB-GRADE-CEILING"),
        ("V-CONTRAST-NO-MODE", mutate(lambda t: ext(t)["contrast"].pop("mode")),
         "V-CONTRAST-NO-MODE"),
        # Same leaf name under two groups, two different concepts -- the `margin` case the
        # vocabulary names outright. A twin in the SAME group cannot reproduce it: two keys
        # of one object cannot share a name.
        ("V-VOCAB-COLLISION",
         _twin("brand", "action", {"term": "Accent", "dimension": "color-system"}),
         "V-VOCAB-COLLISION"),
        ("V-VOCAB-CONFUSED-PAIR",
         _twin("space", "gap", {"term": "Gutter", "dimension": "grid-and-spacing"}),
         "V-VOCAB-CONFUSED-PAIR"),
        ("V-ASSET-UNKNOWN", assets_with({"class": "Mood board", "delivered": "system"}),
         "V-ASSET-UNKNOWN"),
        ("V-ASSET-ORIGIN-OVERREACH",
         assets_with({"class": "Logo / wordmark", "delivered": "asset"}),
         "V-ASSET-ORIGIN-OVERREACH"),
        ("V-COVERAGE-MANDATORY", assets_without("Error state illustration"),
         "V-COVERAGE-MANDATORY"),
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

    # --- negative controls for the vocabulary rules. A rule that only ever fires is
    # --- indistinguishable from a rule that always fires.
    def silent(label: str, doc, prefix: str) -> None:
        nonlocal failures
        hits = sorted(f.rule for f in validate(doc) if f.rule.startswith(prefix))
        ok = not hits
        print(f"  {label:<52} {'ok' if ok else 'FAIL  got ' + str(hits)}")
        failures += 0 if ok else 1

    silent("a declared extension passes",
           _with(vocab={"term": "Density bias", "extends": "no vocabulary term for a "
                        "per-surface density offset", "declaredBy": "CARD-031"}),
           "V-VOCAB")
    silent("a token AT its written ceiling passes",
           _with(vocab={"term": "Baseline grid", "dimension": "grid-and-spacing"},
                 reliability="C", corroboratedBy="CARD-012"),
           "V-VOCAB-GRADE")
    silent("the same leaf name for the SAME concept is not a collision",
           _twin("brand", "action",
                 {"term": "Action / interactive", "dimension": "color-system",
                  "kind": "token"}),
           "V-VOCAB-COLLISION")
    silent("a complete asset inventory passes", SELFTEST_ASSETS, "V-ASSET")
    silent("and covers the three mandatory classes", SELFTEST_ASSETS, "V-COVERAGE")

    # Fail closed: a registry that cannot be built must NOT let the vocabulary rules
    # quietly disappear. This is the difference between 'no findings' and 'no checks'.
    real_dir = vocablib.VOCAB_DIR
    try:
        vocablib.VOCAB_DIR = real_dir.parent / "__no_such_vocabulary__"
        rules = {f.rule for f in validate(SELFTEST_CLEAN)}
    finally:
        vocablib.VOCAB_DIR = real_dir
    ok = "V-VOCAB-REGISTRY" in rules
    print(f"  {'an unbuildable registry fails closed':<52} "
          f"{'ok' if ok else 'FAIL  got ' + str(sorted(rules))}")
    failures += 0 if ok else 1

    ok_secondary = _c.deepcopy(SELFTEST_CLEAN)
    e2 = ok_secondary["color"]["action"]["$extensions"][EXT]
    e2.update({"secondary": True, "reliability": "B", "describes": "Apple HIG"})
    if any(f.rule.startswith("V-SECONDARY") for f in validate(ok_secondary)):
        print("  secondary at B with a subject passes  FAIL")
        failures += 1
    else:
        print("  secondary at B with a subject passes  ok")

    print(f"\n{len(cases) + 8} case(s), {failures} failure(s)")
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
            print(f"{args.tokens}: valid against the matrize DTCG profile")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
