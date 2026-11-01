#!/usr/bin/env python3
"""Renders a cupertino-review run's fixed nine-stage pipeline (longevity and
integrate as a real parallel fork) as a self-contained HTML flow diagram.

MUST be called before cupertino-review's own end-of-run flag cleanup --
every stage's content lives at .cupertino/flags/<stage>-output (a plain text
file holding that stage's full reported JSON, per cupertino-review's own
"Thread each stage's real content into the next dispatch" step), and those
flags are deliberately removed at the end of every run so a stale flag can
never leak into an unrelated future review. This script only reads them; it
never writes to flags/ and never clears anything itself.

A flag can be in one of three states, not two -- "absent" is ambiguous
between "pipeline hasn't reached this stage yet" and "explicitly skipped",
so cupertino-review's SKILL.md persists an explicit {"skipped": true, ...}
marker for prototype/elevate when they don't run, instead of just omitting
the flag. This script trusts that marker rather than treating absence and
skip as the same thing.

Usage:
    build_review_flow_html.py <cupertino_dir> --template <path> --d3 <path> [--tokens <path>] [--out <path>]

Rendered through the vendored report kit (scripts/report_kit.py). --tokens is
still accepted so existing callers keep working; when given it replaces the
kit's default assets/tokens.css.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from report_kit import render  # noqa: E402

# (stage_id, flag_name, display_label, lane) -- lane 0 is the main sequence;
# longevity/integrate share lane 1/2 at the same x-position, a real fork.
STAGES = [
    ("backwards", "backwards-done", "cupertino-backwards", 0),
    ("focus", "focus-output", "cupertino-focus", 0),
    ("longevity", "longevity-output", "cupertino-longevity", 1),
    ("integrate", "integrate-output", "cupertino-integrate", 2),
    ("council", "council-output", "cupertino-council", 0),
    ("prototype", "prototype-output", "cupertino-prototype", 0),
    ("elevate", "elevate-output", "cupertino-elevate", 0),
    ("unbox", "unbox-output", "cupertino-unbox", 0),
    ("reveal", "reveal-output", "cupertino-reveal", 0),
]


def _read_flag(flags_dir: Path, flag_name: str):
    path = flags_dir / flag_name
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Not every stage's reported result is guaranteed strict JSON --
        # keep the raw text rather than silently dropping the stage's content.
        return {"raw": raw}


def build_flow(cupertino_dir) -> dict:
    flags_dir = Path(cupertino_dir) / "flags"
    stages = []
    for stage_id, flag_name, label, lane in STAGES:
        content = _read_flag(flags_dir, flag_name)
        if content is None:
            status = "not-run"
        elif isinstance(content, dict) and content.get("skipped") is True:
            status = "skipped"
        else:
            status = "ran"
        stages.append({"id": stage_id, "label": label, "lane": lane, "status": status, "content": content})
    # "source" is provenance for the viewer's subtitle, kept repo-shaped (the
    # last two path parts) so a screenshot rendered from a temp dir leaks no
    # absolute path. Counts are deliberately not here: the viewer's glance tiles
    # own them (report-viewer-standard R2).
    parts = Path(*flags_dir.parts).parts
    source = "/".join(parts[-2:]) if len(parts) >= 2 else str(flags_dir)
    return {"source": source, "stages": stages}


def render_html(template_path, d3_path, tokens_path, flow: dict) -> str:
    template = Path(template_path)
    tpl = template.read_text(encoding="utf-8")
    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(d3_marker, Path(d3_path).read_text(encoding="utf-8"))
    return render(tpl, template.parent, flow, Path(tokens_path) if tokens_path else None)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cupertino_dir", help="the .cupertino directory for this repo")
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", help="optional tokens.css override; the kit's assets/tokens.css is used otherwise")
    parser.add_argument("--out", help="defaults to <cupertino_dir>/CUPERTINO_REVIEW_FLOW.html")
    args = parser.parse_args(argv)

    flow = build_flow(args.cupertino_dir)
    out_path = Path(args.out) if args.out else Path(args.cupertino_dir) / "CUPERTINO_REVIEW_FLOW.html"
    out_path.write_text(render_html(args.template, args.d3, args.tokens, flow), encoding="utf-8")
    print(json.dumps({"flowPath": str(out_path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
