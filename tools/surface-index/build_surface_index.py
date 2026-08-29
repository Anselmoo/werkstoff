#!/usr/bin/env python3
"""Generate docs/.vitepress/data/surface.json -- werkstoff's actual capability surface.

This exists so documentation can be a PROJECTION of what the plugins actually
ship (skills, agents, commands, hooks, workflows) rather than prose asserting
facts about them that silently drift the moment a plugin changes. Every field
in the output is read from the filesystem at generation time; nothing here is
hardcoded.

Sources per plugin (`plugins/<name>/`):
    .claude-plugin/plugin.json  -> name, version, description
    skills/*/SKILL.md           -> frontmatter: name, description
    agents/*.md                 -> frontmatter: name, description, tools
    commands/*.md                -> command name (the filename stem)
    hooks/hooks.json            -> presence + which events are registered
    workflows/*.js               -> the `name` field of `export const meta = {...}`

Frontmatter parsing: PyYAML is used when available (a project dependency
already present in this environment; not vendored). When it is not
installed, a minimal line-based fallback parser handles the frontmatter
shapes actually used across this repo's SKILL.md/agent files: `key: value`,
`key: "quoted value"`, and `key:` followed by an indented YAML list of
`- item` lines. See `_parse_frontmatter_minimal` below.

Why this matters more than it looks: per this repo's CLAUDE.md, frontmatter
that fails to parse still LOADS at runtime -- with EMPTY metadata, silently.
A skill/agent with a name and description that failed to parse is
indistinguishable, at a glance, from one that never had them. So this script
never treats a parse failure or an empty name/description as "just skip it" --
every such case is a loud, non-zero-exit error naming the exact file.

Parsing is line-based throughout, never a regex spanning multiple lines --
this repo has been burned before by exactly that shape of bug (see the
`[^.]{0,80}` and `[^\\n]` entries in CLAUDE.md's defect table), so every
scanner here walks lines one at a time and stops looking rather than trying
to be clever with a single all-matching pattern.

Usage:
    python3 tools/surface-index/build_surface_index.py            # regenerate
    python3 tools/surface-index/build_surface_index.py --check    # verify, no write
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML installed
    # Bind the name unconditionally. `HAVE_YAML`-style flags are correct at
    # runtime but unprovable statically, so a type checker cannot tell that
    # `yaml.safe_load` below is reachable only when the import succeeded --
    # exactly the "looks correct, silently wrong" shape this repo guards against.
    yaml = None

HAVE_YAML = yaml is not None

REPO = Path(__file__).resolve().parents[2]
PLUGINS = REPO / "plugins"
OUTPUT = REPO / "docs" / ".vitepress" / "data" / "surface.json"


class SurfaceIndexError(RuntimeError):
    """Raised for anything that must fail loudly rather than silently under-report."""


# --------------------------------------------------------------------------
# Frontmatter parsing
# --------------------------------------------------------------------------


def parse_frontmatter(path: Path) -> dict:
    """Parse the YAML frontmatter block (between `---` lines) of a markdown file.

    Raises SurfaceIndexError -- never returns an empty/partial dict -- on any
    of: no frontmatter, an unterminated frontmatter block, or content that
    doesn't parse to a mapping. A silent partial result here is exactly the
    "loads with empty metadata" bug class this script exists to catch.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise SurfaceIndexError(f"{path}: no YAML frontmatter (file must start with '---')")

    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise SurfaceIndexError(f"{path}: unterminated frontmatter (no closing '---')")

    block = "\n".join(lines[1:end])
    if not block.strip():
        raise SurfaceIndexError(f"{path}: frontmatter block is empty")

    if yaml is not None:
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            raise SurfaceIndexError(f"{path}: frontmatter failed to parse as YAML: {exc}") from exc
        if not isinstance(data, dict):
            raise SurfaceIndexError(f"{path}: frontmatter did not parse to a mapping")
        return data

    return _parse_frontmatter_minimal(block, path)


def _parse_frontmatter_minimal(block: str, path: Path) -> dict:
    """Fallback frontmatter parser used only when PyYAML is not installed.

    Handles exactly the shapes this repo's SKILL.md/agent frontmatter uses:
    `key: value`, `key: "quoted value"`, and `key:` (no inline value)
    followed by an indented YAML list of `- item` lines (used by
    `plugins/andon/agents/*.md`'s block-style `tools:` field). Anything else
    raises rather than guessing -- a wrong guess here silently mis-reports
    the surface, which is worse than refusing to run.
    """
    data: dict = {}
    lines = block.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line[:1] in (" ", "\t", "-"):
            raise SurfaceIndexError(
                f"{path}: unexpected indented line outside a recognized list: {line!r}"
            )
        if ":" not in line:
            raise SurfaceIndexError(f"{path}: cannot parse frontmatter line: {line!r}")

        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()

        if rest:
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "\"'":
                rest = rest[1:-1]
            data[key] = rest
            index += 1
            continue

        # `key:` with no inline value -- collect a following indented `- item` list.
        items: list[str] = []
        cursor = index + 1
        while cursor < len(lines) and lines[cursor][:1] in (" ", "\t") and lines[cursor].lstrip().startswith("-"):
            item = lines[cursor].strip()[1:].strip()
            items.append(item)
            cursor += 1
        if not items:
            raise SurfaceIndexError(f"{path}: key {key!r} has no inline value and no following list")
        data[key] = items
        index = cursor

    return data


