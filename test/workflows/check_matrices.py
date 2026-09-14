#!/usr/bin/env python3
"""Prove the committed templates resolve into matrices the landed runner accepts.

Token-free. Every matrix is expanded with `build_matrices.py` into a temporary directory and then
handed to `run_matrix.sh --dry-run --skip-probe`, which prints each cell's argv and runs nothing.

Two failures this catches that reading the JSON could not:
  * a template the runner REJECTS (a key it does not know, a value it validates) -- the sweep
    would die at cell zero, after the operator had already committed to it;
  * a resolved matrix whose enabled arm points at a directory that does not exist, which the
    runner refuses rather than running an arm that loads nothing.

`--templates-only` skips the dry run and checks just the committed files: no absolute machine
path, no home directory, nothing that looks like a credential.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TEMPLATES = HERE / "matrices"
RUNNER = REPO / "plugins" / "arbeitsplan" / "scripts" / "run_matrix.sh"

ABSOLUTE_PATH = re.compile(r"(/Users/|/home/|/root/|[A-Z]:\\\\)")
SECRETISH = re.compile(r"(?i)(api[_-]?key|secret|token|password|bearer\s)")


def check_templates() -> list[str]:
    problems = []
    files = sorted(TEMPLATES.glob("*.template.json"))
    if not files:
        return [f"no templates in {TEMPLATES}"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        if ABSOLUTE_PATH.search(text):
            problems.append(f"{path.name}: contains an absolute machine path -- templates carry "
                            "placeholders only, so they work on a machine that is not this one")
        if SECRETISH.search(text):
            problems.append(f"{path.name}: contains something that looks like a credential")
    print(f"  ok   {len(files)} template(s): no absolute paths, nothing credential-shaped"
          if not problems else "")
    return problems


def check_dry_run() -> list[str]:
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        build = subprocess.run(
            [sys.executable, str(HERE / "build_matrices.py"), "--out", tmp],
            capture_output=True, text=True, check=False, cwd=REPO,
        )
        if build.returncode != 0:
            return [f"build_matrices.py failed: {build.stdout}{build.stderr}"]
        matrices = sorted(Path(tmp).glob("*.json"))
        if not matrices:
            return ["build_matrices.py wrote no matrices"]
        for matrix in matrices:
            dry = subprocess.run(
                ["bash", str(RUNNER), "--matrix", str(matrix), "--dry-run", "--skip-probe"],
                capture_output=True, text=True, check=False, cwd=REPO, timeout=300,
            )
            if dry.returncode != 0:
                problems.append(f"{matrix.name}: the runner refused it "
                                f"(exit {dry.returncode}): {dry.stderr.strip()[:400]}")
                continue
            lines = [ln for ln in dry.stdout.splitlines() if "subrun.py" in ln or "claude" in ln]
            if not lines:
                problems.append(f"{matrix.name}: --dry-run printed no cell argv at all, so "
                                "nothing about this matrix was actually exercised")
                continue
            print(f"  ok   {matrix.name}: {len(lines)} cell(s) expand and the runner accepts them")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--templates-only", action="store_true",
                        help="check the committed templates, skip the dry run")
    args = parser.parse_args()

    problems = check_templates()
    if not args.templates_only:
        problems += check_dry_run()

    print()
    if problems:
        for problem in problems:
            print(f"  FAIL {problem}")
        return 1
    print("matrices ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
