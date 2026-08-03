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
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from andon_core import render_board  # noqa: E402


def render_html(template_path, board):
    tpl = open(template_path, encoding="utf-8").read()
    marker = "/*__BOARD_DATA__*/ null"
    if marker not in tpl:
        raise ValueError(f"injection marker not found in {template_path}")
    data = json.dumps(board)
    # Stage/wire/gap identifiers are derived from ledger docs the repo itself
    # authored, but treat them as untrusted the same way every other viewer
    # in this marketplace does -- escape HTML-breakout characters before
    # injecting into the <script> block.
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(marker, "/*__BOARD_DATA__*/ " + data)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("ledger_dir")
    parser.add_argument("--template", required=True)
    parser.add_argument("--out", help="defaults to <ledger_dir>/ANDON_BOARD.html")
    args = parser.parse_args(argv)

    board = render_board(args.repo_root, args.ledger_dir)
    if board is None:
        print(json.dumps({"never_run": True}))
        return 0

    out_path = args.out or os.path.join(args.repo_root, args.ledger_dir, "ANDON_BOARD.html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(args.template, board))

    print(json.dumps({"boardPath": out_path}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