def normalize_tools(value: object, path: Path) -> list[str]:
    """Normalize an agent's `tools` frontmatter field to a list of tool names.

    Observed in this repo in three equivalent shapes: an unquoted comma
    string (`tools: Read, Glob, Bash`), a quoted comma string
    (`tools: "Read, Grep, Glob"`), and a YAML block list. All three must
    produce the same normalized list, or downstream consumers of
    surface.json would see the same capability reported differently
    depending on which plugin happened to write it.
    """
    if isinstance(value, list):
        tools = [str(item).strip() for item in value]
    elif isinstance(value, str):
        tools = [item.strip() for item in value.split(",")]
    else:
        raise SurfaceIndexError(f"{path}: unexpected type for 'tools': {type(value).__name__}")

    tools = [tool for tool in tools if tool]
    if not tools:
        raise SurfaceIndexError(f"{path}: 'tools' is present but empty after normalization")
    return tools


# --------------------------------------------------------------------------
# Per-plugin collectors
# --------------------------------------------------------------------------


def discover_plugins() -> list[Path]:
    if not PLUGINS.is_dir():
        raise SurfaceIndexError(f"no plugins/ directory found at {PLUGINS}")
    plugin_dirs = sorted(d for d in PLUGINS.iterdir() if d.is_dir())
    if not plugin_dirs:
        raise SurfaceIndexError(f"zero plugin directories found under {PLUGINS}")
    return plugin_dirs


