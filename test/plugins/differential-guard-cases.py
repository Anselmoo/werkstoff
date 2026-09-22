#!/usr/bin/env python3
"""Gate: a guard fix must CHANGE one decision and PRESERVE another.

A fix and a blanket rewrite of the rule are textually similar in a diff. What
separates them is whether some OTHER input still gets the answer it had before.
So every guard fix in this repo ships a PAIR of cases: one whose decision
changes, and one that must not move.

Which way round depends on the defect, and both directions are real here:

    an OVER-DENIAL fix (the guard refused too much -- PR #95)
        old=deny   new=allow   the defect, gone
        old=deny   new=deny    the rule the guard is actually for, intact

    a FAIL-OPEN fix (the guard allowed too much -- PR #97)
        old=allow  new=deny    the hole, closed
        old=allow  new=allow   and not everything gated instead

Shipping only the first half is a loosening, or a blanket gate, wearing a fix's
clothing. This script is what makes that a check rather than a sentence -- the
same move `test/plugins/lint-oracles.sh` makes for silent-failure regex forms.

This docstring originally described only the first shape, because the first five
fixes it graded were all over-denial. load_case then REFUSED the first
allow/allow case written against it. The lesson is recorded there too: what makes
a pair a pair is that one case changes and one does not; the polarity is a
property of the defect, not of this file.

HOW "OLD" IS OBTAINED, AND WHY THE BASE IS PINNED PER CASE
----------------------------------------------------------
The old guard is materialised from git: the whole plugin directory is extracted
at the case's declared `base` commit, so a hook that computes its own plugin
root from `__file__` (befund's guard_target_edit.py does, to find scripts/lib/)
still resolves its imports. Extracting the single file would silently change
what it can import -- and a hook whose import fails DENIES EVERY CALL, which
would read as "old=deny" for entirely the wrong reason.

`base` is a pinned SHA in each case, never a moving ref like `main`. A moving
base goes vacuous the moment the fix lands -- old and new become the same file,
every case trivially agrees with itself, and the check reports success forever
while testing nothing. That is exactly the failure CLAUDE.md records for
`rrt artifacts --check` comparing an artifact to a lock snapshotted while it was
already stale. A pinned SHA keeps the case meaning what it meant the day it was
written.

CASE LAYOUT
-----------
    test/plugins/fixtures/guard-differential/<case-id>/
        _PAIR           required. key=value lines:
                            guard=plugins/<p>/.../<guard>.py   repo-relative
                            base=<sha>                          FULL 40-char sha,
                                                                pinned, never a ref
                            old=deny|allow
                            new=deny|allow
                            issue=<n>                           optional, for the report
        _EVENT.json     required. the PreToolUse payload; "cwd" is injected, and
                        {REPO} / {PARENT} in any string are expanded to the probe
                        repo and its parent.
        _EXPECTED.md    required. prose: why THIS pair is the right pair.
        _ENV            optional. key=value lines, set for both runs.
        _SETUP.py       optional. python script run as `_SETUP.py <repo> <repo-parent>`
                        before _GIT_INIT, for anything that must exist OUTSIDE
                        the probe repo -- the fixture directory itself becomes
                        the repo, so a sibling path cannot be a committed file.
        _GIT_INIT       optional. git init + commit the probe copy before running,
                        for any guard that checks tree cleanliness. Same marker
                        convention as verify-hooks-deny.py.
    Everything else in the directory is the probe repository.

Exit: 0 if every case's (old, new) pair is exactly as declared; 1 otherwise.
A case whose guard exits something other than 0 or 2 is an ERROR, not a FAIL --
the run never happened, and a tally that cannot tell those apart is the thing
CLAUDE.md warns about.

Usage:
    differential-guard-cases.py [<case-id> ...] [--force-base REF] [--selftest]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CASES_ROOT = REPO / "test" / "plugins" / "fixtures" / "guard-differential"

ALLOW, DENY = 0, 2
WORD = {ALLOW: "allow", DENY: "deny"}
CODE = {"allow": ALLOW, "deny": DENY}

MARKERS = {"_PAIR", "_EVENT.json", "_EXPECTED.md", "_ENV", "_GIT_INIT", "_SETUP.py"}


class CaseError(Exception):
    """The case itself is malformed -- distinct from the case failing."""


def read_kv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise CaseError(f"{path}: line is not key=value: {raw!r}")
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def load_case(case_dir: Path) -> dict:
    pair_file = case_dir / "_PAIR"
    if not pair_file.is_file():
        raise CaseError(f"{case_dir.name}: no _PAIR file")
    pair = read_kv(pair_file)

    for key in ("guard", "base", "old", "new"):
        if key not in pair:
            raise CaseError(f"{case_dir.name}: _PAIR is missing {key}=")
    # The base must be the FULL 40-char sha, not an abbreviation. CI checks out
    # shallow, so the base is usually absent and has to be fetched -- and
    # `git fetch origin <short-sha>` fails with "couldn't find remote ref",
    # while the full sha fetches fine. Caught by running the suite against a
    # real --depth=1 clone; every case errored, which is the right failure but
    # an obscure one to debug from. Rejecting it here names the cause instead.
    if not re.fullmatch(r"[0-9a-f]{40}", pair["base"]):
        raise CaseError(
            f"{case_dir.name}: base={pair['base']!r} is not a full 40-character sha. "
            "An abbreviated sha cannot be fetched into a shallow clone, so this case "
            "would ERROR in CI while passing locally. Use `git rev-parse <ref>`."
        )
    for key in ("old", "new"):
        if pair[key] not in CODE:
            raise CaseError(f"{case_dir.name}: {key}={pair[key]!r}, expected allow or deny")
    # An old == new case is the ANTI-OVER-REACH half of a pair, and it is valid
    # in BOTH polarities. This originally refused allow/allow, on the assumption
    # that every guard fix loosens -- true of the over-denial bugs in PR #95,
    # where the half that must not move is a deny. It is exactly wrong for a
    # fail-OPEN fix, which adds denials: there the half that must not move is an
    # allow, proving the fix did not start gating everything. Rejecting it forced
    # the first such case to be written as its own opposite.
    #
    # What makes a pair a pair is that one case CHANGES and one does not; which
    # way round depends on the defect, not on this file's assumptions.

    if not (case_dir / "_EVENT.json").is_file():
        raise CaseError(f"{case_dir.name}: no _EVENT.json")
    if not (case_dir / "_EXPECTED.md").is_file():
        raise CaseError(
            f"{case_dir.name}: no _EXPECTED.md -- a pair nobody explained is a pair "
            "nobody can review"
        )

    env_file = case_dir / "_ENV"
    return {
        "id": case_dir.name,
        "dir": case_dir,
        "guard": pair["guard"],
        "base": pair["base"],
        "old": CODE[pair["old"]],
        "new": CODE[pair["new"]],
        "issue": pair.get("issue", ""),
        "env": read_kv(env_file) if env_file.is_file() else {},
        "git_init": (case_dir / "_GIT_INIT").is_file(),
        "event": json.loads((case_dir / "_EVENT.json").read_text(encoding="utf-8")),
    }


def plugin_dir_of(guard: str) -> str:
    parts = Path(guard).parts
    if len(parts) < 2 or parts[0] != "plugins":
        raise CaseError(f"guard={guard!r} is not under plugins/<name>/")
    return f"{parts[0]}/{parts[1]}"


def _archive(repo: Path, base: str, plugin: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), "archive", base, "--", plugin],
        capture_output=True, check=True,
    ).stdout


def materialise_old(repo: Path, guard: str, base: str, dest: Path) -> Path:
    """Extract the guard's WHOLE plugin at `base`, so its imports still resolve."""
    plugin = plugin_dir_of(guard)
    try:
        archive = _archive(repo, base, plugin)
    except subprocess.CalledProcessError:
        # CI checks out shallow (fetch-depth: 1), so a pinned base commit is
        # simply absent rather than wrong. Fetch it once and retry. This runs
        # only after a real failure, so the normal path makes no network call --
        # and if the fetch also fails the case still reports ERROR, never a
        # silent pass.
        try:
            subprocess.run(
                ["git", "-C", str(repo), "fetch", "--quiet", "--depth=1", "origin", base],
                capture_output=True, check=True,
            )
            archive = _archive(repo, base, plugin)
        except subprocess.CalledProcessError as exc:
            raise CaseError(
                f"cannot read {plugin} at base {base!r} (and fetching it failed): "
                f"{exc.stderr.decode(errors='replace').strip()}"
            ) from exc

    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    # git archive preserves repo-root-relative paths, so the tree lands at
    # <dest>/plugins/<name>/... -- the guard keeps its position inside its own
    # plugin, which is the whole point: befund's guard derives its plugin root
    # from __file__ to put scripts/ on sys.path.
    old_guard = dest / guard
    if not old_guard.is_file():
        raise CaseError(f"{guard} does not exist at base {base!r}")
    return old_guard


