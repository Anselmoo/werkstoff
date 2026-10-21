def split_bill(total_cents, n):
    q, r = divmod(total_cents, n)
    return [q + 1] * r + [q] * (n - r)
