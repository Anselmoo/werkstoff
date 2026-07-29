"""Shared numeric formulas -- defined once here so validators.py's
recomputation checks can never drift from the value self_assess_cli.py
reports."""

SEVERITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}


def complexity_index(ksloc):
    return 2.94 * (ksloc ** 1.10)


def work_item_rank(severity, complexity_weight=None):
    weight = complexity_weight if complexity_weight is not None else 1
    return SEVERITY_WEIGHT[severity] * weight
