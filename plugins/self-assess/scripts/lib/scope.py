"""Exclude CI/remote-topology claims from self-assess-docs-drift's scope --
those are self-assess-ci-topology's rules to check, not this skill's."""

CI_PATH_PATTERNS = (
    ".github/workflows/",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
    "azure-pipelines.yml",
)
CI_KEYWORD_PATTERNS = ("git remote", "mirror script", "pipeline config")


def _claim_text(claim):
    if isinstance(claim, dict):
        return " ".join(str(claim.get(field, "")) for field in ("doc_citation", "code_citation", "text"))
    return str(claim)


def _matches_ci(claim):
    haystack = _claim_text(claim)
    if any(pattern in haystack for pattern in CI_PATH_PATTERNS):
        return True
    lowered = haystack.lower()
    return any(pattern in lowered for pattern in CI_KEYWORD_PATTERNS)


def exclude_ci_claims(claims):
    in_scope, excluded = [], []
    for claim in claims:
        (excluded if _matches_ci(claim) else in_scope).append(claim)
    return in_scope, excluded
