#!/usr/bin/env python3
"""Unit tests for docs_ux_audit.py's srcExclude derivation.

Mirrors tools/catalog-validator/test_validate_catalog.py's style: load the
script as a module via importlib (it has no package, so it can't be `import`ed
normally) and assert on real files -- no mocking of the filesystem calls
themselves.

Why only this one function has a unit test
------------------------------------------
`published_pages()` used to carry its own copy of config.mjs's `srcExclude`
list while its docstring claimed "srcExclude honoured". Two lists, hand-edited
together, with nothing comparing them -- CLAUDE.md's release-wiring drift (#46
takt, then lehre) in a second place, and it had already bitten: updating only
config.mjs left the audit reporting C3 orphan failures for pages the site does
not build.

The fix reads config.mjs live, which trades a duplication defect for a parsing
one. These tests are that parser's calibration. The first case pins the exact
literals a human can read at config.mjs's `srcExclude:` line: hardcoded on
purpose, because a test deriving its expectation from the same parser it grades
proves nothing. It goes red when config.mjs changes, which is the point -- a
deliberate, visible update instead of the silent drift it replaces.

The rest are the two failure modes the audit cannot survive, stated as the
brief did: a silently EMPTY exclusion set (the audit grades pages VitePress
never builds) and a silently OVER-BROAD one (the audit skips pages it does).

Usage:
    python3 -m unittest test_docs_ux_audit -v     # from test/docs/
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "docs_ux_audit.py"
SPEC = importlib.util.spec_from_file_location("docs_ux_audit", SCRIPT)
assert SPEC and SPEC.loader
AUDIT: Any = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)

# What config.mjs declares today. Hand-maintained; see the module docstring.
LIVE_SRC_EXCLUDE = [
    "andon-pilot-findings.md",
    "andon-pilot-handoff.md",
    "catalog/_UNRESOLVED.md",
]


def scan(source: str, key: str = "srcExclude") -> list[str]:
    """Run the scanner over a fixture string, comment-stripped the way
    src_exclude() strips the real config.mjs."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.mjs"
        path.write_text(source, encoding="utf-8")
        return AUDIT.js_string_array(AUDIT.js_code(path), key, path)


class TestSrcExcludeParse(unittest.TestCase):
    """The parse returns what config.mjs actually declares."""

    def test_returns_the_live_config_entries(self) -> None:
        self.assertEqual(AUDIT.src_exclude(), LIVE_SRC_EXCLUDE)

    def test_single_line_array(self) -> None:
        source = "export default defineConfig({\n  srcExclude: ['a.md', 'b.md'],\n})\n"
        self.assertEqual(scan(source), ["a.md", "b.md"])

    def test_multiline_array(self) -> None:
        """A prettier reflow past the print width must not change the result."""
        source = textwrap.dedent("""\
            export default defineConfig({
              srcExclude: [
                'a.md',
                'b.md',
                'catalog/_UNRESOLVED.md',
              ],
            })
            """)
        self.assertEqual(scan(source), ["a.md", "b.md", "catalog/_UNRESOLVED.md"])

    def test_double_quoted_and_mixed_literals(self) -> None:
        source = """  srcExclude: ["a.md", 'b.md'],\n"""
        self.assertEqual(scan(source), ["a.md", "b.md"])

    def test_closing_bracket_inside_a_glob_does_not_truncate(self) -> None:
        """`]` inside a quoted character class is data, not the array's end --
        the exact span a regex over the whole array would get wrong."""
        source = """  srcExclude: ['draft/[0-9]*.md', 'b.md'],\n"""
        self.assertEqual(scan(source), ["draft/[0-9]*.md", "b.md"])


