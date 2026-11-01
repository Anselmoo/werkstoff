#!/usr/bin/env python3
"""Inline the werkstoff report kit into a viewer template.

usage: report_kit.py [-h] --template FILE --data FILE [--out FILE] [--selftest]

Source of truth for every plugin's vendored scripts/report_kit.py (.rrt.toml
artifact_targets). A builder imports render() rather than re-implementing the
three injections every viewer needs:

  <!--__DESIGN_TOKENS__-->   -> <style> assets/tokens.css </style>
  <!--__REPORT_KIT__-->      -> <style> assets/report-kit.css </style>
                                <script> assets/report-kit.js </script>
  @@DATA@@                   -> the report as JSON, with < > & escaped, inside
                                <script type="application/json" id="report-data">

The escaping is the first of the two safety barriers report-viewer-standard S3
requires; the kit's textContent-only DOM helper is the second. A marker that is
absent from the template is an error, never a silent skip: a viewer that lost
its kit marker would otherwise render unstyled and nobody would notice.

Exit: 0 written, 1 selftest failed, 2 an input or marker is missing.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
KIT_MARKER = "<!--__REPORT_KIT__-->"
DATA_MARKER = "@@DATA@@"


class KitError(Exception):
    """A template or asset the render needs is missing."""


def escape_json(report: object) -> str:
    payload = json.dumps(report, indent=1, ensure_ascii=False)
    return payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _inert(text: str, tag: str) -> str:
    """Stop inlined CSS/JS from closing its own element: `</style` becomes `<\\/style`.

    In CSS and JS alike `\\/` reads as `/`, so the meaning is unchanged; only the
    HTML tokenizer, which would end the element at the first `</style`, is defused.
    A token value or comment that happened to contain the tag would otherwise end
    the stylesheet and spill the rest into the page as text.
    """
    return re.sub(rf"</({tag})", r"<\\/\1", text, flags=re.IGNORECASE)


def render(template: str, assets: Path, report: object, tokens: Path | None = None) -> str:
    """Return the template with tokens, kit and data inlined.

    tokens defaults to assets/tokens.css; only the kit's own example passes it.
    """
    for marker in (TOKENS_MARKER, KIT_MARKER, DATA_MARKER):
        if marker not in template:
            raise KitError(f"template has no {marker} marker")
    need = {name: assets / name for name in ("report-kit.css", "report-kit.js")}
    need["tokens.css"] = tokens or assets / "tokens.css"
    missing = [str(p) for p in need.values() if not p.is_file()]
    if missing:
        raise KitError("missing vendored asset(s): " + ", ".join(missing))
    tokens = need["tokens.css"].read_text(encoding="utf-8")
    css = need["report-kit.css"].read_text(encoding="utf-8")
    js = need["report-kit.js"].read_text(encoding="utf-8")
    out = template.replace(TOKENS_MARKER, "<style>\n" + _inert(tokens, "style") + "\n</style>", 1)
    out = out.replace(KIT_MARKER, "<style>\n" + _inert(css, "style") + "\n</style>\n<script>\n"
                      + _inert(js, "script") + "\n</script>", 1)
    return out.replace(DATA_MARKER, escape_json(report), 1)


def selftest() -> int:
    fails: list[str] = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    tpl = (f"<head>{TOKENS_MARKER}{KIT_MARKER}</head><body>"
           f'<script type="application/json" id="report-data">{DATA_MARKER}</script></body>')
    with tempfile.TemporaryDirectory() as td:
        assets = Path(td)
        for name, body in (("tokens.css", ":root{--bg:#000}"), ("report-kit.css", ".rk{}"), ("report-kit.js", "const RK={};")):
            (assets / name).write_text(body, encoding="utf-8")
        html = render(tpl, assets, {"claim": "</script><script>alert(1)</script> & co"})
        ok("tokens inlined", "--bg:#000" in html and TOKENS_MARKER not in html)
        ok("kit css and js inlined", ".rk{}" in html and "const RK={};" in html and KIT_MARKER not in html)
        ok("data inlined", DATA_MARKER not in html and "\\u003c/script\\u003e" in html)
        ok("no raw closing script tag from data", html.count("</script>") == 2)  # kit js + the island; none from data
        ok("ampersand escaped", "\\u0026 co" in html)
        (assets / "tokens.css").write_text(":root{--x:1} /* </style><b>spill</b> */", encoding="utf-8")
        spill = render(tpl, assets, {})
        ok("a </style> inside inlined css cannot close the element", "</style><b>" not in spill and "<\\/style>" in spill)
        try:
            render(tpl.replace(KIT_MARKER, ""), assets, {})
            ok("missing kit marker is an error", False)
        except KitError:
            ok("missing kit marker is an error", True)
        (assets / "report-kit.js").unlink()
        try:
            render(tpl, assets, {})
            ok("missing vendored asset is an error", False)
        except KitError:
            ok("missing vendored asset is an error", True)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("selftest passed")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="report_kit.py", description="Inline tokens, report kit and data into a viewer template.",
                                     epilog="exit 0 written, 1 selftest failed, 2 an input or marker is missing")
    parser.add_argument("--template")
    parser.add_argument("--data")
    parser.add_argument("--assets", help="directory holding tokens.css, report-kit.css, report-kit.js (default: the template's)")
    parser.add_argument("--tokens", help="tokens.css to inline (default: <assets>/tokens.css)")
    parser.add_argument("--out")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.template or not args.data:
        parser.error("--template and --data are required unless --selftest is given")
    template = Path(args.template)
    try:
        html = render(template.read_text(encoding="utf-8"), Path(args.assets) if args.assets else template.parent,
                      json.loads(Path(args.data).read_text(encoding="utf-8")),
                      Path(args.tokens) if args.tokens else None)
    except (OSError, ValueError, KitError) as err:
        print(f"report_kit: {err}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else template.with_name("run-report.html")
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
