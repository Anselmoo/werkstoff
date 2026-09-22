#!/usr/bin/env python3
"""Tests for the andon PreToolUse enforcement hook.

Every case is a property the hook must hold regardless of what any model does —
that is the entire point of it being a hook. Run: python3 test_andon_enforce.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).parent / "andon_enforce.py"

GAP_NO_BLAST = """---
type: gap
title: "get_user returns uid but callers expect id"
tags: ["kind:bug", "status:open"]
---
## Gap detail
- On constraint: false
"""

GAP_LEGACY_TAGS = """---
type: gap
title: "consumer expects uuid but producer emits id"
tags: ["kind:wire", "status:open", "blast-radius:local+reversible"]
---
"""

GAP_OVER_CEILING = """---
type: gap
title: "public API rename"
tags: ["kind:bug", "status:open", "blast-radius:shared-state-visible"]
---
"""

GAP_THRASH = """---
type: gap
title: "wire keeps reopening"
tags: ["kind:wire", "status:open", "blast-radius:local+reversible", "reopen-count:3"]
---
"""

GAP_CLOSED_OVER_CEILING = """---
type: gap
title: "already dealt with"
tags: ["kind:bug", "status:closed", "blast-radius:shared-state-visible"]
---
"""

EVIDENCE_RED = """---
type: evidence
title: "wire not proven"
tags: ["strategy:a"]
---
## Evidence detail
- Verdict: red
"""

# #68: evidence with a non-advancing verdict, used both standalone (still
# gates) and superseded/retired (stops gating).
EVIDENCE_UNKNOWN_WIRE_AB = """---
type: evidence
title: "wire not conclusively proven"
wire: "stage-a->stage-b"
strategy: a
verdict: unknown
tags: ["strategy:a", "verdict:unknown"]
---
"""

EVIDENCE_GREEN_WIRE_AB = """---
type: evidence
title: "wire re-verified green"
wire: "stage-a->stage-b"
strategy: a
verdict: green
tags: ["strategy:a", "verdict:green"]
---
"""

# A gap whose resolved_by names EVIDENCE_UNKNOWN_WIRE_AB's slug -- used to
# prove #68a's join skips exactly that evidence once its gap is closed.
# Fixture below names the first (and, in these tests, only) evidence doc it
# writes "e0.md", so resolved_by must target that exact slug.
GAP_CLOSED_RESOLVED_BY_WIRE_AB = """---
type: gap
title: "stage-a->stage-b wire already re-verified"
stage: stage-a
kind: wire
status: closed
resolved_by: "[[evidence/e0]]"
tags: ["kind:wire", "status:closed"]
---
"""

GAP_OPEN_WIRE_AB = """---
type: gap
title: "stage-a->stage-b wire not yet resolved"
stage: stage-a
kind: wire
status: open
blast_radius: local+reversible
tags: ["kind:wire", "status:open", "blast-radius:local+reversible"]
---
"""


def run(cwd: Path, file_path: str = "src/api.py", env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook and return the raw CompletedProcess.

    The runtime distinguishes allow from deny by EXIT CODE (0 vs 2), not by
    JSON content alone -- so callers must check returncode, not just parse
    stdout. Deny must be 2, allow must be 0; anything else means the hook
    would be silently ignored by the real runtime.
    """
    payload = json.dumps({"cwd": str(cwd), "tool_name": "Edit",
                          "tool_input": {"file_path": file_path}})
    full_env = {**os.environ, **env} if env else None
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, timeout=30, env=full_env)
    assert r.returncode in (0, 2), f"hook must exit 0 (allow) or 2 (deny), got {r.returncode}: {r.stderr}"
    return r


def out_json(r: subprocess.CompletedProcess) -> dict:
    return json.loads(r.stdout)


def decision(r: subprocess.CompletedProcess) -> str:
    out = out_json(r)
    hso = out["hookSpecificOutput"]
    # The runtime-accepted contract: hookEventName must be present, and the
    # exit code and permissionDecision must agree with each other.
    assert hso.get("hookEventName") == "PreToolUse", (
        f"hookSpecificOutput missing/wrong hookEventName: {hso!r}")
    pd = hso["permissionDecision"]
    if pd == "deny":
        assert r.returncode == 2, f"deny must exit 2, got {r.returncode}"
    elif pd == "allow":
        assert r.returncode == 0, f"allow must exit 0, got {r.returncode}"
    return pd


def deny_reason(r: subprocess.CompletedProcess) -> str:
    """The deny reason, asserted present in BOTH the JSON field the runtime
    reads (permissionDecisionReason) and on stderr (the belt-and-braces
    exit-2 mechanism)."""
    out = out_json(r)
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason, "permissionDecisionReason must be non-empty on deny"
    assert reason.strip() in r.stderr, "deny reason must also be written to stderr"
    return reason


