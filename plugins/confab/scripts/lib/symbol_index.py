"""Single-flight, build-once-per-invocation_id cache in front of the
symbol-index snapshot, so every domain skill within one confab-cycle
invocation shares the same build instead of each rebuilding it (rule:
symbol-index-shared-per-invocation). Consumed by scripts/symbol_index_cli.py.
"""
import json
import os
import socket
import time

from lib.paths import ensure_parent_dir, safe_output_path

LOCK_WAIT_SECONDS = 60
LOCK_TTL_SECONDS = 300


class _SnapshotLock:
    """Single-flight PID/TTL lockfile. Same algorithm as
    build_symbol_index.py's own BuildLock, reimplemented (not imported) so
    lib/ stays self-contained rather than reaching across sys.path into a
    sibling script's internals."""

    def __init__(self, path, wait_seconds=LOCK_WAIT_SECONDS, ttl_seconds=LOCK_TTL_SECONDS):
        self.path, self.wait_seconds, self.ttl_seconds = path, wait_seconds, ttl_seconds

    def __enter__(self):
        deadline = time.monotonic() + self.wait_seconds
        payload = {"pid": os.getpid(), "host": socket.gethostname(), "expires_at": time.time() + self.ttl_seconds}
        while True:
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
                return self
            except FileExistsError:
                try:
                    with open(self.path, "r", encoding="utf-8") as fh:
                        existing = json.load(fh)
                    expired = float(existing.get("expires_at", 0)) < time.time()
                except (OSError, ValueError, json.JSONDecodeError):
                    expired = True
                if expired:
                    try:
                        os.unlink(self.path)
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out waiting for symbol-index lock {self.path}")
                time.sleep(0.2)

    def __exit__(self, *exc_info):
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        return False


def get_or_build_snapshot(repo_root, invocation_id, build_fn):
    """Return the cached snapshot for invocation_id, building it via the
    zero-arg build_fn (at most once) if not already cached. The on-disk
    cache at analysis/confab/symbol_index/<invocation_id>.json is the real
    contract -- symbol_index_cli.py re-derives that same path independently
    rather than trusting this function's return value."""
    cache_path = safe_output_path(repo_root, f"symbol_index/{invocation_id}.json")
    if os.path.isfile(cache_path):
        with open(cache_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    lock_path = cache_path + ".lock"
    ensure_parent_dir(lock_path)
    with _SnapshotLock(lock_path):
        if os.path.isfile(cache_path):
            with open(cache_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        snapshot = build_fn()
        ensure_parent_dir(cache_path)
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)
        return snapshot
