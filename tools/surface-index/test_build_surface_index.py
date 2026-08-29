#!/usr/bin/env python3
"""Unit tests for build_surface_index.py.

Mirrors tools/symbol-indexer/test_build_symbol_index.py's style: load the
script as a module via importlib (it has no package, so it can't be
`import`ed normally), build small fixture trees under a TemporaryDirectory,
and assert on real files -- no mocking of the filesystem calls themselves.

The three cases the task called out explicitly are covered directly:
  - test_load_plugin_manifest_missing_file        (loud failure, missing plugin.json)
  - test_collect_skills_empty_description_raises  (loud failure, empty frontmatter description)
  - test_collect_skills_id_construction            (correct "plugin:skill" id shape)
Everything else here is the surrounding coverage needed to trust the script:
frontmatter fallback parsing, tools normalization, hooks/workflow/command
collection, and the --check drift gate.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "build_surface_index.py"

SPEC = importlib.util.spec_from_file_location("surface_indexer", SCRIPT)
assert SPEC and SPEC.loader
INDEXER: Any = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = INDEXER
SPEC.loader.exec_module(INDEXER)


def write_plugin_json(plugin_dir: Path, name: str, version: str = "0.1.0", description: str = "A fixture plugin.") -> None:
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": name, "version": version, "description": description}),
        encoding="utf-8",
    )


def write_skill(plugin_dir: Path, skill_dir_name: str, name: str, description: str) -> Path:
    skill_dir = plugin_dir / "skills" / skill_dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: \"{description}\"\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return path


def write_agent(plugin_dir: Path, filename: str, name: str, description: str, tools: str = "Read, Grep, Glob") -> Path:
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / filename
    path.write_text(
        f'---\nname: {name}\ndescription: "{description}"\ntools: {tools}\n---\n\nBody.\n',
        encoding="utf-8",
    )
    return path


class LoadPluginManifestTest(unittest.TestCase):
    """Covers HARD REQUIREMENT 1's 'a plugin dir has no plugin.json' case."""

    def test_missing_file_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "ghost"
            plugin_dir.mkdir()
            with self.assertRaises(INDEXER.SurfaceIndexError) as ctx:
                INDEXER.load_plugin_manifest(plugin_dir)
            self.assertIn("plugin.json", str(ctx.exception))

    def test_missing_required_field_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "incomplete"
            manifest_dir = plugin_dir / ".claude-plugin"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "plugin.json").write_text(
                json.dumps({"name": "incomplete", "version": "0.1.0", "description": ""}),
                encoding="utf-8",
            )
            with self.assertRaises(INDEXER.SurfaceIndexError) as ctx:
                INDEXER.load_plugin_manifest(plugin_dir)
            self.assertIn("description", str(ctx.exception))

    def test_valid_manifest_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            write_plugin_json(plugin_dir, "fixture", "1.2.3", "Does a thing.")
            manifest = INDEXER.load_plugin_manifest(plugin_dir)
            self.assertEqual(manifest["name"], "fixture")
            self.assertEqual(manifest["version"], "1.2.3")


