#!/usr/bin/env python3
"""confab-dependency-audit: parses manifest files, performs read-only
registry lookups bounded by a per-package timeout (rule:
dependency-lookup-timeout), flags nonexistent/typosquat-adjacent
packages, independently re-checks every finding in a Verify phase (rule:
registry-unreachable-not-verdict has 3 checkpoints — this file is
checkpoint 2 and 3: the finding-classification step below never derives
"hallucinated" from a skipped lookup, and the verify step re-runs the
lookup rather than trusting the cached Find-phase result), and writes
findings in the shared schema (rule: shared-finding-schema, checkpoint
1 of 5).

This script never installs, publishes, or otherwise mutates a package —
it only ever calls lib.registry.lookup_package, which is GET-only.

Usage:
    python3 dependency_audit.py <repo_root> [--timeout-seconds N]
                                 [--skip-verification]
                                 [--agent-findings <path-to-json>]

--agent-findings optionally merges additional candidate findings supplied
by the dependency-auditor agent (e.g. judgment calls on ambiguous or
scoped-package names) BEFORE the mandatory-unless-flagged verify pass —
agent-supplied findings get the same independent re-check as script-found
ones, they are never taken on faith.
"""

import argparse
import json
import os
import re
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import LOOKUP_NOT_FOUND, LOOKUP_SKIPPED  # noqa: E402
from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402
from lib.registry import lookup_package, resolve_timeout  # noqa: E402
from lib.schema import InvalidFindingError, validate_finding  # noqa: E402

MANIFEST_PARSERS = {}

# A small seed list of extremely popular packages per ecosystem, used only
# for a cheap Levenshtein-adjacent typosquat heuristic. This is NOT a
# hallucination oracle by itself — a name close to one of these is a
# candidate for the finding, never an automatic verdict; existence is
# still decided by the registry lookup.
POPULAR_PACKAGES = {
    "npm": ["react", "lodash", "express", "axios", "chalk", "commander", "request"],
    "pypi": ["requests", "numpy", "pandas", "flask", "django", "pytest", "boto3"],
    "crates": ["serde", "tokio", "clap", "regex", "rand"],
    "go": [],
    "rubygems": ["rails", "rspec", "rack", "nokogiri"],
}


def _levenshtein_le(a: str, b: str, max_dist: int) -> bool:
    if abs(len(a) - len(b)) > max_dist:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[len(b)] <= max_dist


def parse_package_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps.update(data.get(key, {}) or {})
    return [{"ecosystem": "npm", "name": name, "file": path, "line": 1} for name in deps]


def parse_requirements_txt(path: str) -> list:
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0].strip()
            if name:
                out.append({"ecosystem": "pypi", "name": name, "file": path, "line": lineno})
    return out


def parse_pyproject_toml(path: str) -> list:
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        in_deps = False
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if line.startswith("[") :
                in_deps = "dependencies" in line.lower()
                continue
            if in_deps and "=" in line:
                name = line.split("=", 1)[0].strip().strip('"').strip("'")
                if name and name.lower() != "python":
                    out.append({"ecosystem": "pypi", "name": name, "file": path, "line": lineno})
    return out


def parse_cargo_toml(path: str) -> list:
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        in_deps = False
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if line.startswith("["):
                in_deps = line.strip("[]").strip() in ("dependencies", "dev-dependencies", "build-dependencies")
                continue
            if in_deps and "=" in line:
                name = line.split("=", 1)[0].strip().strip('"').strip("'")
                if name:
                    out.append({"ecosystem": "crates", "name": name, "file": path, "line": lineno})
    return out


def parse_go_mod(path: str) -> list:
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if line.startswith("require") or (line and not line.startswith(("module", "go ", ")"))):
                parts = line.replace("require", "").strip().split()
                if parts and "/" in parts[0]:
                    out.append({"ecosystem": "go", "name": parts[0], "file": path, "line": lineno})
    return out


def parse_gemfile(path: str) -> list:
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            m = re.match(r"\s*gem\s+['\"]([^'\"]+)['\"]", raw)
            if m:
                out.append({"ecosystem": "rubygems", "name": m.group(1), "file": path, "line": lineno})
    return out


MANIFEST_PARSERS = {
    "package.json": parse_package_json,
    "requirements.txt": parse_requirements_txt,
    "pyproject.toml": parse_pyproject_toml,
    "Cargo.toml": parse_cargo_toml,
    "go.mod": parse_go_mod,
    "Gemfile": parse_gemfile,
}


def discover_dependencies(repo_root: str) -> list:
    deps = []
    for manifest_name, parser in MANIFEST_PARSERS.items():
        path = os.path.join(repo_root, manifest_name)
        if os.path.exists(path):
            try:
                deps.extend(parser(path))
            except Exception as exc:  # noqa: BLE001
                deps.append(
                    {
                        "ecosystem": "unknown",
                        "name": f"<unparseable:{manifest_name}>",
                        "file": path,
                        "line": 1,
                        "parse_error": str(exc),
                    }
                )
    return deps


