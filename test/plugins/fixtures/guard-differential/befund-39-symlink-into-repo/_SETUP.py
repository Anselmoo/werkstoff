"""Park a symlink OUTSIDE the probe repo aimed at unlisted in-repo source.

This cannot be a committed fixture file: the fixture directory IS the probe
repo, so there is no "outside" to commit into. Hence _SETUP.

argv[1] = the probe repo, argv[2] = its parent.
"""
import os
import sys
from pathlib import Path


def main() -> int:
    repo, parent = Path(sys.argv[1]), Path(sys.argv[2])
    outside = parent / "outside"
    outside.mkdir(exist_ok=True)
    link = outside / "looks-outside.py"
    if not link.exists():
        os.symlink(repo / "src" / "secret.py", link)
    # Prove the construction rather than assume it: if this ever stops being a
    # symlink (the way shutil's defaults silently dereferenced committed ones),
    # the case would quietly become a plain out-of-repo write and pass for the
    # wrong reason. Fail loudly instead.
    if not link.is_symlink():
        raise SystemExit(f"{link} is not a symlink; this case would prove nothing")
    if link.resolve() != (repo / "src" / "secret.py").resolve():
        raise SystemExit(f"{link} does not resolve into the repo; this case would prove nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
