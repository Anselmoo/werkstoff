#!/usr/bin/env python3
"""confab-status: read-only staleness check plus a single next-action
suggestion, combining all domain sidecars and ledger state into one
dashboard JSON.

Read-only: this script only ever runs `git log` (read) via subprocess,
never a mutating git command, and only ever opens existing files for
reading except for its own two output artifacts.

Usage:
    python3 status_dashboard.py <repo_root>
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402

DOMAIN_SKILLS = {
    "dependency_audit": ("confab-dependency-audit", "dependency_audit_summary.json"),
    "assertion_audit": ("confab-assertion-audit", "assertion_audit_summary.json"),
    "contract_drift": ("confab-contract-drift", "contract_drift_summary.json"),
    "agentic_reliability": ("confab-agentic-reliability", "agentic_reliability_summary.json"),
}


def _confab_relpath_mtime(repo_root: str, relpath: str):
    path = safe_output_path(repo_root, relpath)
    if not os.path.exists(path):
        return None
    return os.path.getmtime(path)


def _git_last_commit_epoch(repo_root: str):
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return int(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def build_dashboard(repo_root: str) -> dict:
    now_reference = _git_last_commit_epoch(repo_root)

    domains = {}
    for domain, (skill_id, relpath) in DOMAIN_SKILLS.items():
        mtime = _confab_relpath_mtime(repo_root, relpath)
        summary = None
        summary_path = safe_output_path(repo_root, relpath)
        if mtime is not None:
            with open(summary_path, "r", encoding="utf-8") as fh:
                summary = json.load(fh)

        stale = None
        if mtime is not None and now_reference is not None:
            stale = now_reference > mtime

        domains[domain] = {
            "skill": skill_id,
            "hasRun": mtime is not None,
            "lastRunEpoch": mtime,
            "staleRelativeToLatestCommit": stale,
            "findingCount": len(summary["findings"]) if summary else None,
        }

    ledger = None
    ledger_path = safe_output_path(repo_root, "ledger.json")
    if os.path.exists(ledger_path):
        with open(ledger_path, "r", encoding="utf-8") as fh:
            ledger = json.load(fh)

    converged = None
    if ledger and ledger.get("passes"):
        last_pass = ledger["passes"][-1]
        converged = last_pass["closed"] == 0 and last_pass["fixOrDraftOutcomes"] == 0

    suggestion = suggest_next_action(domains, ledger, converged)

    return {
        "domains": domains,
        "ledgerPresent": ledger is not None,
        "cycleConverged": converged,
        "suggestion": suggestion,
    }


def suggest_next_action(domains: dict, ledger, converged) -> dict:
    never_run = [d for d, info in domains.items() if not info["hasRun"]]
    if never_run:
        skill = DOMAIN_SKILLS[never_run[0]][0]
        return {"action": skill, "reason": f"{never_run[0]} has never been run"}

    stale = [(d, info) for d, info in domains.items() if info["staleRelativeToLatestCommit"]]
    if stale:
        stalest_domain, _ = min(stale, key=lambda pair: pair[1]["lastRunEpoch"])
        return {"action": DOMAIN_SKILLS[stalest_domain][0], "reason": f"{stalest_domain} is stale relative to the latest commit"}

    if ledger is not None and converged is False:
        return {"action": "confab-cycle", "reason": "prior cycle has not converged yet"}

    if ledger is None:
        return {"action": "confab-cycle", "reason": "all domains have run at least once; a self-optimization pass has not"}

    return {"action": None, "reason": "all domains fresh and cycle converged; nothing pending"}


def render_html(dashboard: dict) -> str:
    rows = []
    for domain, info in dashboard["domains"].items():
        rows.append(
            f"<tr><td>{domain}</td><td>{info['hasRun']}</td>"
            f"<td>{info['findingCount']}</td><td>{info['staleRelativeToLatestCommit']}</td></tr>"
        )
    suggestion = dashboard["suggestion"]
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>confab status</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; }}
td, th {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
</style></head>
<body>
<h1>confab findings dashboard</h1>
<table>
<tr><th>Domain</th><th>Has run</th><th>Findings</th><th>Stale</th></tr>
{''.join(rows)}
</table>
<h2>Suggested next action</h2>
<p><strong>{suggestion['action']}</strong> — {suggestion['reason']}</p>
</body></html>
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: status_dashboard.py <repo_root>", file=sys.stderr)
        return 2
    repo_root = os.path.abspath(sys.argv[1])

    dashboard = build_dashboard(repo_root)

    data_path = safe_output_path(repo_root, "findings_dashboard_data.json")
    ensure_parent_dir(data_path)
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(dashboard, fh, indent=2, sort_keys=True)

    html_path = safe_output_path(repo_root, "reports/findings-dashboard.html")
    ensure_parent_dir(html_path)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(dashboard))

    print(json.dumps({"data_path": data_path, "html_path": html_path, "suggestion": dashboard["suggestion"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
