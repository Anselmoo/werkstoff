"""Confirm a P0 business rule needs >=2 distinct judges, all agreeing."""


def confirm_p0_rule(rule, judges):
    distinct = {}
    for judge in judges:
        judge_id = judge.get("judge_id")
        if judge_id is not None:
            distinct[judge_id] = judge.get("confirms")
    panel_confirmed = len(distinct) >= 2 and all(distinct.values())
    return {"rule": rule, "panel_confirmed": panel_confirmed, "judges": judges}
