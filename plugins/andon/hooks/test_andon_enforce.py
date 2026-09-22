#!/usr/bin/env python3
"""Tests for the andon PreToolUse enforcement hook.

Every case is a property the hook must hold regardless of what any model does —
that is the entire point of it being a hook. Run: python3 test_andon_enforce.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).parent / "andon_enforce.py"

# Three of the classes below (submodule resolution, git-absent-from-PATH,
# relative-gitdir) build their fixtures with real `git` subprocess calls --
# git itself is not this hook's dependency (see resolve_main_root's own
# docstring: "pure filesystem walk (no subprocess)"), but building a real
# worktree/submodule to test that claim against needs a real git binary.
# Skip those, and only those, when this machine has none.
GIT_AVAILABLE = shutil.which("git") is not None

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

EVIDENCE_UNRECOGNISED_VERDICT = """---
type: evidence
title: "verdict outside the schema's three values"
wire: "stage-a->stage-b"
strategy: a
verdict: amber
tags: ["strategy:a", "verdict:amber"]
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


LOG_WITH_SUBCYCLES = """# andon OKF log

Append-only. Never rewritten. See okf-ledger-schema.md.

### Pass 1 (cycle 1) -- 2026-01-01T00:00:00Z
### Sub-cycle: ingest->normalize reopened (count 1) -- 2026-01-01T00:01:00Z
### Sub-cycle: ingest->normalize reopened (count 2) -- 2026-01-01T00:02:00Z
### Sub-cycle: enrich->score reopened (count 1) -- 2026-01-01T00:03:00Z
"""

LOG_AT_THRESHOLD = LOG_WITH_SUBCYCLES + (
    "### Sub-cycle: ingest->normalize reopened (count 3) -- 2026-01-01T00:04:00Z\n"
)


GAP_BLOCK_LIST_TAGS_ONLY = """---
type: gap
title: "state only in a block-list tags array"
tags:
  - kind:wire
  - status:open
  - blast-radius:local+reversible
---
"""


