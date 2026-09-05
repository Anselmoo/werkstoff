#!/usr/bin/env python3
"""Guard against a release tag that exists with no GitHub Release behind it.

This repo tags and publishes in two different places, and BOTH can push a tag
that publishes nothing without reporting an error:

    plugins        `<group>-vX.Y.Z` -> plugin-release.yml
    werkstoff-cli  `vX.Y.Z`         -> cicd.yml (PyPI + GitHub release)

Both are `on: push: tags`, and a push made with the default GITHUB_TOKEN
creates no events at all -- so for two months every tag auto-version-bump.yml
created was a tag nobody released. Six of them (andon-v0.9.0, compass-v0.5.0,
confab-v0.7.0, cupertino-v0.7.0, lehre-v0.2.0, self-assess-v0.7.0) sat that way
from 2026-09-03 to 2026-09-05 with a green CI the whole time. auto-version-bump
now CALLS plugin-release.yml rather than relying on the tag push, but nothing
was checking the invariant itself -- and the cicd.yml half is still exposed.

The invariant: every release-shaped tag older than the grace period has a
GitHub Release whose tag_name matches it.

Grace period, default 60 minutes: a tag is pushed before the release job that
publishes it has finished, and this check runs on pushes to main. Without a
window it would go red on every release for a few minutes and be tuned out --
which is how a real check becomes decoration.

FAILS LOUDLY IF IT CANNOT SEE WHAT IT GRADES. No tags found, no releases
endpoint, an HTTP error: all exit 1 with the reason. A "0 problems" that was
really "0 inputs" is the failure shape this repo keeps getting bitten by.

KNOWN-UNRELEASED BASELINE. 21 tags from before 2026-08 never got a release
either, and a guard that is red on the day it lands gets ignored on the day
after. `tag-releases-baseline.txt` names them explicitly -- a list, not a date
cutoff, because a cutoff silently forgives anything that lands on the wrong
side of it. A baseline entry that HAS a release is reported as stale so the
list can only shrink.

Usage:
    python3 test/plugins/lint-tag-releases.py
    python3 test/plugins/lint-tag-releases.py --grace-minutes 0
    python3 test/plugins/lint-tag-releases.py \
        --tags-file tags.tsv --releases-file releases.json   # offline, for tests

Auth: uses GH_TOKEN / GITHUB_TOKEN if set, otherwise unauthenticated (this
repo is public). Exit: 0 every tag has a release; 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
import time
import urllib.error
import urllib.request

#: `andon-v0.10.0` and `v0.1.0`, and nothing else. Explicit, never a dot-star:
#: a pattern loose enough to match anything silently matches the wrong thing.
TAG_RE = re.compile(r"^(?:[A-Za-z0-9][A-Za-z0-9._-]*-)?v[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*$")

API = "https://api.github.com"


class TagReleaseLintError(Exception):
    """A structural problem that must fail loudly rather than return empty."""


def repo_slug() -> str:
    env = os.environ.get("GITHUB_REPOSITORY")
    if env:
        return env
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TagReleaseLintError(f"cannot determine the repository: {exc}") from exc
    match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        raise TagReleaseLintError(f"cannot parse an owner/repo out of remote url '{url}'")
    return match.group(1)


def tags_from_git() -> list[tuple[str, int]]:
    try:
        out = subprocess.run(
            [
                "git", "for-each-ref",
                "--format=%(refname:strip=2)\t%(creatordate:unix)",
                "refs/tags",
            ],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TagReleaseLintError(f"cannot list tags: {exc}") from exc
    return parse_tags(out)


def parse_tags(text: str) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        name, _, when = line.partition("\t")
        if not when.strip().isdigit():
            raise TagReleaseLintError(f"tag line has no unix timestamp: {line!r}")
        rows.append((name.strip(), int(when.strip())))
    return rows


def releases_from_api(slug: str) -> set[str]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "werkstoff-lint-tag-releases",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    found: set[str] = set()
    for page in range(1, 21):  # 2000 releases is far past this repo's scale
        url = f"{API}/repos/{slug}/releases?per_page=100&page={page}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                batch = json.load(response)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise TagReleaseLintError(
                f"cannot read releases for {slug}: {exc} -- refusing to report success "
                f"on a list this check never actually saw"
            ) from exc
        if not batch:
            break
        found.update(r["tag_name"] for r in batch if not r.get("draft"))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grace-minutes", type=int, default=60)
    parser.add_argument(
        "--baseline",
        default=str(Path(__file__).with_name("tag-releases-baseline.txt")),
        help="file of known-unreleased tags to exempt (one per line, # comments)",
    )
    parser.add_argument("--tags-file", help="TSV of '<tag>\\t<unix time>' instead of git")
    parser.add_argument("--releases-file", help="JSON array of tag_name strings instead of the API")
    parser.add_argument("--now", type=int, default=None, help="override the clock, for tests")
    args = parser.parse_args()

    now = args.now if args.now is not None else int(time.time())

    try:
        if args.tags_file:
            with open(args.tags_file, encoding="utf-8") as handle:
                tags = parse_tags(handle.read())
        else:
            tags = tags_from_git()

        release_shaped = [(name, when) for name, when in tags if TAG_RE.match(name)]
        if not release_shaped:
            raise TagReleaseLintError(
                f"no release-shaped tags found among {len(tags)} tag(s) -- refusing to "
                f"report success on an empty set (a shallow clone with no tags looks "
                f"exactly like a repo that has never released)"
            )

        if args.releases_file:
            with open(args.releases_file, encoding="utf-8") as handle:
                releases = set(json.load(handle))
        else:
            releases = releases_from_api(repo_slug())
    except (TagReleaseLintError, OSError, json.JSONDecodeError) as exc:
        print(f"lint-tag-releases: {exc}", file=sys.stderr)
        return 1

    baseline: set[str] = set()
    baseline_path = Path(args.baseline)
    if baseline_path.exists():
        baseline = {
            line.strip()
            for line in baseline_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    cutoff = now - args.grace_minutes * 60
    missing = sorted(
        name
        for name, when in release_shaped
        if when <= cutoff and name not in releases and name not in baseline
    )
    # A baseline entry that now has a release is stale. Reported rather than
    # ignored, for the same reason lint-release-wiring.py reports its stale
    # names: an exemption list nobody ever removes from is an exemption list
    # that eventually hides a real failure.
    stale = sorted(name for name in baseline if name in releases)
    waiting = sorted(
        name for name, when in release_shaped if when > cutoff and name not in releases
    )

    for name in waiting:
        print(f"  (within the {args.grace_minutes}m grace window, not judged: {name})")

    if stale:
        print(
            f"{len(stale)} stale entr(y/ies) in {baseline_path.name} -- "
            f"these now HAVE a release:"
        )
        for name in stale:
            print(f"  {name}")
        print("\nRemove them from the baseline; it is only allowed to shrink.")

    if missing:
        print(f"{len(missing)} tag(s) published with no GitHub Release:")
        for name in missing:
            print(f"  {name}")
        print(
            "\nA tag with no release means the publish never ran. Plugin tags are "
            "released by auto-version-bump.yml calling plugin-release.yml; recover one "
            "by hand with `gh workflow run plugin-release.yml -f tag=<tag>`. A bare "
            "`vX.Y.Z` tag is werkstoff-cli's and belongs to cicd.yml, which can only be "
            "reached by a real tag push -- re-push that tag from a developer machine, "
            "one tag per push."
        )
        return 1

    if stale:
        return 1

    print(
        f"checked {len(release_shaped)} release tag(s) against {len(releases)} "
        f"GitHub Release(s): 0 unreleased"
        + (f", {len(baseline)} baselined" if baseline else "")
        + (f" ({len(waiting)} inside the grace window)" if waiting else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
