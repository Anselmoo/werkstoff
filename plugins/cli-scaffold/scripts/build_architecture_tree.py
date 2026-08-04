#!/usr/bin/env python3
"""Renders a generated scaffold's real directory tree as a self-contained
HTML viewer, each file tagged with which five-pillar role(s) it plays --
derived entirely from cli-scaffold.manifest.json's own gating keys (the same
fields cli-scaffold-verifier already reads to decide pass/fail), not
re-invented here.

Written INSIDE the scaffold directory itself (generated-clis/<app-name>/),
not under analysis/ -- unlike the other six plugins, cli-scaffold's output
IS the deliverable, not an audit report about an existing codebase. Shipping
the architecture diagram alongside the code it describes means whoever
receives the generated CLI also gets a visual explanation of it.

Usage:
    build_architecture_tree.py <scaffold_dir> --template <path> [--out <path>]
"""
import argparse
import json
import os
import sys

MANIFEST_NAME = "cli-scaffold.manifest.json"

# Every manifest key that names a file, mapped to the pillar role it plays.
# core_files is the only list-valued key; the rest are single paths (or, for
# completion, a nested {file: ...} that may be null / absent for languages
# with no native completion mechanism).
ROLE_LABELS = {
    "core": "Backend/core (zero CLI-framework imports)",
    "entry": "Entry point (thin, wires flags to core)",
    "distribution": "Idiomatic distribution / packaging metadata",
    "test": "Stability (--help snapshot test)",
    "help": "UX/discoverability (--help golden output)",
    "completion": "UX/discoverability (shell completion)",
}

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "target", "dist", "build"}


def _roles_by_relpath(manifest):
    roles = {}

    def add(relpath, role):
        if not relpath:
            return
        norm = os.path.normpath(relpath)
        roles.setdefault(norm, []).append(role)

    for f in manifest.get("core_files", []) or []:
        add(f, "core")
    add(manifest.get("entry_file"), "entry")
    add(manifest.get("distribution_file"), "distribution")
    add(manifest.get("snapshot_test"), "test")
    add(manifest.get("help_file"), "help")
    completion = manifest.get("completion") or {}
    add(completion.get("file"), "completion")
    return roles


def build_tree(scaffold_dir, manifest):
    roles_by_path = _roles_by_relpath(manifest)

    def walk(abs_dir, rel_dir):
        entries = []
        try:
            names = sorted(os.listdir(abs_dir))
        except OSError:
            return entries
        for name in names:
            if name in EXCLUDE_DIRS or name == MANIFEST_NAME:
                continue
            abs_path = os.path.join(abs_dir, name)
            rel_path = os.path.normpath(os.path.join(rel_dir, name)) if rel_dir else name
            if os.path.isdir(abs_path):
                entries.append({
                    "name": name,
                    "type": "dir",
                    "children": walk(abs_path, rel_path),
                })
            else:
                entries.append({
                    "name": name,
                    "type": "file",
                    "roles": roles_by_path.get(os.path.normpath(rel_path), []),
                })
        return entries

    return {
        "name": manifest.get("app_name") or os.path.basename(os.path.normpath(scaffold_dir)),
        "type": "dir",
        "children": walk(scaffold_dir, ""),
    }


def render_html(template_path, d3_path, tokens_path, payload):
    tpl = open(template_path, encoding="utf-8").read()
    d3_snippet = open(d3_path, encoding="utf-8").read()
    tokens_css = open(tokens_path, encoding="utf-8").read()

    tokens_marker = "/*__TOKENS__*/"
    if tokens_marker not in tpl:
        raise ValueError(f"tokens injection marker not found in {template_path}")
    tpl = tpl.replace(tokens_marker, tokens_css)

    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(d3_marker, d3_snippet)

    data_marker = "/*__TREE_DATA__*/ null"
    if data_marker not in tpl:
        raise ValueError(f"data injection marker not found in {template_path}")
    data = json.dumps(payload)
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(data_marker, "/*__TREE_DATA__*/ " + data)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("scaffold_dir")
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", required=True, help="path to the vendored tokens.css")
    parser.add_argument("--out", help="defaults to <scaffold_dir>/ARCHITECTURE.html")
    args = parser.parse_args(argv)

    manifest_path = os.path.join(args.scaffold_dir, MANIFEST_NAME)
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    tree = build_tree(args.scaffold_dir, manifest)
    payload = {
        "appName": manifest.get("app_name"),
        "language": manifest.get("language"),
        "tree": tree,
        "roleLabels": ROLE_LABELS,
    }

    out_path = args.out or os.path.join(args.scaffold_dir, "ARCHITECTURE.html")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(args.template, args.d3, args.tokens, payload))

    print(json.dumps({"architecturePath": out_path}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
