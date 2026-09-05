#!/usr/bin/env python3
"""Calibration for lint-tag-releases.py: prove it goes red before trusting it.

    python3 test/plugins/test-lint-tag-releases.py

Written against fabricated tag/release lists BEFORE the guard was pointed at
the real repository, because an oracle tuned after seeing the thing it grades
is an oracle tuned to pass. Every case below is a hand-written pair of inputs
with a known answer.

The cases that matter most are the ones where a naive implementation reports
success:

  * a tag inside the grace window is not yet a failure, but a tag past it is --
    a guard that never fires during a release and never fires after it is
    decoration;
  * an empty or tagless input must be an ERROR, not a pass. A shallow CI clone
    with no tags fetched looks exactly like a repo that has released nothing;
  * a bare `vX.Y.Z` tag (werkstoff-cli, published by cicd.yml) must be judged
    too -- that half of the repo is still exposed to the GITHUB_TOKEN blind
    spot, so it is the half most likely to break;
  * a tag that is not release-shaped at all must NOT be demanded a release.

Each case is (label, tags, releases, grace, expected exit, expected substring).
The substring matters as much as the code: a guard that fails for the wrong
reason gets "fixed" by silencing the wrong thing.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "test/plugins/lint-tag-releases.py"

NOW = 1_800_000_000
OLD = NOW - 24 * 3600          # a day ago: well past any grace window
JUST_NOW = NOW - 5 * 60        # five minutes ago: mid-release

FAILURES: list[str] = []


def run_case(label, tags, releases, grace, want_rc, want_text, baseline=()) -> None:
    with tempfile.TemporaryDirectory(prefix="tag-releases-") as box:
        tags_file = Path(box) / "tags.tsv"
        tags_file.write_text("".join(f"{n}\t{t}\n" for n, t in tags), encoding="utf-8")
        rel_file = Path(box) / "releases.json"
        rel_file.write_text(json.dumps(releases), encoding="utf-8")
        # Always passed explicitly: defaulting to the repo's real baseline would
        # make these cases depend on a file they are not testing.
        base_file = Path(box) / "baseline.txt"
        base_file.write_text("# fixture\n" + "".join(f"{n}\n" for n in baseline), encoding="utf-8")

        proc = subprocess.run(
            [
                sys.executable, str(GUARD),
                "--tags-file", str(tags_file),
                "--releases-file", str(rel_file),
                "--baseline", str(base_file),
                "--grace-minutes", str(grace),
                "--now", str(NOW),
            ],
            capture_output=True, text=True,
        )
    output = proc.stdout + proc.stderr
    problems = []
    if proc.returncode != want_rc:
        problems.append(f"exit {proc.returncode}, wanted {want_rc}")
    if want_text not in output:
        problems.append(f"output missing {want_text!r}")
    if problems:
        FAILURES.append(f"  {label}: {'; '.join(problems)}\n      got: {output.strip()[:300]}")
        print(f"FAIL  {label}")
    else:
        print(f"ok    {label}")


#: (label, tags, releases, grace, want_rc, want_text, baseline)
CASES = [
    (
        "every tag has a release",
        [("andon-v0.10.0", OLD), ("v0.1.0", OLD)],
        ["andon-v0.10.0", "v0.1.0"],
        60, 0, "0 unreleased",
    ),
    (
        "a plugin tag with no release, past the grace window",
        [("andon-v0.10.0", OLD), ("confab-v0.8.0", OLD)],
        ["andon-v0.10.0"],
        60, 1, "confab-v0.8.0",
    ),
    (
        "the same tag inside the grace window is not judged yet",
        [("andon-v0.10.0", OLD), ("confab-v0.8.0", JUST_NOW)],
        ["andon-v0.10.0"],
        60, 0, "grace window",
    ),
    (
        "grace 0 judges even a just-pushed tag",
        [("confab-v0.8.0", JUST_NOW)],
        [],
        0, 1, "confab-v0.8.0",
    ),
    (
        "werkstoff-cli's bare tag is judged too",
        [("v0.2.0", OLD)],
        [],
        60, 1, "v0.2.0",
    ),
    (
        "a non-release tag is not demanded a release",
        [("andon-v0.10.0", OLD), ("sandbox-snapshot", OLD)],
        ["andon-v0.10.0"],
        60, 0, "0 unreleased",
    ),
    (
        "no tags at all is an ERROR, not a pass",
        [],
        ["andon-v0.10.0"],
        60, 1, "refusing to report success on an empty set",
    ),
    (
        "tags exist but none are release-shaped: still an ERROR",
        [("nightly", OLD), ("latest", OLD)],
        ["andon-v0.10.0"],
        60, 1, "refusing to report success on an empty set",
    ),
    (
        "a tag line with no timestamp is an ERROR, not a silent skip",
        [],
        [],
        60, 1, "no unix timestamp",
    ),
    (
        "a draft-only release does not count as published",
        [("lehre-v0.3.0", OLD)],
        [],
        60, 1, "lehre-v0.3.0",
    ),
    (
        "a baselined legacy tag is exempt",
        [("andon-v0.4.0", OLD)],
        [],
        60, 0, "1 baselined",
        ["andon-v0.4.0"],
    ),
    (
        "a NEW unreleased tag still fails even with a baseline present",
        [("andon-v0.4.0", OLD), ("confab-v0.8.0", OLD)],
        [],
        60, 1, "confab-v0.8.0",
        ["andon-v0.4.0"],
    ),
    (
        "a baseline entry that gained a release is reported as stale",
        [("andon-v0.4.0", OLD)],
        ["andon-v0.4.0"],
        60, 1, "stale entr",
        ["andon-v0.4.0"],
    ),
]


def main() -> int:
    for case in CASES:
        label, tags, releases, grace, rc, text = case[:6]
        baseline = case[6] if len(case) > 6 else ()
        if label.startswith("a tag line with no timestamp"):
            # This one needs a malformed file, not a well-formed pair.
            with tempfile.TemporaryDirectory(prefix="tag-releases-") as box:
                bad = Path(box) / "tags.tsv"
                bad.write_text("andon-v0.10.0\n", encoding="utf-8")
                rel = Path(box) / "releases.json"
                rel.write_text("[]", encoding="utf-8")
                base = Path(box) / "baseline.txt"
                base.write_text("# fixture\n", encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, str(GUARD), "--tags-file", str(bad),
                     "--releases-file", str(rel), "--baseline", str(base),
                     "--now", str(NOW)],
                    capture_output=True, text=True,
                )
            out = proc.stdout + proc.stderr
            if proc.returncode == rc and text in out:
                print(f"ok    {label}")
            else:
                FAILURES.append(f"  {label}: exit {proc.returncode}, got: {out.strip()[:200]}")
                print(f"FAIL  {label}")
            continue
        run_case(label, tags, releases, grace, rc, text, baseline)

    if FAILURES:
        print(f"\n{len(FAILURES)} calibration failure(s):")
        print("\n".join(FAILURES))
        return 1
    print(f"\nlint-tag-releases.py is calibrated: {len(CASES)} case(s) behave as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
