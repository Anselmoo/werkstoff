#!/usr/bin/env python3
"""Shim: the prompt-quality linter and its calibration moved into the nacharbeit plugin.

CLAUDE.md and CI keep calling this path; the instrument's self-assertion ships with the
plugin at plugins/nacharbeit/scripts/test_nacharbeit_lint.py, the way lehre's evaluator
tests ship in plugins/lehre/scripts/. Runs it in a subprocess and passes the exit code
through.

Usage: test-lint-prompts.py            (exit 0 green, 1 red)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / "plugins" / "nacharbeit" / "scripts" / "test_nacharbeit_lint.py"

if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, str(TARGET)]))
