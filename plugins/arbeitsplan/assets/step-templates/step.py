#!/usr/bin/env python3
# ARBEITSPLAN-STUB -- the author removes this line when the step is written.
# Step {{NODE}} of plan {{PLAN}} (arbeitsplan-waves, authored).
# Purpose: {{PURPOSE}}
# Contract: arguments are positional (sys.argv[1:]); print exactly ONE JSON object
# on stdout (the node's output_schema); diagnostics go to stderr; exit with one of
# {{EXITS}}. Standard library only: the step runs wherever the plan runs.
# Verified by `{{HELPER}} verify-step --node {{NODE}}` with the sample {{SAMPLE}}.
from __future__ import annotations

import json
import sys


def emit(result: dict) -> None:
    print(json.dumps(result))


def main(argv: list) -> int:
    print("step {{NODE}} is not written yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
