def with_retries(fn, attempts):
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except Exception as exc:  # the caller decides what is retryable
            last = exc
    raise last
