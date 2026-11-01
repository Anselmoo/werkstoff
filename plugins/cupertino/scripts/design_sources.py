#!/usr/bin/env python3
"""Read the design a repair must respect -- from up to three sources, without writing to any.

usage: design_sources.py snapshot [--run ID] [--artifact DIR] [--matrize FILE]
       design_sources.py css FILE...        (mode-aware custom-property lift, printed)
       design_sources.py charts FILE...     (colour literals and var() strings inside JS)
       design_sources.py artifact DIR       (normalise a Claude Design System export)
       design_sources.py --selftest

Sources, in the order a conflict is reported (never silently resolved):
  1. a Claude Design System artifact, read by the session with the Artifact tool into
     .cupertino/repair/<run>/design/artifact/ (scripts cannot call that tool). Its
     project/tokens.json is NOT DTCG: version 1, colours under color.tokens with
     per-theme value maps ({"default","dark","light"}) and {name} aliases. A folder
     with no project/ is an EMPTY SHELL -- the type's own files only -- and is refused
     by name: building against it silently means building against nothing.
  2. matrize's DTCG file (.design/system/tokens.json, or the root: in .claude/matrize.local.md).
  3. the target's own CSS, lifted per mode -- :root, @media (prefers-color-scheme: dark|light),
     [data-theme=dark|light], .dark/.light -- because a flat lift keeps the last value and
     loses a theme (the defect matrize's retrofit_css.py now refuses).
Plus every colour literal inside JS/TS, because a chart drawn on canvas or SVG takes its
palette from JS, and swapping such a literal for "var(--x)" paints it black.

`snapshot` writes .cupertino/repair/<run>/design/source.json:
  {"tokens": {"--name": {"light": v, "dark": v, "base": v, "origin": [...]}},
   "conflicts": [{"name", "values": {source: value}}], "charts": [...], "sources": {...}}

Exit: 0 ok; 1 a source is unusable (e.g. an empty artifact shell); 2 bad usage.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_lib import RepairError, active_run, project_root, read_json, run_dir, scope_files, write_json  # noqa: E402

DECL = re.compile(r"(--[\w-]+)\s*:\s*([^;{}]+?)\s*(?:;|(?=\}))")
COLOR_LIT = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|\b(?:rgb|rgba|hsl|hsla|oklch)\([^)]*\)")
VAR_IN_JS = re.compile(r"""["'`]\s*var\(\s*--[\w-]+\s*\)\s*["'`]""")
REF = re.compile(r"^\{([\w.-]+)\}$")
CSS_SUFFIXES = {".css", ".scss", ".html", ".htm", ".vue", ".svelte"}
JS_SUFFIXES = {".js", ".mjs", ".ts", ".jsx", ".tsx", ".vue", ".svelte", ".html", ".htm"}


def _mode_of(header: str) -> str | None:
    h = header.lower()
    if re.search(r"prefers-color-scheme\s*:\s*dark|\[data-theme\s*=\s*[\"']?dark|\.dark\b", h):
        return "dark"
    if re.search(r"prefers-color-scheme\s*:\s*light|\[data-theme\s*=\s*[\"']?light|\.light\b", h):
        return "light"
    return None


def css_modes(text: str) -> dict[str, dict[str, str]]:
    """{--name: {mode: value}} where mode is base / light / dark, by enclosing block."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out: dict[str, dict[str, str]] = {}
    stack: list[str] = []
    i, start = 0, 0
    while i < len(text):
        ch = text[i]
        if ch == "{":
            stack.append(text[start:i].strip()[-200:])
            start = i + 1
        elif ch == "}":
            body = text[start:i]
            mode = next((m for m in (_mode_of(h) for h in reversed(stack)) if m), "base")
            for name, value in DECL.findall(body + ";"):
                out.setdefault(name, {})[mode] = value.strip()
            if stack:
                stack.pop()
            start = i + 1
        i += 1
    return out


def chart_literals(path: Path, text: str) -> dict:
    """Colour literals and var() strings in script. A var() string in JS is a defect."""
    scripts = text
    if path.suffix in (".html", ".htm", ".vue", ".svelte"):
        scripts = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", text, flags=re.S | re.I))
    # Comments out first: a comment WARNING against var() in JS is not a use of it.
    scripts = re.sub(r"/\*.*?\*/", "", scripts, flags=re.S)
    scripts = re.sub(r"(?<![:\\])//[^\n]*", "", scripts)
    lits = sorted(set(COLOR_LIT.findall(scripts)))
    var_strings = [m.group(0) for m in VAR_IN_JS.finditer(scripts)]
    return {"file": path.name, "literals": lits, "varStringsInJs": var_strings}


def artifact_tokens(art_dir: Path) -> dict[str, dict[str, str]]:
    """Normalise a Claude Design System export (project/tokens.json, version 1)."""
    project = art_dir / "project"
    tokens_file = project / "tokens.json"
    if not project.is_dir() or not tokens_file.is_file():
        raise RepairError(
            f"{art_dir} holds no project/tokens.json -- this Design System artifact is an EMPTY SHELL (only the type's own "
            "files). Ask the user for one that has content, or build its tokens from this repo's code first.")
    doc = json.loads(tokens_file.read_text(encoding="utf-8"))
    flat: dict[str, object] = {}
    for group, body in doc.items():
        if isinstance(body, dict) and isinstance(body.get("tokens"), list):
            for tok in body["tokens"]:
                flat[tok["name"]] = tok.get("value")
    families = (doc.get("type") or {}).get("families") or {}
    flat.update(families)

    def resolve(value: object, mode: str, depth: int = 0) -> str | None:
        if depth > 10:
            return None
        if isinstance(value, dict):
            value = value.get(mode, value.get("default"))
        if not isinstance(value, str):
            return None if value is None else str(value)
        m = REF.match(value.strip())
        return resolve(flat.get(m.group(1)), mode, depth + 1) if m else value

    out: dict[str, dict[str, str]] = {}
    for name, value in flat.items():
        modes = {}
        for mode in ("light", "dark"):
            v = resolve(value, mode)
            if v is not None:
                modes[mode] = v
        if modes:
            out["--" + name] = modes
    return out


def matrize_tokens(path: Path) -> dict[str, dict[str, str]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}

    def walk(node: dict, trail: list[str]) -> None:
        if "$value" in node:
            ext = (node.get("$extensions") or {}).get("com.werkstoff.matrize", {})
            name = ext.get("cssName") or "--" + "-".join(trail)
            v = node["$value"]
            if isinstance(v, dict) and "hex" in v:
                v = v["hex"]
            elif isinstance(v, dict) and "value" in v:
                v = f"{v['value']}{v.get('unit', '')}"
            out[name] = {"base": v if isinstance(v, str) else json.dumps(v)}
            return
        for k, child in node.items():
            if isinstance(child, dict) and not k.startswith("$"):
                walk(child, [*trail, k])

    walk(doc, [])
    return out


def _norm(v: str) -> str:
    return re.sub(r"\s+", "", v.lower())


def snapshot(root: Path, run_id: str, artifact: Path | None, matrize: Path | None) -> dict:
    rdir = run_dir(root, run_id)
    objective = read_json(rdir / "objective.json")
    sources: dict[str, dict] = {}
    if artifact is None and (rdir / "design" / "artifact").is_dir():
        artifact = rdir / "design" / "artifact"
    if artifact is not None:
        sources["artifact"] = artifact_tokens(artifact)
    if matrize is not None and matrize.is_file():
        sources["matrize"] = matrize_tokens(matrize)
    repo: dict[str, dict[str, str]] = {}
    charts = []
    for rel in scope_files(root, objective["scope"]):
        p = root / rel
        if p.suffix not in CSS_SUFFIXES | JS_SUFFIXES:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix in CSS_SUFFIXES:
            for name, modes in css_modes(text).items():
                repo.setdefault(name, {}).update(modes)
        if p.suffix in JS_SUFFIXES:
            c = chart_literals(p, text)
            if c["literals"] or c["varStringsInJs"]:
                c["file"] = rel
                charts.append(c)
    sources["repo"] = repo
    tokens: dict[str, dict] = {}
    for origin, toks in sources.items():
        for name, modes in toks.items():
            entry = tokens.setdefault(name, {"origin": []})
            entry["origin"].append(origin)
            for mode, v in modes.items():
                entry.setdefault(f"{origin}:{mode}", v)
    conflicts = []
    for name, entry in tokens.items():
        for mode in ("light", "dark", "base"):
            vals = {k.split(":")[0]: v for k, v in entry.items() if k.endswith(":" + mode)}
            if len({_norm(v) for v in vals.values()}) > 1:
                conflicts.append({"name": name, "mode": mode, "values": vals})
    snap = {"sources": {k: len(v) for k, v in sources.items()}, "tokens": tokens, "conflicts": conflicts,
            "charts": charts,
            "warnings": [f"{c['file']}: JS passes {c['varStringsInJs'][0]} as a colour -- a canvas/SVG renderer cannot "
                         "resolve CSS variables" for c in charts if c["varStringsInJs"]]}
    write_json(rdir / "design" / "source.json", snap)
    return snap


def selftest() -> int:
    import tempfile
    fails: list[str] = []

    def ok(name: str, cond: bool, extra: str = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + extra}")
        if not cond:
            fails.append(name)

    css = ":root{--bg:#fff;--fg:#111}\n@media (prefers-color-scheme: dark){:root{--bg:#000}}\n[data-theme=\"light\"]{--fg:#222}"
    m = css_modes(css)
    ok("base value kept", m["--bg"].get("base") == "#fff", str(m))
    ok("dark override kept beside it, not collapsed", m["--bg"].get("dark") == "#000", str(m))
    ok("data-theme light recognised", m["--fg"].get("light") == "#222", str(m))
    c = chart_literals(Path("c.js"), "const P={bar:'#1874c2', bad:'var(--accent)'}")
    ok("JS colour literal found", "#1874c2" in c["literals"], str(c))
    ok("var() string in JS flagged", bool(c["varStringsInJs"]), str(c))
    c2 = chart_literals(Path("c.js"), "// never write 'var(--accent)' here\nconst u='https://x.org'; const P={bar:'#1874c2'}")
    ok("a var() inside a comment is not flagged; a URL survives", not c2["varStringsInJs"] and "#1874c2" in c2["literals"], str(c2))
    with tempfile.TemporaryDirectory() as td:
        art = Path(td)
        try:
            artifact_tokens(art)
            ok("an empty artifact shell is refused", False)
        except RepairError as err:
            ok("an empty artifact shell is refused", "EMPTY SHELL" in str(err))
        (art / "project").mkdir()
        (art / "project" / "tokens.json").write_text(json.dumps({"version": 1, "color": {"themes": [], "tokens": [
            {"name": "amber-400", "value": "#ffb36c"}, {"name": "ink-900", "value": "#2a1c10"},
            {"name": "reto-text", "value": {"default": "{amber-400}", "dark": "{amber-400}", "light": "{ink-900}"}}]}}),
            encoding="utf-8")
        t = artifact_tokens(art)
        ok("artifact aliases resolve per theme", t["--reto-text"] == {"light": "#2a1c10", "dark": "#ffb36c"}, str(t.get("--reto-text")))
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("selftest passed")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--selftest"]:
        return selftest()
    parser = argparse.ArgumentParser(prog="design_sources.py", description="Read a repair's design sources without writing to them.",
                                     epilog="exit 0 ok, 1 a source is unusable, 2 bad usage")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--run")
    s.add_argument("--artifact", help="folder holding an Artifact-tool export (project/tokens.json)")
    s.add_argument("--matrize", help="DTCG tokens.json (default: .design/system/tokens.json if present)")
    sub.add_parser("css").add_argument("files", nargs="+")
    sub.add_parser("charts").add_argument("files", nargs="+")
    sub.add_parser("artifact").add_argument("dir")
    args = parser.parse_args(argv)
    root = project_root()
    try:
        if args.cmd == "snapshot":
            run_id = args.run or active_run(root)
            if not run_id:
                raise RepairError("no repair run is active")
            matrize = Path(args.matrize) if args.matrize else root / ".design" / "system" / "tokens.json"
            out = snapshot(root, run_id, Path(args.artifact) if args.artifact else None, matrize)
            out = {"sources": out["sources"], "conflicts": len(out["conflicts"]), "charts": len(out["charts"]),
                   "warnings": out["warnings"]}
        elif args.cmd == "css":
            out = {f: css_modes(Path(f).read_text(encoding="utf-8")) for f in args.files}
        elif args.cmd == "charts":
            out = [chart_literals(Path(f), Path(f).read_text(encoding="utf-8")) for f in args.files]
        else:
            out = artifact_tokens(Path(args.dir))
    except (RepairError, OSError, ValueError) as err:
        print(f"design_sources: {err}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
