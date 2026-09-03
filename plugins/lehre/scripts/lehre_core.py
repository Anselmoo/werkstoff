#!/usr/bin/env python3
"""Shared ruleset schema, predicate evaluator, and unit-order model for lehre.

WHY ONE FILE. Two consumers evaluate the same rules: the PreToolUse hook
(`hooks/lehre_guard.py`, which denies a write) and the gauge skill (which
sweeps a tree and reports). If each carried its own evaluator they would drift,
and the drift would be silent -- a rule the hook denies but the gauge calls
clean, or the reverse. Both import this module. There is exactly one definition
of what a rule means.

WHY A CLOSED CHECK VOCABULARY. The hook is `type: "command"`. It cannot ask a
model anything, so a rule is only enforceable at write time if its predicate is
deterministic. This module accepts five check kinds and rejects every other
value rather than skipping it -- an unknown kind is a schema error, never a
silently-unevaluated rule.

WHY NO REGEX. Path matching is fnmatch throughout, and structural matching is
Python's stdlib `ast`. This repository's CLAUDE.md catalogues six defects whose
common shape is "code that looks correct and silently does nothing", and three
of the six are regex forms: `[^.]{0,80}` cannot span a dotted filename,
`[^\n]` in a bracket expression means "not backslash, not the letter n", and
`\b!==\b` never matches because no word character is adjacent to `!`. A glob
cannot express any of those failures and an AST walk does not need to.

ENFORCEMENT TIER IS DERIVED, NOT DECLARED. `enforcement` is computed from the
check kind by `validate_ruleset` and is never taken from the file. Four kinds
are evaluable inside a PreToolUse hook; `linter` is not, because the content
being written is not on disk yet and shelling a linter out to a temp tree
inside a 15-second hook is neither fast nor trustworthy. A `linter` rule is
therefore gauge-tier: real, blocking in a sweep or in CI, and honestly NOT a
write-time denial. Declaring it otherwise in the file cannot make it so, which
is the point -- the alternative is a rule everyone believes blocks and doesn't.
"""

from __future__ import annotations

import ast
import fnmatch
import json
import os
from typing import Any

SCHEMA_VERSION = 1
PROVENANCE = "lehre"

#: Check kinds a PreToolUse hook can decide on its own, with no subprocess and
#: no filesystem state beyond the file being written.
HOOK_KINDS = ("forbid-path", "require-location", "python-import", "python-construct")
#: Evaluable only in a sweep, where the tree is real and on disk.
GAUGE_KINDS = ("linter",)
#: Not machine-evaluable at all, by admission rather than by omission.
#:
#: `doctrine-researcher` is instructed to return candidates whose predicate is
#: NONE -- "is this a process boundary", "does this handler own business logic" --
#: and `lehre-codify` is told to file those as advisory. Before this kind existed
#: the schema then refused to persist them, because `check.kind` had to be one of
#: the five machine kinds. So the pipeline researched a rule class it could not
#: store, and `violation-auditor` (whose whole job is auditing exactly that class)
#: was dispatched by nothing, because nothing could ever be in its input set.
#: A judgement rule is the honest home for those: recorded, justified, reported by
#: the gauge as needing a human/agent pass, and never silently counted as clean.
JUDGEMENT_KINDS = ("judgement",)
CHECK_KINDS = HOOK_KINDS + GAUGE_KINDS + JUDGEMENT_KINDS

SEVERITIES = ("blocking", "advisory")
#: How a rule earned the right to exist. Greenfield has no repo to cite, so
#: `scaffolded-default` is its normal case, not a degraded one -- and a rule
#: claiming `evidence-backed` while citing a file that does not exist is the
#: specific fabrication `rule-critic` is dispatched to catch.
SOURCE_MODES = ("evidence-backed", "intent-derived", "scaffolded-default")

