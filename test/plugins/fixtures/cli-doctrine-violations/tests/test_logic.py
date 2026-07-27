from widget.core.logic import normalise


def test_normalise_strips_and_lowercases():
    assert normalise([" A ", "B"]) == ["a", "b"]
