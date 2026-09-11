#!/usr/bin/env python3
"""Build the self-contained derivation-health report from a decode run.

Design note — the fixture cannot state a contrast ratio
-------------------------------------------------------
Input colour pairs carry `fg` and `bg` only. Every ratio and every pass/fail flag in the
output is COMPUTED here by contrast.py, and any ratio present in the input is ignored and
reported as an error. That is not defensive tidiness: writing this builder the obvious
way (trust the input) immediately produced a demo file claiming 2.98:1 for a pair that is
actually 2.89:1 — the exact "asserted rather than computed" defect the report exists to
catch, shipped inside the report's own demo data.

A number a human typed is a claim. A number this script derived is a measurement.

Usage:
    build_derivation_html.py --data scripts/fixtures/derivation-demo.json \\
                             --out /tmp/derivation.html
    build_derivation_html.py --selftest
Exit: 0 built, 1 the input was unusable or carried a pre-stated ratio.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contrast  # noqa: E402  (same directory, deliberate)

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "derivation-viewer.html"
TOKENS = HERE.parent / "assets" / "tokens.css"
TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
PAYLOAD_OPEN = '<script type="application/json" id="payload">'
PAYLOAD_CLOSE = "</script>"

REQUIRED = ("scope", "verdict", "references", "gradeCOnly", "contrast")


def build_payload(data: dict) -> dict:
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError(f"input is missing {', '.join(missing)}")

    pairs = []
    for entry in data["contrast"]:
        for stated in ("ratio", "passesAA", "passesAALarge"):
            if stated in entry:
                raise ValueError(
                    f"contrast entry for role {entry.get('role')!r} states {stated!r}. "
                    "Contrast is computed here, never supplied — remove it from the input."
                )
        computed = contrast.verdict(contrast.ratio(entry["fg"], entry["bg"]))
        pairs.append({
            "role": entry["role"],
            "fg": entry["fg"],
            "bg": entry["bg"],
            "ratio": computed["ratio"],
            "passesAA": computed["passesAA"],
            "passesAALarge": computed["passesAALarge"],
        })

    return {
        "scope": data["scope"],
        "verdict": data["verdict"],
        "references": data["references"],
        "gradeCOnly": data["gradeCOnly"],
        "contrast": pairs,
    }


def render(payload: dict) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    if TOKENS_MARKER not in template:
        raise ValueError(f"template has no {TOKENS_MARKER}")

    out = template.replace(TOKENS_MARKER, TOKENS.read_text(encoding="utf-8"), 1)

    # S3, barrier one: escape the delimiters that could break out of the <script> block.
    # The template's own reader is barrier two -- it renders via textContent, never
    # innerHTML. Two independent barriers, because either alone has failed somewhere.
    blob = json.dumps(payload, indent=2, ensure_ascii=False)
    blob = blob.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    start = out.index(PAYLOAD_OPEN) + len(PAYLOAD_OPEN)
    end = out.index(PAYLOAD_CLOSE, start)
    return out[:start] + blob + out[end:]


def selftest() -> int:
    """The builder asserts itself: it must compute, and it must refuse a stated ratio."""
    failures = 0

    sample = {
        "scope": "s", "verdict": "v", "references": [], "gradeCOnly": [],
        "contrast": [{"role": "dominant-action", "fg": "#FA2E1A", "bg": "#FFFFFF"}],
    }
    got = build_payload(sample)["contrast"][0]
    if got["ratio"] != 3.84 or got["passesAA"] or not got["passesAALarge"]:
        print(f"  computes the ratio            FAIL ({got})")
        failures += 1
    else:
        print("  computes the ratio            ok")

    lying = json.loads(json.dumps(sample))
    lying["contrast"][0]["ratio"] = 9.99
    try:
        build_payload(lying)
        print("  refuses a pre-stated ratio    FAIL (accepted 9.99)")
        failures += 1
    except ValueError:
        print("  refuses a pre-stated ratio    ok")

    for key in REQUIRED:
        broken = json.loads(json.dumps(sample))
        broken.pop(key)
        try:
            build_payload(broken)
            print(f"  refuses input missing {key:<8} FAIL")
            failures += 1
        except ValueError:
            pass
    print("  refuses incomplete input      ok")

    # The escaping barrier must actually escape.
    nasty = json.loads(json.dumps(sample))
    nasty["verdict"] = "</script><script>alert(1)</script>"
    page = render(build_payload(nasty))
    marker = page[page.index(PAYLOAD_OPEN):]
    if "</script><script>alert(1)" in marker.split("</script>")[0]:
        print("  escapes script delimiters     FAIL")
        failures += 1
    else:
        print("  escapes script delimiters     ok")

    print(f"\n{failures} failure(s)")
    print("RED" if failures else "GREEN")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--data", help="decode-run JSON")
    ap.add_argument("--out", help="output HTML path")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.data or not args.out:
        ap.print_help()
        return 1

    try:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
        page = render(build_payload(data))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"build_derivation_html.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    Path(args.out).write_text(page, encoding="utf-8")
    print(f"wrote {args.out} ({len(page):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
