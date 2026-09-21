"""Attribute a "path:line" citation to an architectural stage."""


def attribute(citation, file_stage_index):
    """Return the owning stage for citation, or "Unattributed" whenever the
    file isn't a key in file_stage_index (or the index itself is absent) --
    a miss here is a deliberately partial index, never an error."""
    if not file_stage_index or not citation:
        return "Unattributed"
    path = citation.split(":", 1)[0]
    return file_stage_index.get(path, "Unattributed")
