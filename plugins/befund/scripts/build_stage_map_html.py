#!/usr/bin/env python3
"""Renders stage_graph.json + file_stage_index.json as a self-contained,
canvas-based D3 viewer -- a force-directed graph (d3-force: forceSimulation
+ forceLink + forceManyBody + forceCenter), pan/zoom, search, and
level-of-detail-safe rendering, following the same vendored-inline-D3
technique as anthropics/claude-plugins-official's code-modernization
topology-viewer.html (see tools/d3-subset/).

befund-stage-map's data is a genuinely FLAT list of stages with
DIRECTED edges (wires) between them -- there is no containment hierarchy at
all, and some wires form real cycles (mutual dependency). build_data() below
returns nodes as a flat list, not nested; a prior version faked a
single-level d3.hierarchy()+d3.pack() layout under a synthetic root, which
positioned nodes by subtree-size accumulation and encoded nothing about
which stage points to which -- two nodes in the same real cycle could land
anywhere relative to each other, so edges drawn between them could visually
cross in ways unrelated to the graph's actual topology. The force layout
below instead lets connectivity itself determine position.

Reads the FULL stage_graph.json (never sampled -- rule
stage-graph-vs-stage-map-json), not the separate, deliberately-sampled
stage_map.json viewer format. A canvas renderer with proper culling doesn't
need the edge count thinned down for readability the way the old prose-only
"simple static graph render" did -- that sampling step for the HTML viewer is
no longer needed and is not reproduced here.

Cycles and god-modules are computed via lib.graph's own find_cycles/
find_god_modules -- the exact same functions befund-arch-health uses,
not reimplemented, so the viewer's highlighting can never drift from what
that skill actually reports.

Every stage carries the files the index assigns it, and the builder turns each
god-module, cycle, unconnected stage and dead-end into a finding record (claim,
evidence, suggested fix) so the page can list them beside the map. The page shell,
theme, search and finding components come from the shared report kit
(scripts/report_kit.py + assets/report-kit.{css,js}).

Usage:
    build_stage_map_html.py --stage-graph <path> --file-stage-index <path> \
        --template <path> --d3 <path> --tokens <path> [--out <path>]
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.graph import (  # noqa: E402
    GOD_MODULE_FANIN_RATIO,
    GOD_MODULE_MIN_FANIN,
    find_cycles,
    find_god_modules,
)
from report_kit import render  # noqa: E402

D3_MARKER = "<!--__D3_SUBSET__-->"
SAMPLE_FILES = 5


def _files_evidence(node):
    files = node["files"]
    if not files:
        return {"label": "Files", "detail": "the file index assigns no file to this stage"}
    shown = ", ".join(files[:SAMPLE_FILES])
    more = f" (+{len(files) - SAMPLE_FILES} more)" if len(files) > SAMPLE_FILES else ""
    return {"label": "Files", "detail": f"{len(files)} file(s), e.g. {shown}{more}"}


def build_findings(nodes, edges, cycles, god_threshold):
    """One finding record per god-module, cycle, unconnected stage and dead-end.

    Shape is the report kit's: {id, severity, claim, file, line, quote, fix,
    evidence[], tags}. `stage` (or `stages`) is extra: the page uses it to link a
    finding to its circle on the map.
    """
    by_id = {n["id"]: n for n in nodes}
    others = max(0, len(nodes) - 1)
    findings = []
    for n in sorted((n for n in nodes if n["godModuleFanIn"]), key=lambda n: -n["godModuleFanIn"]):
        importers = sorted(e["source"] for e in edges if e["target"] == n["id"])
        findings.append({
            "id": f"god-{n['id']}", "severity": "high", "stage": n["id"],
            "claim": f"{n['id']} is a god-module: {n['godModuleFanIn']} of {others} other stages import it "
                     f"(the threshold for this graph is {god_threshold:g}).",
            "fix": f"Split {n['id']} along its responsibilities so each importer depends on a narrow interface; "
                   "until then, re-test every importer together with any change to it.",
            "evidence": [
                {"label": "Imported by", "detail": ", ".join(importers)},
                _files_evidence(n),
                {"label": "On the map", "detail": n["id"], "href": f"#stage-{n['id']}"},
            ],
            "tags": {"kind": "god-module", "stage": n["id"]},
        })
    for i, members in enumerate(cycles):
        inside = [e for e in edges if e["source"] in members and e["target"] in members]
        findings.append({
            "id": f"cycle-{i + 1}", "severity": "high", "stages": members,
            "claim": f"Dependency cycle #{i + 1}: {' ⇄ '.join(members)} import each other, "
                     "so none of them can be changed or tested alone.",
            "fix": "Break it where the dependency is weakest: move what both sides need into a third stage, "
                   "or invert one direction behind an interface. Until then change all members together.",
            "evidence": [{"label": "Wire", "detail": f"{e['source']} → {e['target']}"} for e in inside]
                        + [_files_evidence(by_id[m]) | {"label": f"Files in {m}"} for m in members]
                        + [{"label": "On the map", "detail": m, "href": f"#stage-{m}"} for m in members],
            "tags": {"kind": "dependency-cycle", "stage": " ⇄ ".join(members)},
        })
    for n in nodes:
        if n["fanIn"] or n["fanOut"]:
            continue
        findings.append({
            "id": f"unconnected-{n['id']}", "severity": "medium", "stage": n["id"],
            "claim": f"{n['id']} is wired to nothing: no stage imports it and it imports no stage.",
            "fix": "Delete it if it is unused; otherwise check whether the import detection missed its wires.",
            "evidence": [_files_evidence(n), {"label": "On the map", "detail": n["id"], "href": f"#stage-{n['id']}"}],
            "tags": {"kind": "unconnected", "stage": n["id"]},
        })
    for n in nodes:
        if not n["deadEnd"] or not (n["fanIn"] or n["fanOut"]):
            continue
        findings.append({
            "id": f"dead-end-{n['id']}", "severity": "low", "stage": n["id"],
            "claim": f"{n['id']} imports nothing outward ({n['fanIn']} stage(s) import it).",
            "fix": "A leaf is expected for shared helpers; confirm it holds no logic that belongs in a named stage.",
            "evidence": [{"label": "Fan-in", "detail": str(n["fanIn"])}, _files_evidence(n),
                         {"label": "On the map", "detail": n["id"], "href": f"#stage-{n['id']}"}],
            "tags": {"kind": "dead-end", "stage": n["id"]},
        })
    return findings


def build_data(stage_graph, file_stage_index):
    stages = stage_graph.get("stages", [])
    wires = [tuple(w) for w in stage_graph.get("wires", [])]
    dead_ends = set(stage_graph.get("deadEnds", []))

    files_of = {s: [] for s in stages}
    for file, stage in (file_stage_index or {}).items():
        if stage in files_of:
            files_of[stage].append(file)
    for listed in files_of.values():
        listed.sort()
    file_count = {s: len(listed) for s, listed in files_of.items()}

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

    nodes = [
        {
            "id": s,
            "name": s,
            "fileCount": file_count.get(s, 0),
            "files": files_of.get(s, []),
            "fanIn": fan_in.get(s, 0),
            "fanOut": fan_out.get(s, 0),
            "inCycle": s in in_cycle,
            "cycleId": cycle_of.get(s),
            "godModuleFanIn": god_modules.get(s),
            "deadEnd": s in dead_ends,
        }
        for s in stages
    ]

    edges = [{"source": a, "target": b} for a, b in wires]
    sorted_cycles = [sorted(c) for c in cycles]
    god_threshold = max(GOD_MODULE_MIN_FANIN, GOD_MODULE_FANIN_RATIO * max(0, len(stages) - 1))
    isolated = [n for n in nodes if not n["fanIn"] and not n["fanOut"]]
    return {
        "nodes": nodes,
        "edges": edges,
        "cycles": sorted_cycles,
        "godThreshold": god_threshold,
        "findings": build_findings(nodes, edges, sorted_cycles, god_threshold),
        "stats": {
            "unconnectedCount": len(isolated),
            "deadEndCount": len(dead_ends),
            "stageCount": len(stages),
            "edgeCount": len(wires),
            "cycleCount": len(cycles),
            "godModuleCount": len(god_modules),
        },
    }


def render_html(template_path, d3_path, tokens_path, data):
    template_path = Path(template_path)
    tpl = template_path.read_text(encoding="utf-8")
    if D3_MARKER not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(D3_MARKER, Path(d3_path).read_text(encoding="utf-8"))
    # render() inlines the tokens, the kit and the data island (< > & escaped: barrier one of S3).
    return render(tpl, template_path.parent, data, tokens=Path(tokens_path))


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
