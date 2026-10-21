def median(xs):
    # TODO: handle empty input
    xs = sorted(xs)
    if not xs:
        raise ValueError('median of empty data')
    n = len(xs)
    mid = n // 2
    return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2