#: Named Python constructs a rule may forbid. A closed set, because "forbid an
#: arbitrary node shape" is where a deterministic check quietly becomes a
#: half-implemented linter.
PY_CONSTRUCTS = {
    "bare-except": "a bare `except:` clause",
    "broad-except": "`except Exception` / `except BaseException`",
    "wildcard-import": "`from x import *`",
    "mutable-default-arg": "a mutable default argument ([], {}, set())",
    "global-statement": "a `global` statement",
    "print-call": "a bare `print(...)` call",
    "assert-statement": "an `assert` statement (stripped under `python -O`)",
}


class RulesetError(Exception):
    """Raised for any malformed ruleset.

    Loudly, and never as a return of an empty list: a schema error that
    degrades to "no rules" is a guard that disables itself on a typo.
    """


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def relative(cwd: str, path: str) -> str:
    """Repo-relative posix form, so `src/domain/*` matches whether the tool
    reported an absolute or a relative path."""
    if not path:
        return ""
    candidate = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        rel = os.path.relpath(os.path.normpath(candidate), os.path.normpath(cwd))
    except ValueError:
        rel = path
    return rel.replace(os.sep, "/")


def matches(target: str, patterns: Any) -> bool:
    """fnmatch against the full repo-relative path AND the bare basename.

    Both, because a rule author writes `*.py` meaning "any Python file" and
    `src/domain/*` meaning "this directory" -- and `fnmatch("src/a/b.py",
    "*.py")` is True while `fnmatch("src/a/b.py", "src/domain/*")` needs the
    full path. Checking only one of the two would silently drop half the
    patterns a reasonable author writes.
    """
    if not target or not isinstance(patterns, list):
        return False
    base = target.rsplit("/", 1)[-1]
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern:
            continue
        if fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(base, pattern):
            return True
    return False


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

def _require(cond: bool, message: str) -> None:
    if not cond:
        raise RulesetError(message)


def enforcement_for(kind: str) -> str:
    """Derived, never read from the file. See the module docstring."""
    if kind in HOOK_KINDS:
        return "hook"
    if kind in GAUGE_KINDS:
        return "gauge"
    return "judgement"


