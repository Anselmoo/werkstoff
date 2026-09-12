#!/usr/bin/env python3
"""Calibration for takt_guard.py — it must DENY and it must ALLOW.

takt was the only hook-bearing plugin in this repository without one of these,
and that is very likely why the staleness bug below survived: a marker was a
bare os.path.exists() check, so a marker left behind by an earlier run
satisfied a later run's beat forever. Nothing measured that, because nothing
measured anything.

Two groups of cases matter most and are marked in their names:

  BACKWARD  a declaration WITHOUT runId must behave byte-identically to the
            pre-runId guard. These are the cases that protect every existing
            user declaration, and they must pass unchanged.
  STALE     a declaration WITH runId must not accept a previous run's marker.
            This is the defect the field was added for.

Sabotage check (run it, do not assume it): make marker_path_for ignore run_id
by returning os.path.join(cwd, marker) unconditionally, and the STALE cases
must go red while the BACKWARD cases stay green. A guard whose test cannot
fail reports success every run and nobody looks again.

Run: python3 plugins/takt/hooks/test_takt_guard.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "takt_guard.py"

DENY = 2
ALLOW = 0

FAILURES: list[str] = []


def run(cwd: Path, tool: str, tool_input: dict, env: dict | None = None) -> tuple[int, str]:
    event = json.dumps({"cwd": str(cwd), "tool_name": tool, "tool_input": tool_input})
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=event,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **(env or {})},
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def declare(tmp: Path, beats: list, run_id: str | None = None) -> None:
    """Write .claude/takt.local.md. run_id=None omits the key entirely, which
    is the pre-runId shape every existing declaration in the wild has."""
    payload: dict = {}
    if run_id is not None:
        payload["runId"] = run_id
    payload["beats"] = beats
    body = "# beats\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    (tmp / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp / ".claude" / "takt.local.md").write_text(body)


UI_BEAT = {
    "id": "ui-before-council",
    "tools": ["Write", "Edit", "MultiEdit"],
    "paths": ["*.tsx", "src/ui/*"],
    "require": ".takt/council-done",
    "reason": "council runs before UI code.",
}

RUN_BEAT = {
    "id": "run-after-build",
    "tools": ["Skill", "Task", "Agent"],
    "skills": ["arbeitsplan-run"],
    "require": "built",
    "reason": "candidates must exist before one is landed.",
}


def check(name: str, got: int, want: int, out: str = "") -> None:
    if got == want:
        print(f"  ok   {name}")
    else:
        want_s = {DENY: "DENY", ALLOW: "ALLOW"}.get(want, want)
        got_s = {DENY: "DENY", ALLOW: "ALLOW"}.get(got, got)
        print(f"  FAIL {name}: wanted {want_s}, got {got_s}")
        if out:
            print(f"       {out.strip().splitlines()[:1]}")
        FAILURES.append(name)


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        # --- inertness -------------------------------------------------
        print("inertness")
        rc, _ = run(tmp, "Edit", {"file_path": "src/ui/App.tsx"})
        check("no declaration file at all -> ALLOW", rc, ALLOW)

        rc, _ = run(tmp, "Edit", {"file_path": "src/ui/App.tsx"}, {"TAKT_DISABLE_GUARD": "1"})
        check("escape hatch -> ALLOW", rc, ALLOW)

        # --- BACKWARD: no runId, behaviour must be unchanged -------------
        print("BACKWARD (declaration without runId)")
        declare(tmp, [UI_BEAT])

        rc, out = run(tmp, "Edit", {"file_path": "src/ui/App.tsx"})
        check("gated path, marker absent -> DENY", rc, DENY, out)
        if rc == DENY and "ui-before-council" not in out:
            FAILURES.append("deny message names the beat id")
            print("  FAIL deny message names the beat id")

        rc, _ = run(tmp, "Edit", {"file_path": "README.md"})
        check("ungated path -> ALLOW", rc, ALLOW)

        rc, _ = run(tmp, "Read", {"file_path": "src/ui/App.tsx"})
        check("tool outside the beat -> ALLOW", rc, ALLOW)

        (tmp / ".takt").mkdir(exist_ok=True)
        (tmp / ".takt" / "council-done").write_text("")
        rc, _ = run(tmp, "Edit", {"file_path": "src/ui/App.tsx"})
        check("marker at the OLD flat path -> ALLOW", rc, ALLOW)

        # No resolvable path at all. `edits` as a STRING is the trap the guard
        # documents: a truthiness check would iterate its characters, making the
        # target set non-empty with junk, so the fail-closed branch never fires.
        # This asserts the branch fires -- and it fires BEFORE the marker check,
        # so an existing marker must not rescue an uncheckable call.
        rc, out = run(tmp, "Edit", {"edits": "notalist"})
        check("indeterminate payload -> DENY (fail-closed)", rc, DENY, out)

        # --- STALE: runId namespaces the marker -------------------------
        print("STALE (declaration with runId)")
        declare(tmp, [RUN_BEAT], run_id="ap-run-2")

        # Plant a stale "built" marker at EVERY location an earlier run could
        # plausibly have left one: the bare cwd-relative path the pre-runId
        # guard would resolve to, the conventional .takt/ directory, and a
        # previous run's own namespace. If any of these satisfies run-2's beat,
        # the staleness bug is still live.
        #
        # Planting all three is what makes these cases real. An earlier draft
        # planted only .takt/built, and the sabotage run proved that case green
        # with the fix removed -- because a bare `require: "built"` resolves to
        # <cwd>/built, which nothing had created. It was passing for the wrong
        # reason, which is the failure mode sabotage testing exists to catch.
        (tmp / "built").write_text("")
        (tmp / ".takt" / "built").write_text("")
        (tmp / ".takt" / "ap-run-1").mkdir(parents=True, exist_ok=True)
        (tmp / ".takt" / "ap-run-1" / "built").write_text("")
        rc, out = run(tmp, "Skill", {"skill": "arbeitsplan-run"})
        check("no previous run's marker satisfies run-2 -> DENY", rc, DENY, out)

        (tmp / ".takt" / "ap-run-2").mkdir(parents=True, exist_ok=True)
        (tmp / ".takt" / "ap-run-2" / "built").write_text("")
        rc, _ = run(tmp, "Skill", {"skill": "arbeitsplan-run"})
        check("this run's namespaced marker satisfies -> ALLOW", rc, ALLOW)

        declare(tmp, [RUN_BEAT], run_id="ap-run-3")
        rc, out = run(tmp, "Skill", {"skill": "arbeitsplan-run"})
        check("a NEW runId invalidates run-2's marker -> DENY", rc, DENY, out)

        rc, _ = run(tmp, "Skill", {"skill": "some-other-skill"})
        check("unlisted skill -> ALLOW", rc, ALLOW)

        rc, out = run(tmp, "Skill", {})
        check("dispatch with no resolvable name -> DENY", rc, DENY, out)

        # --- REPO-LEVEL markers coexist with a runId --------------------
        # One compiled declaration must carry BOTH a per-run marker and a
        # durable repo-level one. A marker already under .takt/ is repo-level
        # and must NOT be namespaced, or a fact that is true reads as false in
        # every run after the one that recorded it.
        print("REPO-LEVEL (a .takt/ marker is not namespaced)")
        MIXED = [
            {"id": "per-run", "tools": ["Skill"], "skills": ["ap-run"],
             "require": "built", "reason": "per-run"},
            {"id": "repo-level", "tools": ["Skill"], "skills": ["andon-loop"],
             "require": ".takt/transform-brief-written", "reason": "repo-level"},
        ]
        declare(tmp, MIXED, run_id="ap-run-7")
        (tmp / ".takt").mkdir(exist_ok=True)
        rc, out = run(tmp, "Skill", {"skill": "andon-loop"})
        check("repo-level marker absent -> DENY", rc, DENY, out)
        (tmp / ".takt" / "transform-brief-written").write_text("")
        rc, _ = run(tmp, "Skill", {"skill": "andon-loop"})
        check("repo-level marker present -> ALLOW even under a runId", rc, ALLOW)
        rc, out = run(tmp, "Skill", {"skill": "ap-run"})
        check("per-run marker in the SAME declaration still namespaced -> DENY", rc, DENY, out)
        (tmp / ".takt" / "ap-run-7").mkdir(parents=True, exist_ok=True)
        (tmp / ".takt" / "ap-run-7" / "built").write_text("")
        rc, _ = run(tmp, "Skill", {"skill": "ap-run"})
        check("both kinds satisfied in one declaration -> ALLOW", rc, ALLOW)

        # --- requireKind: what SHAPE satisfies a beat --------------------
        # The bypass this closes: with plain os.path.exists, `mkdir <path>`
        # opens any gate. Harmless while markers were empty touch-files;
        # a one-command bypass once a beat gates on a real artifact.
        print("REQUIREKIND (file / dir / any)")
        ART = {"id": "artifact-gate", "tools": ["Skill"], "skills": ["consumer"],
               "require": "analysis/x/brief.md", "requireKind": "file", "reason": "artifact gate"}
        declare(tmp, [ART])
        (tmp / "analysis" / "x").mkdir(parents=True, exist_ok=True)
        rc, out = run(tmp, "Skill", {"skill": "consumer"})
        check("file evidence absent -> DENY", rc, DENY, out)

        # A DIRECTORY at the artifact path must NOT satisfy a file gate.
        (tmp / "analysis" / "x" / "brief.md").mkdir(parents=True, exist_ok=True)
        rc, out = run(tmp, "Skill", {"skill": "consumer"})
        check("a DIRECTORY does not satisfy requireKind file -> DENY", rc, DENY, out)

        (tmp / "analysis" / "x" / "brief.md").rmdir()
        (tmp / "analysis" / "x" / "brief.md").write_text("# brief\n")
        rc, _ = run(tmp, "Skill", {"skill": "consumer"})
        check("a real FILE satisfies it -> ALLOW", rc, ALLOW)

        # Omitted requireKind must behave exactly as before the field existed.
        BARE = dict(ART)
        BARE.pop("requireKind")
        BARE["require"] = "analysis/x/dirish"
        declare(tmp, [BARE])
        (tmp / "analysis" / "x" / "dirish").mkdir(parents=True, exist_ok=True)
        rc, _ = run(tmp, "Skill", {"skill": "consumer"})
        check("omitted requireKind is exists() -- a dir satisfies -> ALLOW", rc, ALLOW)

        DIRK = dict(BARE)
        DIRK["requireKind"] = "dir"
        declare(tmp, [DIRK])
        rc, _ = run(tmp, "Skill", {"skill": "consumer"})
        check("requireKind dir accepts a directory -> ALLOW", rc, ALLOW)

        BADK = dict(BARE)
        BADK["requireKind"] = "socket"
        declare(tmp, [BADK])
        rc, out = run(tmp, "Skill", {"skill": "consumer"})
        check("an unknown requireKind -> DENY (fail-closed)", rc, DENY, out)

        # --- runId charset is fail-closed -------------------------------
        print("runId charset")
        for bad in ("../escape", "a/b", "a..b", 17):
            declare(tmp, [RUN_BEAT], run_id=bad)
            rc, out = run(tmp, "Skill", {"skill": "arbeitsplan-run"})
            check(f"invalid runId {bad!r} -> DENY", rc, DENY, out)

        # --- the deny protocol itself -----------------------------------
        print("deny protocol")
        declare(tmp, [RUN_BEAT], run_id="ap-run-9")
        proc = subprocess.run(
            [sys.executable, str(GUARD)],
            input=json.dumps(
                {"cwd": str(tmp), "tool_name": "Skill", "tool_input": {"skill": "arbeitsplan-run"}}
            ),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin"},
        )
        ok = proc.returncode == DENY
        try:
            payload = json.loads(proc.stdout)["hookSpecificOutput"]
        except Exception:
            payload = {}
        for field, want in (
            ("hookEventName", "PreToolUse"),
            ("permissionDecision", "deny"),
        ):
            if payload.get(field) != want:
                ok = False
        if not payload.get("permissionDecisionReason"):
            ok = False
        if not proc.stderr.strip():
            ok = False
        check("exit 2 + stdout JSON (hookEventName/decision/reason) + stderr", ALLOW if ok else DENY, ALLOW)
        if not ok:
            print(f"       stdout={proc.stdout[:200]!r} stderr={proc.stderr[:120]!r}")
        if "TAKT_DISABLE_GUARD" not in (proc.stdout + proc.stderr):
            FAILURES.append("deny message names the escape hatch")
            print("  FAIL deny message names the escape hatch")

    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("all takt guard cases passed (denies AND allows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
