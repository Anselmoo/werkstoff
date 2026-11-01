#!/usr/bin/env python3
"""Build the provenance graph — reference -> card -> token, from WRITTEN edges only.

The rule this file exists to obey (I8)
---------------------------------------
Edges are read from `$extensions["com.werkstoff.matrize"].edge` and from DTCG `{ref}`
aliases. Nothing here matches values across files to infer a relationship, and
`--paranoid` makes that refusal testable: it re-derives the graph by value-matching and
reports how badly that disagrees.

It disagrees badly, on real material. Against this repo's own 50-declaration token file:

  * `4px` is both `--space-1` and `--radius-sm`; `8px` is both `--space-2` and
    `--radius-panel`. Value-matching merges a spacing role into a radius role.
  * `--cat-1`, `--accent` and `--diverging-cool` all resolve to `var(--silica)`. A
    reconstructed graph shows ONE dependent where there are THREE — so it answers "what
    breaks if I change this?" with one when the truth is three, which is the only
    question the graph exists to answer.

Why this one artefact is interactive (the I7 exemption)
-------------------------------------------------------
Everything else matrize emits is print-first, because an approval artefact ends as a PDF
in front of someone who does not get a localhost URL. A graph earns the exception: it has
no readable static layout, and the reader arrives with a target question rather than
reading it end to end.

Usage:
    build_provenance_html.py --tokens FILE --out FILE [--scope TEXT]
    build_provenance_html.py --paranoid --tokens FILE   # written vs value-matched
    build_provenance_html.py --selftest
Exit: 0 built, 1 unusable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from report_kit import render as kit_render  # noqa: E402

TEMPLATE = HERE.parent / "assets" / "provenance-viewer.html"
TOKENS_CSS = HERE.parent / "assets" / "tokens.css"

EXT = "com.werkstoff.matrize"
REF = re.compile(r"^\{([A-Za-z0-9_.-]+)\}$")
DATA_MARKER = "@@DATA@@"
TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
KIT_MARKER = "<!--__REPORT_KIT__-->"
VERDICT_MARKER = "<!--__VERDICT__-->"


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


def build_graph(doc: dict) -> dict:
    tokens = walk(doc)
    doc_ext = (doc.get("$extensions") or {}).get(EXT) or {}
    default_ref = doc_ext.get("retrofittedFrom") or "references"

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(nid: str, kind: str, label: str, sub: str = "", detail: dict | None = None) -> None:
        nodes.setdefault(nid, {"id": nid, "kind": kind, "label": label, "sub": sub,
                               "detail": detail or {}})

    for path, token in tokens:
        ext = (token.get("$extensions") or {}).get(EXT) or {}
        css = ext.get("cssName") or "--" + path.replace(".", "-")
        grade = (ext.get("edge") or {}).get("grade") or ext.get("reliability") or "A"
        ref_name = ext.get("reference") or default_ref
        card = ext.get("card")

        node(f"ref:{ref_name}", "reference", ref_name, "collected reference")
        # What the token IS and where its evidence came from: previously dropped, and the
        # two questions the graph exists to answer ("why this value?") need both.
        node(f"tok:{path}", "token", css, path, {
            "value": value_text(token.get("$value")), "type": token.get("$type", ""),
            "role": ext.get("role", ""), "reference": ref_name, "card": card or "",
            "grade": grade, "rights": ext.get("rights", ""),
            "description": token.get("$description", ""),
        })

        if card:
            node(f"card:{card}", "card", card, ext.get("role", ""))
            edges.append({"from": f"ref:{ref_name}", "to": f"card:{card}", "grade": grade,
                          "kind": "derive"})
            edges.append({"from": f"card:{card}", "to": f"tok:{path}", "grade": grade,
                          "kind": "sets"})
        else:
            edges.append({"from": f"ref:{ref_name}", "to": f"tok:{path}", "grade": grade,
                          "kind": "sets"})

    # Alias edges come from the DTCG reference itself, not from comparing values.
    by_path = {p for p, _ in tokens}
    for path, token in tokens:
        value = token.get("$value")
        m = REF.match(value) if isinstance(value, str) else None
        if m and m.group(1) in by_path:
            edges.append({"from": f"tok:{m.group(1)}", "to": f"tok:{path}",
                          "grade": "A", "kind": "alias"})

    # de-duplicate, preserving order
    seen: set[tuple] = set()
    unique: list[dict] = []
    for e in edges:
        key = (e["from"], e["to"], e["kind"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return {"nodes": list(nodes.values()), "edges": unique}


def value_text(value) -> str:
    """A token value as one readable line: an alias as written, a colour as its hex, else JSON."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("hex"), str):
        return value["hex"]
    if isinstance(value, dict) and "value" in value and "unit" in value:
        return f"{value['value']}{value['unit']}"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def dependents(graph: dict, node_id: str) -> set[str]:
    out: set[str] = set()
    queue = [node_id]
    while queue:
        cur = queue.pop()
        for e in graph["edges"]:
            if e["from"] == cur and e["to"] not in out:
                out.add(e["to"])
                queue.append(e["to"])
    return out