def untracked_dirs(case_dir: Path) -> list[str]:
    """Directories in the case that git will not carry into a fresh checkout.

    Git does not store empty directories. A guard whose activation gate is
    `isdir(cwd/analysis/<plugin>)` therefore goes INERT in CI while passing
    locally, and every case for it allows both revisions and proves nothing.
    That is not hypothetical: all three zeugnis cases shipped this way and were
    caught only by running the suite against a real --depth=1 clone.

    So the case's own layout is checked before it is trusted. A directory with
    no tracked file anywhere beneath it is reported, and the case ERRORs.
    """
    try:
        tracked = subprocess.run(
            ["git", "-C", str(case_dir), "ls-files"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    except subprocess.CalledProcessError:
        return []  # not a git checkout (the selftest's planted cases); nothing to check
    if not tracked:
        # The whole case is untracked -- it is being authored right now, and
        # every directory in it would be reported. Say nothing; the case cannot
        # reach CI in this state anyway.
        return []
    carried = {str(Path(f).parent) for f in tracked}
    carried |= {str(parent) for f in tracked for parent in Path(f).parents}
    on_disk = {
        str(d.relative_to(case_dir))
        for d in case_dir.rglob("*")
        if d.is_dir() and not d.is_symlink()
    }
    return sorted(on_disk - carried)


def probe_repo(case: dict, workdir: Path) -> Path:
    repo = workdir / "probe"
    repo.mkdir(parents=True)
    for child in case["dir"].iterdir():
        if child.name in MARKERS:
            continue
        target = repo / child.name
        # symlinks=True / follow_symlinks=False are load-bearing, not tidiness.
        # shutil's defaults DEREFERENCE: a committed symlink arrives in the probe
        # copy as a plain file, so a case built to prove a symlink is handled
        # correctly would silently prove nothing -- is_symlink() is False before
        # the guard ever runs. Found by a builder trying to write exactly such a
        # case, after three constructions all came back dereferenced.
        if child.is_dir() and not child.is_symlink():
            shutil.copytree(child, target, symlinks=True)
        else:
            shutil.copy2(child, target, follow_symlinks=False)
    setup = case["dir"] / "_SETUP.py"
    if setup.is_file():
        # Run with the probe repo as argv[1] and its PARENT as argv[2]. A case
        # that needs something outside the repo -- a sibling directory, a symlink
        # parked outside pointing back in -- cannot express it as a committed
        # file, because the fixture directory IS the repo. This is the hook for
        # that, and it runs before _GIT_INIT so anything it creates inside the
        # repo is committed too.
        subprocess.run(
            [sys.executable, str(setup), str(repo), str(repo.parent)],
            capture_output=True, check=True,
        )
    if case["git_init"]:
        run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True)  # noqa: E731
        run("init", "-q")
        run("config", "user.email", "differential@test.invalid")
        run("config", "user.name", "differential")
        run("add", "-A")
        run("commit", "-qm", "fixture")
    return repo


def _expand(value, cwd: Path):
    """Substitute {REPO} / {PARENT} in string leaves of the event payload.

    The probe repo is a fresh temp directory on every run, so a case that must
    name a path OUTSIDE it (a sibling file, a symlink parked next to it) has no
    literal to write into _EVENT.json. These two tokens are that literal.
    """
    if isinstance(value, str):
        return value.replace("{REPO}", str(cwd)).replace("{PARENT}", str(cwd.parent))
    if isinstance(value, dict):
        return {k: _expand(v, cwd) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v, cwd) for v in value]
    return value


