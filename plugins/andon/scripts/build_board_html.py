#!/usr/bin/env python3
"""Renders andon_core.py's render_board() output as a self-contained HTML
dashboard, alongside the markdown board andon-status already prints to the
chat. Written INSIDE the ledger directory (not analysis/andon/ itself) on
purpose: andon_enforce.py's PreToolUse hook allows any write whose resolved
path is the ledger dir or a descendant of it unconditionally ("the loop must
always be able to record its halt") -- a sibling path would instead fall
through to stop_reason(), which can legitimately deny a write while the
ledger holds a stop condition. This is a read-only rendering of
already-persisted evidence, so it should never itself be blocked by the same
gate that blocks advancing the loop.

Usage:
    build_board_html.py <repo_root> <ledger_dir> --template <path> [--out <path>]

Exits 0 with {"never_run": true} (no HTML written) if render_board returns
None -- never fabricate a board for a ledger that has never run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from andon_core import read_all_docs, render_board, resolve_main_root  # noqa: E402
from report_kit import render  # noqa: E402

D3_MARKER = "<!--__D3_SUBSET__-->"


def _text(value):
    return value if isinstance(value, str) else ("" if value is None else json.dumps(value))


def enrich(board, repo_root, ledger_dir):
    """Add the ledger documents behind render_board()'s counts.

    render_board() keeps its shape for its other consumers; this adds what a
    drill-down needs and the counts used to hide: each open gap's body and
    proposal, every evidence document (verdict, tier, strategy, supersession,
    expiry, prose) and each stage's description, confidence and prose.
    """
    root = resolve_main_root(repo_root)
    abs_ledger = Path(root) / ledger_dir
    gaps = {g["slug"]: g for g in read_all_docs(str(abs_ledger), "gaps")}
    report = dict(board)
    open_gaps = []
    for g in board.get("open_gaps", []):
        doc = gaps.get(g["slug"], {"fields": {}, "body": ""})
        proposal = doc["fields"].get("proposal")
        open_gaps.append({
            **g,
            "path": f"{ledger_dir}/gaps/{g['slug']}.md",
            "body": doc["body"].strip(),
            "proposal": proposal if isinstance(proposal, dict) else {"summary": _text(proposal)} if proposal else None,
        })
    report["open_gaps"] = open_gaps
    report["evidence"] = [
        {
            "slug": e["slug"],
            "path": f"{ledger_dir}/evidence/{e['slug']}.md",
            "title": e["fields"].get("title"),
            "wire": e["fields"].get("wire"),
            "strategy": e["fields"].get("strategy"),
            "verdict": e["fields"].get("verdict"),
            "tier": e["fields"].get("tier"),
            "non_overridable": bool(e["fields"].get("non_overridable")),
            "superseded_by": e["fields"].get("superseded_by"),
            "valid_until": _text(e["fields"].get("valid_until")) or None,
            "body": e["body"].strip(),
        }
        for e in read_all_docs(str(abs_ledger), "evidence")
    ]
    report["stage_docs"] = {
        s["fields"].get("title"): {
            "order": s["fields"].get("order"),
            "confidence": s["fields"].get("confidence"),
            "description": s["fields"].get("description"),
            "body": s["body"].strip(),
            "path": f"{ledger_dir}/stages/{s['slug']}.md",
        }
        for s in read_all_docs(str(abs_ledger), "stages")
    }
    report["ledger_dir"] = ledger_dir
    return report


def render_html(template_path, d3_path, tokens_path, board):
    template_path = Path(template_path)
    tpl = template_path.read_text(encoding="utf-8")
    if D3_MARKER not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(D3_MARKER, Path(d3_path).read_text(encoding="utf-8"))
    # report_kit.render() escapes < > & in the JSON island (the first barrier;
    # the template's textContent-only DOM is the second) and inlines the
    # design tokens and the report kit. Stage/wire/gap identifiers come from
    # ledger documents the repo itself authored, but are treated as untrusted.
    return render(tpl, template_path.parent, board, tokens=Path(tokens_path))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("ledger_dir")
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", required=True, help="path to the vendored tokens.css snippet")
    parser.add_argument("--out", help="defaults to <ledger_dir>/ANDON_BOARD.html")
    args = parser.parse_args(argv)

    board = render_board(args.repo_root, args.ledger_dir)
    if board is None:
        print(json.dumps({"never_run": True}))
        return 0

    out_path = Path(args.out) if args.out else Path(args.repo_root) / args.ledger_dir / "ANDON_BOARD.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        render_html(args.template, args.d3, args.tokens, enrich(board, args.repo_root, args.ledger_dir)),
        encoding="utf-8")

    print(json.dumps({"boardPath": str(out_path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