class TestSrcExcludeFailsLoudly(unittest.TestCase):
    """Neither failure mode may be survivable: a silently empty exclusion set
    grades unbuilt pages, a silently truncated one skips built ones."""

    def test_missing_declaration_raises(self) -> None:
        with self.assertRaises(AUDIT.DocsAuditError) as caught:
            scan("export default defineConfig({ title: 'werkstoff' })\n")
        self.assertIn("cannot find `srcExclude: [`", str(caught.exception))

    def test_commented_out_declaration_does_not_count(self) -> None:
        """js_code() strips comments first. Without that, the five-line comment
        above the real srcExclude -- which names the excluded files verbatim --
        is indistinguishable from the declaration itself. This is the failure
        js_code()'s own docstring records having been measured."""
        source = textwrap.dedent("""\
            // srcExclude: ['stale.md'],
            /* srcExclude: ['also-stale.md'], */
            export default defineConfig({ title: 'werkstoff' })
            """)
        with self.assertRaises(AUDIT.DocsAuditError):
            scan(source)

    def test_empty_array_raises(self) -> None:
        with self.assertRaises(AUDIT.DocsAuditError) as caught:
            scan("  srcExclude: [],\n")
        self.assertIn("parsed as empty", str(caught.exception))

    def test_unclosed_array_raises(self) -> None:
        with self.assertRaises(AUDIT.DocsAuditError) as caught:
            scan("  srcExclude: ['a.md',\n")
        self.assertIn("never closed", str(caught.exception))

    def test_unterminated_string_raises(self) -> None:
        with self.assertRaises(AUDIT.DocsAuditError) as caught:
            scan("  srcExclude: ['a.md\n")
        self.assertIn("never closed", str(caught.exception))

    def test_two_declarations_raise_rather_than_guess(self) -> None:
        source = "  srcExclude: ['a.md'],\n  srcExclude: ['b.md'],\n"
        with self.assertRaises(AUDIT.DocsAuditError) as caught:
            scan(source)
        self.assertIn("ambiguous", str(caught.exception))

    def test_missing_config_file_raises(self) -> None:
        """The real shape of this failure is config.mjs deleted or renamed in
        place, so the stand-in stays under REPO -- src_exclude() reports the
        path relative to it, the same idiom breather_params() and
        outline_max_level() use for their own constants."""
        absent = AUDIT.DOCS / ".vitepress" / "config.deleted.mjs"
        self.assertFalse(absent.exists())
        with mock.patch.object(AUDIT, "CONFIG", absent):
            with self.assertRaises(AUDIT.DocsAuditError) as caught:
                AUDIT.src_exclude()
        self.assertIn("is missing", str(caught.exception))


class TestPublishedPages(unittest.TestCase):
    """The derived set is actually applied, and applied as globs."""

    def test_every_excluded_file_exists_but_is_not_published(self) -> None:
        """Exclusion must be doing real work: each pattern names a file that is
        on disk (so the check isn't vacuous) and absent from published_pages()."""
        published = {p.relative_to(AUDIT.DOCS).as_posix() for p in AUDIT.published_pages()}
        for rel in LIVE_SRC_EXCLUDE:
            with self.subTest(rel=rel):
                self.assertTrue((AUDIT.DOCS / rel).is_file(), f"{rel} is not on disk")
                self.assertNotIn(rel, published)

    def test_publishes_pages_the_site_does_build(self) -> None:
        published = {p.relative_to(AUDIT.DOCS).as_posix() for p in AUDIT.published_pages()}
        self.assertIn("index.md", published)
        self.assertIn("orchestration/README.md", published)

    def test_vitepress_internals_are_never_published(self) -> None:
        """The `.vitepress/` skip, exercised against a tree where it can fire.

        Asserting this over the live docs/ proves nothing: there are no .md
        files under docs/.vitepress/ today, so rglob("*.md") yields none and the
        assertion passes whether or not the guard exists -- confirmed by
        deleting the guard and watching the suite stay green. A config or theme
        dir picking up a README.md later is exactly when this must hold, so the
        test builds that tree instead of hoping for it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / ".vitepress").mkdir()
            (docs / "keep.md").write_text("# keep\n", encoding="utf-8")
            (docs / ".vitepress" / "README.md").write_text("# internal\n", encoding="utf-8")
            with mock.patch.object(AUDIT, "DOCS", docs), \
                 mock.patch.object(AUDIT, "src_exclude", list):
                published = {p.relative_to(docs).as_posix() for p in AUDIT.published_pages()}
        self.assertEqual(published, {"keep.md"})

    def test_a_directory_glob_excludes_the_whole_directory(self) -> None:
        """A future `'superpowers/**'` in config.mjs must take effect with no
        second edit here -- that hand-edited-in-two-places coupling is the whole
        reason this derivation exists."""
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "superpowers").mkdir()
            (docs / "keep.md").write_text("# keep\n", encoding="utf-8")
            (docs / "superpowers" / "drop.md").write_text("# drop\n", encoding="utf-8")
            with mock.patch.object(AUDIT, "DOCS", docs), \
                 mock.patch.object(AUDIT, "src_exclude", lambda: ["superpowers/**"]):
                published = {p.relative_to(docs).as_posix() for p in AUDIT.published_pages()}
        self.assertEqual(published, {"keep.md"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
