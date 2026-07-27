#!/usr/bin/env python3
"""confab-preflight: runs all five readiness checks unconditionally (rule:
preflight-all-checks-run) and yields four independent readiness verdicts.

Each check is wrapped in its own try/except so a crash in one check can
never prevent the others from running — this is the actual enforcement
of "no early exit," not a comment promising it. All five checks always
appear in the output, with status "error" (not "skipped") if a check
itself blew up.

Usage:
    python3 preflight.py <repo_root> [--timeout-seconds N]

Writes analysis/confab/reports/PREFLIGHT.md and analysis/confab/preflight_summary.json.
Exits 0 always (preflight is diagnostic, never a gate).
"""

import argparse
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import PREFLIGHT_CHECKS  # noqa: E402
from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402
from lib.registry import lookup_package, resolve_timeout  # noqa: E402

MANIFEST_GLOBS = [
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
]
MUTATION_TOOLS = ["mutmut", "cosmic-ray", "stryker", "cargo-mutants", "go-mutesting"]
AGENTIC_DIR_NAMES = ["skills", "agents", "workflows", "commands"]


def check_manifests(repo_root: str) -> dict:
    found = [m for m in MANIFEST_GLOBS if os.path.exists(os.path.join(repo_root, m))]
    return {
        "check": "manifests",
        "status": "ready" if found else "not_ready",
        "detail": f"found manifests: {found}" if found else "no dependency manifest files found",
        "readiness_verdicts_supported": ["dependency-audit"],
    }


def check_registry_reachability(repo_root: str, timeout_seconds) -> dict:
    # A single cheap, well-known lookup per ecosystem is enough to establish
    # reachability without doing real audit work here.
    probes = [("npm", "left-pad"), ("pypi", "pip")]
    results = []
    reachable_any = False
    for ecosystem, name in probes:
        outcome = lookup_package(ecosystem, name, timeout_seconds=timeout_seconds)
        results.append(outcome)
        if outcome["outcome"] != "skipped":
            reachable_any = True
    # rule: registry-unreachable-not-verdict — "not reachable" here means
    # "we could not confirm reachability," never "registries are confirmed
    # down." status stays conservative: "degraded", not "not_ready".
    status = "ready" if reachable_any else "degraded"
    return {
        "check": "registry_reachability",
        "status": status,
        "detail": results,
        "readiness_verdicts_supported": ["dependency-audit"],
    }


def check_mutation_tools(repo_root: str) -> dict:
    found = [t for t in MUTATION_TOOLS if shutil.which(t)]
    return {
        "check": "mutation_tools",
        "status": "ready" if found else "degraded",
        "detail": (
            f"found real mutation tools on PATH: {found}"
            if found
            else "no real mutation tool on PATH; assertion-audit will fall back to llm-reasoned findings"
        ),
        "readiness_verdicts_supported": ["assertion-audit"],
    }


def check_source_schema_evidence(repo_root: str) -> dict:
    typed_hits = glob.glob(os.path.join(repo_root, "**", "*.pyi"), recursive=True)
    typed_hits += glob.glob(os.path.join(repo_root, "**", "*.ts"), recursive=True)
    schema_hits = glob.glob(os.path.join(repo_root, "**", "openapi*.*"), recursive=True)
    schema_hits += glob.glob(os.path.join(repo_root, "**", "*.graphql"), recursive=True)
    evidence = bool(typed_hits or schema_hits)
    return {
        "check": "source_schema_evidence",
        "status": "ready" if evidence else "not_ready",
        "detail": {
            "typed_source_sample": typed_hits[:5],
            "schema_files_sample": schema_hits[:5],
        },
        "readiness_verdicts_supported": ["contract-drift"],
    }


def check_agentic_files(repo_root: str) -> dict:
    found = [d for d in AGENTIC_DIR_NAMES if os.path.isdir(os.path.join(repo_root, d))]
    return {
        "check": "agentic_files",
        "status": "ready" if found else "not_ready",
        "detail": f"found agentic definition dirs: {found}" if found else "no skills/agents/workflows directories found",
        "readiness_verdicts_supported": ["agentic-reliability"],
    }


def run_all_checks(repo_root: str, timeout_seconds) -> list:
    checks_impl = {
        "manifests": lambda: check_manifests(repo_root),
        "registry_reachability": lambda: check_registry_reachability(repo_root, timeout_seconds),
        "mutation_tools": lambda: check_mutation_tools(repo_root),
        "source_schema_evidence": lambda: check_source_schema_evidence(repo_root),
        "agentic_files": lambda: check_agentic_files(repo_root),
    }
    results = []
    # rule: preflight-all-checks-run — five independent try/except blocks,
    # NOT a single try wrapping the whole loop, so one check's exception
    # cannot prevent the loop from reaching the rest.
    for name in PREFLIGHT_CHECKS:
        try:
            results.append(checks_impl[name]())
        except Exception as exc:  # noqa: BLE001 - intentionally broad, this is the guarantee
            results.append(
                {
                    "check": name,
                    "status": "error",
                    "detail": f"check raised {type(exc).__name__}: {exc}",
                    "readiness_verdicts_supported": [],
                }
            )
    assert len(results) == len(PREFLIGHT_CHECKS), "internal error: not all checks ran"
    return results


def derive_verdicts(check_results: list) -> dict:
    by_verdict = {
        "dependency-audit": [],
        "assertion-audit": [],
        "contract-drift": [],
        "agentic-reliability": [],
    }
    for r in check_results:
        for v in r["readiness_verdicts_supported"]:
            by_verdict[v].append(r["status"])

    verdicts = {}
    for verdict_name, statuses in by_verdict.items():
        if not statuses:
            verdicts[verdict_name] = "unknown"
        elif any(s == "error" for s in statuses):
            verdicts[verdict_name] = "error"
        elif any(s == "not_ready" for s in statuses):
            verdicts[verdict_name] = "not_ready"
        elif any(s == "degraded" for s in statuses):
            verdicts[verdict_name] = "degraded"
        else:
            verdicts[verdict_name] = "ready"
    return verdicts


def render_markdown(check_results: list, verdicts: dict) -> str:
    lines = ["# confab Preflight", "", "## Checks", "", "| Check | Status | Detail |", "|---|---|---|"]
    for r in check_results:
        detail = json.dumps(r["detail"]) if not isinstance(r["detail"], str) else r["detail"]
        if len(detail) > 200:
            detail = detail[:197] + "..."
        lines.append(f"| {r['check']} | {r['status']} | {detail} |")
    lines += ["", "## Readiness Verdicts", "", "| Skill | Verdict |", "|---|---|"]
    for name, verdict in verdicts.items():
        lines.append(f"| {name} | {verdict} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--timeout-seconds", type=int, default=None)
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    timeout_seconds = resolve_timeout(args.timeout_seconds)

    check_results = run_all_checks(repo_root, timeout_seconds)
    verdicts = derive_verdicts(check_results)

    summary = {
        "domain": "preflight",
        "checks": check_results,
        "verdicts": verdicts,
    }

    summary_path = safe_output_path(repo_root, "preflight_summary.json")
    ensure_parent_dir(summary_path)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)

    report_path = safe_output_path(repo_root, "reports/PREFLIGHT.md")
    ensure_parent_dir(report_path)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(check_results, verdicts))

    print(json.dumps({"summary_path": summary_path, "report_path": report_path, "verdicts": verdicts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
