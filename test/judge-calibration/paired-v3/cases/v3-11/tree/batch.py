from concurrent.futures import ThreadPoolExecutor


def run_all(jobs, workers=4):
    """Run every job (a zero-argument callable) on a thread pool; their results, in order."""
    jobs = list(jobs)
    results = [None] * len(jobs)

    def run(i, job):
        results[i] = job()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, job in enumerate(jobs):
            pool.submit(run, i, job)
    return results
