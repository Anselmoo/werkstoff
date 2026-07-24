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

    def test_plugin_copies_default_to_their_own_plugin(self) -> None:
        plugins = ("self-assess", "andon", "compass", "confab", "cupertino", "cli-scaffold")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.py").write_text("def example(): pass\n", encoding="utf-8")
            for plugin in plugins:
                script = next(Path("plugins", plugin, "skills").glob("*-query-symbol/scripts/build_symbol_index.py"))
                subprocess.run([sys.executable, str(script), "--repo-path", str(root), "--no-fts"], check=True, cwd=Path.cwd())
                pointer = json.loads((root / "analysis" / plugin / "current.json").read_text())
                self.assertEqual(pointer["plugin_name"], plugin)


if __name__ == "__main__":
    unittest.main()