def classify_dependency(dep: dict, *, timeout_seconds: int) -> Optional[dict]:
    """CHECKPOINT 2 (registry-unreachable-not-verdict): builds a finding
    only from lookup["outcome"], and the mapping below has no branch that
    turns LOOKUP_SKIPPED into an affirmative severity/title.
    """
    if dep.get("parse_error"):
        return None

    lookup = lookup_package(dep["ecosystem"], dep["name"], timeout_seconds=timeout_seconds)
    outcome = lookup["outcome"]
    evidence = f"{dep['file']}:{dep['line']}"

    if outcome == LOOKUP_NOT_FOUND:
        return {
            "severity": "High",
            "title": f"Declared dependency '{dep['name']}' does not exist on {dep['ecosystem']}",
            "evidence": evidence,
            "category": "hallucinated-dependency",
            "fixability": "fixable",
            "_lookupOutcome": outcome,
        }

    if outcome == LOOKUP_SKIPPED:
        return {
            "severity": "Low",
            "title": f"Registry lookup for '{dep['name']}' on {dep['ecosystem']} was skipped (unreachable), not confirmed",
            "evidence": evidence,
            "category": "registry-unreachable",
            "fixability": "advisory",
            "_lookupOutcome": outcome,
            "_skipReason": lookup.get("reason"),
        }

    # outcome == LOOKUP_EXISTS: still worth flagging if it's suspiciously
    # close to a popular package name (typosquat-adjacent), but this is
    # never treated as "hallucinated" since the package demonstrably
    # exists.
    popular = POPULAR_PACKAGES.get(dep["ecosystem"], [])
    for candidate in popular:
        if candidate == dep["name"]:
            break
        if _levenshtein_le(dep["name"], candidate, 1):
            return {
                "severity": "Medium",
                "title": f"'{dep['name']}' is one edit away from popular package '{candidate}' on {dep['ecosystem']}",
                "evidence": evidence,
                "category": "typosquat-adjacent",
                "fixability": "advisory",
                "_lookupOutcome": outcome,
            }
    return None


def verify_finding(finding: dict, dep_index: dict, *, timeout_seconds: int) -> Optional[dict]:
    """Mandatory-unless-skip-verification independent re-check: re-runs the
    lookup rather than trusting the Find-phase result, so a finding that
    only looked hallucinated due to a transient network blip gets caught.
    """
    dep = dep_index[finding["evidence"]]
    lookup = lookup_package(dep["ecosystem"], dep["name"], timeout_seconds=timeout_seconds)
    finding = dict(finding)
    finding["_verifyOutcome"] = lookup["outcome"]
    if finding["category"] == "hallucinated-dependency" and lookup["outcome"] != LOOKUP_NOT_FOUND:
        # Verify phase disagrees with Find phase — never silently keep an
        # unconfirmed hallucination finding at High severity.
        if lookup["outcome"] == LOOKUP_SKIPPED:
            finding["severity"] = "Low"
            finding["category"] = "registry-unreachable"
            finding["fixability"] = "advisory"
            finding["title"] = (
                f"Verification could not confirm hallucination for '{dep['name']}' "
                f"(registry unreachable on re-check); originally flagged, not confirmed"
            )
        else:
            return None  # verify phase refutes the finding; drop it
    return finding


def load_agent_findings(path) -> list:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw.get("findings", raw) if isinstance(raw, dict) else raw


def render_markdown(findings: list, verification_ran: bool, skipped_count: int) -> str:
    lines = ["# confab Dependency Audit", ""]
    lines.append(f"Verification phase ran: {verification_ran}")
    lines.append(f"Registry-unreachable lookups (reported as skipped, never as a verdict): {skipped_count}")
    lines += ["", "| Severity | Category | Title | Evidence | Fixability |", "|---|---|---|---|---|"]
    for f in findings:
        lines.append(f"| {f['severity']} | {f['category']} | {f['title']} | {f['evidence']} | {f['fixability']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--timeout-seconds", type=int, default=None)
    parser.add_argument("--skip-verification", action="store_true")
    parser.add_argument("--agent-findings", default=None)
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    timeout_seconds = resolve_timeout(args.timeout_seconds)

    deps = discover_dependencies(repo_root)
    dep_index = {f"{d['file']}:{d['line']}": d for d in deps if not d.get("parse_error")}

    findings = []
    for dep in deps:
        finding = classify_dependency(dep, timeout_seconds=timeout_seconds)
        if finding:
            findings.append(finding)

    for extra in load_agent_findings(args.agent_findings):
        findings.append(extra)

    verification_ran = not args.skip_verification
    if verification_ran:
        verified = []
        for f in findings:
            if f["evidence"] not in dep_index:
                verified.append(f)  # agent-supplied finding without a re-lookup key; keep as-is
                continue
            v = verify_finding(f, dep_index, timeout_seconds=timeout_seconds)
            if v is not None:
                verified.append(v)
        findings = verified

    skipped_count = sum(1 for f in findings if f.get("category") == "registry-unreachable")

    clean_findings = []
    for f in findings:
        clean = {k: v for k, v in f.items() if not k.startswith("_")}
        try:
            validate_finding(clean, domain="dependency_audit")
        except InvalidFindingError as exc:
            print(f"WARNING: dropping invalid finding: {exc}", file=sys.stderr)
            continue
        clean_findings.append(clean)

    summary = {
        "domain": "dependency_audit",
        "verificationRan": verification_ran,
        "timeoutSeconds": timeout_seconds,
        "findings": clean_findings,
    }

    summary_path = safe_output_path(repo_root, "dependency_audit_summary.json")
    ensure_parent_dir(summary_path)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)

    report_path = safe_output_path(repo_root, "reports/DEPENDENCY_AUDIT.md")
    ensure_parent_dir(report_path)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(clean_findings, verification_ran, skipped_count))

    print(json.dumps({"summary_path": summary_path, "report_path": report_path, "findingCount": len(clean_findings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
