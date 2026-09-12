#!/usr/bin/env python3
"""Lift an existing CSS custom-property block into DTCG, changing nothing visually.

The discipline this implements
------------------------------
If the pixels move, the retrofit failed. A value you want to change is a FINDING, not a
change. Nothing here rounds, normalises a colour, reorders a font stack, or "tidies while
it is in there" — every one of those would destroy the only equivalence proof available.

Aliases are the subtle half. `--accent: var(--silica)` must round-trip as a DTCG
reference `{color.silica}`, NOT as the hex it happens to resolve to. Flattening it
renders pixel-identical and is still wrong: the system forgets that accent IS silica, and
the provenance graph loses an edge. That is why `prove_retrofit.py` has two arms.

Usage:
    retrofit_css.py <tokens.css> --out <tokens.json> [--reference <slug>]
    retrofit_css.py --selftest
Exit: 0 written, 1 the input could not be read or a declaration could not be typed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXT = "com.werkstoff.matrize"
DECL = re.compile(r"^[ \t]*(--[\w-]+)[ \t]*:[ \t]*([^;]+);", re.M)
VAR = re.compile(r"^var\(\s*(--[\w-]+)\s*\)$")
HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
PX = re.compile(r"^(-?[\d.]+)(px|rem|em|%)$")
DUR = re.compile(r"^(-?[\d.]+)(ms|s)$")
NUM = re.compile(r"^-?[\d.]+$")
TRANSITION = re.compile(r"^(-?[\d.]+)(ms|s)\s+([a-z-]+(?:\([^)]*\))?)$")

# Which DTCG group a custom property belongs in, by name prefix. Longest prefix wins, so
# `--font-size-base` lands in dimension rather than fontFamily.
GROUPS: list[tuple[str, str]] = [
    ("--font-size", "dimension"),
    ("--line-height", "number"),
    ("--font", "fontFamily"),
    ("--transition", "transition"),
    ("--space", "dimension"),
    ("--radius", "dimension"),
    ("--header", "dimension"),
]


def group_for(name: str, kind: str) -> str:
    """Dotted DTCG path for a custom property. Structure mirrors the name, not the type."""
    stem = name.lstrip("-")
    for prefix, _ in sorted(GROUPS, key=lambda g: -len(g[0])):
        if name.startswith(prefix):
            return f"{prefix.lstrip('-')}.{stem[len(prefix) - 2:].lstrip('-') or 'base'}"
    return f"{kind}.{stem}"


def hex_to_components(value: str) -> dict:
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    alpha = None
    if len(v) == 8:
        alpha = round(int(v[6:8], 16) / 255, 4)
        v = v[:6]
    out: dict = {
        "colorSpace": "srgb",
        "components": [round(int(v[i : i + 2], 16) / 255, 6) for i in (0, 2, 4)],
        # `hex` is kept so a formatter can round-trip the ORIGINAL spelling rather than
        # recomputing it. Recomputation is where "#fff" quietly becomes "#ffffff" and a
        # textual diff starts reporting a change that is not one.
        "hex": value,
    }
    if alpha is not None:
        out["alpha"] = alpha
    return out


def typed(value: str) -> tuple[str, object] | None:
    """(type, $value) for a declaration, or None when nothing here can express it."""
    if HEX.match(value):
        return "color", hex_to_components(value)
    m = PX.match(value)
    if m:
        return "dimension", {"value": float(m.group(1)), "unit": m.group(2)}
    m = TRANSITION.match(value)
    if m:
        return "transition", {
            "duration": {"value": float(m.group(1)), "unit": m.group(2)},
            "timingFunction": m.group(3),
        }
    m = DUR.match(value)
    if m:
        return "duration", {"value": float(m.group(1)), "unit": m.group(2)}
    if NUM.match(value):
        return "number", float(value)
    if "," in value or value.startswith("-apple-system"):
        # Font stacks stay a LIST in source order. Re-sorting or de-duplicating would
        # change which face actually resolves on some platform.
        return "fontFamily", [f.strip().strip('"\'') for f in value.split(",")]
    return None


def retrofit(css: str, reference: str = "existing-css") -> tuple[dict, list[str]]:
    decls = DECL.findall(css)
    if not decls:
        raise ValueError("no custom-property declarations found")

    # First pass: decide every declaration's dotted path, so aliases can resolve to one.
    paths: dict[str, str] = {}
    kinds: dict[str, str] = {}
    for name, raw in decls:
        value = raw.strip()
        if VAR.match(value):
            continue
        t = typed(value)
        if t:
            kinds[name] = t[0]
            paths[name] = group_for(name, t[0])

    # Aliases inherit their target's path group, so `--accent` sits beside `--silica`.
    for name, raw in decls:
        value = raw.strip()
        m = VAR.match(value)
        if m:
            target = m.group(1)
            kinds[name] = kinds.get(target, "color")
            paths[name] = group_for(name, kinds[name])

    doc: dict = {}
    findings: list[str] = []

    def put(path: str, token: dict) -> None:
        node = doc
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = token

    for name, raw in decls:
        value = raw.strip()
        path = paths.get(name)
        if path is None:
            findings.append(f"{name}: {value!r} has no DTCG type in this profile — left out")
            continue

        ext = {
            "cssName": name,
            "card": f"CARD-RETRO-{name.lstrip('-')}",
            "reliability": "A",   # the project's own source
            "rights": "R1",       # the user's own material
            "edge": {"from": f"CARD-RETRO-{name.lstrip('-')}", "grade": "A"},
        }

        m = VAR.match(value)
        if m:
            target = paths.get(m.group(1))
            if target is None:
                findings.append(f"{name}: aliases {m.group(1)}, which is not declared here")
                continue
            # THE LOAD-BEARING LINE. A reference, never the resolved value.
            put(path, {"$value": f"{{{target}}}", "$extensions": {EXT: ext}})
            continue

        t = typed(value)
        if t is None:
            findings.append(f"{name}: {value!r} has no DTCG type in this profile — left out")
            continue
        put(path, {"$type": t[0], "$value": t[1], "$extensions": {EXT: ext}})

    doc["$extensions"] = {EXT: {"retrofittedFrom": reference, "note":
        "Lifted from existing CSS. Values are unchanged by construction; aliases are "
        "preserved as references, not resolved."}}
    return doc, findings


SAMPLE = """:root {
  --ink: #dfe6ea;
  --paper: #0a0d10;
  --accent: var(--ink);
  --space-1: 4px;
  --radius-sm: 4px;
  --line-height-base: 1.45;
  --transition-fast: 120ms ease;
  --font-sans: -apple-system, "Segoe UI", sans-serif;
}"""


def selftest() -> int:
    doc, findings = retrofit(SAMPLE)
    checks: list[tuple[str, bool]] = []

    alias = doc["color"]["accent"]["$value"]
    checks.append(("alias stays a reference, not a hex", alias == "{color.ink}"))
    checks.append(("alias carries no $type of its own", "$type" not in doc["color"]["accent"]))
    checks.append(("hex spelling preserved verbatim",
                   doc["color"]["ink"]["$value"]["hex"] == "#dfe6ea"))
    # The F14 case: two roles, one value, must stay two tokens.
    checks.append(("4px stays TWO tokens, not one",
                   doc["space"]["1"]["$value"]["value"] == 4.0
                   and doc["radius"]["sm"]["$value"]["value"] == 4.0))
    checks.append(("transition typed, not stringified",
                   doc["transition"]["fast"]["$type"] == "transition"))
    checks.append(("font stack stays an ordered list",
                   doc["font"]["sans"]["$value"][0] == "-apple-system"))
    checks.append(("line-height is a number", doc["line-height"]["base"]["$value"] == 1.45))
    checks.append(("every token carries an edge", all(
        EXT in t.get("$extensions", {}) and "edge" in t["$extensions"][EXT]
        for grp in doc.values() if isinstance(grp, dict)
        for t in grp.values() if isinstance(t, dict) and "$value" in t)))
    checks.append(("nothing silently dropped", not findings))

    for label, ok in checks:
        print(f"  {label:<40} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    if findings:
        for f in findings:
            print(f"  finding: {f}")
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("css", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--reference", default="existing-css")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.css or not args.out:
        ap.print_help()
        return 1

    try:
        doc, findings = retrofit(Path(args.css).read_text(encoding="utf-8"), args.reference)
    except (OSError, ValueError) as exc:
        print(f"retrofit_css.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n = sum(1 for grp in doc.values() if isinstance(grp, dict)
            for t in grp.values() if isinstance(t, dict) and "$value" in t)
    print(f"wrote {args.out}: {n} token(s)")
    for f in findings:
        print(f"  FINDING (not a change): {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
