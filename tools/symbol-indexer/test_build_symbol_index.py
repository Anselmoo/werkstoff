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
        # Superseded a per-plugin regression test. Until the six plugins were
        # regenerated from behavior specs (see docs/plugin-rebuild-findings.md),
        # each vendored a byte-identical synced copy of this script (kept in
        # sync via `.rrt.toml`'s now-removed artifact_targets), and this test
        # asserted every copy was present and ran. None of the rebuilt plugins
        # reference the symbol indexer at all -- each ships its own
        # purpose-built scripts instead -- so there is no longer a "copy" to
        # assert on. What's left worth covering: the canonical script itself
        # still runs correctly standalone for an arbitrary --plugin-name, the
        # same invocation shape a vendored copy used to be exercised with.
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

    def test_no_plugin_vendors_a_stale_copy(self) -> None:
        # Regression guard for the retired convention above: nothing should
        # silently reintroduce a per-plugin vendored copy that could drift
        # from the canonical source without anything noticing.
        for plugin_dir in sorted((REPO_ROOT / "plugins").iterdir()):
            stale = plugin_dir / "scripts" / "build_symbol_index.py"
            self.assertFalse(
                stale.is_file(),
                f"{stale} exists, but the vendoring convention was retired -- "
                f"either this is a real regression or the convention was intentionally "
                f"reinstated and this test needs updating too",
            )


if __name__ == "__main__":
    unittest.main()
