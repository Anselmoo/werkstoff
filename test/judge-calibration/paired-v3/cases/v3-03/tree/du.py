import os
import stat


def total_size(root):
    """Total size in bytes of the regular files under root."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            st = os.lstat(os.path.join(dirpath, name))
            if stat.S_ISREG(st.st_mode):
                total += st.st_size
    return total
