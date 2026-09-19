#!/usr/bin/env python3
"""Assert every academic fixture's planted property is still mechanically detectable.

Why this exists: a fixture is an INSTRUMENT. `plugins/arbeitsplan/scripts/subrun.py` copies one
into a cell and scores what a workflow did to it, so a fixture whose planted defect has been
accidentally repaired -- or whose failing test was quietly made to pass -- turns the whole sweep
into a green run over nothing. That is this repository's signature failure: code that looks
correct and silently does nothing. `calibrate-then-measure` says the instrument is verified
BEFORE it decides anything expensive, and this file is that verification.

Each check states the planted property as a POSITIVE assertion about detectability, never as
"the tests pass" -- for three of these fixtures a passing test suite is the defect.

Exit 0 iff every planted property is present and detectable.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# A fixture must never ask a model to work on werkstoff itself: the examples are academic.
FORBIDDEN_REFERENCES = ("plugins/andon", "plugins/arbeitsplan", "plugins/nacharbeit", "werkstoff/plugins")


class Failure(Exception):
    """A planted property is missing, so the fixture set cannot measure anything."""


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a command in a fixture, never raising on a non-zero exit -- the exit IS the signal."""
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, timeout=120)


def check_numerics_feature_is_missing() -> str:
    """numerics-greenfield: the wanted feature is absent and its suite says so."""
    root = FIXTURES / "numerics-greenfield"
    wanted = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], root)
    if wanted.returncode == 0:
        raise Failure("numerics-greenfield: the suite PASSES, so logsumexp already exists -- "
                      "there is no feature left to build and the cell would measure nothing")
    if "logsumexp" not in (wanted.stderr + wanted.stdout):
        raise Failure("numerics-greenfield: the suite fails for some reason OTHER than the "
                      "missing logsumexp; the planted gap is not what a cell would hit")
    done = _run([sys.executable, "-m", "unittest", "tests.test_summation"], root)
    if done.returncode != 0:
        raise Failure("numerics-greenfield: the ALREADY-implemented kahan_sum suite fails, so a "
                      "cell cannot tell its own regression from the starting state")
    return "logsumexp missing (suite red), kahan_sum green"