class Fixture:
    def __init__(self, gaps=(), evidence=(), settings: str | None = None, ledger=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        if ledger:
            for sub in ("gaps", "evidence", "stages"):
                (self.root / "analysis/andon/ledger" / sub).mkdir(parents=True)
            for i, g in enumerate(gaps):
                (self.root / f"analysis/andon/ledger/gaps/g{i}.md").write_text(g)
            for i, e in enumerate(evidence):
                (self.root / f"analysis/andon/ledger/evidence/e{i}.md").write_text(e)
        if settings is not None:
            (self.root / ".claude").mkdir(parents=True, exist_ok=True)
            (self.root / ".claude/andon.local.md").write_text(settings)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


class TestInertness(unittest.TestCase):
    def test_no_ledger_allows_and_says_nothing(self):
        """Without this, the hook polices every repo on the machine."""
        with Fixture(ledger=False) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "allow")
            self.assertEqual(r.returncode, 0)
            self.assertNotIn("systemMessage", out_json(r))

    def test_empty_ledger_allows(self):
        with Fixture() as f:
            self.assertEqual(decision(run(f.root)), "allow")


class TestStopConditions(unittest.TestCase):
    def test_missing_blast_radius_denies(self):
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("never inferred", deny_reason(r))

    def test_blast_radius_over_ceiling_denies(self):
        with Fixture(gaps=[GAP_OVER_CEILING]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("condition 2", deny_reason(r))

    def test_reopen_threshold_denies(self):
        with Fixture(gaps=[GAP_THRASH]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("escalation", deny_reason(r))

    def test_red_verdict_denies(self):
        with Fixture(gaps=[GAP_LEGACY_TAGS], evidence=[EVIDENCE_RED]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("condition 1", deny_reason(r))

    def test_closed_gap_does_not_gate(self):
        """A closed gap over the ceiling is history, not a live stop."""
        with Fixture(gaps=[GAP_CLOSED_OVER_CEILING]) as f:
            self.assertEqual(decision(run(f.root)), "allow")


class TestLegacyLedgerCompatibility(unittest.TestCase):
    def test_tags_array_shape_is_read_not_rejected(self):
        """101 production records use tags:[...]; rejecting them would deny
        every edit in every existing andon repo on first install."""
        with Fixture(gaps=[GAP_LEGACY_TAGS]) as f:
            self.assertEqual(decision(run(f.root)), "allow")


class TestDenialScope(unittest.TestCase):
    def test_ledger_writes_allowed_even_while_stopped(self):
        """The loop must still record WHY it halted."""
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            r = run(f.root, "analysis/andon/ledger/gaps/g0.md")
            self.assertEqual(decision(r), "allow")

    def test_source_write_denied_while_stopped(self):
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            self.assertEqual(decision(run(f.root, "src/api.py")), "deny")

    def test_absolute_ledger_path_allowed(self):
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            p = str(f.root / "analysis/andon/ledger/log.md")
            self.assertEqual(decision(run(f.root, p)), "allow")


class TestContainment(unittest.TestCase):
    """#69: a target outside the repo is none of this hook's business,
    whatever the ledger's own stop conditions say. Permanent regressions for
    test/plugins/fixtures/guard-differential/andon-69-*."""

    def test_target_outside_repo_allowed_even_while_stopped(self):
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            outside = str(Path(f.tmp.name).parent / "definitely-not-in-the-probe-repo" / "notes.md")
            r = run(f.root, outside)
            self.assertEqual(decision(r), "allow")

    def test_target_inside_repo_still_denied_while_stopped(self):
        """The anti-loosening half: an ordinary in-repo write must still gate."""
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            self.assertEqual(decision(run(f.root, "src/api.py")), "deny")

    def test_relative_traversal_outside_repo_allowed(self):
        """A relative '../../elsewhere' target normalizes outside cwd too --
        the containment check must not be fooled by a merely-relative path."""
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            r = run(f.root, "../../elsewhere/notes.md")
            self.assertEqual(decision(r), "allow")


class TestSupersedeAndRetire(unittest.TestCase):
    """#68: evidence whose gap already closed, or whose wire was later
    re-verified, must not gate forever. Permanent regressions for
    test/plugins/fixtures/guard-differential/andon-68-*."""

    def test_evidence_for_a_closed_gap_does_not_gate(self):
        with Fixture(gaps=[GAP_CLOSED_RESOLVED_BY_WIRE_AB],
                     evidence=[EVIDENCE_UNKNOWN_WIRE_AB]) as f:
            self.assertEqual(decision(run(f.root)), "allow")

    def test_same_evidence_still_gates_while_gap_open(self):
        """The anti-loosening half: the same non-advancing evidence still
        gates when nothing has closed the gap it would resolve."""
        with Fixture(gaps=[GAP_OPEN_WIRE_AB], evidence=[EVIDENCE_UNKNOWN_WIRE_AB]) as f:
            self.assertEqual(decision(run(f.root)), "deny")

    def test_superseding_green_evidence_for_same_wire_allows(self):
        """#68c: a later green re-verify for the same wire supersedes the
        earlier red/unknown one, matching andon_core.py's compute_wire_status
        (last evidence, by filename order, wins)."""
        with Fixture(evidence=[EVIDENCE_UNKNOWN_WIRE_AB, EVIDENCE_GREEN_WIRE_AB]) as f:
            self.assertEqual(decision(run(f.root)), "allow")

    def test_retired_gap_stops_gating(self):
        """andon_core.py retire moves a gap into ledger/retired/, which
        _list_md never walks -- so a retired stale record stops gating by
        construction."""
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            self.assertEqual(decision(run(f.root)), "deny")
            retire = subprocess.run(
                [sys.executable, str(HOOK.parent.parent / "scripts" / "andon_core.py"),
                 "retire", str(f.root), "analysis/andon/ledger", "gaps", "g0",
                 "--reason", "superseded"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(retire.returncode, 0, retire.stderr)
            self.assertEqual(decision(run(f.root)), "allow")


class TestEscapeHatchEnvVar(unittest.TestCase):
    """#70: the narrowest of the three named remedies -- a single env var for
    one call, distinct from the wholesale `enforcement: off` setting.
    Permanent regressions for
    test/plugins/fixtures/guard-differential/andon-70-*."""

    def test_env_var_set_allows(self):
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            r = run(f.root, env={"ANDON_DISABLE_GUARD": "1"})
            self.assertEqual(decision(r), "allow")

    def test_env_var_unset_still_denies(self):
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            self.assertEqual(decision(run(f.root)), "deny")

    def test_both_remedies_named_in_deny_reason(self):
        """Narrowest-first: the per-call env var and the wholesale setting
        must both be named, not just the most destructive one."""
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            reason = deny_reason(run(f.root))
            self.assertIn("ANDON_DISABLE_GUARD", reason)
            self.assertIn("enforcement: off", reason)


class TestFailureMode(unittest.TestCase):
    def test_escape_hatch_disables(self):
        with Fixture(gaps=[GAP_NO_BLAST], settings="---\nenforcement: off\n---\n") as f:
            self.assertEqual(decision(run(f.root)), "allow")

    def test_custom_ledger_dir_honored(self):
        with Fixture(gaps=[GAP_NO_BLAST], settings="---\nledger_dir: nowhere/at/all\n---\n") as f:
            self.assertEqual(decision(run(f.root)), "allow")

    def test_raised_authorization_level_permits(self):
        with Fixture(gaps=[GAP_OVER_CEILING],
                     settings="---\nauthorization_level: shared-state-visible\n---\n") as f:
            self.assertEqual(decision(run(f.root)), "allow")

    def test_unreadable_ledger_denies_rather_than_failing_open(self):
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            (f.root / "analysis/andon/ledger/gaps").chmod(0o000)
            try:
                r = run(f.root)
                self.assertEqual(decision(r), "deny")
                self.assertIn("enforcement: off", deny_reason(r))
            finally:
                (f.root / "analysis/andon/ledger/gaps").chmod(0o755)

    def test_empty_stdin_does_not_crash(self):
        r = subprocess.run([sys.executable, str(HOOK)], input="",
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        json.loads(r.stdout)


class TestOutputContractRegression(unittest.TestCase):
    """Guards against re-introducing the exact shape the runtime silently
    ignores: `{"hookSpecificOutput": {"permissionDecision": "deny"},
    "systemMessage": "..."}` -- missing `hookEventName`, reason in
    `systemMessage` instead of `permissionDecisionReason`. That shape passed
    every test in this file (all 16 asserted only on the ignored field) while
    doing nothing at runtime; these assertions are on the field the runtime
    actually reads.
    """

    def test_deny_shape_matches_runtime_accepted_contract(self):
        with Fixture(gaps=[GAP_NO_BLAST]) as f:
            r = run(f.root)
            self.assertEqual(r.returncode, 2, "deny must exit 2")
            out = out_json(r)
            hso = out["hookSpecificOutput"]
            self.assertEqual(hso.get("hookEventName"), "PreToolUse",
                             "hookEventName is required or the runtime ignores the deny")
            self.assertEqual(hso.get("permissionDecision"), "deny")
            self.assertTrue(hso.get("permissionDecisionReason"),
                            "reason must be in permissionDecisionReason, not systemMessage")
            self.assertIn(hso["permissionDecisionReason"].strip(), r.stderr,
                          "reason must also land on stderr (belt-and-braces exit 2)")

    def test_allow_shape_matches_runtime_accepted_contract(self):
        with Fixture() as f:
            r = run(f.root)
            self.assertEqual(r.returncode, 0, "allow must exit 0")
            hso = out_json(r)["hookSpecificOutput"]
            self.assertEqual(hso.get("hookEventName"), "PreToolUse")
            self.assertEqual(hso.get("permissionDecision"), "allow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
