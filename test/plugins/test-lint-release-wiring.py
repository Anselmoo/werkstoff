#!/usr/bin/env python3
"""Calibration for lint-release-wiring.py: prove it catches drift before trusting it.

    python3 test/plugins/test-lint-release-wiring.py

A drift guard that cannot fail is worse than no guard: it reports success every
run and nobody looks again. So this builds a throwaway copy of the four files
the guard reads, breaks one thing at a time, and asserts the guard notices.

Its first run earned its place immediately. The guard's reverse check ("a name
in a list with no plugin directory is stale") fired on `werkstoff-cli`, which is
a legitimate version group targeting tools/werkstoff-cli/pyproject.toml rather
than a plugin -- so the guard failed on a clean tree and would have broken CI on
its first commit. Which groups are plugin groups is now derived from each
group's own version_targets path.

Each case is (mutation, expected exit code, expected substring). The substring
matters as much as the code: a guard that fails for the wrong reason is a guard
that will be "fixed" by silencing the wrong thing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = "test/plugins/lint-release-wiring.py"
WORKFLOWS = ("plugin-release.yml", "auto-version-bump.yml")
FAILURES: list[str] = []


def build_box() -> Path:
    """A minimal tree containing only what the guard reads."""
    box = Path(tempfile.mkdtemp(prefix="release-wiring-"))
    (box / "test/plugins").mkdir(parents=True)
    (box / ".github/workflows").mkdir(parents=True)
    shutil.copy(REPO_ROOT / GUARD, box / GUARD)
    shutil.copy(REPO_ROOT / ".rrt.toml", box / ".rrt.toml")
    for name in WORKFLOWS:
        shutil.copy(REPO_ROOT / ".github/workflows" / name, box / ".github/workflows" / name)
    for manifest in sorted(REPO_ROOT.glob("plugins/*/.claude-plugin/plugin.json")):
        target = box / "plugins" / manifest.parent.parent.name / ".claude-plugin"
        target.mkdir(parents=True)
        shutil.copy(manifest, target / "plugin.json")
    return box


def edit(box: Path, rel: str, fn) -> None:
    path = box / rel
    path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8")


def case(label: str, mutate, want_rc: int, want_text: str) -> None:
    box = build_box()
    try:
        mutate(box)
        proc = subprocess.run([sys.executable, str(box / GUARD)],
                              capture_output=True, text=True, timeout=60)
        out = proc.stdout + proc.stderr
        ok = proc.returncode == want_rc and want_text.lower() in out.lower()
        print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} rc={proc.returncode}")
        if not ok:
            FAILURES.append(label)
            print("        " + out.strip()[:300].replace("\n", "\n        "))
    finally:
        shutil.rmtree(box, ignore_errors=True)


RELEASE = ".github/workflows/plugin-release.yml"
BUMP = ".github/workflows/auto-version-bump.yml"
#: Any wired plugin works as the probe; lehre is used because its omission from
#: these very lists is what prompted this guard.
PROBE = "lehre"

case("clean tree passes", lambda _box: None, 0, "0 failure(s)")

case("missing .rrt.toml version_group",
     lambda b: edit(b, ".rrt.toml", lambda t: re.sub(
         r'\[\[tool\.rrt\.version_groups\]\]\nname = "' + PROBE + r'"\n(?:.*\n)*?  kind = "package_json"\n\n',
         "", t)), 1, "version_groups")

case("missing .rrt.toml field_targets",
     lambda b: edit(b, ".rrt.toml", lambda t: re.sub(
         r'\[\[tool\.rrt\.field_targets\]\]\nsource = "plugins/' + PROBE + r'/[^\n]*\n(?:[^\n]*\n)*?\]\n\n',
         "", t)), 1, "field_targets")

case("missing plugin-release.yml allowlist entry",
     lambda b: edit(b, RELEASE, lambda t: t.replace(f"|{PROBE}|takt)", "|takt)")),
     1, "plugin-release.yml")

case("missing auto-version-bump.yml matcher",
     lambda b: edit(b, BUMP, lambda t: re.sub(rf"^.*\^plugins/{PROBE}/.*\n", "", t, flags=re.M)),
     1, "auto-version-bump.yml")

case("stale name in allowlist (no plugin dir)",
     lambda b: edit(b, RELEASE, lambda t: t.replace(f"|{PROBE}|takt)", f"|{PROBE}|ghost|takt)")),
     1, "no plugins/ghost/")

# Structural changes must fail LOUDLY. A guard that silently finds zero names in
# a restructured file and reports success is the exact defect it exists to stop.
case("restructured release wf fails loudly",
     lambda b: edit(b, RELEASE, lambda t: t.replace("Unknown plugin group", "Unrecognised group")),
     1, "restructured")

case("restructured bump wf fails loudly",
     lambda b: edit(b, BUMP, lambda t: t.replace("^plugins/", "^PLUGINS/")),
     1, "restructured")

case("empty plugin set refuses to pass",
     lambda b: shutil.rmtree(b / "plugins"), 1, "refusing to report success")

if FAILURES:
    print(f"\n{len(FAILURES)} calibration case(s) failed -- fix the GUARD before trusting it")
    sys.exit(1)
print("\nlint-release-wiring: instrument verified against 9 known answers")
