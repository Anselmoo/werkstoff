import os
import re

_BACKUP = re.compile(r"backup-([0-9]+)\.tar")


def latest_backup(directory):
    """Name of the newest backup-N.tar in directory, or None."""
    names = sorted(n for n in os.listdir(directory) if _BACKUP.fullmatch(n))
    return names[-1] if names else None
