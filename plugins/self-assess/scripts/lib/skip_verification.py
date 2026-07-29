"""Label findings when self-assess-docs-drift's skip_verification setting
is active, or refuse when it's off and a finding wasn't verified."""

from lib.errors import SelfAssessError


def label_findings(findings, skip):
    if skip:
        return [{**finding, "verified": False} for finding in findings]
    missing = [f for f in findings if "verified" not in f]
    if missing:
        raise SelfAssessError(
            f"{len(missing)} finding(s) are missing 'verified' and "
            "skip_verification is false; every finding must carry a verified "
            "flag or skip_verification must be set true."
        )
    return findings
