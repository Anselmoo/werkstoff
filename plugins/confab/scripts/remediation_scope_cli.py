#!/usr/bin/env python3
"""CLI wrapper around lib.remediation_scope, for the orchestrating skill
to call via Bash immediately before and after dispatching
confab-remediator for one finding.

Usage:
    python3 remediation_scope_cli.py open <repo_root> --finding-id ID
        --domain DOMAIN --category CATEGORY --target-file FILE
    python3 remediation_scope_cli.py close <repo_root>

Exit code 3 means "this finding is not auto-fixable" — the calling skill
must treat that as a hard stop for this finding (route it to advisory
instead of dispatching confab-remediator at all).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.paths import UnsafeWritePathError  # noqa: E402
from lib.remediation_scope import RemediationNotFixableError, close_scope, open_scope  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open")
    p_open.add_argument("repo_root")
    p_open.add_argument("--finding-id", required=True)
    p_open.add_argument("--domain", required=True)
    p_open.add_argument("--category", required=True)
    p_open.add_argument("--target-file", required=True)

    p_close = sub.add_parser("close")
    p_close.add_argument("repo_root")

    args = parser.parse_args()
    repo_root = os.path.abspath(args.repo_root)

    if args.command == "open":
        try:
            path = open_scope(
                repo_root,
                finding_id=args.finding_id,
                domain=args.domain,
                category=args.category,
                target_file=args.target_file,
            )
        except RemediationNotFixableError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 3
        except UnsafeWritePathError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 4
        print(json.dumps({"scopePath": path}))
        return 0

    if args.command == "close":
        close_scope(repo_root)
        print(json.dumps({"closed": True}))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
