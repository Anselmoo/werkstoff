"""The shared finding schema, validated on every write, for every domain.

Only enforces the base 5 fields plus the two domain-specific rules that are
directly evidenced (assertion_audit's always-advisory fixability,
agentic_reliability's 4-category enum + fixable-only-for-excessive-tool-grant).
contract_drift's declaredLocation/actualUsageLocation and assertion_audit's
toolSource are left to each caller's own pre-filter, since both already
enforce them before ever calling validate_finding -- duplicating that here
would add a second, unverifiable enforcement point for the same rule.
"""
from lib.constants import AGENTIC_RELIABILITY_CATEGORIES


class InvalidFindingError(Exception):
    """A finding is missing a gating field or violates a domain rule.
    Never repaired or defaulted -- the caller drops it with a warning."""


_BASE_REQUIRED_FIELDS = ("severity", "title", "evidence", "category", "fixability")
_SEVERITIES = {"Low", "Medium", "High"}


def validate_finding(finding, *, domain):
    missing = [field for field in _BASE_REQUIRED_FIELDS if field not in finding]
    if missing:
        raise InvalidFindingError(f"{domain}: finding is missing required field(s) {missing!r}.")
    if finding["severity"] not in _SEVERITIES:
        raise InvalidFindingError(
            f"{domain}: severity {finding['severity']!r} is not one of {sorted(_SEVERITIES)!r}."
        )

    if domain == "assertion_audit" and finding["fixability"] != "advisory":
        raise InvalidFindingError(
            "assertion_audit: fixability must always be 'advisory' "
            "(rule: assertion-fixability-always-advisory)."
        )

    if domain == "agentic_reliability":
        if finding["category"] not in AGENTIC_RELIABILITY_CATEGORIES:
            raise InvalidFindingError(
                f"agentic_reliability: category {finding['category']!r} is not one of "
                f"{AGENTIC_RELIABILITY_CATEGORIES!r} (rule: agentic-reliability-four-categories)."
            )
        if finding["fixability"] == "fixable" and finding["category"] != "excessive-tool-grant":
            raise InvalidFindingError(
                "agentic_reliability: only 'excessive-tool-grant' findings may "
                "carry fixability='fixable'."
            )