class CollectSkillsTest(unittest.TestCase):
    """Covers the empty-frontmatter-description case and id construction."""

    def test_empty_description_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            skill_dir = plugin_dir / "skills" / "do-thing"
            skill_dir.mkdir(parents=True)
            # description present as a key but empty -- the exact shape CLAUDE.md
            # warns loads silently with empty metadata if not asserted against.
            (skill_dir / "SKILL.md").write_text(
                '---\nname: do-thing\ndescription: ""\n---\n\nBody.\n',
                encoding="utf-8",
            )
            with self.assertRaises(INDEXER.SurfaceIndexError) as ctx:
                INDEXER.collect_skills(plugin_dir, "fixture")
            self.assertIn("description", str(ctx.exception))

    def test_missing_name_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            skill_dir = plugin_dir / "skills" / "do-thing"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                '---\ndescription: "Does a thing."\n---\n\nBody.\n',
                encoding="utf-8",
            )
            with self.assertRaises(INDEXER.SurfaceIndexError):
                INDEXER.collect_skills(plugin_dir, "fixture")

    def test_id_construction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            write_skill(plugin_dir, "do-thing", "do-thing", "Does a thing.")
            skills = INDEXER.collect_skills(plugin_dir, "fixture")
            self.assertEqual(len(skills), 1)
            self.assertEqual(skills[0]["id"], "fixture:do-thing")
            self.assertEqual(skills[0]["name"], "do-thing")
            self.assertEqual(skills[0]["description"], "Does a thing.")

    def test_no_skills_dir_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            plugin_dir.mkdir()
            self.assertEqual(INDEXER.collect_skills(plugin_dir, "fixture"), [])

    def test_empty_skills_dir_raises_loudly(self) -> None:
        """HARD REQUIREMENT 1: zero skills for a plugin that HAS a skills/ dir."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            (plugin_dir / "skills").mkdir(parents=True)
            with self.assertRaises(INDEXER.SurfaceIndexError) as ctx:
                INDEXER.collect_skills(plugin_dir, "fixture")
            self.assertIn("zero", str(ctx.exception))


class CollectAgentsTest(unittest.TestCase):
    def test_id_and_tools_construction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            write_agent(plugin_dir, "watcher.md", "watcher", "Watches things.", tools="Read, Grep, Glob")
            agents = INDEXER.collect_agents(plugin_dir, "fixture")
            self.assertEqual(len(agents), 1)
            self.assertEqual(agents[0]["id"], "fixture:watcher")
            self.assertEqual(agents[0]["tools"], ["Read", "Grep", "Glob"])

    def test_tools_as_yaml_list_normalizes_same_as_comma_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            agents_dir = plugin_dir / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "watcher.md").write_text(
                "---\nname: watcher\ndescription: \"Watches things.\"\ntools:\n  - Read\n  - Grep\n  - Glob\n---\n\nBody.\n",
                encoding="utf-8",
            )
            agents = INDEXER.collect_agents(plugin_dir, "fixture")
            self.assertEqual(agents[0]["tools"], ["Read", "Grep", "Glob"])

    def test_missing_tools_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            agents_dir = plugin_dir / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "watcher.md").write_text(
                '---\nname: watcher\ndescription: "Watches things."\n---\n\nBody.\n',
                encoding="utf-8",
            )
            with self.assertRaises(INDEXER.SurfaceIndexError) as ctx:
                INDEXER.collect_agents(plugin_dir, "fixture")
            self.assertIn("tools", str(ctx.exception))


class CollectCommandsTest(unittest.TestCase):
    def test_command_names_are_filename_stems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            commands_dir = plugin_dir / "commands"
            commands_dir.mkdir(parents=True)
            (commands_dir / "do-thing.md").write_text("---\ndescription: x\n---\nBody.\n", encoding="utf-8")
            (commands_dir / "undo-thing.md").write_text("---\ndescription: y\n---\nBody.\n", encoding="utf-8")
            commands = INDEXER.collect_commands(plugin_dir)
            self.assertEqual(commands, ["do-thing", "undo-thing"])

    def test_empty_commands_dir_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            (plugin_dir / "commands").mkdir(parents=True)
            with self.assertRaises(INDEXER.SurfaceIndexError):
                INDEXER.collect_commands(plugin_dir)


class CollectHooksTest(unittest.TestCase):
    def test_absent_hooks_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            plugin_dir.mkdir()
            self.assertEqual(INDEXER.collect_hooks(plugin_dir), {"present": False, "events": []})

    def test_present_hooks_reports_sorted_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            hooks_dir = plugin_dir / "hooks"
            hooks_dir.mkdir(parents=True)
            (hooks_dir / "hooks.json").write_text(
                json.dumps({"hooks": {"PostToolUse": [], "PreToolUse": []}}),
                encoding="utf-8",
            )
            result = INDEXER.collect_hooks(plugin_dir)
            self.assertEqual(result, {"present": True, "events": ["PostToolUse", "PreToolUse"]})

    def test_hooks_json_with_zero_events_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            hooks_dir = plugin_dir / "hooks"
            hooks_dir.mkdir(parents=True)
            (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": {}}), encoding="utf-8")
            with self.assertRaises(INDEXER.SurfaceIndexError):
                INDEXER.collect_hooks(plugin_dir)


class CollectWorkflowsTest(unittest.TestCase):
    def test_parses_name_from_meta_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            workflows_dir = plugin_dir / "workflows"
            workflows_dir.mkdir(parents=True)
            (workflows_dir / "solve.js").write_text(
                "export const meta = {\n"
                "  name: 'fixture-solve',\n"
                "  description: 'does a thing',\n"
                "  phases: [\n"
                "    { title: 'Clarify' },\n"
                "  ],\n"
                "}\n",
                encoding="utf-8",
            )
            workflows = INDEXER.collect_workflows(plugin_dir)
            self.assertEqual(workflows, ["fixture-solve"])

    def test_missing_name_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            workflows_dir = plugin_dir / "workflows"
            workflows_dir.mkdir(parents=True)
            (workflows_dir / "solve.js").write_text(
                "export const meta = {\n  description: 'no name here',\n}\n",
                encoding="utf-8",
            )
            with self.assertRaises(INDEXER.SurfaceIndexError):
                INDEXER.collect_workflows(plugin_dir)

    def test_does_not_match_name_key_inside_units_shape(self) -> None:
        """A `name` field nested in a later structure (e.g. per-unit objects)
        must not be picked up as the workflow's own name -- only the first
        `name:` line inside the leading `meta` object counts."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            workflows_dir = plugin_dir / "workflows"
            workflows_dir.mkdir(parents=True)
            (workflows_dir / "batch.js").write_text(
                "export const meta = {\n"
                "  name: 'fixture-batch',\n"
                "  description: 'batches units',\n"
                "  whenToUse: 'units: [{name, path, deps?}]',\n"
                "}\n"
                "\n"
                "function run(units) {\n"
                "  return units.map(({ name }) => name)\n"
                "}\n",
                encoding="utf-8",
            )
            workflows = INDEXER.collect_workflows(plugin_dir)
            self.assertEqual(workflows, ["fixture-batch"])


