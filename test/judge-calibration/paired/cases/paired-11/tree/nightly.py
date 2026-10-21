def batches(n, size):
    return [(i, min(i + size, n)) for i in range(0, n, size)]
