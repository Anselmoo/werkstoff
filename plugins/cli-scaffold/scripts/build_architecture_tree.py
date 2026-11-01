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
    build_architecture_tree.py <scaffold_dir> --template <path> --d3 <path> --tokens <path>
                               [--out <path>]

The page is composed by the shared report kit (assets/report-kit.{css,js}, scripts/report_kit.py):
the figure (an icicle of the tree joined by ribbons to a per-pillar role ledger) and the indented
file list below it stay bespoke d3-hierarchy, while the doctrine gaps, the evidence
behind each one and the scaffold's CLI surface come from the same manifest and are shown in the
kit's findings and table components.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from report_kit import KitError  # noqa: E402
from report_kit import render as kit_render  # noqa: E402

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

# The manifest key each role is read from, so the viewer's detail panel can name
# the exact line a file's badge comes from (verify_scaffold.py gates on the same keys).
ROLE_KEYS = {
    "core": "core_files",
    "entry": "entry_file",
    "distribution": "distribution_file",
    "test": "snapshot_test",
    "help": "help_file",
    "completion": "completion.file",
}

# Which of cli-architecture's five pillars each role is evidence for. Only four
# pillars appear: the fifth, Unix composability, is behavioural (exit codes
# 0/1/2, data on stdout, diagnostics on stderr) and no file can carry its badge,
# so the viewer states that in prose rather than scoring a pillar it cannot see.
# A pillar counts as evidenced when ANY of its roles has a file behind it.
ROLE_PILLARS = {
    "core": "backend/core separation",
    "entry": "backend/core separation",
    "distribution": "idiomatic distribution",
    "test": "stability",
    "help": "UX/discoverability",
    "completion": "UX/discoverability",
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


def _manifest_paths(manifest):
    """Every (manifest key, relative path, role) the manifest names, present on disk or not."""
    out = [("core_files", f, "core") for f in manifest.get("core_files", []) or [] if f]
    for key, role in (("entry_file", "entry"), ("distribution_file", "distribution"),
                      ("snapshot_test", "test"), ("help_file", "help")):
        if manifest.get(key):
            out.append((key, manifest[key], role))
    completion = manifest.get("completion") or {}
    if completion.get("file"):
        out.append(("completion.file", completion["file"], "completion"))
    return out


def build_findings(scaffold_dir, manifest):
    """The doctrine gaps this scaffold has, each with the manifest line that proves it.

    Two kinds. A role no file plays (the manifest declares nothing for it), and a role whose
    file the manifest names but the tree does not contain -- which the tree walk alone drops
    without a word, so the role would render as merely "absent".
    """
    scaffold = Path(scaffold_dir)
    declared = _manifest_paths(manifest)
    declared_roles = {role for _, _, role in declared}
    findings = []

    for key, rel, role in declared:
        if not (scaffold / rel).exists():
            findings.append({
                "id": f"missing-{role}-{rel}", "severity": "blocker", "rule": "declared-file-missing",
                "claim": f"The manifest names {rel} for the {role} role, but that file is not in the scaffold",
                "file": MANIFEST_NAME, "quote": f'"{key}": {json.dumps(rel)}',
                "fix": f"Create {rel}, or correct the manifest key {key}; verify_scaffold.py reads the same key and will fail it.",
                "evidence": [{"label": "role", "detail": ROLE_LABELS[role]},
                             {"label": "checked", "detail": f"{rel} does not exist under {scaffold.name}/"}],
                "tags": {"role": role, "pillar": ROLE_PILLARS[role]},
            })

    pillar_roles = {}
    for role, pillar in ROLE_PILLARS.items():
        pillar_roles.setdefault(pillar, []).append(role)
    completion = manifest.get("completion") or {}
    quotes = {
        "core": '"core_files": ' + json.dumps(manifest.get("core_files")),
        "entry": '"entry_file": ' + json.dumps(manifest.get("entry_file")),
        "distribution": '"distribution_file": ' + json.dumps(manifest.get("distribution_file")),
        "test": '"snapshot_test": ' + json.dumps(manifest.get("snapshot_test")),
        "help": '"help_file": ' + json.dumps(manifest.get("help_file")),
        "completion": '"completion": ' + json.dumps(completion or None),
    }
    for role in ROLE_LABELS:
        if role in declared_roles:
            continue
        pillar = ROLE_PILLARS[role]
        others = [r for r in pillar_roles[pillar] if r != role and r in declared_roles]
        bare = not others
        evidence = [{"label": "role", "detail": ROLE_LABELS[role]},
                    {"label": "pillar", "detail": pillar + (" has no file behind it at all" if bare
                                                             else " is still evidenced by the " + ", ".join(others) + " role")}]
        if role == "completion" and completion.get("note"):
            evidence.append({"label": "manifest note", "detail": completion["note"]})
        findings.append({
            "id": f"no-{role}", "severity": "major" if bare else "minor", "rule": "role-unclaimed",
            "claim": f"No file plays the {role} role: {ROLE_LABELS[role]}",
            "file": MANIFEST_NAME, "quote": quotes[role],
            "fix": f"Generate the file for the {role} role and name it in the manifest; the verifier gates on that key.",
            "evidence": evidence,
            "tags": {"role": role, "pillar": pillar},
        })
    return findings


def build_surface(manifest):
    """The CLI surface the manifest declares -- flags, positional arguments, completion --
    which the viewer used to drop."""
    rows = [{"kind": "flag", "name": f.get("name", ""), "required": "", "description": f.get("description", "")}
            for f in manifest.get("flags", []) or [] if isinstance(f, dict)]
    rows += [{"kind": "argument", "name": a.get("name", ""),
              "required": "required" if a.get("required") else "optional",
              "description": a.get("description", "")}
             for a in manifest.get("positional_args", []) or [] if isinstance(a, dict)]
    completion = manifest.get("completion") or {}
    return {"rows": rows, "completion": completion.get("note") or "",
            "completionSupported": bool(completion.get("supported") or completion.get("file")),
            "paradigm": manifest.get("paradigm", "")}


def render_html(template_path, d3_path, tokens_path, payload):
    template = Path(template_path)
    tpl = template.read_text(encoding="utf-8")
    d3_snippet = Path(d3_path).read_text(encoding="utf-8")

    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")

    # The kit's own assets sit beside the template; a template kept elsewhere (a test stub)
    # falls back to this plugin's vendored copy. The kit inlines the tokens, its css/js and the
    # data island with < > & escaped (barrier one of S3); the template's textContent-only DOM
    # code is barrier two. The d3 snippet is trusted vendored code, so it is spliced in after.
    assets = template.parent if (template.parent / "report-kit.css").is_file() else Path(__file__).resolve().parent.parent / "assets"
    page = kit_render(tpl, assets, payload, tokens=Path(tokens_path))
    return page.replace(d3_marker, d3_snippet, 1)


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
        "paradigm": manifest.get("paradigm"),
        "tree": tree,
        "roleLabels": ROLE_LABELS,
        "rolePillars": ROLE_PILLARS,
        "roleKeys": ROLE_KEYS,
        "findings": build_findings(args.scaffold_dir, manifest),
        "surface": build_surface(manifest),
    }

    out_path = args.out or os.path.join(args.scaffold_dir, "ARCHITECTURE.html")
    try:
        html = render_html(args.template, args.d3, args.tokens, payload)
    except (KitError, ValueError, OSError) as exc:
        print(f"build_architecture_tree.py: {exc}", file=sys.stderr)
        return 2
    Path(out_path).write_text(html, encoding="utf-8")

    print(json.dumps({"architecturePath": out_path}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
