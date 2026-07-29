#!/usr/bin/env python3
"""CLI wrapper around lib.symbol_index.get_or_build_snapshot -- the "CLI
wrapper the cycle skill points you at" that confab-assertion-audit and
confab-contract-drift's "Shared symbol index" sections already reference by
name (rule: symbol-index-shared-per-invocation).

Builds the snapshot via the canonical tools/symbol-indexer build at most
once per invocation_id and caches it under
analysis/confab/symbol_index/<invocation_id>.json; any other skill in the
same confab-cycle invocation passing the same invocation_id gets the cached
result instead of rebuilding (single-flight lock makes concurrent callers
safe -- see lib/symbol_index.py).

Usage:
    python3 symbol_index_cli.py resolve <repo_root> --invocation-id ID [--no-fts]

Prints the resolved snapshot's cache path to stdout.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.paths import safe_output_path  # noqa: E402
from lib.symbol_index import get_or_build_snapshot  # noqa: E402

import build_symbol_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("repo_root")
    p_resolve.add_argument("--invocation-id", required=True)
    p_resolve.add_argument("--no-fts", action="store_true")

    args = parser.parse_args()
    repo_root = os.path.abspath(args.repo_root)

    if args.command == "resolve":
        def build_fn():
            pointer, _reused = build_symbol_index.build_or_reuse(Path(repo_root), "confab", args.no_fts)
            run_dir = Path(repo_root) / "analysis" / "confab" / "runs" / pointer["generation_id"]
            with open(run_dir / "symbol_index.json", "r", encoding="utf-8") as fh:
                return json.load(fh)

        get_or_build_snapshot(repo_root, args.invocation_id, build_fn)
        cache_path = safe_output_path(repo_root, f"symbol_index/{args.invocation_id}.json")
        print(cache_path)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
