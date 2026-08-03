#!/usr/bin/env python3
"""Renders stage_graph.json + file_stage_index.json as a self-contained,
canvas-based D3 viewer -- circle-pack layout (stage size ~ file count),
pan/zoom, search, and level-of-detail-safe rendering, following the same
techniques as anthropics/claude-plugins-official's code-modernization
topology-viewer.html (vendored inline D3 subset, see tools/d3-subset/).

Unlike that reference's system/domain/module hierarchy, self-assess-stage-map
clusters files by the *shallowest importable package boundary* -- a genuinely
flat list of stages, never nested. Faking a multi-level hierarchy here would
misrepresent the actual data; this renders a single-level pack (one synthetic
root, stages as direct children) instead.

Reads the FULL stage_graph.json (never sampled -- rule
stage-graph-vs-stage-map-json), not the separate, deliberately-sampled
stage_map.json viewer format. A canvas renderer with proper culling doesn't
need the edge count thinned down for readability the way the old prose-only
"simple static graph render" did -- that sampling step for the HTML viewer is
no longer needed and is not reproduced here.

Cycles and god-modules are computed via lib.graph's own find_cycles/
find_god_modules -- the exact same functions self-assess-arch-health uses,
not reimplemented, so the viewer's highlighting can never drift from what
that skill actually reports.

Usage:
    build_stage_map_html.py --stage-graph <path> --file-stage-index <path> \
        --template <path> --d3 <path> --tokens <path> [--out <path>]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.graph import find_cycles, find_god_modules  # noqa: E402


def build_data(stage_graph, file_stage_index):
    stages = stage_graph.get("stages", [])
    wires = [tuple(w) for w in stage_graph.get("wires", [])]
    dead_ends = set(stage_graph.get("deadEnds", []))

    file_count = {s: 0 for s in stages}
    for _file, stage in (file_stage_index or {}).items():
        if stage in file_count:
            file_count[stage] += 1

    cycles = find_cycles(stages, wires)
    in_cycle = {s for comp in cycles for s in comp}
    cycle_of = {}
    for i, comp in enumerate(cycles):
        for s in comp:
            cycle_of[s] = i

    god_modules = dict(find_god_modules(stages, wires))

    fan_in = {s: 0 for s in stages}
    fan_out = {s: 0 for s in stages}
    for a, b in wires:
        if a in fan_out:
            fan_out[a] += 1
        if b in fan_in:
            fan_in[b] += 1

    root = {
        "id": "__root__",
        "name": "repository",
        "kind": "root",
        "children": [
            {
                "id": s,
                "name": s,
                "kind": "stage",
                "fileCount": file_count.get(s, 0),
                "fanIn": fan_in.get(s, 0),
                "fanOut": fan_out.get(s, 0),
                "inCycle": s in in_cycle,
                "cycleId": cycle_of.get(s),
                "godModuleFanIn": god_modules.get(s),
                "deadEnd": s in dead_ends,
            }
            for s in stages
        ],
    }

    return {
        "root": root,
        "edges": [{"source": a, "target": b} for a, b in wires],
        "cycles": [sorted(c) for c in cycles],
        "stats": {
            "stageCount": len(stages),
            "edgeCount": len(wires),
            "cycleCount": len(cycles),
            "godModuleCount": len(god_modules),
        },
    }


def render_html(template_path, d3_path, tokens_path, data):
    tpl = open(template_path, encoding="utf-8").read()
    d3_snippet = open(d3_path, encoding="utf-8").read()
    tokens_css = open(tokens_path, encoding="utf-8").read()

    tokens_marker = "<!--__DESIGN_TOKENS__-->"
    if tokens_marker not in tpl:
        raise ValueError(f"design-tokens injection marker not found in {template_path}")
    tpl = tpl.replace(tokens_marker, f"<style>\n{tokens_css}\n</style>")

    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(d3_marker, d3_snippet)

    data_marker = "/*__STAGE_MAP_DATA__*/ null"
    if data_marker not in tpl:
        raise ValueError(f"data injection marker not found in {template_path}")
    payload = json.dumps(data)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(data_marker, "/*__STAGE_MAP_DATA__*/ " + payload)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-graph", required=True)
    parser.add_argument("--file-stage-index", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", required=True, help="path to the vendored design-tokens/tokens.css file")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    with open(args.stage_graph, encoding="utf-8") as fh:
        stage_graph = json.load(fh)
    with open(args.file_stage_index, encoding="utf-8") as fh:
        file_stage_index = json.load(fh)

    data = build_data(stage_graph, file_stage_index)
    html = render_html(args.template, args.d3, args.tokens, data)

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(json.dumps({"stageMapPath": args.out, "stats": data["stats"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
