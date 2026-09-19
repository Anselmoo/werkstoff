"""Stage 3: score records.

Imports `normalize` to re-normalize mid-scoring -- the other half of the cycle.
"""

DEFAULT_WEIGHTS = {"mass": 2.0, "charge": 1.5}


def score(records: list) -> list:
    from pipeline.normalize import normalize

    return [sum(record.values()) for record in normalize(records)]
