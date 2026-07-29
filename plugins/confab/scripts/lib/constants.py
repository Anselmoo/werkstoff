"""Fixed vocabularies shared across confab's domains."""

# assertion_audit findings are never auto-fixable -- draft-only/advisory by
# design (rule: assertion-fixability-always-advisory).
DRAFT_ONLY_DOMAINS = {"assertion_audit"}

FIXABLE_DOMAINS = {
    "dependency_audit": {"mode": "all", "categories": []},
    "contract_drift": {"mode": "all", "categories": []},
    # The only agentic_reliability category confab may ever mark fixable.
    "agentic_reliability": {"mode": "category", "categories": ["excessive-tool-grant"]},
}

AGENTIC_RELIABILITY_CATEGORIES = [
    "unbounded-retry",
    "no-escalation-path",
    "find-no-verify-wiring",
    "excessive-tool-grant",
]

TOOL_SOURCE_LLM = "llm-reasoned"
VALID_TOOL_SOURCES = {"real-tool", "llm-reasoned"}

LOOKUP_NOT_FOUND = "not_found"
LOOKUP_SKIPPED = "skipped"

PREFLIGHT_CHECKS = [
    "manifests",
    "registry_reachability",
    "mutation_tools",
    "source_schema_evidence",
    "agentic_files",
]
