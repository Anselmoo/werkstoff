#!/usr/bin/env python3
"""Shared validation logic for the cupertino plugin.

Every function here is a mechanical check backing one guarantee from the
plugin's behavioral spec. Nothing in this file infers, repairs, or defaults a
missing gating value -- a missing or malformed field is always a validation
failure, never silently patched.

Used two ways:
  1. As a library, imported by hooks/pretooluse_guard.py (so the same logic
     that blocks a bad tool call is the logic skills are told to self-check
     against before they even attempt the call).
  2. As a CLI, invoked by skills via Bash: `python3 validators.py <check> `
     with the subject JSON on stdin. Exits 0 and prints `{"ok": true, ...}`
     on success; exits 1 and prints `{"ok": false, "errors": [...]}` on
     failure. Skills MUST treat a non-zero exit as "revise and re-check",
     never as something to narrate around.
"""
import json
import re
import sys

# ---------------------------------------------------------------------------
# Numeric bounds -- named constants, not sentences.
# ---------------------------------------------------------------------------
EVOLUTION_SCORE_DIMENSIONS = 6
EVOLUTION_SCORE_MIN_PER_DIMENSION = 1
EVOLUTION_SCORE_MAX_PER_DIMENSION = 5
EVOLUTION_SCORE_ROADMAP_THRESHOLD = 18  # score < 18 => Rosetta Roadmap required
COUNCIL_LENS_COUNT = 5
COUNCIL_LENSES = ("Reduction", "Craft", "Hierarchy", "Usability", "Metaphor")
COUNCIL_TENSION_ORDER = ("Usability", "Reduction", "Craft", "Hierarchy", "Metaphor")
REVEAL_MAX_SUGGESTIONS = 1
FOCUS_MAX_SENTENCES_PER_SURVIVOR = 1

TECH_NOUNS = (
    "database", "db", "framework", "api", "widget", "button", "screen",
    "endpoint", "server", "backend", "frontend", "microservice", "sdk",
    "library", "queue", "cache", "schema", "table", "component", "react",
    "vue", "angular", "kubernetes", "docker", "container", "cloud",
    "lambda", "rest", "graphql", "json", "sql", "nosql", "orm", "cli",
    "class", "function", "method", "interface", "module", "package",
    "repository", "middleware", "webhook", "cron", "thread", "process",
)

SEVERITIES = ("High", "Medium", "Low")


class ValidationError(ValueError):
    pass


def _fail(errors):
    raise ValidationError("; ".join(errors))


# ---------------------------------------------------------------------------
# cupertino-backwards: experience-zero-tech-nouns
# ---------------------------------------------------------------------------
def check_zero_tech_nouns(statement):
    if not isinstance(statement, str) or not statement.strip():
        _fail(["experience statement is missing or empty"])
    lowered = re.sub(r"[^a-z0-9\s]", " ", statement.lower())
    words = set(lowered.split())
    hits = sorted(words & set(TECH_NOUNS))
    if hits:
        _fail([f"experience statement contains technology nouns: {', '.join(hits)}"])
    return {"ok": True, "statement": statement, "wordCount": len(words)}


# ---------------------------------------------------------------------------
# cupertino-focus: focus-one-sentence-per-survivor
# ---------------------------------------------------------------------------
def _sentence_count(text):
    stripped = text.strip()
    if not stripped:
        return 0
    # Split on sentence-ending punctuation followed by whitespace or end of string.
    parts = re.split(r"(?<=[.!?])\s+", stripped)
    return len([p for p in parts if p.strip()])


def check_one_sentence_per_survivor(survivors):
    if not isinstance(survivors, list) or not survivors:
        _fail(["survivors must be a non-empty list of {name, description} objects"])
    flagged = []
    for s in survivors:
        if not isinstance(s, dict) or "name" not in s or "description" not in s:
            _fail([f"survivor entry missing name/description: {s!r}"])
        count = _sentence_count(s["description"])
        if count > FOCUS_MAX_SENTENCES_PER_SURVIVOR:
            flagged.append({"name": s["name"], "sentenceCount": count})
    return {
        "ok": len(flagged) == 0,
        "flagged": flagged,
        "note": "any flagged survivor indicates the cut was not deep enough" if flagged else None,
    }