def run_guard(guard: Path, cwd: Path, event: dict, env_extra: dict[str, str]) -> int:
    payload = _expand(dict(event), cwd)
    payload["cwd"] = str(cwd)
    env = {**os.environ, **env_extra}
    result = subprocess.run(
        [sys.executable, str(guard)],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return result.returncode


def verdict(case: dict, got_old: int, got_new: int) -> tuple[str, str]:
    """(status, detail). status is one of ok / FAIL / ERROR."""
    for label, got in (("old", got_old), ("new", got_new)):
        if got not in WORD:
            return "ERROR", f"{label} guard exited {got}, not 0 or 2 -- the run never happened"

    if got_old == case["old"] and got_new == case["new"]:
        return "ok", ""

    parts = []
    if got_old != case["old"]:
        parts.append(
            f"old expected {WORD[case['old']]}, got {WORD[got_old]}"
            + (" -- the defect is not present at base, so this case proves nothing"
               if got_old == ALLOW and case["old"] == DENY else "")
        )
    if got_new != case["new"]:
        parts.append(
            f"new expected {WORD[case['new']]}, got {WORD[got_new]}"
            + (" -- THE FIX LOOSENED A RULE IT WAS MEANT TO KEEP"
               if got_new == ALLOW and case["new"] == DENY else "")
        )
    return "FAIL", "; ".join(parts)


def execute(case: dict, repo: Path, force_base: str | None) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        base = force_base or case["base"]
        try:
            old_guard = materialise_old(repo, case["guard"], base, work / "old")
        except CaseError as exc:
            return "ERROR", str(exc)
        new_guard = repo / case["guard"]
        if not new_guard.is_file():
            return "ERROR", f"{case['guard']} does not exist in the working tree"

        empty = untracked_dirs(case["dir"])
        if empty:
            return "ERROR", (
                f"git will not carry {', '.join(empty)} into a fresh checkout (empty "
                "directories are not tracked), so this case tests something CI never "
                "sees. Put a tracked file in it."
            )

        got_old = run_guard(old_guard, probe_repo(case, work / "a"), case["event"], case["env"])
        got_new = run_guard(new_guard, probe_repo(case, work / "b"), case["event"], case["env"])
    return verdict(case, got_old, got_new)


def discover(only: list[str]) -> list[Path]:
    if not CASES_ROOT.is_dir():
        return []
    dirs = sorted(d for d in CASES_ROOT.iterdir() if d.is_dir())
    if only:
        wanted = set(only)
        found = {d.name for d in dirs}
        missing = wanted - found
        if missing:
            raise CaseError(f"no such case(s): {', '.join(sorted(missing))}")
        dirs = [d for d in dirs if d.name in wanted]
    return dirs


def report(rows: list[tuple[str, str, str, str]]) -> int:
    if not rows:
        print("no differential cases found -- nothing was checked")
        return 1
    width = max(len(r[0]) for r in rows)
    print(f"{'case'.ljust(width)}  {'issue':6}  {'verdict':8}  detail")
    print("-" * (width + 32))
    for name, issue, status, detail in rows:
        print(f"{name.ljust(width)}  {issue:6}  {status:8}  {detail}")
    fails = sum(1 for r in rows if r[2] != "ok")
    print()
    print(
        f"{len(rows)} case(s), {fails} not ok. A fix ships a PAIR: one case whose "
        "decision CHANGES, and one that must not move. Which way round depends on the "
        "defect -- an over-denial fix keeps a deny, a fail-open fix keeps an allow. "
        "Only the second half separates a fix from a blanket loosening or a blanket gate."
    )
    return 1 if fails else 0


# --------------------------------------------------------------------------
# self-test: this instrument asserts itself before anyone trusts its verdict
# --------------------------------------------------------------------------

ALWAYS_DENY = '''#!/usr/bin/env python3
import json, sys
sys.stdin.read()
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
      "permissionDecision": "deny", "permissionDecisionReason": "planted"}}))
print("planted", file=sys.stderr)
sys.exit(2)
'''

OUTSIDE_AWARE = '''#!/usr/bin/env python3
"""Planted 'fixed' guard: allows a target outside cwd, still denies inside."""
import json, os, sys
event = json.loads(sys.stdin.read())
cwd = os.path.realpath(event["cwd"])
target = event["tool_input"]["file_path"]
target = os.path.realpath(target if os.path.isabs(target) else os.path.join(cwd, target))
if not (target == cwd or target.startswith(cwd + os.sep)):
    sys.exit(0)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
      "permissionDecision": "deny", "permissionDecisionReason": "planted"}}))
print("planted", file=sys.stderr)
sys.exit(2)
'''

ALWAYS_BROKEN = '''#!/usr/bin/env python3
import sys
sys.exit(7)
'''


def _plant_repo(root: Path) -> str:
    """A throwaway git repo: guard at base = always deny, at HEAD = outside-aware."""
    guard = root / "plugins" / "planted" / "hooks" / "planted_guard.py"
    guard.parent.mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True, check=True)  # noqa: E731
    git("init", "-q")
    git("config", "user.email", "s@t.invalid")
    git("config", "user.name", "s")
    guard.write_text(ALWAYS_DENY)
    git("add", "-A")
    git("commit", "-qm", "base")
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    guard.write_text(OUTSIDE_AWARE)
    # Commit the fixed guard too, so HEAD models "the fix has landed". Without
    # this, --force-base HEAD would still hand back the OLD guard and the
    # vacuity check below would pass while proving nothing -- which is exactly
    # the failure that check exists to catch, so it caught it here first.
    git("add", "-A")
    git("commit", "-qm", "fix")
    return base


