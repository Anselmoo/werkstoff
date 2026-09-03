#!/usr/bin/env python3
"""Known-answer tests for lehre_core's evaluator and schema.

Run before trusting any verdict this plugin produces:
    python3 plugins/lehre/scripts/test_lehre_core.py

This exists because of a rule this repository learned the hard way: verify the
instrument before trusting it. The first run of these assertions caught a real
defect -- `from src.db.session import get` reported TWO violations for one
import statement, because the extractor deliberately yields both
`src.db.session` and `src.db.session.get` so a rule may name either. Nothing
else would have noticed; the hook would still have denied, just with a doubled
count feeding every report built on top of it.
"""

from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lehre_core as C  # noqa: E402

FAILS: list[str] = []


def check(label, got, want):
    if got != want:
        FAILS.append(f"{label}: got {got!r} want {want!r}")


def expect_raises(label, exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return
    FAILS.append(f"{label}: expected {exc.__name__}, nothing raised")


BASE = {"version": 1, "provenance": "lehre", "mode": "greenfield", "rules": [], "units": []}


def rule(**over):
    base = {"id": "r", "severity": "blocking", "sourceMode": "scaffolded-default",
            "rationale": "x", "authority": {"source": "s"}}
    base.update(over)
    return base


# -- path matching, including the two globbing traps ------------------------
check("basename glob on nested path", C.matches("src/a/b.py", ["*.py"]), True)
check("dir glob", C.matches("src/domain/x.py", ["src/domain/*"]), True)
check("dir glob negative", C.matches("src/api/x.py", ["src/domain/*"]), False)
check("dotted filename spans", C.matches("report/build.py", ["report/*"]), True)
check("empty target never matches", C.matches("", ["*"]), False)

# -- dotted-module globs ----------------------------------------------------
check("package itself matches pkg.*", C._module_matches("src.domain", ["src.domain.*"]), True)
check("package child matches", C._module_matches("src.domain.model", ["src.domain.*"]), True)
check("unrelated module", C._module_matches("src.api", ["src.domain.*"]), False)

# -- import extraction ------------------------------------------------------
mods = {m for m, _ in C._imported_modules(ast.parse("from a.b import c\nimport d.e\nfrom . import f\n"))}
check("from-import yields package and member; relative skipped", mods, {"a.b", "a.b.c", "d.e"})

# -- layering (the architectural check linters generally cannot do) ---------
LAYER = rule(check={"kind": "python-import", "paths": ["src/api/*"], "forbid": ["src.db.*"]})
LAYER["enforcement"] = "hook"
v = C.evaluate_file(LAYER, "src/api/handler.py", "from src.db.session import get\n")
check("one import statement -> one violation", len(v), 1)
check("violation names the real target", v[0].detail, "imports 'src.db.session', forbidden here")
check("violation line", v[0].line, 1)
check("clean file", C.evaluate_file(LAYER, "src/api/h.py", "import src.services.x\n"), [])
check("rule scoped to its own paths", C.evaluate_file(LAYER, "src/worker/h.py", "from src.db.session import get\n"), [])

ALLOWED = rule(check={"kind": "python-import", "paths": ["src/api/*"],
                      "forbid": ["src.db.*"], "allow": ["src.db.readonly"]})
ALLOWED["enforcement"] = "hook"
check("allow-list carves out an exception",
      C.evaluate_file(ALLOWED, "src/api/h.py", "import src.db.readonly\n"), [])

# -- constructs -------------------------------------------------------------
CONS = rule(check={"kind": "python-construct", "paths": ["*.py"],
                   "forbid": ["bare-except", "mutable-default-arg"]})
CONS["enforcement"] = "hook"
check("two distinct constructs found",
      len(C.evaluate_file(CONS, "a.py", "def f(x=[]):\n    try:\n        pass\n    except:\n        pass\n")), 2)
check("broad-except not reported when not forbidden",
      C.evaluate_file(CONS, "a.py", "try:\n    pass\nexcept Exception:\n    pass\n"), [])

# -- path-only kinds --------------------------------------------------------
FORBID = rule(check={"kind": "forbid-path", "paths": ["utils.py", "utils/*"]})
FORBID["enforcement"] = "hook"
check("forbid-path fires with no content", len(C.evaluate_file(FORBID, "src/utils.py", None)), 1)

LOC = rule(check={"kind": "require-location", "paths": ["test_*.py"], "allowed": ["tests/*"]})
LOC["enforcement"] = "hook"
check("misplaced test flagged", len(C.evaluate_file(LOC, "src/test_thing.py", None)), 1)
check("correctly placed test clean", C.evaluate_file(LOC, "tests/test_thing.py", None), [])

# -- content-dependent kinds abstain when content is unknown ----------------
check("no content -> no guess", C.evaluate_file(LAYER, "src/api/h.py", None), [])

# -- unparseable is raised, never swallowed as 'clean' ----------------------
expect_raises("unparseable python", C.UnparseablePython, C.evaluate_file, CONS, "a.py", "def f(:\n")

# -- schema rejects rather than skips ---------------------------------------
check("valid minimal accepted", C.validate_ruleset(dict(BASE))["mode"], "greenfield")
expect_raises("foreign provenance", C.RulesetError, C.validate_ruleset, {**BASE, "provenance": "modernize"})
expect_raises("wrong version", C.RulesetError, C.validate_ruleset, {**BASE, "version": 99})
expect_raises("unknown check kind", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [rule(check={"kind": "grep", "paths": ["*.py"]})]})
expect_raises("unknown construct name", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [rule(check={"kind": "python-construct", "paths": ["*.py"], "forbid": ["no-such"]})]})
expect_raises("evidence-backed with no evidence", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [rule(sourceMode="evidence-backed", check={"kind": "forbid-path", "paths": ["x"]})]})
expect_raises("empty rationale", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [rule(rationale="  ", check={"kind": "forbid-path", "paths": ["x"]})]})
expect_raises("missing authority", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [{"id": "r", "severity": "blocking", "sourceMode": "scaffolded-default",
                                  "rationale": "x", "check": {"kind": "forbid-path", "paths": ["x"]}}]})