# ---------------------------------------------------------------------------
# cupertino-longevity: evolution-score-triggers-roadmap
# ---------------------------------------------------------------------------
def evolution_score(dimension_scores):
    if not isinstance(dimension_scores, list) or len(dimension_scores) != EVOLUTION_SCORE_DIMENSIONS:
        _fail([
            f"evolution readiness score requires exactly {EVOLUTION_SCORE_DIMENSIONS} "
            f"dimension scores, got {len(dimension_scores) if isinstance(dimension_scores, list) else 'non-list'}"
        ])
    for v in dimension_scores:
        if not isinstance(v, int) or not (EVOLUTION_SCORE_MIN_PER_DIMENSION <= v <= EVOLUTION_SCORE_MAX_PER_DIMENSION):
            _fail([
                f"each dimension score must be an integer between "
                f"{EVOLUTION_SCORE_MIN_PER_DIMENSION} and {EVOLUTION_SCORE_MAX_PER_DIMENSION}, got {v!r}"
            ])
    total = sum(dimension_scores)
    roadmap_required = total < EVOLUTION_SCORE_ROADMAP_THRESHOLD
    return {
        "ok": True,
        "total": total,
        "threshold": EVOLUTION_SCORE_ROADMAP_THRESHOLD,
        "rosettaRoadmapRequired": roadmap_required,
    }


# ---------------------------------------------------------------------------
# cupertino-council: council-five-lenses-exactly, council-tension-order-fixed
# ---------------------------------------------------------------------------
def check_council_lenses(lenses):
    if not isinstance(lenses, list):
        _fail(["lenses must be a list"])
    if len(lenses) != COUNCIL_LENS_COUNT:
        _fail([f"council must evaluate exactly {COUNCIL_LENS_COUNT} lenses, got {len(lenses)}"])
    if set(lenses) != set(COUNCIL_LENSES):
        missing = set(COUNCIL_LENSES) - set(lenses)
        extra = set(lenses) - set(COUNCIL_LENSES)
        errs = []
        if missing:
            errs.append(f"missing lenses: {', '.join(sorted(missing))}")
        if extra:
            errs.append(f"unrecognized lenses: {', '.join(sorted(extra))}")
        _fail(errs)
    return {"ok": True, "lenses": lenses}


def check_tension_order(resolved_order):
    """resolved_order: the subsequence of lens names in the order tensions were
    resolved. Every pair (a, b) that both appear must respect COUNCIL_TENSION_ORDER."""
    if not isinstance(resolved_order, list):
        _fail(["resolved order must be a list of lens names"])
    rank = {name: i for i, name in enumerate(COUNCIL_TENSION_ORDER)}
    for name in resolved_order:
        if name not in rank:
            _fail([f"unrecognized lens in tension order: {name}"])
    ranks = [rank[name] for name in resolved_order]
    if ranks != sorted(ranks):
        _fail([
            "tension order violates the fixed precedence "
            + " > ".join(COUNCIL_TENSION_ORDER)
        ])
    return {"ok": True, "order": resolved_order}


# ---------------------------------------------------------------------------
# cupertino-reveal: reveal-exactly-one, reveal-must-be-built
# ---------------------------------------------------------------------------
NUMBERED_LIST_RE = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+", re.MULTILINE)


def check_reveal_shape(text):
    if not isinstance(text, str) or not text.strip():
        _fail(["reveal text is missing or empty"])
    numbered_hits = NUMBERED_LIST_RE.findall(text)
    if len(numbered_hits) > REVEAL_MAX_SUGGESTIONS:
        _fail([
            f"reveal must present exactly {REVEAL_MAX_SUGGESTIONS} suggestion, "
            f"but the text contains a numbered/bulleted list ({len(numbered_hits)} items)"
        ])
    has_code = "```" in text
    if not has_code:
        _fail(["reveal must include a fenced production-grade code block; a pitched-but-unbuilt idea is not a reveal"])
    return {"ok": True}