def _import_graph(package: Path) -> dict[str, set[str]]:
    """Module -> modules it imports, from the AST. Import statements inside functions count."""
    graph: dict[str, set[str]] = {}
    for module in sorted(package.glob("*.py")):
        edges: set[str] = set()
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                edges.add(node.module.split(".")[-1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    edges.add(alias.name.split(".")[-1])
        graph[module.stem] = edges
    return graph


def _find_cycle(graph: dict[str, set[str]]) -> list[str]:
    """Any cycle, as a list of module names. Empty when the graph is acyclic."""
    for start in graph:
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            for neighbour in graph.get(node, set()):
                if neighbour == start:
                    return [*path, neighbour]
                if neighbour in graph and neighbour not in path:
                    stack.append((neighbour, [*path, neighbour]))
    return []


def check_toy_pipeline_cycle() -> str:
    """toy-pipeline: a real import cycle, not a documented one."""
    cycle = _find_cycle(_import_graph(FIXTURES / "toy-pipeline" / "pipeline"))
    if not cycle:
        raise Failure("toy-pipeline: no import cycle found -- the planted architecture defect is "
                      "gone, so an arch-health workflow has nothing real to detect")
    return "import cycle " + " -> ".join(cycle)


def check_median_bug() -> str:
    """median-seeded: the seeded off-by-one is live and a test pins the right answer."""
    root = FIXTURES / "median-seeded"
    result = _run([sys.executable, "-m", "unittest", "discover", "-t", "."], root)
    if result.returncode == 0:
        raise Failure("median-seeded: the suite PASSES, so the seeded off-by-one has been fixed "
                      "and a debugging cell would have no bug to find")
    if "2.5" not in (result.stderr + result.stdout):
        raise Failure("median-seeded: the suite fails, but not on the even-length case that "
                      "states the correct median -- the failure is not the planted one")
    return "median() off-by-one live (even-length case red)"


def check_ui_defects() -> str:
    """element-card-ui: an image with no alt, and raw hex where a token belongs."""
    html = (FIXTURES / "element-card-ui" / "index.html").read_text(encoding="utf-8")
    images = re.findall(r"<img\b[^>]*>", html)
    if not images:
        raise Failure("element-card-ui: no <img> at all, so the missing-alt finding is gone")
    if all("alt=" in tag for tag in images):
        raise Failure("element-card-ui: every <img> now has alt text -- the planted "
                      "accessibility defect a UI audit is meant to catch is gone")
    css = (FIXTURES / "element-card-ui" / "styles.css").read_text(encoding="utf-8")
    hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", css)
    if len(hexes) < 3:
        raise Failure("element-card-ui: fewer than three raw hex colours remain, so there is "
                      "little for a design-token workflow to derive")
    return f"{len(images)} img without alt, {len(hexes)} raw hex colours"


def check_toy_plugin_vague_description() -> str:
    """toy-plugin: the description says what it IS, never WHEN to use it."""
    skill = FIXTURES / "toy-plugin" / "skills" / "toy-check" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    if not match:
        raise Failure("toy-plugin: SKILL.md has no description line at all -- that is a "
                      "different defect (it would not load) than the planted vague one")
    description = match.group(1).lower()
    if "use when" in description or "use this when" in description:
        raise Failure("toy-plugin: the description now carries a trigger condition, so the "
                      "planted vagueness a plugin review is meant to find is gone")
    return "SKILL.md description carries no trigger condition"


def check_plan_under_lock() -> str:
    """plan-under-lock: an open run-scope lock with a scope narrow enough to deny."""
    lock = FIXTURES / "plan-under-lock" / "analysis" / "arbeitsplan" / "run_scope.json"
    data = json.loads(lock.read_text(encoding="utf-8"))
    scope = data.get("writeScope")
    if not scope:
        raise Failure("plan-under-lock: run_scope.json declares no writeScope, and an absent "
                      "scope is never read as 'anything' -- the lock would gate nothing")
    if data.get("sharedTreeWritable") is not False:
        raise Failure("plan-under-lock: the lock leaves the shared tree writable, so no write "
                      "would be denied and the hazard cannot reproduce")
    return f"lock open, writeScope {scope}"


def check_examples_are_academic() -> str:
    """No fixture points a model at werkstoff's own source."""
    offenders = []
    for path in FIXTURES.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        # fixtures/README.md names the hazard fixture's own guard by path, which is description,
        # not a task; only files that would reach a model as WORK are checked.
        if path.name == "README.md" and path.parent == FIXTURES:
            continue
        for needle in FORBIDDEN_REFERENCES:
            if needle in text:
                offenders.append(f"{path.relative_to(FIXTURES)} mentions {needle}")
    if offenders:
        raise Failure("a fixture points at werkstoff's own code, so the example is not "
                      "academic: " + "; ".join(offenders))
    return "no fixture references werkstoff source"


CHECKS = (
    ("numerics-greenfield", check_numerics_feature_is_missing),
    ("toy-pipeline", check_toy_pipeline_cycle),
    ("median-seeded", check_median_bug),
    ("element-card-ui", check_ui_defects),
    ("toy-plugin", check_toy_plugin_vague_description),
    ("plan-under-lock", check_plan_under_lock),
    ("all fixtures", check_examples_are_academic),
)


def main() -> int:
    failures = []
    for name, check in CHECKS:
        try:
            detail = check()
        except Failure as exc:
            print(f"  FAIL {name}: {exc}")
            failures.append(name)
        else:
            print(f"  ok   {name}: {detail}")
    print()
    if failures:
        print(f"FIXTURE VERIFICATION FAILED ({len(failures)}): "
              "the instrument cannot measure what it claims to measure.")
        return 1
    print(f"all {len(CHECKS)} planted properties present and detectable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