class TestFrontmatterListForms(unittest.TestCase):
    """Both YAML list syntaxes, because both are in the wild.

    The block form is what andon_core.dump_frontmatter writes, what
    okf-ledger-schema.md documents and what every sample_ledger record uses. The
    hook could not read it: `tags` came back as the empty string, so tag_value's
    fallback found nothing. Every fixture constant in this file was inline-JSON,
    which is why 34 passing tests never noticed.

    The inline form stays supported -- CLAUDE.md records 101 production records
    in spectrafit-core whose state is only there.
    """

    def test_block_list_tags_are_read(self):
        with Fixture(gaps=[GAP_BLOCK_LIST_TAGS_ONLY]) as f:
            # blast-radius resolves from the block list, so no required-field stop
            self.assertEqual(decision(run(f.root)), "allow")

    def test_block_list_missing_blast_radius_still_halts(self):
        gap = GAP_BLOCK_LIST_TAGS_ONLY.replace(
            "  - blast-radius:local+reversible\n", "")
        with Fixture(gaps=[gap]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("blast-radius", deny_reason(r))

    def test_writer_output_is_readable_by_this_hook(self):
        """Round-trip: andon_core writes a record, the hook reads it back.

        Nothing tested this, which is exactly how the two disagreed from 0c10fa0
        until now -- the writer emitting a shape its own hook could not parse.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "andon_core_rt", Path(__file__).resolve().parents[1] / "scripts" / "andon_core.py")
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)

        spec2 = importlib.util.spec_from_file_location(
            "andon_enforce_rt", Path(__file__).resolve().parent / "andon_enforce.py")
        hook = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(hook)

        fields = {
            "type": "gap", "title": "round trip", "stage": "ingest",
            "kind": "wire", "status": "open", "blast_radius": "hard-to-reverse",
        }
        fields["tags"] = core.build_tags_for_doc(fields)
        text = core.dump_frontmatter(fields)

        fm = hook.frontmatter(text)
        self.assertIsInstance(fm.get("tags"), list, "writer emits a block list")
        self.assertIn("kind:wire", fm["tags"])
        # and every tag the writer derived is retrievable through the fallback
        stripped = {k: v for k, v in fm.items() if k in ("tags",)}
        self.assertEqual(hook.tag_value(stripped, "status"), "open")
        self.assertEqual(hook.tag_value(stripped, "blast_radius"), "hard-to-reverse")


class TestReopenParserAgreement(unittest.TestCase):
    """The hook copies one regex from andon_core.parse_log_counters.

    It has to: the hook is stdlib-only and imports nothing from the plugin, so a
    broken install can never stop it loading. A copied regex is the drift this
    repo keeps getting bitten by, so both parsers are run over the same text and
    required to agree. Change one and this goes red.
    """

    def _core_counts(self, log_text):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "andon_core", Path(__file__).resolve().parents[1] / "scripts" / "andon_core.py")
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "analysis" / "andon" / "ledger"
            ledger.mkdir(parents=True)
            (ledger / "log.md").write_text(log_text, encoding="utf-8")
            return core.parse_log_counters(tmp, "analysis/andon/ledger")["reopen_counts"]

    def _hook_counts(self, log_text):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "andon_enforce_mod", Path(__file__).resolve().parent / "andon_enforce.py")
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            (ledger / "log.md").write_text(log_text, encoding="utf-8")
            return hook.reopen_counts(ledger)

    def test_both_parsers_agree(self):
        for log in (LOG_WITH_SUBCYCLES, LOG_AT_THRESHOLD, "# empty log\n"):
            self.assertEqual(self._hook_counts(log), self._core_counts(log))

    def test_counts_are_per_wire_and_take_the_maximum(self):
        self.assertEqual(
            self._hook_counts(LOG_WITH_SUBCYCLES),
            {"ingest->normalize": 2, "enrich->score": 1},
        )


class TestSubCycleEscalation(unittest.TestCase):
    """The stop that could never fire.

    It read `reopen_count` off a GAP doc. No writer puts it there -- the value is
    keyed by wire and lives only in log.md -- so on any real ledger this branch
    was unreachable. It passed its test because the fixture hand-wrote an inline
    tag nothing emits.
    """

    def test_wire_at_threshold_halts(self):
        with Fixture(gaps=[GAP_LEGACY_TAGS]) as f:
            (f.root / "analysis" / "andon" / "ledger" / "log.md").write_text(
                LOG_AT_THRESHOLD, encoding="utf-8")
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("sub-cycle escalation", deny_reason(r).lower())
            self.assertIn("ingest->normalize", deny_reason(r))

    def test_wire_under_threshold_advances(self):
        with Fixture(gaps=[GAP_LEGACY_TAGS]) as f:
            (f.root / "analysis" / "andon" / "ledger" / "log.md").write_text(
                LOG_WITH_SUBCYCLES, encoding="utf-8")
            self.assertEqual(decision(run(f.root)), "allow")


class TestVerdictPolarity(unittest.TestCase):
    """A verdict is judged against an ALLOWLIST of good, not a denylist of bad.

    The hook used to hold NON_ADVANCING_VERDICTS = ("red", "unknown") and halt
    only on a member of it, so every OTHER verdict advanced -- it failed open.
    `amber` reached that branch for real: validate_ledger.py accepted it as a
    valid gating value, while compute_wire_status collapsed it to `unknown` and
    the board drew the wire amber, labelled unproven. The operator saw a gated
    wire; the hook was not gating.

    These two run together on purpose. The first alone cannot tell "unknown
    verdicts now halt" from "everything now halts", and the second is the far
    worse regression.
    """

    def test_unrecognised_verdict_halts(self):
        with Fixture(gaps=[GAP_LEGACY_TAGS], evidence=[EVIDENCE_UNRECOGNISED_VERDICT]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("condition 1", deny_reason(r))
            self.assertIn("amber", deny_reason(r))

    def test_green_still_advances(self):
        with Fixture(gaps=[GAP_LEGACY_TAGS], evidence=[EVIDENCE_GREEN_WIRE_AB]) as f:
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


EVIDENCE_GREEN_HEAD = """---
type: evidence
title: "later green re-verify"
wire: "stage-x->stage-y"
strategy: a
verdict: green
tags: ["strategy:a", "verdict:green"]
---
"""

EVIDENCE_RED_SUPERSEDED_BY_HEAD = """---
type: evidence
title: "earlier red, now superseded"
wire: "stage-x->stage-y"
strategy: a
verdict: red
superseded_by: a-green-head
tags: ["strategy:a", "verdict:red"]
---
"""

EVIDENCE_RED_DANGLING = """---
type: evidence
title: "red, dangling supersede"
wire: "stage-p->stage-q"
strategy: a
verdict: red
superseded_by: nonexistent-slug-zzz
tags: ["strategy:a", "verdict:red"]
---
"""

EVIDENCE_GREEN_DANGLING = """---
type: evidence
title: "green, but dangling supersede -- must still deny"
wire: "stage-p->stage-q"
strategy: a
verdict: green
superseded_by: nonexistent-slug-zzz
tags: ["strategy:a", "verdict:green"]
---
"""

EVIDENCE_GREEN_EXPIRED = """---
type: evidence
title: "green but expired"
wire: "stage-m->stage-n"
strategy: a
verdict: green
valid_until: 2020-01-01
tags: ["strategy:a", "verdict:green"]
---
"""

EVIDENCE_GREEN_NOT_YET_DUE = """---
type: evidence
title: "green, not yet due"
wire: "stage-r->stage-s"
strategy: a
verdict: green
valid_until: 2099-01-01
tags: ["strategy:a", "verdict:green"]
---
"""

EVIDENCE_GREEN_BAD_VALID_UNTIL = """---
type: evidence
title: "green, but unparseable valid_until"
wire: "stage-t->stage-u"
strategy: a
verdict: green
valid_until: not-a-date
tags: ["strategy:a", "verdict:green"]
---
"""


class TestLifecycleFields(unittest.TestCase):
    """#72: superseded_by (chain-head-resolution), measured_against,
    valid_until. See analysis/arbeitsplan/.../checks/probe_lifecycle.py's
    L1-L7 for the sealed, cross-candidate version of these same cases; the
    tests below are this candidate's own, including the multi-hop and
    fail-closed-on-green cases the sealed probe does not cover.
    """

    def test_superseding_evidence_defers_to_the_chain_head(self):
        """Built with explicit filenames so superseded_by can name a real
        slug (Fixture's e0/e1 auto-naming can't be referenced in advance)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "analysis/andon/ledger"
            for sub in ("gaps", "evidence", "stages"):
                (ledger / sub).mkdir(parents=True)
            (ledger / "evidence/a-green-head.md").write_text(EVIDENCE_GREEN_HEAD)
            (ledger / "evidence/b-red-superseded.md").write_text(EVIDENCE_RED_SUPERSEDED_BY_HEAD)
            self.assertEqual(decision(run(root)), "allow")

    def test_dangling_superseded_by_denies_even_when_green(self):
        """Fail closed: a broken chain denies regardless of the leaf's own
        verdict -- the sealed probe only exercises the red case (L2)."""
        with Fixture(evidence=[EVIDENCE_GREEN_DANGLING]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("dangling", deny_reason(r).lower())

    def test_multi_hop_chain_resolves_past_an_intermediate_red(self):
        """v1 (green, the true head) <- v2 (red, superseded_by v1) <- v3
        (red, superseded_by v2, the filename-latest record). A resolver that
        stopped after one hop would read v2's own red verdict and deny;
        walking the WHOLE chain to v1 must allow instead."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "analysis/andon/ledger"
            for sub in ("gaps", "evidence", "stages"):
                (ledger / sub).mkdir(parents=True)
            (ledger / "evidence/v1.md").write_text(
                '---\ntype: evidence\ntitle: "head"\nwire: "a->b"\nstrategy: a\n'
                'verdict: green\n---\n')
            (ledger / "evidence/v2.md").write_text(
                '---\ntype: evidence\ntitle: "mid"\nwire: "a->b"\nstrategy: a\n'
                'verdict: red\nsuperseded_by: v1\n---\n')
            (ledger / "evidence/v3.md").write_text(
                '---\ntype: evidence\ntitle: "leaf"\nwire: "a->b"\nstrategy: a\n'
                'verdict: red\nsuperseded_by: v2\n---\n')
            self.assertEqual(decision(run(root)), "allow")

    def test_dangling_deep_in_chain_denies(self):
        """A dangling link two hops out from the leaf must still be caught."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "analysis/andon/ledger"
            for sub in ("gaps", "evidence", "stages"):
                (ledger / sub).mkdir(parents=True)
            (ledger / "evidence/v1.md").write_text(
                '---\ntype: evidence\ntitle: "mid"\nwire: "a->b"\nstrategy: a\n'
                'verdict: green\nsuperseded_by: ghost\n---\n')
            (ledger / "evidence/v2.md").write_text(
                '---\ntype: evidence\ntitle: "leaf"\nwire: "a->b"\nstrategy: a\n'
                'verdict: green\nsuperseded_by: v1\n---\n')
            r = run(root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("dangling", deny_reason(r).lower())

    def test_supersession_cycle_denies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "analysis/andon/ledger"
            for sub in ("gaps", "evidence", "stages"):
                (ledger / sub).mkdir(parents=True)
            (ledger / "evidence/x.md").write_text(
                '---\ntype: evidence\ntitle: "x"\nwire: "a->b"\nstrategy: a\n'
                'verdict: green\nsuperseded_by: y\n---\n')
            (ledger / "evidence/y.md").write_text(
                '---\ntype: evidence\ntitle: "y"\nwire: "a->b"\nstrategy: a\n'
                'verdict: green\nsuperseded_by: x\n---\n')
            r = run(root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("cycle", deny_reason(r).lower())

    def test_expired_valid_until_denies_even_when_green(self):
        with Fixture(evidence=[EVIDENCE_GREEN_EXPIRED]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("expir", deny_reason(r).lower())

    def test_future_valid_until_allows(self):
        with Fixture(evidence=[EVIDENCE_GREEN_NOT_YET_DUE]) as f:
            self.assertEqual(decision(run(f.root)), "allow")

    def test_unparseable_valid_until_denies(self):
        with Fixture(evidence=[EVIDENCE_GREEN_BAD_VALID_UNTIL]) as f:
            r = run(f.root)
            self.assertEqual(decision(r), "deny")

    def test_expiry_judged_on_chain_head_not_the_superseded_leaf(self):
        """The superseded record carries an expired valid_until; the head
        does not carry one at all. The wire must still allow -- expiry is
        never read off anything but the head."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "analysis/andon/ledger"
            for sub in ("gaps", "evidence", "stages"):
                (ledger / sub).mkdir(parents=True)
            (ledger / "evidence/a-head.md").write_text(
                '---\ntype: evidence\ntitle: "head"\nwire: "a->b"\nstrategy: a\n'
                'verdict: green\n---\n')
            (ledger / "evidence/b-leaf.md").write_text(
                '---\ntype: evidence\ntitle: "leaf"\nwire: "a->b"\nstrategy: a\n'
                'verdict: green\nsuperseded_by: a-head\nvalid_until: 2020-01-01\n---\n')
            self.assertEqual(decision(run(root)), "allow")

    def test_measured_against_named_in_deny_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "analysis/andon/ledger"
            for sub in ("gaps", "evidence", "stages"):
                (ledger / sub).mkdir(parents=True)
            (ledger / "evidence/f0.md").write_text(
                '---\ntype: evidence\ntitle: "tied to a decision"\nwire: "a->b"\n'
                'strategy: a\nverdict: red\nmeasured_against: decision-017\n---\n')
            r = run(root)
            self.assertEqual(decision(r), "deny")
            self.assertIn("decision-017", deny_reason(r))


EVIDENCE_A_RED_SUPERSEDED_BY_B = """---
type: evidence
title: "a, red -- superseded by b"
wire: "x->y"
strategy: a
verdict: red
superseded_by: b-red
tags: ["strategy:a", "verdict:red"]
---
"""

EVIDENCE_B_RED_SUPERSEDED_BY_A = """---
type: evidence
title: "b, red -- superseded by a, closing the cycle"
wire: "x->y"
strategy: a
verdict: red
superseded_by: a-red
tags: ["strategy:a", "verdict:red"]
---
"""


class TestSupersessionCycleTwoRedRecords(unittest.TestCase):
    """A ledger whose only two evidence docs for one wire supersede EACH
    OTHER -- a-red.md names b-red as its successor, b-red.md names a-red as
    its own -- has no resolvable chain head at all. Same shape as
    TestLifecycleFields.test_supersession_cycle_denies above (which uses two
    GREEN docs on wire a->b); this pins the RED-verdict, named-file variant
    the task called out explicitly. The library-level half of the same
    scenario (andon_core.compute_wire_status must never report this wire
    green) lives in scripts/test_andon_core.py's
    ComputeWireStatusChainHeadResolution class, not here -- this hook is
    stdlib-only and does not import andon_core as a library (see this file's
    and andon_enforce.py's module docstrings for why).
    """

    def test_hook_denies_editing_a_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "analysis/andon/ledger"
            for sub in ("gaps", "evidence", "stages"):
                (ledger / sub).mkdir(parents=True)
            (ledger / "evidence/a-red.md").write_text(EVIDENCE_A_RED_SUPERSEDED_BY_B, encoding="utf-8")
            (ledger / "evidence/b-red.md").write_text(EVIDENCE_B_RED_SUPERSEDED_BY_A, encoding="utf-8")
            r = run(root, "src/api.py")
            self.assertEqual(decision(r), "deny")
            self.assertIn("cycle", deny_reason(r).lower())


class TestChainHeadResolutionAgreement(unittest.TestCase):
    """The hook duplicates andon_core.resolve_chain_head verbatim (the hook
    is stdlib-only and imports nothing from the plugin -- see this file's and
    andon_enforce.py's module docstrings). Both are fed the SAME
    superseded_by map here, in the style of TestReopenParserAgreement above,
    and must agree on every case: the same resolved head, or both raising
    their own ChainResolutionError.
    """

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "andon_core_agree", Path(__file__).resolve().parents[1] / "scripts" / "andon_core.py")
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)

        spec2 = importlib.util.spec_from_file_location(
            "andon_enforce_agree", Path(__file__).resolve().parent / "andon_enforce.py")
        hook = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(hook)
        return core, hook

    def test_both_resolve_a_clean_chain_to_the_same_head(self):
        core, hook = self._load()
        mapping = {"leaf": "mid", "mid": "head", "head": None}
        self.assertEqual(
            hook.resolve_chain_head("leaf", mapping),
            core.resolve_chain_head("leaf", mapping),
        )
        self.assertEqual(hook.resolve_chain_head("leaf", mapping), "head")

    def test_both_agree_a_trivial_chain_is_its_own_head(self):
        core, hook = self._load()
        mapping = {"solo": None}
        self.assertEqual(
            hook.resolve_chain_head("solo", mapping),
            core.resolve_chain_head("solo", mapping),
        )

    def test_both_raise_on_a_dangling_link(self):
        core, hook = self._load()
        mapping = {"leaf": "ghost"}
        with self.assertRaises(hook.ChainResolutionError):
            hook.resolve_chain_head("leaf", mapping)
        with self.assertRaises(core.ChainResolutionError):
            core.resolve_chain_head("leaf", mapping)

    def test_both_raise_on_a_cycle(self):
        core, hook = self._load()
        mapping = {"x": "y", "y": "x"}
        with self.assertRaises(hook.ChainResolutionError):
            hook.resolve_chain_head("x", mapping)
        with self.assertRaises(core.ChainResolutionError):
            core.resolve_chain_head("x", mapping)

    def test_both_raise_on_a_dangling_link_deep_in_the_chain(self):
        core, hook = self._load()
        mapping = {"leaf": "mid", "mid": "ghost"}
        with self.assertRaises(hook.ChainResolutionError):
            hook.resolve_chain_head("leaf", mapping)
        with self.assertRaises(core.ChainResolutionError):
            core.resolve_chain_head("leaf", mapping)


def _git(args, cwd):
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {r.stderr}")
    return r


class GitRepoWithWorktree:
    """A throwaway main checkout plus one linked worktree, built with real
    git (git init + commit + git worktree add) inside a tempdir -- per
    CLAUDE.md, this worktree's own tests must never depend on the layout of
    the checkout they run in. Duplicated from
    scripts/test_andon_core.py's identically-shaped fixture: each test file
    builds its own throwaway repos rather than sharing one across files."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Resolved once, up front: tempfile.TemporaryDirectory() can hand
        # back a path through a symlink (e.g. macOS /tmp -> /private/tmp),
        # which would make a direct comparison against resolve_main_root()'s
        # (also-resolved) output fail for a reason unrelated to the
        # behaviour under test.
        base = Path(self.tmp.name).resolve()
        self.main = base / "main"
        self.main.mkdir()
        _git(["init", "-q"], self.main)
        _git(["config", "user.email", "test@test.local"], self.main)
        _git(["config", "user.name", "Test"], self.main)
        (self.main / "README.md").write_text("init\n", encoding="utf-8")
        _git(["add", "README.md"], self.main)
        _git(["commit", "-q", "-m", "init"], self.main)
        self.worktree = base / "wt"
        _git(["worktree", "add", "-q", "-b", "wt-branch", str(self.worktree)], self.main)

    def cleanup(self):
        self.tmp.cleanup()


class GitRepoWithSubmodule:
    """A throwaway `sub` repo added as a real git SUBMODULE of a throwaway
    `sup` superproject -- built with real git (git init + commit +
    `git submodule add`) inside a tempdir, same discipline as
    GitRepoWithWorktree above.

    Pins #71's resolver against the one concretely wrong implementation the
    task names: a resolver built from the PARENT of `git rev-parse
    --git-common-dir` would land in `<sup>/.git/modules` -- no ledger lives
    there, so that resolver would silently ALLOW. The actual resolver never
    does this: a submodule's own gitdir (`<sup>/.git/modules/sub`) carries
    no `commondir` file -- that file exists only inside a linked WORKTREE's
    admin dir, never a submodule's -- so resolve_main_root's read of it
    fails and it falls back to `start`, landing on the submodule's own
    checkout root, exactly where `<sup>/sub/analysis/andon/ledger` lives.
    Confirmed against real git before writing this fixture: `sup/.git/modules/sub/commondir`
    does not exist after `git submodule add`, only after `git worktree add`.
    """

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        sub_origin = base / "sub-origin"
        sub_origin.mkdir()
        _git(["init", "-q"], sub_origin)
        _git(["config", "user.email", "test@test.local"], sub_origin)
        _git(["config", "user.name", "Test"], sub_origin)
        _git(["commit", "-q", "--allow-empty", "-m", "init"], sub_origin)

        self.sup = base / "sup"
        self.sup.mkdir()
        _git(["init", "-q"], self.sup)
        _git(["config", "user.email", "test@test.local"], self.sup)
        _git(["config", "user.name", "Test"], self.sup)
        _git(["commit", "-q", "--allow-empty", "-m", "init"], self.sup)
        # protocol.file.allow=always: modern git refuses a local-path
        # submodule remote by default (CVE-2022-39253); this fixture is a
        # throwaway tempdir under our own control, not untrusted input.
        _git(["-c", "protocol.file.allow=always", "submodule", "add", "-q",
              str(sub_origin), "sub"], self.sup)
        self.sub = self.sup / "sub"

    def cleanup(self):
        self.tmp.cleanup()


class TestMainRootResolutionAgreement(unittest.TestCase):
    """The hook duplicates andon_core.resolve_main_root (#71) -- the hook is
    stdlib-only and imports nothing from the plugin (see this file's and
    andon_enforce.py's module docstrings). Both are fed the SAME real git
    fixtures here, in the style of TestChainHeadResolutionAgreement and
    TestReopenParserAgreement above, and must agree on every case.
    """

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "andon_core_mainroot", Path(__file__).resolve().parents[1] / "scripts" / "andon_core.py")
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)

        spec2 = importlib.util.spec_from_file_location(
            "andon_enforce_mainroot", Path(__file__).resolve().parent / "andon_enforce.py")
        hook = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(hook)
        return core, hook

    def test_both_resolve_a_worktree_to_the_same_main_root(self):
        core, hook = self._load()
        fx = GitRepoWithWorktree()
        try:
            self.assertEqual(
                str(hook.resolve_main_root(fx.worktree)),
                core.resolve_main_root(str(fx.worktree)),
            )
            self.assertEqual(str(hook.resolve_main_root(fx.worktree)), str(fx.main))
        finally:
            fx.cleanup()

    def test_both_resolve_the_main_checkout_to_itself(self):
        core, hook = self._load()
        fx = GitRepoWithWorktree()
        try:
            self.assertEqual(
                str(hook.resolve_main_root(fx.main)),
                core.resolve_main_root(str(fx.main)),
            )
        finally:
            fx.cleanup()

    def test_both_fall_back_to_start_outside_git(self):
        core, hook = self._load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.assertEqual(
                str(hook.resolve_main_root(root)),
                core.resolve_main_root(str(root)),
            )
            self.assertEqual(str(hook.resolve_main_root(root)), str(root))

    def test_both_fall_back_on_a_malformed_gitdir_file(self):
        core, hook = self._load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / ".git").write_text("nonsense, no gitdir: line\n", encoding="utf-8")
            self.assertEqual(
                str(hook.resolve_main_root(root)),
                core.resolve_main_root(str(root)),
            )
            self.assertEqual(str(hook.resolve_main_root(root)), str(root))

    @unittest.skipUnless(GIT_AVAILABLE, "git is not installed")
    def test_both_resolve_a_submodule_to_its_own_root(self):
        """Not the superproject, and not `<sup>/.git/modules` -- the
        submodule's own checkout root, where ITS ledger lives. See
        GitRepoWithSubmodule's docstring for why a naive
        parent-of-git-common-dir resolver would get this wrong."""
        core, hook = self._load()
        fx = GitRepoWithSubmodule()
        try:
            self.assertEqual(
                str(hook.resolve_main_root(fx.sub)),
                core.resolve_main_root(str(fx.sub)),
            )
            self.assertEqual(str(hook.resolve_main_root(fx.sub)), str(fx.sub))
        finally:
            fx.cleanup()


class TestWorktreeLedgerResolution(unittest.TestCase):
    """#71: the hook resolves the ledger and settings from the MAIN
    checkout root, never from `cwd` directly -- a linked worktree has
    neither of its own. Exercises the same behaviour probe_worktree.py's
    W1-W10 exercise (run via `python3
    analysis/arbeitsplan/<runId>/checks/probe_worktree.py <tree>`), at the
    unittest layer rather than a standalone script.
    """

    def test_worktree_cwd_denies_on_the_main_ledgers_red_evidence(self):
        fx = GitRepoWithWorktree()
        try:
            ledger = fx.main / "analysis/andon/ledger/evidence"
            ledger.mkdir(parents=True)
            (ledger / "e0.md").write_text(EVIDENCE_RED, encoding="utf-8")
            self.assertEqual(decision(run(fx.worktree)), "deny")
        finally:
            fx.cleanup()

    def test_worktree_cwd_allows_when_no_ledger_exists_anywhere(self):
        fx = GitRepoWithWorktree()
        try:
            self.assertEqual(decision(run(fx.worktree)), "allow")
        finally:
            fx.cleanup()

    def test_worktree_cwd_honors_main_checkouts_enforcement_off(self):
        """Settings resolve from main too -- a worktree-local
        `.claude/andon.local.md` (there isn't one here) is never consulted."""
        fx = GitRepoWithWorktree()
        try:
            ledger = fx.main / "analysis/andon/ledger/evidence"
            ledger.mkdir(parents=True)
            (ledger / "e0.md").write_text(EVIDENCE_RED, encoding="utf-8")
            (fx.main / ".claude").mkdir()
            (fx.main / ".claude/andon.local.md").write_text(
                "---\nenforcement: off\n---\n", encoding="utf-8")
            self.assertEqual(decision(run(fx.worktree)), "allow")
        finally:
            fx.cleanup()

    def test_write_to_main_ledger_path_from_worktree_cwd_still_allowed(self):
        """#69's containment check on `cwd` is unchanged -- a write to the
        MAIN checkout's own ledger path from a worktree cwd stays allowed;
        the loop must always be able to record its halt."""
        fx = GitRepoWithWorktree()
        try:
            ledger = fx.main / "analysis/andon/ledger/evidence"
            ledger.mkdir(parents=True)
            (ledger / "e0.md").write_text(EVIDENCE_RED, encoding="utf-8")
            target = str(fx.main / "analysis/andon/ledger/log.md")
            self.assertEqual(decision(run(fx.worktree, target)), "allow")
        finally:
            fx.cleanup()

    def test_non_git_cwd_fallback_is_unchanged(self):
        """No `.git` anywhere above cwd -> resolve_main_root falls back to
        cwd itself, exactly like every caller's behaviour before #71."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "analysis/andon/ledger/evidence").mkdir(parents=True)
            (root / "analysis/andon/ledger/evidence/e0.md").write_text(EVIDENCE_RED, encoding="utf-8")
            self.assertEqual(decision(run(root)), "deny")


class TestSubmoduleLedgerResolution(unittest.TestCase):
    """A submodule with its OWN ledger must gate edits made inside it, and
    must do so by resolving `cwd` to the submodule's own root -- never by
    wandering up into the superproject's `.git/modules`, which has no
    ledger and would silently allow. See GitRepoWithSubmodule's docstring
    for the concrete wrong implementation this pins against.
    """

    @unittest.skipUnless(GIT_AVAILABLE, "git is not installed")
    def test_hook_denies_source_edit_inside_submodule_with_red_evidence(self):
        fx = GitRepoWithSubmodule()
        try:
            ledger = fx.sub / "analysis/andon/ledger"
            for sub in ("gaps", "evidence", "stages"):
                (ledger / sub).mkdir(parents=True)
            (ledger / "evidence/e0.md").write_text(EVIDENCE_RED, encoding="utf-8")
            r = run(fx.sub, "src/x.py")
            self.assertEqual(decision(r), "deny")
        finally:
            fx.cleanup()


class TestHookWorksWithoutGitBinaryInPath(unittest.TestCase):
    """resolve_main_root's own docstring says it is a "pure filesystem walk
    (no subprocess)" -- so resolution from inside a linked worktree must not
    actually depend on a `git` binary being reachable on PATH at all. This
    builds a real worktree with real git (setup only, guarded by
    GIT_AVAILABLE), then runs the HOOK ITSELF with PATH pointed at an empty,
    git-free directory. Python is still found because run()'s subprocess
    call already invokes `sys.executable` -- an absolute path -- as argv[0],
    never relying on PATH lookup for the interpreter.
    """

    @unittest.skipUnless(GIT_AVAILABLE, "git is not installed")
    def test_worktree_hook_denies_with_git_absent_from_path(self):
        fx = GitRepoWithWorktree()
        try:
            ledger = fx.main / "analysis/andon/ledger/evidence"
            ledger.mkdir(parents=True)
            (ledger / "e0.md").write_text(EVIDENCE_RED, encoding="utf-8")

            with tempfile.TemporaryDirectory() as no_git_dir:
                self.assertIsNone(
                    shutil.which("git", path=no_git_dir),
                    "sanity: this PATH must contain no git binary at all",
                )
                r = run(fx.worktree, env={"PATH": no_git_dir})
                self.assertEqual(decision(r), "deny")
        finally:
            fx.cleanup()


class TestRelativeGitdirWorktree(unittest.TestCase):
    """A linked worktree's `.git` file conventionally holds an ABSOLUTE
    gitdir path -- that's `git worktree add`'s own default, and what every
    other worktree fixture in this file relies on unmodified. Nothing in
    the format, or in resolve_main_root's contract, requires that: a
    relative gitdir line is equally legal git syntax (git itself accepts
    it -- asserted below), and this repo's own resolvers must handle it
    exactly as readily as the absolute form.
    """

    @unittest.skipUnless(GIT_AVAILABLE, "git is not installed")
    def test_relative_gitdir_still_resolves_to_main_and_denies(self):
        fx = GitRepoWithWorktree()
        try:
            ledger = fx.main / "analysis/andon/ledger/evidence"
            ledger.mkdir(parents=True)
            (ledger / "e0.md").write_text(EVIDENCE_RED, encoding="utf-8")

            admin_dir = fx.main / ".git" / "worktrees" / fx.worktree.name
            self.assertTrue(admin_dir.is_dir(),
                             "sanity: git's own worktree admin dir must exist first")
            rel_gitdir = os.path.relpath(str(admin_dir), str(fx.worktree))
            (fx.worktree / ".git").write_text(f"gitdir: {rel_gitdir}\n", encoding="utf-8")

            # Sanity: git itself still accepts the rewritten, now-relative line.
            rp = subprocess.run(
                ["git", "-C", str(fx.worktree), "rev-parse", "--git-common-dir"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(rp.returncode, 0, rp.stderr)

            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "andon_core_relgitdir", Path(__file__).resolve().parents[1] / "scripts" / "andon_core.py")
            core = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(core)
            spec2 = importlib.util.spec_from_file_location(
                "andon_enforce_relgitdir", Path(__file__).resolve().parent / "andon_enforce.py")
            hook = importlib.util.module_from_spec(spec2)
            spec2.loader.exec_module(hook)

            self.assertEqual(str(hook.resolve_main_root(fx.worktree)), str(fx.main))
            self.assertEqual(core.resolve_main_root(str(fx.worktree)), str(fx.main))

            self.assertEqual(decision(run(fx.worktree)), "deny")
        finally:
            fx.cleanup()


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
