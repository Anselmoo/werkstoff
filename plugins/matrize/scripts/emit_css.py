#!/usr/bin/env python3
"""Emit CSS custom properties from a DTCG token file. Deterministic, no model in the loop.

Determinism is the requirement, not a nicety: the same tokens must produce byte-identical
output every run, because that property is what makes the retrofit equivalence proof
possible at all. A formatter that re-decides its output cannot prove equivalence with
anything.

A DTCG reference `{color.ink}` emits `var(--ink)`, never the resolved value. Resolving it
would render identically and lose the fact that one role IS another — the structural half
of the proof in `prove_retrofit.py`.

Usage:
    emit_css.py <tokens.json> [--out FILE] [--selector ':root'] [--order FILE]
    emit_css.py --selftest
`--order` takes the original CSS and emits in ITS declaration order, so a textual diff
shows value changes rather than reordering noise.
Exit: 0 emitted, 1 unusable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXT = "com.werkstoff.matrize"
REF = re.compile(r"^\{([A-Za-z0-9_.-]+)\}$")
DECL = re.compile(r"^[ \t]*(--[\w-]+)[ \t]*:", re.M)


def walk(node: dict, prefix: str = "") -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for key, value in node.items():
        if key.startswith("$") or not isinstance(value, dict):
            continue
        path = f"{prefix}.{key}" if prefix else key
        if "$value" in value:
            out.append((path, value))
        else:
            out.extend(walk(value, path))
    return out


def css_name(path: str, token: dict) -> str:
    """The custom-property name. A retrofitted token remembers its original spelling."""
    ext = (token.get("$extensions") or {}).get(EXT) or {}
    if ext.get("cssName"):
        return ext["cssName"]
    return "--" + path.replace(".", "-")


def render(kind: str | None, value, names: dict[str, str]) -> str | None:
    if isinstance(value, str):
        m = REF.match(value)
        if m:
            target = names.get(m.group(1))
            return f"var({target})" if target else None
        return value
    if kind == "color" and isinstance(value, dict):
        if value.get("hex"):
            return value["hex"]          # original spelling, never recomputed
        comps = value.get("components", [])
        body = "".join(f"{round(c * 255):02x}" for c in comps)
        alpha = value.get("alpha")
        if alpha is not None and alpha < 1:
            body += f"{round(alpha * 255):02x}"
        return f"#{body}"
    if kind in ("dimension", "duration") and isinstance(value, dict):
        n = value["value"]
        n = int(n) if float(n).is_integer() else n
        return f"{n}{value['unit']}"
    if kind == "transition" and isinstance(value, dict):
        d = value["duration"]
        n = d["value"]
        n = int(n) if float(n).is_integer() else n
        return f"{n}{d['unit']} {value.get('timingFunction', 'ease')}"
    if kind == "fontFamily":
        if isinstance(value, list):
            return ", ".join(f'"{f}"' if " " in f and not f.startswith("-") else f for f in value)
        return str(value)
    if kind == "number":
        n = value
        return str(int(n) if float(n).is_integer() else n)
    return None


def emit(doc: dict, selector: str = ":root", order: list[str] | None = None) -> str:
    tokens = walk(doc)
    names = {path: css_name(path, tok) for path, tok in tokens}

    # A token's type may be declared on a parent group; resolve it down the path.
    def kind_of(path: str, token: dict) -> str | None:
        if token.get("$type"):
            return token["$type"]
        node = doc
        found = None
        for part in path.split("."):
            if isinstance(node, dict):
                if "$type" in node:
                    found = node["$type"]
                node = node.get(part, {})
        if isinstance(node, dict) and "$type" in node:
            found = node["$type"]
        if found:
            return found
        # An alias inherits its target's type.
        m = REF.match(token["$value"]) if isinstance(token.get("$value"), str) else None
        if m:
            for p, t in tokens:
                if p == m.group(1):
                    return kind_of(p, t)
        return None

    lines: dict[str, str] = {}
    for path, token in tokens:
        text = render(kind_of(path, token), token["$value"], names)
        if text is None:
            raise ValueError(f"{path}: cannot render {token['$value']!r} to CSS")
        lines[names[path]] = f"  {names[path]}: {text};"

    if order:
        ordered = [lines[n] for n in order if n in lines]
        ordered += [v for k, v in lines.items() if k not in order]
    else:
        ordered = list(lines.values())

    return f"{selector} {{\n" + "\n".join(ordered) + "\n}\n"


def selftest() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import retrofit_css

    doc, _ = retrofit_css.retrofit(retrofit_css.SAMPLE)
    out = emit(doc)
    checks = [
        ("alias emits var(), not a hex", "--accent: var(--ink);" in out),
        ("hex spelling round-trips", "--ink: #dfe6ea;" in out),
        ("both 4px roles survive separately",
         "--space-1: 4px;" in out and "--radius-sm: 4px;" in out),
        ("transition reassembles", "--transition-fast: 120ms ease;" in out),
        ("font stack order preserved", out.count("-apple-system") == 1
         and out.index("-apple-system") < out.index("sans-serif")),
        ("number emits bare", "--line-height-base: 1.45;" in out),
        ("deterministic: two runs identical", emit(doc) == out),
    ]
    for label, ok in checks:
        print(f"  {label:<38} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    if bad:
        print("\n--- emitted ---\n" + out)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("tokens", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--selector", default=":root")
    ap.add_argument("--order", help="original CSS, to emit in its declaration order")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.tokens:
        ap.print_help()
        return 1

    try:
        doc = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
        order = None
        if args.order:
            order = DECL.findall(Path(args.order).read_text(encoding="utf-8"))
        text = emit(doc, args.selector, order)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"emit_css.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} ({text.count(chr(10))} lines)")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