def _plant_case(root: Path, name: str, target: str, old: str, new: str, base: str) -> Path:
    case = root / "cases" / name
    (case / "src").mkdir(parents=True)
    (case / "src" / "api.py").write_text("x = 1\n")
    (case / "_PAIR").write_text(
        f"guard=plugins/planted/hooks/planted_guard.py\nbase={base}\nold={old}\nnew={new}\n"
    )
    (case / "_EVENT.json").write_text(
        json.dumps({"tool_name": "Write", "tool_input": {"file_path": target}})
    )
    (case / "_EXPECTED.md").write_text("planted\n")
    return case


def selftest() -> int:
    """Eight planted checks. Each names the specific way this script could lie."""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, why: str = "") -> None:
        checks.append((name, passed, why))

    # 1-4: the verdict table, independent of any subprocess.
    fake = {"old": DENY, "new": ALLOW}
    check("verdict: declared pair met -> ok", verdict(fake, DENY, ALLOW)[0] == "ok")
    check("verdict: new still denies -> FAIL", verdict(fake, DENY, DENY)[0] == "FAIL")
    check("verdict: old did not deny -> FAIL", verdict(fake, ALLOW, ALLOW)[0] == "FAIL")
    check("verdict: non-0/2 exit -> ERROR, not FAIL", verdict(fake, DENY, 7)[0] == "ERROR")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = _plant_repo(root)
        outside = str(root / "elsewhere" / "scratch.md")

        # 5: end to end, a real pair over a real two-commit history.
        good = _plant_case(root, "good", outside, "deny", "allow", base)
        status, detail = execute(load_case(good), root, None)
        check("end-to-end: genuine fix pair -> ok", status == "ok", detail)

        # 6: the anti-loosening half must actually hold.
        keep = _plant_case(root, "keep", "src/api.py", "deny", "deny", base)
        status, detail = execute(load_case(keep), root, None)
        check("end-to-end: in-repo target still denied -> ok", status == "ok", detail)

        # 7: THE CENTRAL ONE. Force base=HEAD so old and new are the same file.
        # Every old!=new case MUST go red. If this passes, the script is not
        # comparing revisions at all and every verdict it has ever printed is void.
        status, detail = execute(load_case(good), root, "HEAD")
        check(
            "vacuity: base==HEAD makes a deny/allow case FAIL",
            status == "FAIL",
            f"got {status} -- the runner is not distinguishing revisions",
        )

        # 8: a guard that crashes is ERROR, never a silent pass.
        (root / "plugins" / "planted" / "hooks" / "planted_guard.py").write_text(ALWAYS_BROKEN)
        status, detail = execute(load_case(good), root, None)
        check("broken guard -> ERROR, not ok", status == "ERROR", f"got {status}")

    width = max(len(c[0]) for c in checks)
    for name, passed, why in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name.ljust(width)}  {why if not passed else ''}")
    bad = sum(1 for c in checks if not c[1])
    print()
    print(f"selftest: {len(checks)} planted checks, {bad} failed.")
    if bad:
        print("An instrument that cannot fail reports success every run and nobody looks again.")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case", nargs="*", help="case ids to run (default: all)")
    ap.add_argument("--force-base", help="override every case's pinned base (selftest/debug only)")
    ap.add_argument("--selftest", action="store_true", help="run the planted-defect calibration")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    try:
        dirs = discover(args.case)
        rows = []
        for case_dir in dirs:
            try:
                case = load_case(case_dir)
            except (CaseError, json.JSONDecodeError) as exc:
                rows.append((case_dir.name, "", "ERROR", str(exc)))
                continue
            status, detail = execute(case, REPO, args.force_base)
            rows.append((case["id"], case["issue"], status, detail))
    except CaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return report(rows)


if __name__ == "__main__":
    sys.exit(main())
