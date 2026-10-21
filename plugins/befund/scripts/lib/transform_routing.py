"""Route zeugnis findings and flag under-confident P0 rules for befund-transform-brief."""
from lib import validators


def route_zeugnis_finding(finding):
    return "advisory" if finding.get("fixability") == "advisory" else "work_item"


def flag_p0_blockers(rules):
    # validators.validate_business_rules_summary only lets the exact string "P0"
    # through, but this reads rules straight from a JSON list that may never have
    # been validated: "p0", "P 0" and fullwidth "\uff30\uff10" are P0 here too, so a
    # Low-confidence one still blocks the brief rather than slipping by on spelling.
    return [
        r
        for r in rules
        if validators.normalised_priority(r.get("priority")) == "P0" and r.get("confidence") != "High"
    ]