class FrontmatterFallbackParserTest(unittest.TestCase):
    """Exercises _parse_frontmatter_minimal directly -- the path only taken
    when PyYAML is not installed -- to prove it agrees with PyYAML on every
    shape actually used in this repo's SKILL.md/agent files."""

    def test_scalar_and_quoted_values(self) -> None:
        block = 'name: do-thing\ndescription: "Does a thing."\nargument-hint: "[filter]"'
        data = INDEXER._parse_frontmatter_minimal(block, Path("fixture.md"))
        self.assertEqual(data["name"], "do-thing")
        self.assertEqual(data["description"], "Does a thing.")
        self.assertEqual(data["argument-hint"], "[filter]")

    def test_block_list(self) -> None:
        block = "name: watcher\ndescription: watches\ntools:\n  - Read\n  - Grep\n  - Glob"
        data = INDEXER._parse_frontmatter_minimal(block, Path("fixture.md"))
        self.assertEqual(data["tools"], ["Read", "Grep", "Glob"])

    def test_agrees_with_pyyaml_on_real_agent_frontmatter(self) -> None:
        if not INDEXER.HAVE_YAML:
            self.skipTest("PyYAML not installed in this environment")
        block = (
            "name: watcher\n"
            'description: "Watches things."\n'
            "tools:\n"
            "  - Read\n"
            "  - Grep\n"
        )
        import yaml

        expected = yaml.safe_load(block)
        actual = INDEXER._parse_frontmatter_minimal(block, Path("fixture.md"))
        self.assertEqual(actual, expected)

    def test_unparseable_line_raises_loudly(self) -> None:
        block = "not a key value pair at all"
        with self.assertRaises(INDEXER.SurfaceIndexError):
            INDEXER._parse_frontmatter_minimal(block, Path("fixture.md"))


class ParseFrontmatterTest(unittest.TestCase):
    def test_no_frontmatter_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            path.write_text("# Just a heading\n", encoding="utf-8")
            with self.assertRaises(INDEXER.SurfaceIndexError):
                INDEXER.parse_frontmatter(path)

    def test_unterminated_frontmatter_raises_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            path.write_text('---\nname: x\ndescription: "y"\n', encoding="utf-8")
            with self.assertRaises(INDEXER.SurfaceIndexError):
                INDEXER.parse_frontmatter(path)