def validate_ruleset(data: Any) -> dict:
    """Validate and normalise a parsed ruleset. Raises RulesetError."""
    _require(isinstance(data, dict), "ruleset must be a JSON object")
    _require(
        data.get("provenance") == PROVENANCE,
        f"ruleset provenance must be {PROVENANCE!r} -- refusing to read a file "
        f"written by another pipeline (see docs/orchestration/references/routing.md "
        f"on the unguarded MODERNIZATION_BRIEF.md clash this guard exists to avoid)",
    )
    _require(
        data.get("version") == SCHEMA_VERSION,
        f"ruleset version must be {SCHEMA_VERSION}, got {data.get('version')!r}",
    )
    mode = data.get("mode")
    _require(mode in ("greenfield", "brownfield"), f"mode must be greenfield|brownfield, got {mode!r}")

    # The verbatim project intent, recorded by lehre-decompose. Optional, but
    # spec-fidelity-auditor cannot run without it -- and a fidelity check is the
    # only thing in this plugin that can catch a unit which satisfies every rule
    # and still is not what it was for. Stored rather than remembered, because a
    # session's recollection of what the user asked for is not evidence.
    intent = data.get("intent")
    _require(intent is None or (isinstance(intent, str) and intent.strip()),
             "ruleset.intent, when present, must be a non-empty string")

    rules = data.get("rules")
    _require(isinstance(rules, list), "ruleset.rules must be a list")
    seen_ids: set[str] = set()
    for rule in rules:
        _require(isinstance(rule, dict), "each rule must be an object")
        rid = rule.get("id")
        _require(isinstance(rid, str) and rid, "each rule needs a non-empty string id")
        _require(rid not in seen_ids, f"duplicate rule id {rid!r}")
        seen_ids.add(rid)
        _require(rule.get("severity") in SEVERITIES, f"rule {rid}: severity must be blocking|advisory")
        _require(rule.get("sourceMode") in SOURCE_MODES, f"rule {rid}: sourceMode must be one of {SOURCE_MODES}")
        _require(
            isinstance(rule.get("rationale"), str) and rule["rationale"].strip(),
            f"rule {rid}: needs a non-empty rationale -- a rule nobody can justify is a rule nobody should obey",
        )
        authority = rule.get("authority")
        _require(
            isinstance(authority, dict) and isinstance(authority.get("source"), str) and authority["source"].strip(),
            f"rule {rid}: needs authority.source (the external doctrine it rests on)",
        )
        if rule["sourceMode"] == "evidence-backed":
            ev = rule.get("evidence")
            _require(
                isinstance(ev, list) and ev,
                f"rule {rid}: sourceMode 'evidence-backed' requires a non-empty evidence list. "
                f"If this repository has no such file yet, the honest mode is 'scaffolded-default'",
            )
        check = rule.get("check")
        _require(isinstance(check, dict), f"rule {rid}: needs a check object")
        kind = check.get("kind")
        _require(
            kind in CHECK_KINDS,
            f"rule {rid}: unknown check kind {kind!r}. Allowed: {CHECK_KINDS}. "
            f"An unknown kind is a schema error, never a skipped rule",
        )
        _require(isinstance(check.get("paths"), list) and check["paths"],
                 f"rule {rid}: check.paths must be a non-empty list of globs")
        if kind == "require-location":
            _require(isinstance(check.get("allowed"), list) and check["allowed"],
                     f"rule {rid}: require-location needs a non-empty check.allowed")
        if kind == "python-import":
            _require(isinstance(check.get("forbid"), list) and check["forbid"],
                     f"rule {rid}: python-import needs a non-empty check.forbid")
        if kind == "python-construct":
            forbid = check.get("forbid")
            _require(isinstance(forbid, list) and forbid,
                     f"rule {rid}: python-construct needs a non-empty check.forbid")
            for name in forbid:
                _require(name in PY_CONSTRUCTS,
                         f"rule {rid}: unknown construct {name!r}. Allowed: {sorted(PY_CONSTRUCTS)}")
        if kind == "linter":
            _require(isinstance(check.get("command"), list) and check["command"],
                     f"rule {rid}: linter needs check.command as an argv list")
        if kind == "judgement":
            # Advisory-only, enforced here rather than trusted. A blocking rule no
            # machine can decide is a rule everyone believes blocks and which fires
            # never -- the precise failure this plugin's enforcement tiers exist to
            # make impossible, so it must be a schema error rather than a footnote.
            _require(
                rule["severity"] == "advisory",
                f"rule {rid}: check kind 'judgement' cannot be blocking -- nothing can "
                f"evaluate it, so a blocking judgement rule would deny nothing while "
                f"appearing to. File it as advisory, or give it a machine predicate",
            )
            _require(
                isinstance(check.get("asks"), str) and check["asks"].strip(),
                f"rule {rid}: judgement needs check.asks -- the single question an auditor "
                f"must answer by reading. Without it there is nothing to dispatch on",
            )
        rule["enforcement"] = enforcement_for(kind)

    units = data.get("units", [])
    _require(isinstance(units, list), "ruleset.units must be a list")
    unit_ids = set()
    for unit in units:
        _require(isinstance(unit, dict), "each unit must be an object")
        uid = unit.get("id")
        _require(isinstance(uid, str) and uid, "each unit needs a non-empty string id")
        _require(uid not in unit_ids, f"duplicate unit id {uid!r}")
        unit_ids.add(uid)
        _require(isinstance(unit.get("paths"), list) and unit["paths"],
                 f"unit {uid}: needs a non-empty paths list")
        deps = unit.get("depends_on", [])
        _require(isinstance(deps, list), f"unit {uid}: depends_on must be a list")
        owns = unit.get("owns")
        _require(owns is None or (isinstance(owns, str) and owns.strip()),
                 f"unit {uid}: owns, when present, must be a non-empty string")
        # The negative space. This is what becomes an enforceable python-import
        # rule, and what spec-fidelity-auditor checks by reading imports rather
        # than by trusting that a layering rule was written for every seam.
        forbidden = unit.get("must_not_know")
        _require(forbidden is None or isinstance(forbidden, list),
                 f"unit {uid}: must_not_know, when present, must be a list of strings")
        if isinstance(forbidden, list):
            for item in forbidden:
                _require(isinstance(item, str) and item.strip(),
                         f"unit {uid}: every must_not_know entry must be a non-empty string")
    for unit in units:
        for dep in unit.get("depends_on", []):
            _require(dep in unit_ids, f"unit {unit['id']}: depends_on unknown unit {dep!r}")
    _require(not _cycle(units), "unit dependency graph contains a cycle")
    data["units"] = units
    return data


