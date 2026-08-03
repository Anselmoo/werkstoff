#!/usr/bin/env python3
"""Renders a cupertino-review run's fixed 8-technique pipeline (longevity and
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
    build_review_flow_html.py <cupertino_dir> --template <path> --d3 <path> --tokens <path> [--out <path>]
"""
import argparse
import json
import os
import sys

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


def _read_flag(flags_dir, flag_name):
    path = os.path.join(flags_dir, flag_name)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Not every stage's reported result is guaranteed strict JSON --
        # keep the raw text rather than silently dropping the stage's content.
        return {"raw": raw}


def build_flow(cupertino_dir):
    flags_dir = os.path.join(cupertino_dir, "flags")
    stages = []
    for stage_id, flag_name, label, lane in STAGES:
        content = _read_flag(flags_dir, flag_name)
        if content is None:
            status = "not-run"
        elif isinstance(content, dict) and content.get("skipped") is True:
            status = "skipped"
        else:
            status = "ran"
        stages.append({
            "id": stage_id,
            "label": label,
            "lane": lane,
            "status": status,
            "content": content,
        })
    return {"stages": stages}


def render_html(template_path, d3_path, tokens_path, flow):
    tpl = open(template_path, encoding="utf-8").read()

    d3_snippet = open(d3_path, encoding="utf-8").read()
    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(d3_marker, d3_snippet)

    tokens_css = open(tokens_path, encoding="utf-8").read()
    tokens_marker = "/*__DESIGN_TOKENS__*/"
    if tokens_marker not in tpl:
        raise ValueError(f"design-tokens injection marker not found in {template_path}")
    tpl = tpl.replace(tokens_marker, tokens_css)

    marker = "/*__FLOW_DATA__*/ null"
    if marker not in tpl:
        raise ValueError(f"injection marker not found in {template_path}")
    data = json.dumps(flow)
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(marker, "/*__FLOW_DATA__*/ " + data)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cupertino_dir", help="the .cupertino directory for this repo")
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", required=True, help="path to the vendored tokens.css snippet")
    parser.add_argument("--out", help="defaults to <cupertino_dir>/CUPERTINO_REVIEW_FLOW.html")
    args = parser.parse_args(argv)

    flow = build_flow(args.cupertino_dir)

    out_path = args.out or os.path.join(args.cupertino_dir, "CUPERTINO_REVIEW_FLOW.html")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(args.template, args.d3, args.tokens, flow))

    print(json.dumps({"flowPath": out_path}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
