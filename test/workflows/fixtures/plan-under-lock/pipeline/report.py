"""Stage 4: render a report."""

from pipeline.score import score


def report(records: list) -> str:
    return "\n".join(f"{value:.3f}" for value in score(records))
