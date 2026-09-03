#!/usr/bin/env python3
"""Unit tests for validate_catalog.py.

Mirrors tools/surface-index/test_build_surface_index.py's style: load the
script as a module via importlib (it has no package, so it can't be
`import`ed normally), build small fixture trees under a TemporaryDirectory,
and assert on real files -- no mocking of the filesystem calls themselves.

Deliberately does not couple to the real docs/catalog/ (25 recipes and
counting, changing under concurrent work) or the real surface.json -- every
test builds its own tiny fixture catalog and fixture surface.json.

Cases the task called out explicitly:
  - a valid recipe passes
  - a recipe missing a required key fails with the right message
  - a recipe whose category doesn't match its directory fails
  - a recipe with an unrecognized category fails
  - a beat missing 'skill' or 'why' fails
  - a beat with no 'prompt' does NOT fail
  - a beat whose skill namespace matches a real plugin but the specific
    skill id doesn't exist fails
  - a beat whose skill namespace doesn't match any known plugin is counted
    as external-unchecked and does NOT fail
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "validate_catalog.py"

SPEC = importlib.util.spec_from_file_location("catalog_validator", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR: Any = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def write_surface(
    surface_path: Path,
    plugins: dict[str, dict[str, list[str]]],
) -> None:
    """plugins: {plugin_name: {"skills": [skill_name, ...], "agents": [agent_name, ...]}}"""
    plugins_out = []
    skill_ids: list[str] = []
    agent_ids: list[str] = []
    for name, contents in plugins.items():
        skills = [
            {"id": f"{name}:{skill}", "name": skill, "description": "Fixture skill."}
            for skill in contents.get("skills", [])
        ]
        agents = [
            {"id": f"{name}:{agent}", "name": agent, "description": "Fixture agent.", "tools": ["Read"]}
            for agent in contents.get("agents", [])
        ]
        skill_ids.extend(s["id"] for s in skills)
        agent_ids.extend(a["id"] for a in agents)
        plugins_out.append(
            {
                "name": name,
                "version": "0.1.0",
                "description": "Fixture plugin.",
                "skills": skills,
                "agents": agents,
                "commands": [],
                "hooks": {"present": False, "events": []},
                "workflows": [],
            }
        )
    surface_path.parent.mkdir(parents=True, exist_ok=True)
    surface_path.write_text(
        json.dumps(
            {
                "generatedBy": "fixture",
                "plugins": plugins_out,
                "skillIds": skill_ids,
                "agentIds": agent_ids,
            }
        ),
        encoding="utf-8",
    )


#: The default body mounts both required components. A recipe body without them
#: is a real validation failure (the page would render missing the content those
#: components produce), so a fixture omitting them silently would make every
#: other assertion in this file test a broken recipe.
DEFAULT_BODY = "<RecipeHeader />\n\nBody text.\n\n<RecipeBeats />\n"


def write_recipe(catalog_dir: Path, category: str, filename: str, frontmatter_yaml: str, body: str = DEFAULT_BODY) -> Path:
    category_dir = catalog_dir / category
    category_dir.mkdir(parents=True, exist_ok=True)
    path = category_dir / filename
    path.write_text(f"---\n{frontmatter_yaml}\n---\n\n{body}", encoding="utf-8")
    return path


VALID_FRONTMATTER = textwrap.dedent(
    """\
    task: "Do a thing"
    category: before-any-code
    summary: "Summary of the thing."
    external: []
    beats:
      - skill: "fixture:fixture-skill"
        why: "Because it must happen first."
        prompt: "do the thing"
    grounding: "Grounded in the fixture."
    """
).rstrip("\n")


class ValidRecipeTest(unittest.TestCase):
    def test_valid_recipe_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "do-a-thing.md", VALID_FRONTMATTER)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertEqual(report.failures, [])
            self.assertEqual(report.files_checked, 1)
            self.assertTrue(report.ok)

    def test_empty_external_is_valid_not_a_failure(self) -> None:
        """docs/catalog/index.md documents an empty `external` list as the
        deliberate 'werkstoff-only' convention, not a defect -- confirmed
        against the real catalog where several recipes carry `external: []`."""
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "do-a-thing.md", VALID_FRONTMATTER)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertTrue(report.ok)


class BodyComponentsTest(unittest.TestCase):
    """A recipe body must mount <RecipeHeader /> and <RecipeBeats />.

    These render the page's h1/summary and its whole Beats section from the
    frontmatter. They sit in the body rather than a VitePress layout slot
    because no slot lands inside <main>: `doc-after` renders below the prev/next
    footer, and `doc-footer-before` renders inside a contentinfo <footer>. A
    recipe missing one renders nothing where its content should be, with no
    error -- which is why this is a build failure and not a review note.
    """

    def _report(self, body: str):
        # TemporaryDirectory, not mkdtemp: every other test in this file cleans up
        # after itself, and a leaked dir per test run is the kind of small untidiness
        # nobody notices until CI runs out of inodes.
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "do-a-thing.md", VALID_FRONTMATTER, body=body)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})
            return VALIDATOR.validate_catalog(catalog_dir, surface_path)

    def test_body_with_both_components_passes(self) -> None:
        report = self._report("<RecipeHeader />\n\nProse.\n\n<RecipeBeats />\n")
        self.assertEqual(report.failures, [])
        self.assertTrue(report.ok)

    def test_missing_recipe_beats_fails(self) -> None:
        report = self._report("<RecipeHeader />\n\nProse.\n")
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failures), 1)
        self.assertIn("<RecipeBeats />", report.failures[0])

    def test_missing_recipe_header_fails(self) -> None:
        report = self._report("Prose.\n\n<RecipeBeats />\n")
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failures), 1)
        self.assertIn("<RecipeHeader />", report.failures[0])

    def test_missing_both_reports_both(self) -> None:
        report = self._report("Prose only, no components at all.\n")
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failures), 2)

    def test_mention_only_inside_a_code_fence_fails(self) -> None:
        """A recipe that DOCUMENTS the pattern renders none of it.

        Caught in review of PR #50: the check was a raw substring search over the
        whole body, so a ```markdown fence showing the components satisfied it
        while the page rendered nothing -- a validator reporting a pass it had
        not earned, which is the failure class it exists to prevent.
        """
        report = self._report("Text.\n\n```markdown\n<RecipeHeader />\n<RecipeBeats />\n```\n")
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failures), 2)

    def test_mention_only_in_a_tilde_fence_fails(self) -> None:
        report = self._report("~~~markdown\n<RecipeHeader />\n<RecipeBeats />\n~~~\n")
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failures), 2)

    def test_mention_only_in_an_inline_code_span_fails(self) -> None:
        report = self._report("Use `<RecipeHeader />` and `<RecipeBeats />` in the body.\n")
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failures), 2)

    def test_real_mount_plus_a_documenting_fence_passes(self) -> None:
        """The inverse case. A recipe may legitimately mount the components AND
        show them in a fence; stripping fences must not break that. The fence
        here is four backticks wrapping a three-backtick block, so this also
        pins the run-length matching -- a fence tracker that closed on the first
        ``` would drop the real mount that follows."""
        report = self._report(
            "<RecipeHeader />\n\nProse:\n\n````markdown\n```\n<RecipeBeats />\n```\n````\n\n<RecipeBeats />\n"
        )
        self.assertEqual(report.failures, [])
        self.assertTrue(report.ok)

    def test_indented_fence_is_still_a_fence(self) -> None:
        report = self._report("Text:\n\n  ```\n  <RecipeHeader />\n  <RecipeBeats />\n  ```\n")
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failures), 2)

    def test_frontmatter_mention_does_not_satisfy_the_check(self) -> None:
        """The check reads the BODY, not the whole file -- a component named in
        frontmatter renders nothing, so it must not count."""
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            fm = VALID_FRONTMATTER + '\ngrounding_note: "<RecipeBeats /> <RecipeHeader />"'
            write_recipe(catalog_dir, "before-any-code", "do-a-thing.md", fm, body="Prose.\n")
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})
            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertEqual(len(report.failures), 2)


class SkippedFilesTest(unittest.TestCase):
    def test_file_with_no_frontmatter_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            catalog_dir.mkdir(parents=True)
            (catalog_dir / "index.md").write_text("# Prompt catalog\n\nNo frontmatter here.\n", encoding="utf-8")
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertEqual(report.files_checked, 0)
            self.assertTrue(report.ok)

    def test_frontmatter_without_category_key_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(
                catalog_dir,
                "before-any-code",
                "_UNRESOLVED.md",
                'title: "Unresolved skills"\nnote: "no category here"',
            )
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertEqual(report.files_checked, 0)
            self.assertTrue(report.ok)


class RequiredKeysTest(unittest.TestCase):
    def test_missing_required_key_fails_with_right_message(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "fixture:fixture-skill"
                why: "Because it must happen first."
            """
        ).rstrip("\n")
        # grounding is deliberately omitted
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "missing-grounding.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertTrue(
                any("missing required key 'grounding'" in f for f in report.failures),
                report.failures,
            )

    def test_empty_string_key_fails(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: ""
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "fixture:fixture-skill"
                why: "Because it must happen first."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "empty-task.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertTrue(any("required key 'task' is empty" in f for f in report.failures), report.failures)

    def test_empty_beats_list_fails(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats: []
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "no-beats.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertTrue(any("'beats' must be a non-empty list" in f for f in report.failures), report.failures)


class CategoryTest(unittest.TestCase):
    def test_category_mismatched_with_directory_fails(self) -> None:
        """Two legitimate category directories exist (both recognized); the
        recipe under test sits in 'dir-a' but claims category 'dir-b' --
        the 'unrecognized' check must NOT fire since dir-b is real, only
        the directory-mismatch check should."""
        frontmatter_a = textwrap.dedent(
            """\
            task: "Do thing A"
            category: dir-b
            summary: "Summary A."
            external: []
            beats:
              - skill: "fixture:fixture-skill"
                why: "Reason A."
            grounding: "Grounded A."
            """
        ).rstrip("\n")
        frontmatter_b = textwrap.dedent(
            """\
            task: "Do thing B"
            category: dir-b
            summary: "Summary B."
            external: []
            beats:
              - skill: "fixture:fixture-skill"
                why: "Reason B."
            grounding: "Grounded B."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "dir-a", "mismatched.md", frontmatter_a)
            write_recipe(catalog_dir, "dir-b", "matched.md", frontmatter_b)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            mismatch_failures = [f for f in report.failures if "does not match its containing directory" in f]
            self.assertEqual(len(mismatch_failures), 1)
            self.assertIn("dir-a", mismatch_failures[0])
            unrecognized_failures = [f for f in report.failures if "not a recognized category" in f]
            self.assertEqual(unrecognized_failures, [])

    def test_unrecognized_category_fails(self) -> None:
        """Placed in a real, recognized directory ('before-any-code') but
        claiming a category value that matches no directory in the fixture
        catalog at all -- distinct from the plain mismatch case above, where
        the claimed category IS a real directory elsewhere. Under this
        tool's live-derived recognized set, a category value can only ever
        be "unrecognized" when it also fails to match its own directory
        (matching your own directory always makes a category trivially
        recognized, since that directory now provably contains an .md file)
        -- so this fixture necessarily fails the mismatch check too; what
        this test actually pins down is that the unrecognized-category
        message specifically fires for a value with no matching directory
        anywhere, not just for a mismatched-but-real one."""
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: totally-bogus
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "fixture:fixture-skill"
                why: "Because it must happen first."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "bogus.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertTrue(
                any("not a recognized category" in f for f in report.failures), report.failures
            )

    def test_recognized_categories_derived_live_not_hardcoded(self) -> None:
        """A category directory that isn't in the shipped catalog's known set
        (e.g. a brand-new 'plugin-authoring' added by concurrent work) must
        be accepted as long as its own recipe's category matches it -- proves
        the recognized set comes from the live filesystem, not a fixed list."""
        frontmatter = textwrap.dedent(
            """\
            task: "Author a plugin"
            category: plugin-authoring
            summary: "Summary."
            external: []
            beats:
              - skill: "fixture:fixture-skill"
                why: "Reason."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "plugin-authoring", "author.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertTrue(report.ok, report.failures)


class BeatsTest(unittest.TestCase):
    def test_beat_missing_skill_fails(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - why: "Because it must happen first."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "no-skill.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertTrue(any("missing or empty 'skill'" in f for f in report.failures), report.failures)

    def test_beat_missing_why_fails(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "fixture:fixture-skill"
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "no-why.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertTrue(any("missing or empty 'why'" in f for f in report.failures), report.failures)

    def test_beat_with_no_prompt_does_not_fail(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "fixture:fixture-skill"
                why: "Because it must happen first."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "no-prompt.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertTrue(report.ok, report.failures)

    def test_known_plugin_namespace_with_nonexistent_skill_fails(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "fixture:does-not-exist"
                why: "Because it must happen first."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "bad-skill-id.md", frontmatter)
            # 'fixture' plugin is known, but it does not ship 'does-not-exist'.
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertTrue(
                any("not found among" in f and "fixture:does-not-exist" in f for f in report.failures),
                report.failures,
            )

    def test_known_plugin_namespace_resolving_to_agent_passes(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "fixture:fixture-agent"
                why: "Because it must happen first."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "agent-beat.md", frontmatter)
            write_surface(surface_path, {"fixture": {"agents": ["fixture-agent"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertTrue(report.ok, report.failures)

    def test_unknown_namespace_counts_as_external_unchecked_not_a_failure(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: ["superpowers"]
            beats:
              - skill: "superpowers:brainstorming"
                why: "Required before any creative work."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "external-beat.md", frontmatter)
            # 'superpowers' is not one of the plugins this fixture surface knows about.
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertTrue(report.ok, report.failures)
            self.assertEqual(report.external_unchecked, 1)

    def test_skill_id_without_colon_fails(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "no-namespace-here"
                why: "Because it must happen first."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "bad-form.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            report = VALIDATOR.validate_catalog(catalog_dir, surface_path)
            self.assertFalse(report.ok)
            self.assertTrue(any("not in 'plugin:skill' form" in f for f in report.failures), report.failures)


class LoadSurfaceTest(unittest.TestCase):
    def test_missing_surface_file_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            surface_path = Path(tmp) / "surface.json"
            with self.assertRaises(VALIDATOR.CatalogValidatorError):
                VALIDATOR.load_surface(surface_path)


class MainCliTest(unittest.TestCase):
    def test_main_exits_zero_on_clean_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "do-a-thing.md", VALID_FRONTMATTER)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            exit_code = VALIDATOR.main(
                ["--catalog-dir", str(catalog_dir), "--surface", str(surface_path)]
            )
            self.assertEqual(exit_code, 0)

    def test_main_exits_one_on_failure(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            task: "Do a thing"
            category: before-any-code
            summary: "Summary of the thing."
            external: []
            beats:
              - skill: "fixture:does-not-exist"
                why: "Reason."
            grounding: "Grounded."
            """
        ).rstrip("\n")
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = Path(tmp) / "catalog"
            surface_path = Path(tmp) / "surface.json"
            write_recipe(catalog_dir, "before-any-code", "bad.md", frontmatter)
            write_surface(surface_path, {"fixture": {"skills": ["fixture-skill"]}})

            exit_code = VALIDATOR.main(
                ["--catalog-dir", str(catalog_dir), "--surface", str(surface_path)]
            )
            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