def kit_report(graph: dict) -> dict:
    """The JSON island: the graph, a token table and the findings the graph implies, in the
    report kit's record shape (R6)."""
    labels = {n["id"]: n for n in graph["nodes"]}
    tokens = [n for n in graph["nodes"] if n["kind"] == "token"]
    rows = []
    for n in tokens:
        d = n["detail"]
        rows.append({"id": n["id"], "css": n["label"], "path": n["sub"], "value": d.get("value", ""),
                     "reference": d.get("reference", ""), "card": d.get("card", ""),
                     "grade": d.get("grade", ""), "dependents": len(dependents(graph, n["id"]))})
    findings = []
    for e in graph["edges"]:
        if e["grade"] != "C":
            continue
        tgt = labels[e["to"]]
        findings.append({
            "id": f"gc-{e['from']}-{e['to']}", "severity": "major", "rule": "grade-C-edge",
            "claim": f"{labels[e['to']]['label']} is reached by a grade-C edge from {labels[e['from']]['label']}",
            "file": tgt["sub"] or tgt["label"], "quote": f"{e['from']} -> {e['to']} ({e['kind']})",
            "fix": "Corroborate the source with a grade-A or grade-B reference before relying on the value; the edge gives direction only.",
            "evidence": [{"label": "grade", "detail": "C -- direction only, drawn dashed in the graph"}],
            "tags": {"kind": "grade-C"},
        })
    fan: dict[str, list[str]] = defaultdict(list)
    for e in graph["edges"]:
        if e["kind"] == "alias":
            fan[e["from"]].append(e["to"])
    for src, users in sorted(fan.items()):
        if len(users) < 2:
            continue
        s_node = labels[src]
        findings.append({
            "id": f"fan-{src}", "severity": "info", "rule": "shared-source",
            "claim": f"Changing {s_node['label']} changes {len(users)} things, not one",
            "file": s_node["sub"], "quote": s_node["detail"].get("value", ""),
            "fix": "Review every dependent before editing the source; each is a separate role that happens to share it.",
            "evidence": [{"label": "dependent", "detail": f"{labels[u]['label']} ({labels[u]['sub']})"} for u in users],
            "tags": {"kind": "shared-source"},
        })
    return {"scope": graph.get("scope", ""), "nodes": graph["nodes"], "edges": graph["edges"],
            "tokens": rows, "findings": findings}


