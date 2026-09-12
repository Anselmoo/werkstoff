#!/usr/bin/env python3
"""Prove a retrofit changed nothing — on three arms, because one is not enough.

Why three
---------
**Arm 1, textual.** Every declaration in the source reappears with an identical value.
Catches a dropped, added or altered token.

**Arm 2, structural.** Every `var(--x)` in the source round-trips as a DTCG *reference*
and emits as `var()` again. Arm 1 does catch the crude flattening — rewriting
`--accent: var(--silica)` as `--accent: #348ad9` is a textual change — and the selftest
asserts that, so this arm is not justified by the case people assume.

What arm 2 catches, and arms 1 and 3 cannot, is a retrofit that keeps the *output* right
and the *source of truth* wrong: storing the literal string `"var(--silica)"` as a token
value instead of the DTCG reference `{color.silica}`. The emitted CSS is byte-identical,
the render is byte-identical, and the token file now holds an opaque string with no edge
in it. The system has forgotten that accent IS silica, which is the answer to "what
breaks if I change silica?" — and every non-CSS formatter emits that string verbatim into
a target where `var()` means nothing.

**Arm 3, visual.** Render a fixture exercising every token against source and
regenerated, screenshot both at width 1600, compare. The equivalence proof the brief asks
for, and the only arm that sees cascade effects.

A retrofit passing 1 and 3 and failing 2 is a silent structural loss — the tokens render
correctly and describe nothing. That is the whole reason this file has more than one
function.

Usage:
    prove_retrofit.py <source.css> <tokens.json> [--chrome PATH] [--workdir DIR]
    prove_retrofit.py --selftest       # the arms must discriminate, not merely pass
Exit: 0 all arms pass, 1 any arm fails, 2 the inputs could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emit_css  # noqa: E402
import retrofit_css  # noqa: E402

DECL = re.compile(r"^[ \t]*(--[\w-]+)[ \t]*:[ \t]*([^;]+);", re.M)
VAR = re.compile(r"^var\(\s*(--[\w-]+)\s*\)$")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def decls(css: str) -> dict[str, str]:
    return {n: v.strip() for n, v in DECL.findall(css)}


def arm1_textual(src: str, regen: str) -> tuple[bool, list[str]]:
    a, b = decls(src), decls(regen)
    problems = [f"missing from regenerated: {n}" for n in sorted(set(a) - set(b))]
    problems += [f"invented by regenerated: {n}" for n in sorted(set(b) - set(a))]
    problems += [
        f"{n}: {a[n]!r} -> {b[n]!r}" for n in sorted(set(a) & set(b)) if a[n] != b[n]
    ]
    return (not problems), problems


def arm2_aliases(src: str, doc: dict, regen: str) -> tuple[bool, list[str]]:
    """Aliases must survive as references. Flattening is invisible to the other arms."""
    source_aliases = {n: m.group(1) for n, v in decls(src).items() if (m := VAR.match(v))}
    regen_decls = decls(regen)
    by_css = {
        emit_css.css_name(p, t): t for p, t in emit_css.walk(doc)
    }
    problems: list[str] = []
    for name, target in source_aliases.items():
        token = by_css.get(name)
        if token is None:
            problems.append(f"{name}: aliased {target} in source, absent from tokens")
            continue
        value = token.get("$value")
        if not (isinstance(value, str) and value.startswith("{")):
            problems.append(
                f"{name}: FLATTENED — source aliased {target}, tokens hold a literal "
                f"{value!r}. Renders identically; the edge is gone."
            )
            continue
        emitted = regen_decls.get(name, "")
        if not emitted.startswith("var("):
            problems.append(f"{name}: reference in tokens but emitted as {emitted!r}")
    return (not problems), problems, len(source_aliases)  # type: ignore[return-value]


FIXTURE = """<!doctype html><meta charset="utf-8"><style>
__TOKENS__
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-sans);
  font-size:var(--font-size-base);line-height:var(--line-height-base)}
.g{display:grid;grid-template-columns:repeat(5,1fr);gap:var(--space-2);padding:var(--space-4)}
.c{height:64px;border-radius:var(--radius-panel);border:1px solid var(--border)}
.p{background:var(--panel);padding:var(--space-3);border-radius:var(--radius-panel);
  margin:var(--space-3) var(--space-4);border:1px solid var(--border)}
