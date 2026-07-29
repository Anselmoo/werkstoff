#!/usr/bin/env python3
"""Regression tests for the standalone symbol-indexer bundle."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent  # tools/symbol-indexer -> tools -> repo root
SCRIPT = ROOT / "build_symbol_index.py"
SPEC = importlib.util.spec_from_file_location("symbol_indexer", SCRIPT)
assert SPEC and SPEC.loader
INDEXER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = INDEXER
SPEC.loader.exec_module(INDEXER)


class SymbolIndexerTest(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "src").mkdir()
        (root / "src" / "service.py").write_text(
            '"""Example service."""\nclass Service:\n    def run(self, name):\n        return name\n',
            encoding="utf-8",
        )
        (root / "README.md").write_text("# Example\nUse --verbose for output.\n", encoding="utf-8")
        return temporary

    def test_snapshot_is_complete_and_reusable(self) -> None:
        temporary = self.make_repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        pointer, reused = INDEXER.build_or_reuse(root, "fixture", False)
        self.assertFalse(reused)
        run = root / "analysis" / "fixture" / "runs" / pointer["generation_id"]
        self.assertTrue((run / "symbol_index.json").is_file())
        self.assertTrue((run / "file_catalog.json").is_file())
        self.assertTrue((run / "artifact_manifest.json").is_file())
        self.assertTrue((run / "evidence_index.json").is_file())
        index = json.loads((run / "symbol_index.json").read_text())
        self.assertEqual(index["plugin_name"], "fixture")
        self.assertEqual(index["generation_id"], pointer["generation_id"])
        self.assertIn("Service.run", {symbol["name"] for symbol in index["symbols"]})
        pointer_again, reused_again = INDEXER.build_or_reuse(root, "fixture", False)
        self.assertTrue(reused_again)
        self.assertEqual(pointer_again["generation_id"], pointer["generation_id"])

    def test_runs_ndjson_records_each_build_and_reuse(self) -> None:
        temporary = self.make_repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        pointer, reused = INDEXER.build_or_reuse(root, "fixture", False)
        self.assertFalse(reused)
        pointer_again, reused_again = INDEXER.build_or_reuse(root, "fixture", False)
        self.assertTrue(reused_again)
        log_path = root / "analysis" / "fixture" / "runs.ndjson"
        lines = log_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2, "one line per build_or_reuse call, build and reuse alike")
        built_entry, reused_entry = (json.loads(line) for line in lines)
        self.assertFalse(built_entry["reused"])
        self.assertEqual(built_entry["generation_id"], pointer["generation_id"])
        self.assertEqual(built_entry["plugin_name"], "fixture")
        self.assertGreaterEqual(built_entry["file_count"], 1)
        self.assertGreaterEqual(built_entry["duration_ms"], 0)
        self.assertTrue(reused_entry["reused"])
        self.assertEqual(reused_entry["generation_id"], pointer_again["generation_id"])
        self.assertEqual(built_entry["source_fingerprint"], reused_entry["source_fingerprint"])

    def test_concurrent_builders_publish_one_valid_generation(self) -> None:
        temporary = self.make_repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: INDEXER.build_or_reuse(root, "fixture", False), range(4)))
        generations = {pointer["generation_id"] for pointer, _ in results}
        self.assertEqual(len(generations), 1)
        current = json.loads((root / "analysis" / "fixture" / "current.json").read_text())
        self.assertIn(current["generation_id"], generations)

    def test_fts_query_returns_line_addressable_results(self) -> None:
        temporary = self.make_repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        pointer, _ = INDEXER.build_or_reuse(root, "fixture", False)
        database = root / "analysis" / "fixture" / "runs" / pointer["generation_id"] / "search.sqlite"
        if not database.exists():
            self.skipTest("SQLite FTS5 unavailable in this Python runtime")
        matches = INDEXER.query_fts(database, "verbose", 5)
        self.assertEqual(matches[0]["file"], "README.md")
        self.assertEqual(matches[0]["line"], 2)

    def test_every_extension_is_cataloged_under_one_second(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number, extension in enumerate(INDEXER.LANG_EXTENSIONS, start=1):
                (root / f"fixture_{number}{extension}").write_text("# fixture\n", encoding="utf-8")
            started = time.monotonic()
            pointer, _ = INDEXER.build_or_reuse(root, "fixture", True)
            elapsed = time.monotonic() - started
            index = json.loads((root / "analysis" / "fixture" / "runs" / pointer["generation_id"] / "symbol_index.json").read_text())
            self.assertEqual(index["files_scanned"], len(INDEXER.LANG_EXTENSIONS))
            self.assertLess(elapsed, float(os.environ.get("SYMBOL_INDEX_MAX_SECONDS", "1")))

    def test_canonical_script_runs_standalone_for_an_arbitrary_plugin_name(self) -> None:
        # The vendoring convention this test's history refers to (each plugin
        # carrying a byte-identical synced copy of this script) was briefly
        # retired in commit 0c10fa0, then reinstated via `.rrt.toml`'s
        # artifact_targets once self-assess and confab's own behavior specs
        # turned out to still require it. See
        # test_every_vendored_copy_matches_the_canonical_source below for the
        # per-plugin drift guard. What's covered here: the canonical script
        # itself still runs correctly standalone for an arbitrary
        # --plugin-name, the same invocation shape a vendored copy is
        # exercised with.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.py").write_text("def example(): pass\n", encoding="utf-8")
            subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-path", str(root), "--plugin-name", "example-plugin", "--no-fts"],
                check=True,
                cwd=REPO_ROOT,
            )
            pointer = json.loads((root / "analysis" / "example-plugin" / "current.json").read_text())
            self.assertEqual(pointer["plugin_name"], "example-plugin")

    def test_every_vendored_copy_matches_the_canonical_source(self) -> None:
        # The vendoring convention (retired in commit 0c10fa0, reinstated via
        # .rrt.toml's artifact_targets) is back: build_symbol_index.py and
        # parallel-safe-research-protocol.md are synced into all six plugins'
        # scripts/ and references/ directories via `rrt artifacts --regenerate`.
        # This is a second, rrt-independent guard against silent drift -- if a
        # vendored copy is hand-edited without re-running rrt, this catches it
        # even in a CI job that never invokes rrt.
        canonical_script = SCRIPT.read_bytes()
        canonical_protocol = (ROOT / "parallel-safe-research-protocol.md").read_bytes()
        for plugin_dir in sorted((REPO_ROOT / "plugins").iterdir()):
            vendored_script = plugin_dir / "scripts" / "build_symbol_index.py"
            vendored_protocol = plugin_dir / "references" / "parallel-safe-research-protocol.md"
            self.assertTrue(vendored_script.is_file(), f"{vendored_script} missing -- run `rrt artifacts --regenerate`")
            self.assertEqual(
                vendored_script.read_bytes(), canonical_script,
                f"{vendored_script} has drifted from the canonical source -- run `rrt artifacts --regenerate`",
            )
            self.assertTrue(vendored_protocol.is_file(), f"{vendored_protocol} missing -- run `rrt artifacts --regenerate`")
            self.assertEqual(
                vendored_protocol.read_bytes(), canonical_protocol,
                f"{vendored_protocol} has drifted from the canonical source -- run `rrt artifacts --regenerate`",
            )


if __name__ == "__main__":
    unittest.main()
