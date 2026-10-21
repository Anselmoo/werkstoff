def delays(attempts, base=0.5, cap=8.0):
    """Exponential backoff schedule, capped."""
    out = []
    d = base
    for _ in range(attempts):
        out.append(min(d, cap))
        d *= 2
    return out
