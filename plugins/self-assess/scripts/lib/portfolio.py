"""Grade a repo for self-assess-portfolio: worst signal wins."""


def grade_repo(has_artifacts, has_high, has_medium_or_gaps):
    if not has_artifacts:
        return "Gray"
    if has_high:
        return "Red"
    if has_medium_or_gaps:
        return "Amber"
    return "Green"
