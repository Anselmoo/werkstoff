#!/usr/bin/env python3
"""confab-code-change: pre-commit quality check scoped to changed files.

  * rule code-change-advisory-verdict: the verdict line is hardcoded to
    "ADVISORY" and this script's exit code is ALWAYS 0 on a successful
    run — there is no code path that returns non-zero for "findings
    exist." The only non-zero exit is the "zero domains matched" failure
    mode below, which is a diagnostic error (nothing to check), never a
    quality gate.
  * "runs only domains whose file patterns match changed files... zero-
    fills no unmatched domain; omits any domain with no matches": domain
    matching is a pure function over the changed-file list, and the report
    renderer iterates ONLY over matched domains — there is no
    zero-finding placeholder section for a domain that didn't match.
  * "dies with clear message if zero domains matched": handled by
    main() exiting 1 with an explicit stderr message when match_domains()
    returns nothing — the one case this script does NOT exit 0, because
    there is no advisory verdict to give.

Usage:
    python3 code_change_review.py <repo_root> --changed-files-json <path>
        [--domain-findings dependency_audit=<path.json>]
        [--domain-findings assertion_audit=<path.json>]
        [--domain-findings contract_drift=<path.json>]
        [--domain-findings agentic_reliability=<path.json>]

<path> for --changed-files-json is a JSON list of repo-relative changed
file paths (the caller runs `git diff --staged --name-only` or
`git diff HEAD --name-only` and dumps it to that file — this script does
not shell out to git itself, keeping it a pure function of its inputs).
"""

import argparse
import fnmatch
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402
from lib.schema import InvalidFindingError, validate_finding  # noqa: E402

DOMAIN_PATTERNS = {
    "dependency_audit": [
        "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod", "Gemfile",
        "*/package.json", "*/requirements.txt", "*/pyproject.toml", "*/Cargo.toml", "*/go.mod", "*/Gemfile",
    ],
    "assertion_audit": [
        "*.py", "*.js", "*.ts", "*.go", "*.rb", "*.java", "*_test.go", "*test*.py", "*.test.ts", "*.test.js",
    ],
    "contract_drift": [
        "*.py", "*.ts", "*.go", "*.java", "*openapi*", "*.graphql", "*schema*.json", "*schema*.yaml", "*schema*.yml",
    ],
    "agentic_reliability": [
        "skills/*", "agents/*", "workflows/*", "commands/*", "hooks/hooks.json",
        "*/skills/*", "*/agents/*", "*/workflows/*", "*/commands/*",
    ],
}


def match_domains(changed_files: list) -> dict:
    matched = {}
    for domain, patterns in DOMAIN_PATTERNS.items():
        hits = [
            f for f in changed_files
            if any(fnmatch.fnmatch(f, p) or fnmatch.fnmatch(os.path.basename(f), p) for p in patterns)
        ]
        if hits:
            matched[domain] = hits
    return matched


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--changed-files-json", required=True)
    parser.add_argument("--domain-findings", action="append", default=[])
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)

    with open(args.changed_files_json, "r", encoding="utf-8") as fh:
        changed_files = json.load(fh)

    matched = match_domains(changed_files)

    if not matched:
        print(
            "confab-code-change: zero domains matched the changed files; "
            "nothing to review (no manifest, source, contract, or agentic-definition files changed)",
            file=sys.stderr,
        )
        return 1

    domain_findings_paths = {}
    for entry in args.domain_findings:
        if "=" not in entry:
            parser.error(f"--domain-findings must be domain=path, got {entry!r}")
        domain, path = entry.split("=", 1)
        domain_findings_paths[domain] = path

    per_domain_findings = {}
    for domain in matched:
        path = domain_findings_paths.get(domain)
        findings = []
        if path:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            candidates = raw.get("findings", raw) if isinstance(raw, dict) else raw
            for f in candidates:
                try:
                    validate_finding(f, domain=domain)
                except InvalidFindingError as exc:
                    print(f"WARNING: dropping invalid {domain} finding: {exc}", file=sys.stderr)
                    continue
                findings.append(f)
        per_domain_findings[domain] = findings

    lines = ["# confab Code Change Review", "", "## Domains checked (matched by changed-file patterns)", ""]
    for domain, files in matched.items():
        lines.append(f"- **{domain}** — matched: {', '.join(files)}")
    lines.append("")

    total_findings = 0
    for domain, findings in per_domain_findings.items():
        lines.append(f"## {domain}")
        lines.append("")
        if not findings:
            lines.append("_no findings_")
            lines.append("")
            continue
        lines += ["| Severity | Title | Evidence | Fixability |", "|---|---|---|---|"]
        for f in findings:
            lines.append(f"| {f['severity']} | {f['title']} | {f['evidence']} | {f['fixability']} |")
            total_findings += 1
        lines.append("")

    verdict = f"ADVISORY: {total_findings} finding(s) across {len(matched)} domain(s). This never blocks the commit."
    lines.append(f"## Verdict\n\n{verdict}\n")

    report_path = safe_output_path(repo_root, "reports/CODE_CHANGE_REVIEW.md")
    ensure_parent_dir(report_path)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(json.dumps({"report_path": report_path, "verdict": verdict, "matchedDomains": list(matched.keys())}, indent=2))
    return 0  # rule: code-change-advisory-verdict — always 0 once a review was produced


if __name__ == "__main__":
    sys.exit(main())
