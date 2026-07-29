"""Cap the number of lint rules dispatched per self-assess-lint-audit run."""

DEFAULT_MAX_RULES = 12


def cap_rules(rules, max_rules):
    cap = max_rules if max_rules else DEFAULT_MAX_RULES
    return rules[:cap], rules[cap:]