expect_raises("duplicate rule id", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [rule(check={"kind": "forbid-path", "paths": ["x"]}),
                                 rule(check={"kind": "forbid-path", "paths": ["y"]})]})
expect_raises("unit cycle", C.RulesetError, C.validate_ruleset,
              {**BASE, "units": [{"id": "a", "paths": ["a/*"], "depends_on": ["b"]},
                                 {"id": "b", "paths": ["b/*"], "depends_on": ["a"]}]})
expect_raises("dependency on unknown unit", C.RulesetError, C.validate_ruleset,
              {**BASE, "units": [{"id": "a", "paths": ["a/*"], "depends_on": ["ghost"]}]})

# -- enforcement tier is DERIVED, so a file cannot overclaim -----------------
claimed = C.validate_ruleset({**BASE, "rules": [rule(id="L", enforcement="hook",
    check={"kind": "linter", "paths": ["*.py"], "command": ["ruff", "check"]})]})
check("linter forced to gauge tier despite the file claiming hook",
      claimed["rules"][0]["enforcement"], "gauge")
expect_raises("linter not evaluable per-file", C.RulesetError,
              C.evaluate_file, claimed["rules"][0], "a.py", "x=1\n")

# -- intent / owns / must_not_know ------------------------------------------
check("intent accepted", C.validate_ruleset({**BASE, "intent": "a CLI that reads CSV"})["intent"],
      "a CLI that reads CSV")
check("absent intent is fine", C.validate_ruleset(dict(BASE)).get("intent"), None)
expect_raises("blank intent", C.RulesetError, C.validate_ruleset, {**BASE, "intent": "   "})
expect_raises("non-string intent", C.RulesetError, C.validate_ruleset, {**BASE, "intent": ["x"]})
ok_unit = C.validate_ruleset({**BASE, "units": [
    {"id": "a", "paths": ["a/*"], "depends_on": [], "owns": "the schema",
     "must_not_know": ["the output format"]}]})
check("owns round-trips", ok_unit["units"][0]["owns"], "the schema")
check("must_not_know round-trips", ok_unit["units"][0]["must_not_know"], ["the output format"])
expect_raises("must_not_know as string not list", C.RulesetError, C.validate_ruleset,
              {**BASE, "units": [{"id": "a", "paths": ["a/*"], "must_not_know": "the output format"}]})
expect_raises("blank must_not_know entry", C.RulesetError, C.validate_ruleset,
              {**BASE, "units": [{"id": "a", "paths": ["a/*"], "must_not_know": [""]}]})

# -- judgement kind: advisory-only, must carry `asks`, never evaluated -------
# severity MUST be passed explicitly: rule() defaults to blocking, and the schema
# correctly refuses a blocking judgement rule. The first run of this test proved that
# by failing on its own fixture.
JUDGE = rule(severity="advisory",
             check={"kind": "judgement", "paths": ["src/api/*"],
                    "asks": "Does this handler own business logic?"})
okj = C.validate_ruleset({**BASE, "rules": [JUDGE]})
check("judgement derives the judgement tier", okj["rules"][0]["enforcement"], "judgement")
expect_raises("blocking judgement refused", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [rule(severity="blocking",
                                      check={"kind": "judgement", "paths": ["a/*"], "asks": "q"})]})
expect_raises("judgement without asks refused", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [rule(severity="advisory",
                                      check={"kind": "judgement", "paths": ["a/*"]})]})
expect_raises("judgement with blank asks refused", C.RulesetError, C.validate_ruleset,
              {**BASE, "rules": [rule(severity="advisory",
                                      check={"kind": "judgement", "paths": ["a/*"], "asks": "  "})]})
expect_raises("judgement never evaluated per-file", C.RulesetError,
              C.evaluate_file, okj["rules"][0], "src/api/h.py", "x = 1\n")

# -- unit ordering ----------------------------------------------------------
UNITS = [{"id": "contracts", "paths": ["src/contracts/*"], "depends_on": []},
         {"id": "domain", "paths": ["src/domain/*"], "depends_on": ["contracts"]}]
check("unit resolved by path", C.unit_for("src/domain/x.py", UNITS)["id"], "domain")
check("path in no unit", C.unit_for("README.md", UNITS), None)
check("unvalidated dependency blocks", C.blocking_dependencies("/nonexistent", UNITS[1]), ["contracts"])
check("unit with no deps never blocks", C.blocking_dependencies("/nonexistent", UNITS[0]), [])

if FAILS:
    print("\n".join(f"  FAIL {f}" for f in FAILS))
    print(f"{len(FAILS)} assertion(s) failed")
    sys.exit(1)
print("lehre_core: all known-answer assertions pass")
