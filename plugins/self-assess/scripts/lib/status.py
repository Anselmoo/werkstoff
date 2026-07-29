"""Build self-assess-status's dashboard from what's actually on disk --
never fabricate a present-artifact entry."""
import os

# Progress/synthesis artifacts, not findings domains -- excluded by design.
SIDECAR_FILES = {
    "self-assess-docs-drift": "docs_drift_summary.json",
    "self-assess-ci-topology": "ci_topology_summary.json",
    "self-assess-lint-audit": "lint_audit_summary.json",
    "self-assess-code-idiom": "code_idiom_summary.json",
    "self-assess-extract-rules": "business_rules_summary.json",
    "self-assess-arch-health": "arch_health_summary.json",
    "self-assess-ui-audit": "ui_audit_summary.json",
}


def build_present_artifacts(output_abs):
    return {
        skill: filename
        for skill, filename in SIDECAR_FILES.items()
        if os.path.isfile(os.path.join(output_abs, filename))
    }


def recommend_transform_brief(output_abs):
    has_any_finding_artifact = bool(build_present_artifacts(output_abs))
    brief_exists = os.path.isfile(os.path.join(output_abs, "MODERNIZATION_BRIEF.md"))
    return has_any_finding_artifact and not brief_exists