def load_plugin_manifest(plugin_dir: Path) -> dict:
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise SurfaceIndexError(f"{plugin_dir.name}: missing {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SurfaceIndexError(f"{manifest_path}: invalid JSON: {exc}") from exc

    for field in ("name", "version", "description"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise SurfaceIndexError(
                f"{manifest_path}: missing or empty required field {field!r}"
            )
    return data


def collect_skills(plugin_dir: Path, plugin_name: str) -> list[dict]:
    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        return []

    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    if not skill_files:
        raise SurfaceIndexError(
            f"{plugin_dir.name}: skills/ exists but zero SKILL.md files found under it"
        )

    skills = []
    for path in skill_files:
        frontmatter = parse_frontmatter(path)
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if not isinstance(name, str) or not name.strip():
            raise SurfaceIndexError(f"{path}: empty or missing 'name' in frontmatter")
        if not isinstance(description, str) or not description.strip():
            raise SurfaceIndexError(f"{path}: empty or missing 'description' in frontmatter")
        skills.append(
            {
                "id": f"{plugin_name}:{name}",
                "name": name,
                "description": description,
            }
        )
    return skills


def collect_agents(plugin_dir: Path, plugin_name: str) -> list[dict]:
    agents_dir = plugin_dir / "agents"
    if not agents_dir.is_dir():
        return []

    agent_files = sorted(agents_dir.glob("*.md"))
    if not agent_files:
        raise SurfaceIndexError(
            f"{plugin_dir.name}: agents/ exists but zero .md files found under it"
        )

    agents = []
    for path in agent_files:
        frontmatter = parse_frontmatter(path)
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if not isinstance(name, str) or not name.strip():
            raise SurfaceIndexError(f"{path}: empty or missing 'name' in frontmatter")
        if not isinstance(description, str) or not description.strip():
            raise SurfaceIndexError(f"{path}: empty or missing 'description' in frontmatter")
        if "tools" not in frontmatter:
            raise SurfaceIndexError(f"{path}: missing 'tools' in frontmatter")
        tools = normalize_tools(frontmatter["tools"], path)
        agents.append(
            {
                "id": f"{plugin_name}:{name}",
                "name": name,
                "description": description,
                "tools": tools,
            }
        )
    return agents


def collect_commands(plugin_dir: Path) -> list[str]:
    commands_dir = plugin_dir / "commands"
    if not commands_dir.is_dir():
        return []

    command_files = sorted(commands_dir.glob("*.md"))
    if not command_files:
        raise SurfaceIndexError(
            f"{plugin_dir.name}: commands/ exists but zero .md files found under it"
        )
    return [path.stem for path in command_files]


def collect_hooks(plugin_dir: Path) -> dict:
    hooks_path = plugin_dir / "hooks" / "hooks.json"
    if not hooks_path.is_file():
        return {"present": False, "events": []}

    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SurfaceIndexError(f"{hooks_path}: invalid JSON: {exc}") from exc

    events = data.get("hooks")
    if not isinstance(events, dict):
        raise SurfaceIndexError(
            f"{hooks_path}: expected a 'hooks' object mapping event name -> handlers"
        )
    if not events:
        raise SurfaceIndexError(f"{hooks_path}: hooks.json exists but registers zero events")
    return {"present": True, "events": sorted(events.keys())}


def parse_workflow_name(path: Path) -> str:
    """Extract the `name` declared in a workflow's `export const meta = {...}` block.

    Scans line by line from the opening of the `meta` object to its first
    `name:` line, deliberately not a regex spanning the whole file -- this
    repo's workflow files also contain other `name`-shaped keys deeper in
    their `phases`/`units` structures (e.g. `{ name, path, deps }` unit
    shapes), so matching anywhere in the file rather than only within the
    leading `meta` block would be exactly the kind of overreaching pattern
    CLAUDE.md warns about.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    in_meta = False
    for line in lines:
        stripped = line.strip()
        if not in_meta:
            if stripped.startswith("export const meta"):
                in_meta = True
            continue
        if stripped.startswith("name:"):
            value = stripped[len("name:") :].strip().rstrip(",")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                return value[1:-1]
            raise SurfaceIndexError(f"{path}: could not parse a quoted name from: {line!r}")
        if stripped == "}":
            break
    raise SurfaceIndexError(f"{path}: no 'name:' field found in its 'export const meta' block")


def collect_workflows(plugin_dir: Path) -> list[str]:
    workflows_dir = plugin_dir / "workflows"
    if not workflows_dir.is_dir():
        return []

    workflow_files = sorted(workflows_dir.glob("*.js"))
    if not workflow_files:
        raise SurfaceIndexError(
            f"{plugin_dir.name}: workflows/ exists but zero .js files found under it"
        )
    return [parse_workflow_name(path) for path in workflow_files]


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------


def build_surface() -> dict:
    plugin_dirs = discover_plugins()

    plugins_out = []
    skill_ids: list[str] = []
    agent_ids: list[str] = []

    for plugin_dir in plugin_dirs:
        manifest = load_plugin_manifest(plugin_dir)
        name = manifest["name"]

        skills = collect_skills(plugin_dir, name)
        agents = collect_agents(plugin_dir, name)
        commands = collect_commands(plugin_dir)
        hooks = collect_hooks(plugin_dir)
        workflows = collect_workflows(plugin_dir)

        skill_ids.extend(skill["id"] for skill in skills)
        agent_ids.extend(agent["id"] for agent in agents)

        plugins_out.append(
            {
                "name": name,
                "version": manifest["version"],
                "description": manifest["description"],
                "skills": skills,
                "agents": agents,
                "commands": commands,
                "hooks": hooks,
                "workflows": workflows,
            }
        )

    if not skill_ids:
        raise SurfaceIndexError("zero skills found across all plugins -- expected at least one")
    if not agent_ids:
        raise SurfaceIndexError("zero agents found across all plugins -- expected at least one")

    return {
        "generatedBy": "tools/surface-index/build_surface_index.py",
        "plugins": plugins_out,
        "skillIds": skill_ids,
        "agentIds": agent_ids,
    }


def render(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "regenerate to a temp location and diff against the committed "
            f"{OUTPUT.relative_to(REPO)}; exit non-zero on drift instead of writing"
        ),
    )
    args = parser.parse_args(argv)

    try:
        data = build_surface()
    except SurfaceIndexError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rendered = render(data)

    if args.check:
        if not OUTPUT.is_file():
            print(
                f"error: --check requested but {OUTPUT.relative_to(REPO)} does not exist yet "
                "-- run without --check first to generate it",
                file=sys.stderr,
            )
            return 1
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "surface.json"
            tmp_path.write_text(rendered, encoding="utf-8")
            diff = subprocess.run(
                ["diff", "-u", str(OUTPUT), str(tmp_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if diff.returncode != 0:
                print(
                    f"error: {OUTPUT.relative_to(REPO)} is stale relative to the current plugin "
                    "surface. Regenerate with:\n"
                    "  python3 tools/surface-index/build_surface_index.py",
                    file=sys.stderr,
                )
                print(diff.stdout, file=sys.stderr)
                return 1
        print(f"OK: {OUTPUT.relative_to(REPO)} matches the current plugin surface")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(
        f"wrote {OUTPUT.relative_to(REPO)}: {len(data['plugins'])} plugins, "
        f"{len(data['skillIds'])} skills, {len(data['agentIds'])} agents"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