.t{color:var(--muted)} .a{color:var(--accent)} .b{color:var(--accent-2)}
.h{height:var(--header-h);background:var(--panel-2);border-bottom:1px solid var(--border)}
.s{border-radius:var(--radius-sm);background:var(--smoke);height:var(--space-5);
  margin:var(--space-1)}
</style><div class="h"></div>
<div class="g">__CHIPS__</div>
<div class="p"><span class="t">muted</span> <span class="a">accent</span>
<span class="b">accent-2</span> <b>text</b></div>
<div class="p"><div class="s"></div><div class="s"></div></div>
"""


def build_fixture(css: str, token_names: list[str]) -> str:
    chips = "".join(
        f'<div class="c" style="background:var({n})"></div>'
        for n in token_names
        if "space" not in n and "radius" not in n and "font" not in n
        and "line-height" not in n and "transition" not in n and "header" not in n
    )
    return FIXTURE.replace("__TOKENS__", css).replace("__CHIPS__", chips)


def png_size(path: Path) -> tuple[int, int]:
    d = path.read_bytes()
    return struct.unpack(">II", d[16:24])


def arm3_visual(src: str, regen: str, workdir: Path, chrome: str) -> tuple[bool, list[str]]:
    if not Path(chrome).exists():
        return True, [f"SKIPPED — no Chromium at {chrome}; arms 1 and 2 still ran"]
    names = list(decls(src))
    shots = []
    for label, css in (("before", src), ("after", regen)):
        html = workdir / f"{label}.html"
        html.write_text(build_fixture(css, names), encoding="utf-8")
        shot = workdir / f"{label}.png"
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
             "--virtual-time-budget=3000", "--window-size=1600,900",
             f"--screenshot={shot}", f"file://{html}"],
            capture_output=True, check=False,
        )
        if not shot.exists():
            return False, [f"render failed for {label}"]
        shots.append(shot)

    a, b = shots[0].read_bytes(), shots[1].read_bytes()

    # An instrument check, not a formality: TWO BLANK PAGES ARE ALSO BYTE-IDENTICAL.
    # Render a control with no tokens at all; if the real fixture is not substantially
    # heavier, it drew nothing and "zero visual diff" would be a vacuous pass.
    blank = workdir / "control.html"
    blank.write_text(FIXTURE.replace("__TOKENS__", "").replace("__CHIPS__", ""), encoding="utf-8")
    ctrl = workdir / "control.png"
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
         "--virtual-time-budget=3000", "--window-size=1600,900",
         f"--screenshot={ctrl}", f"file://{blank}"],
        capture_output=True, check=False,
    )
    # Categorical, not a threshold: the tokenised render must DIFFER from the
    # untokenised one. A byte-size ratio would be a magic number tuned until it passed;
    # "the tokens changed the picture" is the claim itself.
    if ctrl.exists() and a == ctrl.read_bytes():
        return False, [
            "the fixture renders identically with and without the tokens, so it exercises "
            "none of them. Two blank pages also compare equal — this would have been a "
            "vacuous pass. Fix the fixture, not the tokens."
        ]

    if png_size(shots[0]) != png_size(shots[1]):
        return False, [f"dimensions differ: {png_size(shots[0])} vs {png_size(shots[1])}"]
    if a != b:
        return False, [
            f"pixels differ ({len(a):,} vs {len(b):,} bytes). Compare {shots[0]} and {shots[1]}."
        ]
    return True, [f"byte-identical render, {png_size(shots[0])[0]}x{png_size(shots[0])[1]}"]


def prove(src_path: Path, tokens_path: Path, workdir: Path, chrome: str) -> int:
    src = src_path.read_text(encoding="utf-8")
    doc = json.loads(tokens_path.read_text(encoding="utf-8"))
    regen = emit_css.emit(doc, order=list(decls(src)))

    print(f"source: {src_path}  ({len(decls(src))} declarations)")
    failed = 0

    ok, problems = arm1_textual(src, regen)
    print(f"\narm 1 — textual      {'PASS' if ok else 'FAIL'}")
    for p in problems[:12]:
        print(f"    {p}")
    failed += 0 if ok else 1

    ok, problems, n_alias = arm2_aliases(src, doc, regen)  # type: ignore[misc]
    print(f"arm 2 — alias structure  {'PASS' if ok else 'FAIL'}  ({n_alias} alias(es) in source)")
    for p in problems[:12]:
        print(f"    {p}")
    failed += 0 if ok else 1

    ok, notes = arm3_visual(src, regen, workdir, chrome)
    print(f"arm 3 — visual       {'PASS' if ok else 'FAIL'}")
    for n in notes:
        print(f"    {n}")
    failed += 0 if ok else 1

    print(f"\n{'ZERO VISUAL DIFF, STRUCTURE PRESERVED' if not failed else 'RETROFIT NOT PROVEN'}")
    return 1 if failed else 0


def selftest() -> int:
    """The arms must DISCRIMINATE. A prover that only ever passes proves nothing."""
    src = retrofit_css.SAMPLE
    doc, _ = retrofit_css.retrofit(src)
    regen = emit_css.emit(doc, order=list(decls(src)))
    checks: list[tuple[str, bool]] = []

    ok1, _ = arm1_textual(src, regen)
    ok2, _, _ = arm2_aliases(src, doc, regen)  # type: ignore[misc]
    checks.append(("honest retrofit passes arm 1", ok1))
    checks.append(("honest retrofit passes arm 2", ok2))

    # Sabotage A -- the crude flattening. Arm 1 DOES catch this one; asserting so keeps
    # arm 2 from being justified by a case that does not need it.
    crude = json.loads(json.dumps(doc))
    crude["color"]["accent"] = {
        "$type": "color",
        "$value": crude["color"]["ink"]["$value"],
        "$extensions": doc["color"]["accent"]["$extensions"],
    }
    crude_css = emit_css.emit(crude, order=list(decls(src)))
    ca1, _ = arm1_textual(src, crude_css)
    ca2, _, _ = arm2_aliases(src, crude, crude_css)  # type: ignore[misc]
    checks.append(("resolved-to-hex alias FAILS arm 1", not ca1))
    checks.append(("resolved-to-hex alias FAILS arm 2 too", not ca2))

    # Sabotage B -- the case arm 2 alone can see: output stays right, source of truth
    # goes wrong. A literal "var(--ink)" string instead of a DTCG reference.
    sneaky = json.loads(json.dumps(doc))
    sneaky["color"]["accent"] = {
        "$type": "color",
        "$value": "var(--ink)",
        "$extensions": doc["color"]["accent"]["$extensions"],
    }
    sneaky_css = emit_css.emit(sneaky, order=list(decls(src)))
    s1, _ = arm1_textual(src, sneaky_css)
    s2, probs2, _ = arm2_aliases(src, sneaky, sneaky_css)  # type: ignore[misc]
    checks.append(("opaque-string alias PASSES arm 1 (arm 2's whole reason)", s1))
    checks.append(("opaque-string alias FAILS arm 2", not s2))
    checks.append(("arm 2 names it FLATTENED", any("FLATTENED" in p for p in probs2)))

    # Sabotage C: change a value. Arm 1 must catch it.
    changed = json.loads(json.dumps(doc))
    changed["color"]["ink"]["$value"]["hex"] = "#ffffff"
    bad_css = emit_css.emit(changed, order=list(decls(src)))
    b1, _ = arm1_textual(src, bad_css)
    checks.append(("changed value FAILS arm 1", not b1))

    # Sabotage D: drop a token. Arm 1 must catch it.
    dropped = json.loads(json.dumps(doc))
    del dropped["space"]["1"]
    drop_css = emit_css.emit(dropped, order=list(decls(src)))
    c1, _ = arm1_textual(src, drop_css)
    checks.append(("dropped token FAILS arm 1", not c1))

    for label, ok in checks:
        print(f"  {label:<52} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("css", nargs="?")
    ap.add_argument("tokens", nargs="?")
    ap.add_argument("--chrome", default=CHROME)
    ap.add_argument("--workdir")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.css or not args.tokens:
        ap.print_help()
        return 2

    try:
        if args.workdir:
            work = Path(args.workdir)
            work.mkdir(parents=True, exist_ok=True)
            return prove(Path(args.css), Path(args.tokens), work, args.chrome)
        with tempfile.TemporaryDirectory() as tmp:
            return prove(Path(args.css), Path(args.tokens), Path(tmp), args.chrome)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"prove_retrofit.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
