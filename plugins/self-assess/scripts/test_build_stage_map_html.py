#!/usr/bin/env python3
"""Tests for self-assess-stage-map's HTML viewer builder.

Two things are locked down here, both of which had already rotted once:

1. The committed demo fixture (`scripts/fixtures/sample_stage_graph.json` +
   `sample_file_stage_index.json`) still passes the REAL validator
   (`lib.validators.validate_stage_graph`, whose one rule is
   `edgeCount == len(wires)`) and still exhibits the failures self-assess
   exists to surface -- a god-module, two real dependency cycles, a dead-end,
   and one stage wired to nothing at all. C3 of
   docs/plugin-authoring/references/report-viewer-standard.md: a clean fixture
   makes a prettier screenshot and a useless one. These assertions call
   lib.graph's own find_cycles/find_god_modules, the same functions the viewer
   and self-assess-arch-health use, so the fixture cannot silently stop being
   a failing example.

2. The rendered HTML actually carries the report shell the standard requires:
   the S2 title/CSP/marker set, the R1 `class="verdict"` element, and the R4
   legend -- checked against the document with <style> blocks stripped, for
   the same reason scripts/ci/check_viewer_conformance.py strips them (confab
   defines a .legend it never uses, so a naive substring search passes on a
   viewer that has no legend at all).

Run: python3 plugins/self-assess/scripts/test_build_stage_map_html.py -v
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.graph import find_cycles, find_god_modules  # noqa: E402
from lib.validators import validate_stage_graph  # noqa: E402

BUILDER = SCRIPT_DIR / "build_stage_map_html.py"
FIXTURES = SCRIPT_DIR / "fixtures"
STAGE_GRAPH = FIXTURES / "sample_stage_graph.json"
FILE_INDEX = FIXTURES / "sample_file_stage_index.json"
TEMPLATE = SCRIPT_DIR.parent / "assets" / "stage-map-viewer.html"
D3 = SCRIPT_DIR.parent / "assets" / "inline-d3.html"
TOKENS = SCRIPT_DIR.parent / "assets" / "tokens.css"

STYLE_RE = re.compile(r"<style\b.*?</style>", re.DOTALL | re.IGNORECASE)


def build() -> tuple[dict, str]:
    """Run the real builder as a subprocess; return (stats json, html)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "STAGE_MAP.html"
        r = subprocess.run(
            [sys.executable, str(BUILDER),
             "--stage-graph", str(STAGE_GRAPH),
             "--file-stage-index", str(FILE_INDEX),
             "--template", str(TEMPLATE),
             "--d3", str(D3),
             "--tokens", str(TOKENS),
             "--out", str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout), out.read_text(encoding="utf-8")


class FixtureTests(unittest.TestCase):
    """C2/C3 -- the committed demo data is valid AND shows the failure."""

    def setUp(self):
        self.graph = json.loads(STAGE_GRAPH.read_text(encoding="utf-8"))
        self.wires = [tuple(w) for w in self.graph["wires"]]

    def test_fixture_passes_the_real_validator(self):
        validate_stage_graph(self.graph)  # raises SelfAssessError on mismatch

    def test_fixture_has_a_god_module(self):
        gods = dict(find_god_modules(self.graph["stages"], self.wires))
        self.assertTrue(gods, "fixture must contain at least one god-module")
        self.assertEqual(gods, {"core": 6})

    def test_fixture_has_real_dependency_cycles(self):
        cycles = [sorted(c) for c in find_cycles(self.graph["stages"], self.wires)]
        self.assertEqual(sorted(cycles), [["auth", "db"], ["queue", "worker"]])

    def test_fixture_has_a_dead_end_and_an_unconnected_stage(self):
        self.assertIn("utils", self.graph["deadEnds"])
        self.assertIn("sandbox", self.graph["deadEnds"])
        endpoints = {s for w in self.wires for s in w}
        self.assertNotIn("sandbox", endpoints, "sandbox must be wired to nothing")

    def test_file_stage_index_is_partial_by_design(self):
        """Rule file-stage-index-partial-coverage: only real endpoints."""
        index = json.loads(FILE_INDEX.read_text(encoding="utf-8"))
        self.assertTrue(index)
        self.assertEqual(set(index.values()), set(self.graph["stages"]))


class BuildTests(unittest.TestCase):
    """The builder joins both fixtures and annotates them from lib.graph."""

    @classmethod
    def setUpClass(cls):
        cls.stats, cls.html = build()
        cls.body = STYLE_RE.sub("", cls.html)

    def test_stats_report_the_failures(self):
        self.assertEqual(self.stats["stats"], {
            "stageCount": 11, "edgeCount": 16,
            "cycleCount": 2, "godModuleCount": 1,
        })

    def test_injection_markers_are_all_consumed(self):
        for marker in ("<!--__DESIGN_TOKENS__-->", "<!--__D3_SUBSET__-->",
                       "/*__STAGE_MAP_DATA__*/ null"):
            self.assertNotIn(marker, self.html)
        self.assertIn("window.d3", self.html)
        self.assertIn("--status-warn:", self.html)

    def test_payload_carries_the_annotated_graph(self):
        self.assertIn('"godModuleFanIn": 6', self.html)
        self.assertIn('"inCycle": true', self.html)
        self.assertIn('"deadEnd": true', self.html)

    def test_s2_head(self):
        self.assertIn("<title>self-assess — stage map</title>", self.html)
        self.assertIn("default-src 'none'", self.html)
        # S1 -- the 61px header literal, checked on the TEMPLATE: the built
        # page legitimately contains it via tokens.css's own --header-h.
        self.assertNotIn("61px", TEMPLATE.read_text(encoding="utf-8"))

    def test_r1_verdict_is_in_static_markup(self):
        self.assertIn('class="verdict"', self.body)

    def test_r4_legend_needs_no_interaction(self):
        """Every colour the canvas assigns is named in always-visible markup."""
        self.assertIn('class="legend"', self.body)
        for label in ("god-module", "dependency cycle", "dead-end", "ordinary stage"):
            self.assertIn(label, self.body)

    def test_r2_findings_are_not_printed_twice(self):
        """The subtitle carries scope; the verdict carries the findings."""
        self.assertNotIn('" cycle(s)"', self.html)
        self.assertNotIn('" god-module(s)"', self.html)


if __name__ == "__main__":
    unittest.main()