class NormalizeToolsTest(unittest.TestCase):
    def test_comma_string(self) -> None:
        self.assertEqual(
            INDEXER.normalize_tools("Read, Grep, Glob", Path("fixture.md")),
            ["Read", "Grep", "Glob"],
        )

    def test_list(self) -> None:
        self.assertEqual(
            INDEXER.normalize_tools(["Read", "Grep"], Path("fixture.md")),
            ["Read", "Grep"],
        )

    def test_empty_string_raises_loudly(self) -> None:
        with self.assertRaises(INDEXER.SurfaceIndexError):
            INDEXER.normalize_tools("   ", Path("fixture.md"))


class BuildSurfaceEndToEndTest(unittest.TestCase):
    """Exercises discover_plugins/build_surface against a fixture plugins/ tree
    by monkeypatching the module's REPO/PLUGINS/OUTPUT globals -- the only
    functions that read those globals directly rather than taking a path."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.plugins = self.repo / "plugins"
        self.plugins.mkdir()
        self._orig_repo = INDEXER.REPO
        self._orig_plugins = INDEXER.PLUGINS
        self._orig_output = INDEXER.OUTPUT
        INDEXER.REPO = self.repo
        INDEXER.PLUGINS = self.plugins
        INDEXER.OUTPUT = self.repo / "docs" / ".vitepress" / "data" / "surface.json"
        self.addCleanup(self._restore_globals)

    def _restore_globals(self) -> None:
        INDEXER.REPO = self._orig_repo
        INDEXER.PLUGINS = self._orig_plugins
        INDEXER.OUTPUT = self._orig_output

    def _write_fixture_plugin(self) -> None:
        plugin_dir = self.plugins / "alpha"
        write_plugin_json(plugin_dir, "alpha", "0.1.0", "Fixture plugin alpha.")
        write_skill(plugin_dir, "alpha-skill", "alpha-skill", "Does the alpha thing.")
        write_agent(plugin_dir, "alpha-agent.md", "alpha-agent", "Watches alpha things.")

    def test_no_plugins_dir_raises_loudly(self) -> None:
        import shutil

        shutil.rmtree(self.plugins)
        with self.assertRaises(INDEXER.SurfaceIndexError):
            INDEXER.discover_plugins()

    def test_empty_plugins_dir_raises_loudly(self) -> None:
        with self.assertRaises(INDEXER.SurfaceIndexError):
            INDEXER.discover_plugins()

    def test_build_surface_end_to_end(self) -> None:
        self._write_fixture_plugin()
        data = INDEXER.build_surface()
        self.assertEqual(data["generatedBy"], "tools/surface-index/build_surface_index.py")
        self.assertEqual(len(data["plugins"]), 1)
        self.assertEqual(data["skillIds"], ["alpha:alpha-skill"])
        self.assertEqual(data["agentIds"], ["alpha:alpha-agent"])

    def test_zero_skills_across_all_plugins_raises_loudly(self) -> None:
        plugin_dir = self.plugins / "beta"
        write_plugin_json(plugin_dir, "beta")
        write_agent(plugin_dir, "beta-agent.md", "beta-agent", "Watches beta things.")
        with self.assertRaises(INDEXER.SurfaceIndexError) as ctx:
            INDEXER.build_surface()
        self.assertIn("skills", str(ctx.exception))

    def test_check_mode_passes_when_output_matches(self) -> None:
        self._write_fixture_plugin()
        INDEXER.main([])  # writes OUTPUT
        exit_code = INDEXER.main(["--check"])
        self.assertEqual(exit_code, 0)

    def test_check_mode_fails_on_drift(self) -> None:
        self._write_fixture_plugin()
        INDEXER.main([])  # writes OUTPUT for the one-plugin surface

        # Now the real surface has grown a second plugin -- OUTPUT is stale.
        second_plugin = self.plugins / "beta"
        write_plugin_json(second_plugin, "beta")
        write_skill(second_plugin, "beta-skill", "beta-skill", "Does the beta thing.")

        exit_code = INDEXER.main(["--check"])
        self.assertEqual(exit_code, 1)

    def test_check_mode_without_prior_output_fails_loudly(self) -> None:
        self._write_fixture_plugin()
        exit_code = INDEXER.main(["--check"])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