def esc(text) -> str:
    """HTML-escape. The Viewer's CSP permits inline script, so its static markup is the
    one place in this plugin where an unescaped input-derived string is an XSS payload."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def verdict(graph: dict) -> str:
    tokens = [n for n in graph["nodes"] if n["kind"] == "token"]
    refs = [n for n in graph["nodes"] if n["kind"] == "reference"]
    aliases = [e for e in graph["edges"] if e["kind"] == "alias"]
    gradec = [e for e in graph["edges"] if e["grade"] == "C"]

    fan: dict[str, int] = defaultdict(int)
    for e in aliases:
        fan[e["from"]] += 1
    worst = max(fan.items(), key=lambda kv: kv[1], default=(None, 0))

    bits = [f"{len(tokens)} tokens trace to {len(refs)} reference(s)"]
    if worst[1] > 1:
        label = next(n["label"] for n in graph["nodes"] if n["id"] == worst[0])
        bits.append(
            f"and {worst[1]} roles share {label}, so changing it changes {worst[1]} things, "
            f"not one"
        )
    if gradec:
        bits.append(f"{len(gradec)} edge(s) rest on grade-C evidence and are drawn dashed")
    return ". ".join([", ".join(bits[:2])] + bits[2:]) + "."


def paranoid(doc: dict) -> list[str]:
    """Re-derive by value-matching and report the disagreement. The refusal, made testable."""
    tokens = walk(doc)
    by_value: dict[str, list[str]] = defaultdict(list)
    for path, token in tokens:
        v = token.get("$value")
        # An ALIAS is a string matching {a.b.c}. Everything else is a literal value.
        # Deciding that with `key.startswith("{")` on the SERIALISED value looks right and
        # silently excludes every JSON object too — so `{"unit": "px", "value": 4.0}` was
        # skipped and the merge case never fired. Test the value, not its serialisation.
        if isinstance(v, str) and REF.match(v):
            continue
        by_value[json.dumps(v, sort_keys=True)].append(path)

    findings: list[str] = []
    for _key, paths in sorted(by_value.items()):
        if len(paths) > 1:
            findings.append(
                f"value-matching would MERGE {len(paths)} distinct roles that share one "
                f"value: {', '.join(sorted(paths))}"
            )
    alias_targets: dict[str, list[str]] = defaultdict(list)
    for path, token in tokens:
        v = token.get("$value")
        m = REF.match(v) if isinstance(v, str) else None
        if m:
            alias_targets[m.group(1)].append(path)
    for target, users in sorted(alias_targets.items()):
        if len(users) > 1:
            findings.append(
                f"value-matching would COLLAPSE {len(users)} roles aliasing {target} into "
                f"one node: {', '.join(sorted(users))} — so \"what breaks if I change "
                f"{target}?\" would answer 1 instead of {len(users)}"
            )
    return findings


def render(doc: dict, scope: str) -> str:
    graph = build_graph(doc)
    graph["scope"] = scope
    template = TEMPLATE.read_text(encoding="utf-8")
    for marker in (DATA_MARKER, TOKENS_MARKER, KIT_MARKER, VERDICT_MARKER):
        if marker not in template:
            raise ValueError(f"template has no {marker}")

    # The kit inlines tokens, its own css/js and the escaped JSON island (barrier one). The
    # template renders every label through textContent (barrier two). The static verdict names
    # a token label taken from the document's own cssName, so it is input-derived and is
    # escaped before it becomes markup -- and filled AFTER the kit has run, so that text can
    # never sit in the template while the kit is still searching it for its own markers.
    page = kit_render(template, TEMPLATE.parent, kit_report(graph), tokens=TOKENS_CSS)
    return page.replace(VERDICT_MARKER, esc(verdict(graph)), 1)


def selftest() -> int:
    """Asserted on the two cases that settled I8, not on synthetic data."""
    sys.path.insert(0, str(HERE))
    import retrofit_css

    repo_css = Path("tools/design-tokens/tokens.css")
    source = repo_css.read_text(encoding="utf-8") if repo_css.exists() else retrofit_css.SAMPLE
    doc, _ = retrofit_css.retrofit(source, "werkstoff-tokens")
    graph = build_graph(doc)
    checks: list[tuple[str, bool]] = []

    ids = {n["id"] for n in graph["nodes"]}
    labels = {n["id"]: n["label"] for n in graph["nodes"]}

    if repo_css.exists():
        # CASE 1 — two roles, one value. They must remain two nodes.
        checks.append(("4px stays two nodes (--space-1 and --radius-sm)",
                       "tok:space.1" in ids and "tok:radius.sm" in ids))
        # CASE 2 — three roles, one source. Forward fan-out must be three.
        silica_users = [e for e in graph["edges"]
                        if e["kind"] == "alias" and labels.get(e["from"]) == "--silica"]
        checks.append((f"--silica shows 3 dependents, not 1 (got {len(silica_users)})",
                       len(silica_users) == 3))
        checks.append(("the verdict states the fan-out in words",
                       "3 roles share --silica" in verdict(graph)))
        # The refusal, made testable.
        p = paranoid(doc)
        checks.append(("value-matching is shown to MERGE distinct roles",
                       any("would MERGE" in f for f in p)))
        checks.append(("value-matching is shown to COLLAPSE aliased roles",
                       any("would COLLAPSE" in f for f in p)))
    else:
        checks.append(("repo tokens.css present for the real cases", False))

    # Structure
    checks.append(("every edge carries a grade",
                   all(e.get("grade") in ("A", "B", "C") for e in graph["edges"])))
    checks.append(("alias edges are typed as aliases",
                   any(e["kind"] == "alias" for e in graph["edges"])))
    checks.append(("no edge points at a node that does not exist",
                   all(e["from"] in ids and e["to"] in ids for e in graph["edges"])))

    # Grade-C edges must be drawable as dashed.
    doc_c = json.loads(json.dumps(doc))
    first = next(iter(doc_c["color"].values()))
    first["$extensions"][EXT]["edge"]["grade"] = "C"
    checks.append(("a grade-C edge survives into the graph",
                   any(e["grade"] == "C" for e in build_graph(doc_c)["edges"])))

    page = render(doc, "selftest")
    def static_markup(html: str) -> str:
        """The page a reader gets before any script runs: <script> and <style> removed."""
        return re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)

    checks.append(("payload marker replaced by a JSON island",
                   DATA_MARKER not in page and 'type="application/json" id="report-data"' in page))
    checks.append(("tokens injected", "--bg:" in page and "<!--__DESIGN_TOKENS__-->" not in page.split("</head>")[1]))
    checks.append(("the report kit is inlined",
                   "const RK = (() =>" in page and ".rk-top" in page))
    checks.append(("the figure-first stage skeleton is in the page (R9)",
                   'id="rk-stage"' in page and "data-rk-figure" in page and 'id="rk-drawer"' in page
                   and 'class="legend rk-legend-float' in page and 'class="rk-hud-stats"' in page))
    checks.append(("every graph node is keyboard-reachable and opens the drawer",
                   'tabindex: "0"' in page and 'role: "button"' in page and "S.open(" in page))
    checks.append(("verdict is in STATIC markup, not written by script",
                   VERDICT_MARKER not in static_markup(page) and "tokens trace to" in static_markup(page)))
    # This check used to read `... or True`, with its middle term sliced to [:0] as well:
    # unconditionally true twice over, so deleting the payload escaping entirely still
    # printed GREEN. It is the defect this repository is named for -- code that looks
    # correct and cannot fail -- sitting inside the calibration meant to prevent it.
    # Now: plant the delimiters in a real label and require the escaped form.
    hostile = json.loads(json.dumps(doc))
    first_key = next(iter(hostile["color"]))
    hostile["color"][first_key]["$extensions"][EXT]["cssName"] = "--</script><img src=x>&"
    hostile_page = render(hostile, "selftest")
    # Extract the payload EXACTLY. render() replaces the whole marker, comment included,
    # so splitting on the comment yields the entire page; slicing to the next "</script>"
    # over-reaches into the surrounding JS, where an ordinary code comment mentioning a
    # tag name reads as a raw `<`. raw_decode returns the JSON value's true end offset.
    # Under the report kit the payload is a JSON island; its end is the closing script tag
    # of that island, which is only safe to look for because the escaping under test is
    # what guarantees no earlier `</script>` can appear inside it.
    island = re.search(r'<script type="application/json" id="report-data">(.*?)</script>',
                       hostile_page, re.S)
    payload = island.group(1) if island else ""
    json.loads(payload)  # the island must still be valid JSON after escaping
    checks.append(("payload: `<` is escaped, and no raw `<` survives in it",
                   "\\u003c" in payload and "<" not in payload))
    checks.append(("payload: `>` and `&` are escaped too",
                   "\\u003e" in payload and "\\u0026" in payload))

    # The verdict is STATIC markup in a page whose CSP allows inline script, so an
    # input-derived label reaching it unescaped is an XSS payload, not a cosmetic bug.
    # It must go through render(), not through esc() directly: a first draft asserted on
    # `esc(verdict(...))` and therefore tested the fix rather than the code -- reverting
    # the escaping left it green.
    #
    # The verdict only names a label when a source has several dependents, so the payload
    # goes on whichever token the fan-out actually reports.
    evil = json.loads(json.dumps(doc))
    fan: dict[str, int] = defaultdict(int)
    for e in build_graph(evil)["edges"]:
        if e["kind"] == "alias":
            fan[e["from"]] += 1
    shared = max(fan.items(), key=lambda kv: kv[1], default=(None, 0))
    if shared[1] > 1:
        target = shared[0].split(":", 1)[-1]
        node = evil
        for part in target.split("."):
            node = node[part]
        node["$extensions"][EXT]["cssName"] = '--x"><img src=x onerror=alert(1)>'
        head = static_markup(render(evil, "selftest"))
        checks.append(("verdict: markup in a shared label cannot form a tag",
                       "<img" not in head and "&lt;img" in head))
    else:
        checks.append(("a shared source exists to carry the verdict payload", False))

    for label, ok in checks:
        print(f"  {label:<52} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--tokens")
    ap.add_argument("--out")
    ap.add_argument("--scope", default="")
    ap.add_argument("--paranoid", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.tokens:
        ap.print_help()
        return 1
    try:
        doc = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"build_provenance_html.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.paranoid:
        findings = paranoid(doc)
        print(f"value-matched reconstruction vs the written edges: {len(findings)} disagreement(s)")
        for f in findings:
            print(f"  - {f}")
        return 0

    if not args.out:
        ap.print_help()
        return 1
    graph = build_graph(doc)
    scope = args.scope or (
        f"{sum(1 for n in graph['nodes'] if n['kind'] == 'token')} tokens, "
        f"{len(graph['edges'])} written edges"
    )
    Path(args.out).write_text(render(doc, scope), encoding="utf-8")
    print(f"wrote {args.out} ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
