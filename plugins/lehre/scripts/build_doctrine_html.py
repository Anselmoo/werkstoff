#!/usr/bin/env python3
"""Render .lehre/ruleset.json as a self-contained doctrine map.

    build_doctrine_html.py <repo_root> --template <path> --tokens <path>
                           [--out <path>] [--json-only]

WHAT IT SHOWS, AND WHY THIS SHAPE. The question this plugin exists to answer is
"of every rule declared, how many actually deny a write". That is a FLOW
question, not a categorical one: each rule travels
provenance -> severity -> check kind -> enforcement outcome, and the interesting
thing is where the flow narrows. So the primary view is a Sankey with a funnel
strip above it, and the ribbons are coloured by where each rule ENDS rather than
where it starts -- a blocking rule that drains into "sweep + CI only" is the
exact failure mode the whole plugin is built around, and a source-coloured
Sankey would hide it.

The one precondition a Sankey needs is satisfied here by construction: every
rule passes through exactly ONE node per stage, so all four stages sum to the
same total and a single global scale makes band widths comparable across stages
as well as within one.

NO D3. The marketplace's vendored d3 subset (tools/d3-subset/) carries
d3-hierarchy, d3-zoom, d3-selection, d3-interpolate, d3-ease, d3-force and
d3-scale -- not d3-sankey. So the layout is hand-written in the template, and
this plugin deliberately does NOT vendor the 125 KB bundle it would not call.
It does vendor tools/design-tokens/tokens.css, because a viewer that invented
its own palette would break the one thing all eight viewers do share.

LINKS ARE KEYED BY FULL PATH, not by adjacent pair. Rules are grouped by their
complete (provenance, severity, kind, outcome) tuple and each group emits three
segments. Grouping by adjacent pair instead would make a segment's membership
ambiguous, and clicking a node would light ribbons whose rules only partly pass
through it -- a filter that is subtly wrong is worse than none.

Exits 2 with a message and writes nothing if the ruleset is missing or invalid.
Never fabricates a doctrine for a repo that has not declared one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lehre_core as core  # noqa: E402

EXIT_OK, EXIT_UNUSABLE = 0, 2

#: Semantic order, not frequency order. A funnel reads top-to-bottom, so the
#: strongest form of each stage is listed first and the flow visibly drains
#: downward. Frequency order would reshuffle the picture on every edit.
STAGE_ORDER = {
    "provenance": ["evidence-backed", "intent-derived", "scaffolded-default"],
    "severity": ["blocking", "advisory"],
    "kind": ["forbid-path", "require-location", "python-import", "python-construct", "linter",
             "judgement"],
    "outcome": ["denied at write time", "sweep + CI only", "advisory only", "judgement only"],
}
STAGE_LABELS = [
    ("provenance", "provenance"),
    ("severity", "severity"),
    ("kind", "check kind"),
    ("outcome", "enforcement"),
]
KIND_NOTE = {"linter": "gauge-tier", "judgement": "no machine check"}


def outcome_for(rule: dict) -> str:
    """The single fact the whole report exists to make visible.

    A blocking rule whose predicate is linter-kind is real and fails a sweep and
    CI -- but it is NOT a write-time denial, because the content being written is
    not on disk when the hook runs. Collapsing that into "blocking" is how a rule
    everybody believes blocks turns out never to fire.
    """
    if rule["enforcement"] == "judgement":
        # Kept distinct from plain "advisory only": an advisory rule with a machine
        # predicate IS checked every sweep, whereas a judgement rule is checked only
        # when someone dispatches violation-auditor. Merging them would hide which
        # advisory findings the script actually produced.
        return "judgement only"
    if rule["severity"] == "advisory":
        return "advisory only"
    return "denied at write time" if rule["enforcement"] == "hook" else "sweep + CI only"


def build(root: str, ruleset_path: str) -> dict:
    data = core.load_ruleset(ruleset_path)
    rules = data["rules"]
    if not rules:
        raise core.RulesetError("ruleset declares no rules; there is nothing to map")

    paths: dict[tuple, list[str]] = {}
    rule_rows, node_counts = [], {}
    for rule in rules:
        oc = outcome_for(rule)
        key = (rule["sourceMode"], rule["severity"], rule["check"]["kind"], oc)
        paths.setdefault(key, []).append(rule["id"])
        ids = [f"provenance:{key[0]}", f"severity:{key[1]}", f"kind:{key[2]}", f"outcome:{key[3]}"]
        for nid in ids:
            node_counts[nid] = node_counts.get(nid, 0) + 1
        rule_rows.append({
            "id": rule["id"],
            "severity": rule["severity"],
            "sourceMode": rule["sourceMode"],
            "kind": rule["check"]["kind"],
            "outcome": oc,
            "rationale": rule["rationale"],
            "authority": rule["authority"].get("source", ""),
            "nodes": ids,
        })

    stages = []
    for stage_key, label in STAGE_LABELS:
        nodes = []
        for value in STAGE_ORDER[stage_key]:
            nid = f"{stage_key}:{value}"
            if node_counts.get(nid):
                nodes.append({"id": nid, "label": value, "count": node_counts[nid],
                              "note": KIND_NOTE.get(value, "")})
        # An unknown value would be a schema change this file has not caught up
        # with. Surface it rather than dropping it silently from the diagram.
        known = {f"{stage_key}:{v}" for v in STAGE_ORDER[stage_key]}
        for nid, count in sorted(node_counts.items()):
            if nid.startswith(stage_key + ":") and nid not in known:
                nodes.append({"id": nid, "label": nid.split(":", 1)[1] + " (unrecognised)",
                              "count": count, "note": ""})
        stages.append({"key": stage_key, "label": label, "nodes": nodes})

    links = []
    for key, ids in sorted(paths.items()):
        through = [f"provenance:{key[0]}", f"severity:{key[1]}",
                   f"kind:{key[2]}", f"outcome:{key[3]}"]
        for i in range(3):
            links.append({"source": through[i], "target": through[i + 1],
                          "value": len(ids), "outcome": key[3],
                          "rules": sorted(ids), "through": through})

    units = []
    for unit in data.get("units", []):
        pending = core.blocking_dependencies(root, unit)
        done = os.path.exists(core.unit_done_marker(root, unit["id"]))
        units.append({
            "id": unit["id"],
            "depends_on": unit.get("depends_on", []),
            "paths": unit.get("paths", []),
            "owns": unit.get("owns", ""),
            "state": "validated" if done else ("blocked" if pending else "ready"),
            "blocked_by": pending,
        })

    blocking = [r for r in rules if r["severity"] == "blocking"]
    return {
        "source": os.path.relpath(ruleset_path, root),
        "mode": data["mode"],
        "intent": data.get("intent") or "",
        "totals": {
            "rules": len(rules),
            "blocking": len(blocking),
            "hook_tier": len([r for r in rules if r["enforcement"] == "hook"]),
            "denied_at_write_time": len([r for r in blocking if r["enforcement"] == "hook"]),
            "units": len(units),
        },
        "stages": stages,
        "links": links,
        "rules": rule_rows,
        "units": units,
    }


def render(template_path: str, tokens_path: str, doctrine: dict) -> str:
    with open(template_path, encoding="utf-8") as fh:
        tpl = fh.read()

    tokens_marker = "<!--__DESIGN_TOKENS__-->"
    if tokens_marker not in tpl:
        raise ValueError(f"design-tokens injection marker not found in {template_path}")
    with open(tokens_path, encoding="utf-8") as fh:
        tpl = tpl.replace(tokens_marker, "<style>\n" + fh.read() + "\n</style>")

    marker = "/*__DOCTRINE_DATA__*/ null"
    if marker not in tpl:
        raise ValueError(f"data injection marker not found in {template_path}")
    payload = json.dumps(doctrine)
    # Rule ids and rationales come from a file the repo itself authored, but every
    # other viewer in this marketplace treats its own input as untrusted here and
    # so does this one: escape the three characters that could break out of the
    # <script> block. The template pairs this with textContent-only rendering, so
    # neither barrier is load-bearing alone.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(marker, "/*__DOCTRINE_DATA__*/ " + payload)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("repo_root")
    ap.add_argument("--ruleset", default=None)
    ap.add_argument("--template", required=True)
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json-only", action="store_true",
                    help="write doctrine.json only; skip the HTML")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.repo_root)
    ruleset = args.ruleset or os.path.join(root, ".lehre", "ruleset.json")
    if not os.path.isfile(ruleset):
        print(f"lehre: no ruleset at {ruleset}. Run lehre-codify first; "
              f"refusing to render a doctrine this repo has not declared.", file=sys.stderr)
        return EXIT_UNUSABLE
    try:
        doctrine = build(root, ruleset)
    except (core.RulesetError, json.JSONDecodeError, ValueError) as exc:
        print(f"lehre: ruleset is unusable -- {exc}", file=sys.stderr)
        return EXIT_UNUSABLE

    out_dir = os.path.join(root, ".lehre")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "doctrine.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(doctrine, fh, indent=2)

    if args.json_only:
        print(json_path)
        return EXIT_OK

    out = args.out or os.path.join(out_dir, "DOCTRINE_MAP.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render(args.template, args.tokens, doctrine))

    t = doctrine["totals"]
    print(f"{out}")
    print(f"  {t['rules']} rules -> {t['denied_at_write_time']} denied at write time"
          f"; {t['blocking'] - t['denied_at_write_time']} blocking rule(s) are gauge-tier")
    print(f"  {t['units']} units, "
          f"{len([u for u in doctrine['units'] if u['state'] == 'blocked'])} currently blocked")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
