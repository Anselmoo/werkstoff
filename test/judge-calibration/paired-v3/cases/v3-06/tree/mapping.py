from concurrent.futures import ThreadPoolExecutor


def map_all(fn, items, workers=8):
    """fn(item) for every item, computed on a thread pool, in the order of items."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))
