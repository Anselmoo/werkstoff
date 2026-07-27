#!/usr/bin/env python3
"""Enforce that paradigm skills REFERENCE the doctrine and never DUPLICATE it.

Rules enforced (in code, exit non-zero on violation):
  * doctrine-mandatory-before-generation -- each of the 3 paradigm skills MUST
    reference the cli-architecture doctrine (so it is loaded before generating).
  * doctrine-not-duplicated -- the five-pillar doctrine and the frozen exit-code
    contract MUST NOT be restated in a paradigm skill file. A paradigm skill that
    spells out the 0/1/2 contract, or re-enumerates the five pillars, is treated
    as a duplication violation.

This is a repo self-check, run by the plugin's own test/CI, not against a
generated scaffold.
"""
import os
import re
import sys

from constants import EXIT_RUNTIME_ERROR, EXIT_SUCCESS

PARADIGM_SKILLS = [
    "cli-scaffold-compiled",
    "cli-scaffold-interpreted",
    "cli-scaffold-shell",
]

# A paradigm skill that contains ALL of these is restating the frozen contract
# instead of referencing it.
CONTRACT_RESTATEMENT = [
    r"\b0\b.*success",
    r"\b1\b.*(runtime|error)",
    r"\b2\b.*(usage|argument)",
]

# Enumerating the five pillars verbatim is duplication too.
PILLAR_RESTATEMENT = r"(ux|discoverab).*separation.*stability.*distribution.*composab"


def check_skill(skills_root, name):
    problems = []
    path = os.path.join(skills_root, name, "SKILL.md")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ["%s: SKILL.md not found" % name]

    lowered = text.lower()

    # must reference the doctrine
    if "cli-architecture" not in lowered:
        problems.append("%s: does not reference cli-architecture doctrine" % name)

    # must not restate the exit-code contract
    if all(re.search(p, lowered) for p in CONTRACT_RESTATEMENT):
        problems.append("%s: appears to RESTATE the 0/1/2 exit contract "
                        "(reference cli-architecture instead)" % name)

    # must not re-enumerate the five pillars
    if re.search(PILLAR_RESTATEMENT, lowered, re.S):
        problems.append("%s: appears to RE-ENUMERATE the five pillars "
                        "(reference cli-architecture instead)" % name)

    return problems


def main(argv):
    # skills root defaults to ../skills relative to this file
    here = os.path.dirname(os.path.abspath(__file__))
    skills_root = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(here), "skills")

    all_problems = []
    for name in PARADIGM_SKILLS:
        all_problems.extend(check_skill(skills_root, name))

    if all_problems:
        sys.stderr.write("DOCTRINE ISOLATION VIOLATIONS:\n")
        for p in all_problems:
            sys.stderr.write("  - %s\n" % p)
        return EXIT_RUNTIME_ERROR

    sys.stdout.write("OK: all %d paradigm skills reference (not duplicate) the doctrine\n"
                     % len(PARADIGM_SKILLS))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main(sys.argv))