def _cycle(units: list) -> bool:
    """Kahn's algorithm. A cycle means no build order exists, so the ordering
    gate could never be satisfied -- caught at codify time, not at first deny."""
    incoming = {u["id"]: set(u.get("depends_on", [])) for u in units}
    ready = [uid for uid, deps in incoming.items() if not deps]
    resolved = 0
    while ready:
        current = ready.pop()
        resolved += 1
        for uid, deps in incoming.items():
            if current in deps:
                deps.discard(current)
                if not deps:
                    ready.append(uid)
    return resolved != len(incoming)


def load_ruleset(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return validate_ruleset(json.load(handle))


# --------------------------------------------------------------------------
# Python AST checks
# --------------------------------------------------------------------------

def _imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    """Every module name this file imports, with its line number.

    `from a.b import c` yields `a.b`, and also `a.b.c` -- because a layering
    rule forbidding `a.b.c` must catch it whether it was reached as a module
    import or as a from-import member, and the AST does not distinguish which
    of the two `c` is.
    """
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import; not addressable by absolute glob
                continue
            module = node.module or ""
            if module:
                found.append((module, node.lineno))
                for alias in node.names:
                    found.append((f"{module}.{alias.name}", node.lineno))
    return found


def _module_matches(name: str, patterns: list) -> bool:
    """Dotted-module glob. `src.domain.*` must also match `src.domain` itself,
    because a rule forbidding a package means the package, not only its
    children -- the off-by-one that would let `import src.domain` slip past a
    rule written to ban exactly that."""
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern:
            continue
        if fnmatch.fnmatch(name, pattern):
            return True
        if pattern.endswith(".*") and name == pattern[:-2]:
            return True
    return False


def _find_constructs(tree: ast.AST, forbid: list) -> list[tuple[str, int]]:
    hits: list[tuple[str, int]] = []
    wanted = {name for name in forbid if name in PY_CONSTRUCTS}
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if "bare-except" in wanted and node.type is None:
                hits.append(("bare-except", node.lineno))
            if "broad-except" in wanted and isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
                hits.append(("broad-except", node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if "wildcard-import" in wanted and any(a.name == "*" for a in node.names):
                hits.append(("wildcard-import", node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if "mutable-default-arg" in wanted:
                for default in list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        hits.append(("mutable-default-arg", default.lineno))
        elif isinstance(node, ast.Global):
            if "global-statement" in wanted:
                hits.append(("global-statement", node.lineno))
        elif isinstance(node, ast.Assert):
            if "assert-statement" in wanted:
                hits.append(("assert-statement", node.lineno))
        elif isinstance(node, ast.Call):
            if "print-call" in wanted and isinstance(node.func, ast.Name) and node.func.id == "print":
                hits.append(("print-call", node.lineno))
    return hits


class UnparseablePython(Exception):
    """The file could not be parsed, so an AST rule could not be decided.

    Deliberately distinct from "no violation found". The caller decides what to
    do with it, and for a blocking rule the answer is deny -- an edit that
    cannot be checked against a gate the repository opted into is the silent
    bypass the gate exists to prevent.
    """


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------

class Violation:
    __slots__ = ("rule_id", "severity", "path", "line", "detail", "rationale")

    def __init__(self, rule_id, severity, path, line, detail, rationale):
        self.rule_id = rule_id
        self.severity = severity
        self.path = path
        self.line = line
        self.detail = detail
        self.rationale = rationale

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule_id, "severity": self.severity, "path": self.path,
            "line": self.line, "detail": self.detail, "rationale": self.rationale,
        }

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"[{self.severity}] {self.rule_id} at {where} -- {self.detail}"


def evaluate_file(rule: dict, path: str, content: str | None) -> list[Violation]:
    """Every violation of ONE rule in ONE file.

    `content` is None when only the path is known (a delete, or a sweep that
    has not read the file). Content-dependent kinds return no violations in
    that case rather than guessing; path-only kinds still decide.
    """
    check = rule["check"]
    kind = check["kind"]
    if not matches(path, check["paths"]):
        return []

    rid, sev, why = rule["id"], rule["severity"], rule["rationale"]

    if kind == "forbid-path":
        return [Violation(rid, sev, path, None,
                          f"path matches a forbidden pattern {check['paths']}", why)]

    if kind == "require-location":
        if matches(path, check["allowed"]):
            return []
        return [Violation(rid, sev, path, None,
                          f"must live under one of {check['allowed']}", why)]

    if kind in ("python-import", "python-construct"):
        if content is None:
            return []
        try:
            tree = ast.parse(content)
        except (SyntaxError, ValueError) as exc:
            raise UnparseablePython(f"{path}: {exc}") from exc
        if kind == "python-import":
            allow = check.get("allow") or []
            out = []
            # One import STATEMENT must yield one violation. `_imported_modules`
            # deliberately reports both `a.b` and `a.b.c` for
            # `from a.b import c`, because a rule may name either -- but a glob
            # broad enough to match both would otherwise report the same line
            # twice, inflating any count taken from this list. Dedupe by line,
            # keeping the shortest matching name (the real import target).
            by_line: dict[int, str] = {}
            for module, line in _imported_modules(tree):
                if not _module_matches(module, check["forbid"]):
                    continue
                if _module_matches(module, allow):
                    continue
                if line not in by_line or len(module) < len(by_line[line]):
                    by_line[line] = module
            for line in sorted(by_line):
                out.append(Violation(rid, sev, path, line,
                                     f"imports {by_line[line]!r}, forbidden here", why))
            return out
        return [Violation(rid, sev, path, line, f"uses {PY_CONSTRUCTS[name]}", why)
                for name, line in _find_constructs(tree, check["forbid"])]

    # `linter` is gauge-tier and run by the sweep; `judgement` is not machine
    # evaluable at all. Reaching this point means the caller asked the wrong
    # evaluator; say so rather than returning "clean", which is how a rule that
    # was never checked becomes a rule reported as passing.
    raise RulesetError(f"rule {rid}: kind {kind!r} is {rule['enforcement']}-tier, not evaluable per-file here")


# --------------------------------------------------------------------------
# Unit ordering
# --------------------------------------------------------------------------

def unit_for(path: str, units: list) -> dict | None:
    for unit in units:
        if matches(path, unit["paths"]):
            return unit
    return None


def unit_done_marker(root: str, unit_id: str) -> str:
    return os.path.join(root, ".lehre", "units", f"{unit_id}.done")


def blocking_dependencies(cwd: str, unit: dict) -> list[str]:
    """Dependencies of `unit` that have not been validated yet.

    The marker is written by lehre-validate, never by conform -- so a unit is
    not "done" because someone wrote its files, it is done because its rules
    and its seam were checked. That distinction is the whole point: the loose
    loop this plugin replaces marks work complete on the author's say-so.
    """
    return [dep for dep in unit.get("depends_on", [])
            if not os.path.exists(unit_done_marker(cwd, dep))]
