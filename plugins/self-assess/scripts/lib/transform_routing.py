"""Route confab findings and flag under-confident P0 rules for self-assess-transform-brief."""


def route_confab_finding(finding):
    return "advisory" if finding.get("fixability") == "advisory" else "work_item"


def flag_p0_blockers(rules):
    return [r for r in rules if r.get("priority") == "P0" and r.get("confidence") != "High"]
