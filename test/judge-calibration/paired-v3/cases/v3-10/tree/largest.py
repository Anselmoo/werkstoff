import os
import stat


def _raise(err):
    raise err


def largest_file(root):
    """(path relative to root, size) of the largest regular file under root, or None."""
    best = None
    for dirpath, dirnames, filenames in os.walk(root, onerror=_raise):
        for name in filenames:
            p = os.path.join(dirpath, name)
            st = os.lstat(p)
            if not stat.S_ISREG(st.st_mode):
                continue
            key = (-st.st_size, os.path.relpath(p, root))
            if best is None or key < best:
                best = key
    return None if best is None else (best[1], -best[0])
