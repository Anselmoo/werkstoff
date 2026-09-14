"""Stage 2: normalize records.

Imports `score` to reuse its weighting table -- one half of the cycle.
"""

from pipeline.score import DEFAULT_WEIGHTS


def normalize(records: list) -> list:
    out = []
    for record in records:
        scaled = {key: value / DEFAULT_WEIGHTS.get(key, 1.0) for key, value in record.items()}
        out.append(scaled)
    return out
