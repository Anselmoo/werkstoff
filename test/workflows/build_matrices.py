#!/usr/bin/env python3
"""Resolve the committed matrix templates into machine-local matrices.

Why templates plus a generator, rather than committed matrices: a matrix names absolute paths --
this machine's plugin cache, this checkout's fixtures -- and a committed absolute path is wrong
on every other machine and leaks a home directory besides. The templates carry placeholders and
nothing else; this script resolves them HERE and writes the result under analysis/, which is
gitignored.

Placeholders:
    ${FIXTURE:<name>}      -> test/workflows/fixtures/<name>            (must exist)
    ${REPO_PLUGIN:<name>}  -> plugins/<name>                            (must exist)
    ${PLUGIN:<name>}       -> the installPath of an installed plugin    (must be installed)

A placeholder that cannot be resolved is a REFUSAL, never a silently dropped arm: an enabled arm
that loads nothing looks exactly like a plugin that did not fire, and the sweep would report a
number for an experiment that never ran.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = Path(__file__).resolve().parent / "matrices"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
INSTALLED = Path.home() / ".claude" / "plugins" / "installed_plugins.json"

PLACEHOLDER = re.compile(r"\$\{(FIXTURE|REPO_PLUGIN|PLUGIN):([A-Za-z0-9._@-]+)\}")


class Unresolvable(Exception):
    """A placeholder names something this machine does not have."""


def installed_plugin_paths() -> dict[str, str]:
    """Plugin name -> installPath, from the CLI's own registry."""
    if not INSTALLED.is_file():
        return {}
    data = json.loads(INSTALLED.read_text(encoding="utf-8"))
    plugins = data.get("plugins", data)
    paths: dict[str, str] = {}
    if isinstance(plugins, dict):
        for key, value in plugins.items():
            name = key.split("@")[0]
            entries = value if isinstance(value, list) else [value]
            for entry in entries:
                if isinstance(entry, dict) and entry.get("installPath"):
                    paths.setdefault(name, entry["installPath"])
    return paths


def resolve_one(kind: str, name: str, installed: dict[str, str]) -> str:
    if kind == "FIXTURE":
        path = FIXTURES / name
        if not path.is_dir():
            raise Unresolvable(f"no fixture '{name}' at {path}")
        return str(path)
    if kind == "REPO_PLUGIN":
        path = REPO / "plugins" / name
        if not path.is_dir():
            raise Unresolvable(f"no plugin '{name}' at {path}")
        return str(path)
    path_text = installed.get(name)
    if not path_text:
        raise Unresolvable(
            f"plugin '{name}' is not installed on this machine. Install it "
            f"(/plugin install {name}) or drop the arm that needs it -- an enabled arm that "
            "loads nothing is indistinguishable from a plugin that did not fire."
        )
    if not Path(path_text).is_dir():
        raise Unresolvable(f"plugin '{name}' claims installPath {path_text}, which does not exist")
    return path_text


def resolve(node: object, installed: dict[str, str]) -> object:
    """Walk the template, replacing every placeholder. Strings only; structure is untouched."""
    if isinstance(node, dict):
        return {key: resolve(value, installed) for key, value in node.items()}
    if isinstance(node, list):
        return [resolve(item, installed) for item in node]
    if isinstance(node, str):
        return PLACEHOLDER.sub(lambda m: resolve_one(m.group(1), m.group(2), installed), node)
    return node


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="directory to write resolved matrices into")
    parser.add_argument("--template", help="resolve only this template (basename or path)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    installed = installed_plugin_paths()

    templates = sorted(TEMPLATES.glob("*.template.json"))
    if args.template:
        wanted = Path(args.template).name
        templates = [t for t in templates if t.name == wanted or t.stem == wanted]
        if not templates:
            print(f"no template matching {args.template!r} in {TEMPLATES}", file=sys.stderr)
            return 2
    if not templates:
        print(f"no templates found in {TEMPLATES}", file=sys.stderr)
        return 2

    written = []
    for template in templates:
        matrix = json.loads(template.read_text(encoding="utf-8"))
        try:
            resolved = resolve(matrix, installed)
        except Unresolvable as exc:
            print(f"REFUSED {template.name}: {exc}", file=sys.stderr)
            return 1
        target = out_dir / template.name.replace(".template", "")
        target.write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")
        cells = (len(resolved["cases"]) * len(resolved["models"])
                 * len(resolved["plugin_states"]) * resolved.get("repeats", 1))
        written.append((target, cells))
        print(f"  {target}  ({cells} cells)")

    print(f"\n{len(written)} matrix file(s), {sum(c for _, c in written)} cells total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
