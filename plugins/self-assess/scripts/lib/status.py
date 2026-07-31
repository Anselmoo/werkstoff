"""Build self-assess-status's dashboard from what's actually on disk --
never fabricate a present-artifact entry."""
import os

# Findings-domain sidecars: presence here drives recommend_transform_brief()
# (rule: "a finding sitting around with no brief yet is worth flagging").
SIDECAR_FILES = {
    "self-assess-docs-drift": "docs_drift_summary.json",
    "self-assess-ci-topology": "ci_topology_summary.json",
    "self-assess-lint-audit": "lint_audit_summary.json",
    "self-assess-code-idiom": "code_idiom_summary.json",
    "self-assess-extract-rules": "business_rules_summary.json",
    "self-assess-arch-health": "arch_health_summary.json",
    "self-assess-ui-audit": "ui_audit_summary.json",
}

# Progress/synthesis artifacts, not findings domains -- deliberately EXCLUDED
# from SIDECAR_FILES/build_present_artifacts so their presence never triggers
# recommend_transform_brief() (running self-assess-stage-map is not itself a
# "finding"). They were previously excluded from the dashboard ENTIRELY, which
# is what let a fresh, valid stage_graph.json go completely unreported to a
# user asking "where does self-assess stand" (Phase 2 benchmark finding
# SA-2, docs/plugin-benchmark-phase2-results.md) -- reported here as their own
# category instead, never merged into SIDECAR_FILES/present.
STRUCTURAL_SIDECAR_FILES = {
    "self-assess-stage-map": "stage_map_summary.json",
    "self-assess-complexity-score": "complexity_score_summary.json",
    "self-assess-transform-brief": "transform_brief_summary.json",
}


def build_present_artifacts(output_abs):
    return {
        skill: filename
        for skill, filename in SIDECAR_FILES.items()
        if os.path.isfile(os.path.join(output_abs, filename))
    }


def build_structural_artifacts(output_abs):
    """Same presence check as build_present_artifacts, over the synthesis/
    progress skills instead of the findings domains -- kept in a separate
    function (not merged into build_present_artifacts) so
    recommend_transform_brief's "any finding artifact" semantics can never
    accidentally start counting a structural artifact as a finding."""
    return {
        skill: filename
        for skill, filename in STRUCTURAL_SIDECAR_FILES.items()
        if os.path.isfile(os.path.join(output_abs, filename))
    }


def recommend_transform_brief(output_abs):
    has_any_finding_artifact = bool(build_present_artifacts(output_abs))
    brief_exists = os.path.isfile(os.path.join(output_abs, "MODERNIZATION_BRIEF.md"))
    return has_any_finding_artifact and not brief_exists
