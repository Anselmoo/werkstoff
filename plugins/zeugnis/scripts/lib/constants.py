"""Fixed vocabularies shared across zeugnis's domains."""

# assertion_audit findings are never auto-fixable -- draft-only/advisory by
# design (rule: assertion-fixability-always-advisory).
DRAFT_ONLY_DOMAINS = {"assertion_audit"}

FIXABLE_DOMAINS = {
    "dependency_audit": {"mode": "all", "categories": []},
    "contract_drift": {"mode": "all", "categories": []},
    # The only agentic_reliability category zeugnis may ever mark fixable.
    "agentic_reliability": {"mode": "category", "categories": ["excessive-tool-grant"]},
    # A surviving mutant is "fixed" by a NEW TEST, never by an edit to the
    # source it survived in -- so this domain's lock is a test-path scope
    # (lib.mutation_scope.scope_write_violation), not remediation_scope's
    # single allowedFile, and its "fixed" outcome additionally needs a kill
    # proof (cycle_engine.py). assertion_audit stays draft-only above: it
    # judges the tests and has no proof step.
    "mutation_harden": {"mode": "all", "categories": []},
}

# Domains whose remediation lock is a test-path write scope. Branching on the
# DOMAIN, not on whether the lock happens to carry testRoots, is the point: a
# lock for this domain without them is refused, never read as single-file.
TEST_SCOPE_DOMAINS = {"mutation_harden"}

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
