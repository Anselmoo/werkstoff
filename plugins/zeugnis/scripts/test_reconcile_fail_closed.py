#!/usr/bin/env python3
"""A verifier that does not answer is an ABSTAIN, and an abstain is never a pass.

History. `f.get("confirmed", True)` counted a verify record that omitted the key
as a confirmation. The first fix (`is True`) closed that, but it made the other
mistake: a missing or ill-typed `confirmed` silently DROPPED the finding -- no
warning, no count -- so the summary read clean and `cycle_engine` converged on a
domain whose findings nobody had verified.

Contract proved here, for all three reconcile() functions
(assertion_audit, contract_drift, agentic_reliability):

  literal True                          -> confirmed, kept, not marked
  literal False                         -> refuted, dropped
  anything else (missing, "yes", 1,     -> UNVERIFIED: kept, marked
    null, [..], no record, conflicting)    verification="unverified", WARNING with
                                           the count on stderr, `unverifiedCount`
                                           in the summary

and for the gate: `cycle_engine record-pass-result` never reports converged=true
while a verified domain's sidecar holds unverified findings, or has no readable
integer `unverifiedCount` (fail closed).

`SabotageProof` re-runs the real tests against a scratch copy of the plugin with
one guard removed each; every sabotage must turn them red, and the untouched
copy must stay green (so a harness that always fails cannot pass).

Run: python3 plugins/zeugnis/scripts/test_reconcile_fail_closed.py
Exit: 0 all cases passed, 1 otherwise.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agentic_reliability
import assertion_audit
import contract_drift

HERE = Path(__file__).resolve().parent
MODULES = (assertion_audit, contract_drift, agentic_reliability)
SCRIPTS = {
    assertion_audit: "assertion_audit.py",
    contract_drift: "contract_drift.py",
    agentic_reliability: "agentic_reliability.py",
}
FIND = [{"evidence": "a.py:1"}, {"evidence": "b.py:2"}]
CORE_CLASSES = ["ReconcileThreeBuckets", "SummaryAndCli", "CycleRefusesConvergence", "UnusableVerifyPayload"]


def reconcile(module, find, verify):
    """-> (survivor findings, stderr text)"""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        out = module.reconcile(find, verify)
    return out, err.getvalue()


def valid_finding(module, evidence):
    base = {"severity": "High", "title": f"t {evidence}", "evidence": evidence, "fixability": "advisory"}
    if module is assertion_audit:
        return {**base, "category": "weak-assertion", "toolSource": "llm-reasoned"}
    if module is contract_drift:
        return {**base, "category": "drift", "declaredLocation": "x.py:1", "actualUsageLocation": "y.py:2"}
    return {**base, "category": "excessive-tool-grant"}


class ReconcileThreeBuckets(unittest.TestCase):
    def evidence(self, module, verify, find=FIND):
        out, _ = reconcile(module, find, verify)
        return [f["evidence"] for f in out]

    def test_literal_true_is_confirmed_and_unmarked(self):
        # positive control: a reconcile() that drops or marks everything fails here
        for module in MODULES:
            with self.subTest(module=module.__name__):
                out, err = reconcile(module, FIND, [{"evidence": "a.py:1", "confirmed": True},
                                                    {"evidence": "b.py:2", "confirmed": True}])
                self.assertEqual([f["evidence"] for f in out], ["a.py:1", "b.py:2"])
                self.assertTrue(all("verification" not in f for f in out))
                self.assertEqual(err, "")

    def test_literal_false_is_refuted_and_dropped_without_warning(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                out, err = reconcile(module, FIND, [{"evidence": "a.py:1", "confirmed": False},
                                                    {"evidence": "b.py:2", "confirmed": False}])
                self.assertEqual(out, [])
                self.assertEqual(err, "")

    def test_malformed_confirmed_is_kept_as_unverified_with_warning(self):
        cases = ["MISSING", "yes", "true", 1, 0, None, [True], {"x": 1}]
        for module in MODULES:
            for value in cases:
                with self.subTest(module=module.__name__, value=value):
                    record = {"evidence": "a.py:1"}
                    if value != "MISSING":
                        record["confirmed"] = value
                    out, err = reconcile(module, [FIND[0]], [record])
                    self.assertEqual([f["evidence"] for f in out], ["a.py:1"])
                    self.assertEqual(out[0]["verification"], "unverified")
                    self.assertIn("WARNING", err)
                    self.assertIn("1 finding(s)", err)

    def test_find_finding_with_no_verify_record_is_unverified(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                out, err = reconcile(module, FIND, [{"evidence": "a.py:1", "confirmed": True}])
                self.assertEqual([(f["evidence"], f.get("verification")) for f in out],
                                 [("a.py:1", None), ("b.py:2", "unverified")])
                self.assertIn("1 finding(s)", err)

    def test_conflicting_records_are_unverified(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                verify = [{"evidence": "a.py:1", "confirmed": True}, {"evidence": "a.py:1", "confirmed": False}]
                out, _ = reconcile(module, [FIND[0]], verify)
                self.assertEqual(out[0]["verification"], "unverified")

    def test_warning_carries_the_count(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                _, err = reconcile(module, FIND, [])
                self.assertIn("2 finding(s)", err)

    def test_spurious_verify_record_without_find_is_ignored(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                self.assertEqual(self.evidence(module, [{"evidence": "zzz:9", "confirmed": True}], find=[]), [])

    def test_unmatchable_evidence_is_unverified_not_matched_to_none(self):
        # a Find finding with no evidence must not "match" a verify record that also lacks it
        for module in MODULES:
            with self.subTest(module=module.__name__):
                out, _ = reconcile(module, [{"title": "x"}], [{"confirmed": True}])
                self.assertEqual(out[0]["verification"], "unverified")


def run_writer(module, find, verify):
    """Run the real CLI against a throwaway repo; -> (summary dict, report text, stderr)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "find.json").write_text(json.dumps({"findings": find}))
        (root / "verify.json").write_text(json.dumps({"findings": verify}))
        r = subprocess.run(
            [sys.executable, str(HERE / SCRIPTS[module]), str(root),
             "--find-json", str(root / "find.json"), "--verify-json", str(root / "verify.json")],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        z = root / "analysis" / "zeugnis"
        summary = json.loads(next(z.glob("*_summary.json")).read_text())
        report = next((z / "reports").glob("*.md")).read_text()
        return summary, report, r.stderr


class SummaryAndCli(unittest.TestCase):
    def test_summary_counts_unverified_and_keeps_the_findings(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                find = [valid_finding(module, "a.py:1"), valid_finding(module, "b.py:2"),
                        valid_finding(module, "c.py:3")]
                verify = [{"evidence": "a.py:1", "confirmed": True},
                          {"evidence": "b.py:2", "confirmed": "yes"},   # abstain
                          {"evidence": "c.py:3", "confirmed": False}]   # refuted
                summary, report, err = run_writer(module, find, verify)
                self.assertEqual(summary["unverifiedCount"], 1)
                self.assertEqual(summary["unverified"], ["b.py:2"])
                by_ev = {f["evidence"]: f for f in summary["findings"]}
                self.assertEqual(sorted(by_ev), ["a.py:1", "b.py:2"])
                self.assertEqual(by_ev["b.py:2"]["verification"], "unverified")
                self.assertNotIn("verification", by_ev["a.py:1"])
                self.assertIn("UNVERIFIED", report)
                self.assertIn("WARNING", err)

    def test_clean_run_reports_zero_unverified(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                find = [valid_finding(module, "a.py:1")]
                summary, report, err = run_writer(module, find, [{"evidence": "a.py:1", "confirmed": True}])
                self.assertEqual(summary["unverifiedCount"], 0)
                self.assertNotIn("UNVERIFIED", report)
                self.assertNotIn("WARNING", err)

    def test_an_abstain_that_later_fails_schema_validation_still_counts(self):
        # the count is taken before the per-finding filters: dropping an invalid
        # abstained finding must not make the abstain disappear
        for module in MODULES:
            with self.subTest(module=module.__name__):
                bad = valid_finding(module, "a.py:1")
                bad["severity"] = "Catastrophic"
                summary, _, _ = run_writer(module, [bad], [])
                self.assertEqual(summary["findings"], [])
                self.assertEqual(summary["unverifiedCount"], 1)


ENGINE = HERE / "cycle_engine.py"


def record_idle_pass(sidecars: dict[str, object]) -> dict:
    """Record a pass that closes nothing (the 'no progress' shape that converges).

    sidecars maps domain -> raw sidecar text (str) or a dict to JSON-encode.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        z = root / "analysis" / "zeugnis"
        z.mkdir(parents=True)
        for domain, body in sidecars.items():
            text = body if isinstance(body, str) else json.dumps(body)
            (z / f"{domain}_summary.json").write_text(text)
        pass_json = root / "pass.json"
        pass_json.write_text(json.dumps({
            "passNumber": 1, "domain": "dependency_audit", "mode": "propose", "outcomes": [],
        }))
        r = subprocess.run(
            [sys.executable, str(ENGINE), "record-pass-result", str(root), "--pass-json", str(pass_json)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        result = json.loads(r.stdout)
        result["_stderr"] = r.stderr
        return result


def sidecar(count, findings=()):
    return {"domain": "x", "verificationRan": True, "unverifiedCount": count, "findings": list(findings)}


class CycleRefusesConvergence(unittest.TestCase):
    def test_no_sidecars_converges(self):
        # positive control: a gate that always refuses fails here
        self.assertTrue(record_idle_pass({})["converged"])

    def test_clean_sidecars_converge(self):
        result = record_idle_pass({d: sidecar(0) for d in ("assertion_audit", "contract_drift", "agentic_reliability")})
        self.assertTrue(result["converged"])
        self.assertEqual(result["unverifiedBlockers"], [])

    def test_unverified_findings_block_convergence_in_every_verified_domain(self):
        for domain in ("assertion_audit", "contract_drift", "agentic_reliability"):
            with self.subTest(domain=domain):
                result = record_idle_pass({domain: sidecar(2)})
                self.assertFalse(result["converged"])
                self.assertFalse(result["shouldContinue"])  # another pass cannot resolve an abstain
                self.assertEqual(result["unverifiedBlockers"][0]["domain"], domain)
                self.assertIn("WARNING", result["_stderr"])

    def test_missing_or_ill_typed_count_fails_closed(self):
        bad = [{"domain": "x", "findings": []},                      # key absent
               {"domain": "x", "unverifiedCount": None},
               {"domain": "x", "unverifiedCount": "0"},
               {"domain": "x", "unverifiedCount": True},
               {"domain": "x", "unverifiedCount": -1},
               [1, 2, 3]]                                            # not an object
        for body in bad:
            with self.subTest(body=body):
                self.assertFalse(record_idle_pass({"contract_drift": body})["converged"])

    def test_unreadable_sidecar_fails_closed(self):
        self.assertFalse(record_idle_pass({"assertion_audit": "not json"})["converged"])

    def test_dependency_audit_sidecar_is_not_gated(self):
        # it has no Verify phase, hence no unverifiedCount to demand
        self.assertTrue(record_idle_pass({"dependency_audit": {"domain": "dependency_audit", "findings": []}})["converged"])


UNUSABLE_PAYLOADS = {
    "null": "null",
    "findings-null": '{"findings": null}',
    "scalar": "42",
    "string": '"yes"',
    "dict-without-list": '{"confirmed": true}',
    "findings-scalar": '{"findings": 7}',
}


def run_cli(module, root: Path, find, verify_text, *extra):
    (root / "find.json").write_text(find if isinstance(find, str) else json.dumps({"findings": find}))
    argv = [sys.executable, str(HERE / SCRIPTS[module]), str(root), "--find-json", str(root / "find.json")]
    if verify_text is not None:
        (root / "verify.json").write_text(verify_text)
        argv += ["--verify-json", str(root / "verify.json")]
    return subprocess.run([*argv, *extra], capture_output=True, text=True)


def record_pass(root: Path) -> dict:
    pass_json = root / "pass.json"
    pass_json.write_text(json.dumps({
        "passNumber": 1, "domain": "dependency_audit", "mode": "propose", "outcomes": [],
    }))
    r = subprocess.run(
        [sys.executable, str(ENGINE), "record-pass-result", str(root), "--pass-json", str(pass_json)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


class UnusableVerifyPayload(unittest.TestCase):
    """A verify-json that parses but holds no record list is NO answer, not a skip.

    The skip-vs-verify branch used to read the loaded value (`is None`), so
    `null` / `{"findings": null}` behaved like --skip-verification: summary
    verificationRan:true, unverifiedCount 0, no marker, converged.
    """

    def test_unusable_payload_marks_every_finding_unverified_via_cli_and_blocks_cycle(self):
        for module in MODULES:
            for label, payload in UNUSABLE_PAYLOADS.items():
                with self.subTest(module=module.__name__, payload=label), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    find = [valid_finding(module, "a.py:1"), valid_finding(module, "b.py:2")]
                    r = run_cli(module, root, find, payload)
                    self.assertEqual(r.returncode, 0, r.stderr)  # no crash, sidecar written
                    z = root / "analysis" / "zeugnis"
                    summary = json.loads(next(z.glob("*_summary.json")).read_text())
                    self.assertTrue(summary["verificationRan"])
                    self.assertEqual(summary["unverifiedCount"], 2)
                    self.assertEqual(sorted(summary["unverified"]), ["a.py:1", "b.py:2"])
                    self.assertTrue(all(f["verification"] == "unverified" for f in summary["findings"]))
                    self.assertIn("WARNING", r.stderr)
                    self.assertIn("UNVERIFIED", next((z / "reports").glob("*.md")).read_text())
                    result = record_pass(root)
                    self.assertFalse(result["converged"])
                    self.assertEqual(result["unverifiedBlockers"][0]["unverifiedCount"], 2)

    def test_explicit_skip_verification_is_still_a_skip(self):
        # positive control: the flag, and only the flag, bypasses reconcile
        for module in (contract_drift, agentic_reliability):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                r = run_cli(module, root, [valid_finding(module, "a.py:1")], None, "--skip-verification")
                self.assertEqual(r.returncode, 0, r.stderr)
                summary = json.loads(next((root / "analysis" / "zeugnis").glob("*_summary.json")).read_text())
                self.assertFalse(summary["verificationRan"])
                self.assertEqual(summary["unverifiedCount"], 0)
                self.assertTrue(record_pass(root)["converged"])

    def test_skip_flag_wins_over_an_unusable_payload_file(self):
        for module in (contract_drift, agentic_reliability):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                r = run_cli(module, Path(tmp), [valid_finding(module, "a.py:1")], "null", "--skip-verification")
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_failed_run_cannot_leave_a_stale_clean_sidecar_readable(self):
        for module in MODULES:
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                z = root / "analysis" / "zeugnis"
                z.mkdir(parents=True)
                domain = module.DOMAIN
                (z / f"{domain}_summary.json").write_text(json.dumps(sidecar(0)))  # last run was clean
                self.assertTrue(record_pass(root)["converged"])  # control: the stale file alone converges
                r = run_cli(module, root, "not json at all", "[]")  # this run dies loading Find
                self.assertNotEqual(r.returncode, 0)
                result = record_pass(root)
                self.assertFalse(result["converged"])
                self.assertIn("did not complete", result["unverifiedBlockers"][0]["reason"])

    def test_status_dashboard_survives_the_incomplete_marker_and_names_the_domain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertNotEqual(run_cli(contract_drift, root, "not json", "[]").returncode, 0)
            r = subprocess.run([sys.executable, str(HERE / "status_dashboard.py"), str(root)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(Path(json.loads(r.stdout)["data_path"]).read_text())
            self.assertIn("did not complete", data["unverifiedBlockers"][0]["reason"])

    def test_a_good_rerun_replaces_the_incomplete_marker(self):
        for module in MODULES:
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.assertNotEqual(run_cli(module, root, "not json", "[]").returncode, 0)
                self.assertFalse(record_pass(root)["converged"])
                r = run_cli(module, root, [valid_finding(module, "a.py:1")],
                            json.dumps([{"evidence": "a.py:1", "confirmed": True}]))
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue(record_pass(root)["converged"])
                self.assertEqual(list((root / "analysis" / "zeugnis").glob("*.tmp")), [])


class SabotageProof(unittest.TestCase):
    """Each guard, removed on a scratch copy, must turn the real tests red."""

    PLUGIN = HERE.parent

    def run_core(self, plugin_copy: Path) -> int:
        return subprocess.run(
            [sys.executable, str(plugin_copy / "scripts" / "test_reconcile_fail_closed.py"), *CORE_CLASSES],
            capture_output=True, text=True,
        ).returncode

    def copy(self, tmp: str) -> Path:
        dest = Path(tmp) / "zeugnis"
        shutil.copytree(self.PLUGIN, dest, ignore=shutil.ignore_patterns("__pycache__", "fixtures"))
        return dest

    def patched(self, rel: str, old: str, new: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            dest = self.copy(tmp)
            target = dest / rel
            text = target.read_text()
            self.assertIn(old, text, f"sabotage target vanished from {rel}; update this test")
            target.write_text(text.replace(old, new))
            return self.run_core(dest)

    def test_untouched_copy_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_core(self.copy(tmp)), 0)

    def test_silent_drop_of_abstains_goes_red(self):
        self.assertNotEqual(self.patched("scripts/lib/verification.py", "elif verdict == UNVERIFIED:", "elif False:"), 0)

    def test_missing_confirmed_defaulting_to_true_goes_red(self):
        self.assertNotEqual(self.patched(
            "scripts/lib/verification.py", 'record.get("confirmed", None)', 'record.get("confirmed", True)'), 0)

    def test_gate_that_ignores_blockers_goes_red(self):
        self.assertNotEqual(self.patched(
            "scripts/cycle_engine.py", "converged = no_progress and not blockers", "converged = no_progress"), 0)

    def test_gate_that_treats_missing_count_as_zero_goes_red(self):
        self.assertNotEqual(self.patched(
            "scripts/lib/verification.py",
            'summary.get("unverifiedCount") if isinstance(summary, dict) else None',
            'summary.get("unverifiedCount", 0) if isinstance(summary, dict) else 0'), 0)

    def test_unusable_payload_treated_as_skip_goes_red(self):
        self.assertNotEqual(self.patched(
            "scripts/lib/verification.py",
            "    if records is None:\n        records = []\n",
            "    if records is None:\n        return find_findings\n"), 0)

    def test_skip_decided_from_loaded_value_in_cli_goes_red(self):
        self.assertNotEqual(self.patched(
            "scripts/contract_drift.py",
            "raw_verify = None if args.skip_verification else load_raw(args.verify_json)",
            "raw_verify = load_raw(args.verify_json)\n    if raw_verify is None:\n        args.skip_verification = True"), 0)

    def test_sidecar_not_invalidated_before_run_goes_red(self):
        self.assertNotEqual(self.patched(
            "scripts/lib/verification.py",
            'path.write_text(json.dumps({"domain": domain, "incomplete": True}), encoding="utf-8")',
            "pass"), 0)

    def test_incomplete_marker_ignored_by_gate_goes_red(self):
        self.assertNotEqual(self.patched(
            "scripts/lib/verification.py",
            'summary.get("incomplete") is True', "False"), 0)

    def test_count_taken_after_filters_goes_red(self):
        self.assertNotEqual(self.patched(
            "scripts/assertion_audit.py", "unverified = unverified_evidence(survivors)",
            "unverified = []  # sabotaged placeholder"), 0)


if __name__ == "__main__":
    unittest.main()