# ---------------------------------------------------------------------------
# cupertino-elevate: status-flip is judgment; nothing mechanical to check here
# beyond scope containment, which the hook layer enforces at dispatch time.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# cupertino-handbook-*: persisted-state schema validation (read AND write)
# ---------------------------------------------------------------------------
def validate_handbook_draft_summary(obj):
    required_top = ("domain", "generatedAt", "dimensions")
    for key in required_top:
        if key not in obj:
            _fail([f"handbook draft summary missing required field '{key}'"])
    if not isinstance(obj["dimensions"], list) or not obj["dimensions"]:
        _fail(["'dimensions' must be a non-empty list"])
    for i, d in enumerate(obj["dimensions"]):
        for key in ("dimension", "rule", "sourceMode"):
            if key not in d:
                _fail([f"dimensions[{i}] missing required field '{key}'"])
        if d["sourceMode"] not in ("analyzed", "scaffolded"):
            _fail([f"dimensions[{i}].sourceMode must be 'analyzed' or 'scaffolded', got {d['sourceMode']!r}"])
        if d["sourceMode"] == "scaffolded" and not d.get("note"):
            _fail([f"dimensions[{i}] is scaffolded but has no 'note' explaining the absent convention"])
        if d["sourceMode"] == "analyzed" and not d.get("evidence"):
            _fail([f"dimensions[{i}] claims sourceMode 'analyzed' but supplies no evidence"])
    return {"ok": True}


def validate_handbook_check_summary(obj):
    required_top = ("domain", "generatedAt", "findings")
    for key in required_top:
        if key not in obj:
            _fail([f"handbook check summary missing required field '{key}'"])
    if not isinstance(obj["findings"], list):
        _fail(["'findings' must be a list (an empty list is a valid, expected outcome)"])
    for i, f in enumerate(obj["findings"]):
        for key in ("file", "line", "severity", "title", "evidence", "mechanical", "suggestedFix"):
            if key not in f:
                _fail([f"findings[{i}] missing required field '{key}' -- a value nobody supplied must never enter this artifact"])
        if f["severity"] not in SEVERITIES:
            _fail([f"findings[{i}].severity must be one of {SEVERITIES}, got {f['severity']!r}"])
        if not isinstance(f["mechanical"], bool):
            _fail([f"findings[{i}].mechanical must be a boolean, got {f['mechanical']!r}"])
        if not isinstance(f["line"], int):
            _fail([f"findings[{i}].line must be an integer, got {f['line']!r}"])
    return {"ok": True}


CHECKS = {
    "zero-tech-nouns": lambda d: check_zero_tech_nouns(d["statement"]),
    "one-sentence-per-survivor": lambda d: check_one_sentence_per_survivor(d["survivors"]),
    "evolution-score": lambda d: evolution_score(d["dimensionScores"]),
    "council-lenses": lambda d: check_council_lenses(d["lenses"]),
    "tension-order": lambda d: check_tension_order(d["resolvedOrder"]),
    "reveal-shape": lambda d: check_reveal_shape(d["text"]),
    "handbook-draft-summary": lambda d: validate_handbook_draft_summary(d),
    "handbook-check-summary": lambda d: validate_handbook_check_summary(d),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in CHECKS:
        sys.stderr.write(f"usage: validators.py <{'|'.join(CHECKS)}>  (payload JSON on stdin)\n")
        sys.exit(2)
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        print(json.dumps({"ok": False, "errors": [f"invalid JSON on stdin: {e}"]}))
        sys.exit(1)
    try:
        result = CHECKS[sys.argv[1]](payload)
        print(json.dumps(result))
        sys.exit(0)
    except ValidationError as e:
        print(json.dumps({"ok": False, "errors": str(e).split("; ")}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"ok": False, "errors": [f"unexpected error: {e}"]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
