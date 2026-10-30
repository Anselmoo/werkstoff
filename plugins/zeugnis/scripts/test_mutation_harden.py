#!/usr/bin/env python3
"""Tests for zeugnis-mutation-harden (issue #142): the harness, the parsed
results, kill proofs, the real-tool citation check, and the cycle gate.

Every refusal here is a fail-closed path -- a citation that no longer holds,
a proof that shows no kill, a kill the re-measure contradicts -- so each has
a case that must be REFUSED next to one that must be accepted. They run on
fabricated tool output (a mutmut 3 `.meta` sidecar is plain JSON), so no
mutation tool is needed.

TestEndToEnd drives a real mutmut on a throwaway repo and runs only when
ZEUGNIS_MUTMUT names a mutmut 3 binary (installed with pytest in a venv,
never into this repo): a survivor must become a proven kill.

Run: python3 plugins/zeugnis/scripts/test_mutation_harden.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).absolute().parent
sys.path.insert(0, str(SCRIPTS))

import mutation_harden as mh  # noqa: E402
from lib.mutation_results import (  # noqa: E402
    PROOF_SCHEMA,
    RESULTS_SCHEMA,
    MutationResultsError,
    load_proof,
    score,
    verify_citation,
)

MUTANT = "shop.pricing.x_discount__mutmut_3"
KILLED = "shop.pricing.x_discount__mutmut_4"
RUN = Path("analysis/zeugnis/mutation/r1")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Repo:
    """A repo holding one collected shard: a .meta sidecar, its results file,
    and (optionally) a kill proof."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "analysis" / "zeugnis").mkdir(parents=True)
        self.meta = self.root / RUN / "shards" / "core" / "mutants" / "src" / "shop" / "pricing.py.meta"
        self.meta.parent.mkdir(parents=True)
        self.meta.write_text(json.dumps({"exit_code_by_key": {MUTANT: 0, KILLED: 1},
                                         "durations_by_key": {}, "estimated_durations_by_key": {}}))
        self.records = self.root / RUN / "records"
        self.records.mkdir(parents=True)
        meta_rel = self.meta.relative_to(self.root).as_posix()
        self.results_rel = (RUN / "records" / "shards-core.results.json").as_posix()
        self.write(self.results_rel, {
            "schema": RESULTS_SCHEMA, "tool": "mutmut", "toolFiles": [{"path": meta_rel, "sha256": sha(self.meta)}],
            "mutants": [{"id": MUTANT, "module": "src/shop/pricing.py", "status": "survived", "exitCode": 0,
                         "toolFile": meta_rel},
                        {"id": KILLED, "module": "src/shop/pricing.py", "status": "killed", "exitCode": 1,
                         "toolFile": meta_rel}]})

    def write(self, relpath: str, data: dict) -> str:
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return relpath

    def proof(self, *, verdict="killed", clean=0, mutant=1, mutant_id=MUTANT, same_sha=False) -> str:
        return self.write((RUN / "records" / f"proof-{verdict}-{clean}-{mutant}.json").as_posix(), {
            "schema": PROOF_SCHEMA, "mutantId": mutant_id, "verdict": verdict, "cleanExit": clean,
            "mutantExit": mutant, "originalSourceSha256": "a", "mutatedSourceSha256": "a" if same_sha else "b",
            "testId": "tests/test_x.py::test_boundary"})

    def finding(self, **over) -> dict:
        return {"severity": "Medium", "title": "boundary survives", "evidence": "src/shop/pricing.py:3",
                "category": "weak-assertion", "fixability": "advisory", "toolSource": "real-tool",
                "resultsFile": self.results_rel, "mutantId": MUTANT, **over}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


class TestCitation(unittest.TestCase):
    def test_valid_citation_holds(self):
        with Repo() as repo:
            self.assertEqual(verify_citation(repo.root, repo.finding())["status"], "survived")

    def test_uncited_real_tool_finding_refused(self):
        with Repo() as repo:
            for over in ({"resultsFile": None}, {"mutantId": ""}):
                with self.assertRaises(MutationResultsError):
                    verify_citation(repo.root, repo.finding(**over))

    def test_sidecar_changed_after_collect_refused(self):
        with Repo() as repo:
            repo.meta.write_text(repo.meta.read_text().replace(f'"{MUTANT}": 0', f'"{MUTANT}": 1'))
            with self.assertRaisesRegex(MutationResultsError, "changed after collect"):
                verify_citation(repo.root, repo.finding())

    def test_killed_mutant_is_not_a_finding(self):
        with Repo() as repo, self.assertRaisesRegex(MutationResultsError, "only"):
            verify_citation(repo.root, repo.finding(mutantId=KILLED))

    def test_results_outside_mutation_tree_refused(self):
        with Repo() as repo:
            moved = repo.write("analysis/zeugnis/fake.results.json",
                               json.loads((repo.root / repo.results_rel).read_text()))
            with self.assertRaisesRegex(MutationResultsError, "not under"):
                verify_citation(repo.root, repo.finding(resultsFile=moved))

    def test_results_file_disagreeing_with_sidecar_refused(self):
        with Repo() as repo:
            data = json.loads((repo.root / repo.results_rel).read_text())
            data["mutants"][1]["status"] = "survived"  # the sidecar says killed
            repo.write(repo.results_rel, data)
            with self.assertRaisesRegex(MutationResultsError, "says 'killed'"):
                verify_citation(repo.root, repo.finding(mutantId=KILLED))


class TestProof(unittest.TestCase):
    def test_kill_accepted(self):
        with Repo() as repo:
            self.assertEqual(load_proof(repo.root, repo.proof(), MUTANT)["verdict"], "killed")

    def test_non_kills_refused(self):
        with Repo() as repo:
            for kwargs in ({"verdict": "survives", "mutant": 0}, {"verdict": "invalid", "clean": 0, "mutant": 2},
                           {"verdict": "killed", "clean": 5, "mutant": 1}, {"same_sha": True}):
                with self.assertRaises(MutationResultsError, msg=kwargs):
                    load_proof(repo.root, repo.proof(**kwargs), MUTANT)

    def test_proof_for_another_mutant_refused(self):
        with Repo() as repo, self.assertRaisesRegex(MutationResultsError, "is for"):
            load_proof(repo.root, repo.proof(mutant_id=KILLED), MUTANT)


class TestAssertionAuditProvenance(unittest.TestCase):
    """The same gap closed in the existing writer: a real-tool finding with no
    citation used to pass on its enum value alone."""

    def _audit(self, repo: Repo, findings: list[dict]) -> dict:
        find = repo.write("find.json", {"findings": findings})
        verify = repo.write("verify.json", {"findings": [{"evidence": f["evidence"], "confirmed": True}
                                                         for f in findings]})
        r = subprocess.run([sys.executable, str(SCRIPTS / "assertion_audit.py"), str(repo.root),
                            "--find-json", str(repo.root / find), "--verify-json", str(repo.root / verify)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads((repo.root / "analysis/zeugnis/assertion_audit_summary.json").read_text())

    def test_cited_real_tool_finding_kept(self):
        with Repo() as repo:
            self.assertEqual(len(self._audit(repo, [repo.finding()])["findings"]), 1)

    def test_uncited_real_tool_finding_dropped(self):
        with Repo() as repo:
            bare = repo.finding()
            del bare["resultsFile"]
            self.assertEqual(self._audit(repo, [bare])["findings"], [])

    def test_llm_reasoned_finding_needs_no_citation(self):
        with Repo() as repo:
            llm = {k: v for k, v in repo.finding(toolSource="llm-reasoned").items()
                   if k not in ("resultsFile", "mutantId")}
            self.assertEqual(len(self._audit(repo, [llm])["findings"]), 1)


class TestCycleGate(unittest.TestCase):
    def _record(self, repo: Repo, outcome: dict) -> subprocess.CompletedProcess:
        pass_json = repo.write("pass.json", {"passNumber": 1, "domain": "mutation_harden", "mode": "fix",
                                             "outcomes": [outcome]})
        return subprocess.run([sys.executable, str(SCRIPTS / "cycle_engine.py"), "record-pass-result",
                               str(repo.root), "--pass-json", str(repo.root / pass_json)],
                              capture_output=True, text=True, timeout=60)

    def _fixed_outcome(self, repo: Repo, **over) -> dict:
        return {"findingId": f"mutant:{MUTANT}", "category": "surviving-mutant", "evidence": "src/shop/pricing.py:3",
                "severity": "Medium", "outcome": "fixed", "mutantId": MUTANT, "proofFile": repo.proof(), **over}

    def test_proven_kill_closes(self):
        with Repo() as repo:
            r = self._record(repo, self._fixed_outcome(repo))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["closed"], 1)

    def test_fixed_without_proof_refused(self):
        with Repo() as repo:
            r = self._record(repo, self._fixed_outcome(repo, proofFile=None))
            self.assertEqual(r.returncode, 2)
            self.assertIn("no kill proof", r.stderr)

    def test_proof_for_other_finding_refused(self):
        with Repo() as repo:
            r = self._record(repo, self._fixed_outcome(repo, findingId=f"mutant:{KILLED}"))
            self.assertEqual(r.returncode, 2)

    def test_surviving_proof_refused(self):
        with Repo() as repo:
            r = self._record(repo, self._fixed_outcome(repo, proofFile=repo.proof(verdict="survives", mutant=0)))
            self.assertEqual(r.returncode, 2)

    def test_assertion_audit_stays_draft_only(self):
        with Repo() as repo:
            pass_json = repo.write("pass.json", {"passNumber": 1, "domain": "assertion_audit", "mode": "fix",
                                                 "outcomes": [self._fixed_outcome(repo, category="weak-assertion")]})
            r = subprocess.run([sys.executable, str(SCRIPTS / "cycle_engine.py"), "record-pass-result",
                                str(repo.root), "--pass-json", str(repo.root / pass_json)],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 2, r.stdout)


class TestJudgeEntry(unittest.TestCase):
    TARGET = {"id": MUTANT, "module": "src/shop/pricing.py", "status": "survived"}

    def test_states(self):
        with Repo() as repo:
            good = {"disposition": "killed", "proof": repo.proof()}
            cases = [
                (good, None, "killed"),
                (good, "killed", "killed"),
                (good, "survived", "contradicted"),
                ({"disposition": "killed", "proof": repo.proof(verdict="survives", mutant=0)}, None, "proof-rejected"),
                ({"disposition": "equivalent", "reason": "differs only where both branches agree"}, "survived",
                 "equivalent"),
                ({"disposition": "equivalent", "reason": "line one\nline two"}, None, "rejected-equivalent"),
                ({"disposition": "equivalent", "reason": ""}, None, "rejected-equivalent"),
                ({"disposition": "skip"}, None, "rejected"),
                (None, None, "unreached"),
                (None, "killed", "killed"),
            ]
            for entry, after, expected in cases:
                self.assertEqual(mh.judge_entry(repo.root, entry, self.TARGET, after)["state"], expected,
                                 (entry, after))

    def test_equivalent_is_never_a_kill(self):
        before = {"killed": 1, "survived": 2, "noTests": 1, "score": 1 / 3}
        after = mh.after_counts({**mh.empty_counts(), **before},
                                [{"state": "equivalent", "before": "survived"}])
        self.assertEqual((after["killed"], after["survived"], after["equivalent"]), (1, 2, 1))
        self.assertEqual(after["score"], score({"killed": 1, "survived": 2}))
        self.assertGreater(after["scoreExcludingEquivalent"], after["score"])

    def test_untested_kill_moves_out_of_no_tests(self):
        after = mh.after_counts({**mh.empty_counts(), "killed": 1, "noTests": 2},
                                [{"state": "killed", "before": "no tests"}])
        self.assertEqual((after["killed"], after["noTests"], after["score"]), (2, 1, 1.0))


class TestScore(unittest.TestCase):
    def test_no_tests_is_not_in_the_denominator(self):
        """The issue's own example: 124 mutants, 38 killed, 86 untested."""
        self.assertEqual(score({"killed": 38, "survived": 0, "noTests": 86}), 1.0)
        self.assertIsNone(score({"killed": 0, "survived": 0, "noTests": 3}))


class TestMutmutConfig(unittest.TestCase):
    def test_rewrites_only_the_mutmut_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            (copy / "pyproject.toml").write_text(
                '[project]\nname = "x"\n\n[tool.mutmut]\npaths_to_mutate = ["src"]\nalso_copy = ["data"]\n'
                'do_not_mutate = ["src/gen.py"]\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
            config = mh.write_mutmut_config(copy, ["src/shop"], ["tests/unit"], ["src/shop/_v.py"])
            self.assertEqual(config, {"also_copy": ["data"], "source_paths": ["src/shop"],
                                      "pytest_add_cli_args_test_selection": ["tests/unit"],
                                      "do_not_mutate": ["src/gen.py", "src/shop/_v.py"]})
            text = (copy / "pyproject.toml").read_text()
            self.assertNotIn("paths_to_mutate", text)
            self.assertIn('testpaths = ["tests"]', text)

    def test_no_pyproject_gets_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            mh.write_mutmut_config(Path(tmp), ["src"], ["tests"], [])
            self.assertIn("[tool.mutmut]", (Path(tmp) / "pyproject.toml").read_text())

    def test_sub_tables_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text('[tool.mutmut]\nx = 1\n[tool.mutmut.extra]\ny = 2\n')
            with self.assertRaises(mh.HarnessError):
                mh.write_mutmut_config(Path(tmp), ["src"], ["tests"], [])

    def test_exclusion_without_reason_refused(self):
        for raw in ("src/gen.py", "src/gen.py=", "=reason", "src/gen=pinned by hashes"):
            with self.assertRaises(mh.HarnessError, msg=raw):
                mh.parse_exclusions([raw])
        self.assertEqual(mh.parse_exclusions(["src/gen.py=pinned by committed hashes"]),
                         [{"glob": "src/gen.py", "reason": "pinned by committed hashes"}])


class TestClassify(unittest.TestCase):
    def test_kinds(self):
        def diff(old: str, new: str) -> str:
            return f"--- a\n+++ b\n-{old}\n+{new}\n"
        cases = {
            ("if a and b >= 100:", "if a or b >= 100:"): "boolean-logic",
            ("if a and b >= 100:", "if a and b > 100:"): "comparison",
            ("if a and b >= 100:", "if a and b >= 101:"): "constant",
            ("return round(x, 2)", "return round(x, None)"): "value-replaced-by-None",
            ("return round(x * 0.9, 2)", "return round(2)"): "code-removed",
            ('name = "abc"', 'name = "XXabcXX"'): "string-literal",
        }
        for (old, new), kind in cases.items():
            self.assertEqual(mh.classify(diff(old, new)), kind, (old, new))


class TestHarnessRefusals(unittest.TestCase):
    def test_tool_refuses_a_directory_that_is_not_a_copy(self):
        with Repo() as repo:
            for path in (repo.root, repo.root / RUN / "shards" / "core"):  # the second has no marker
                with self.assertRaises(mh.HarnessError):
                    mh.require_copy(path)


class TestProofImportsTheCopy(unittest.TestCase):
    """A project installed editable imports the WORKING TREE's package from
    inside a proof copy; applying the mutant there would then prove nothing.
    prove() pins the copy's import root first and refuses (verdict invalid)
    when the module still resolves outside the copy."""

    def test_dotted_module_and_import_root(self):
        self.assertEqual(mh.dotted_module("shop.pricing.x_discount__mutmut_3"), "shop.pricing")
        self.assertEqual(mh.dotted_module("shop.cart.xǁCartǁtotal__mutmut_1"), "shop.cart")
        copy = Path("/c")
        self.assertEqual(mh.import_root(copy, "src/shop/pricing.py", "shop.pricing"), copy / "src")
        self.assertEqual(mh.import_root(copy, "shop/pricing.py", "shop.pricing"), copy)
        self.assertEqual(mh.import_root(copy, "src/shop/__init__.py", "shop"), copy / "src")
        self.assertEqual(mh.import_root(copy, "odd/place.py", "shop.pricing"), copy)

    def test_pinned_root_wins_and_outside_origin_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree, copy = Path(tmp) / "tree", Path(tmp) / "copy"
            for root in (tree, copy):
                (root / "src" / "zshopx").mkdir(parents=True)
                (root / "src" / "zshopx" / "__init__.py").write_text("")
                (root / "src" / "zshopx" / "pricing.py").write_text("X = 1\n")
            # The editable-install stand-in: the working tree is already on the path.
            stale = {**os.environ, "PYTHONPATH": str(tree / "src")}
            outside = mh.module_origin(sys.executable, "zshopx.pricing", copy, stale)
            self.assertFalse(mh.imports_from_copy(outside, copy))
            pinned = mh.test_env(mh.import_root(copy, "src/zshopx/pricing.py", "zshopx.pricing"))
            pinned["PYTHONPATH"] += os.pathsep + str(tree / "src")
            self.assertTrue(mh.imports_from_copy(mh.module_origin(sys.executable, "zshopx.pricing", copy, pinned), copy))
            self.assertFalse(mh.imports_from_copy(None, copy))


@unittest.skipUnless(os.environ.get("ZEUGNIS_MUTMUT"), "set ZEUGNIS_MUTMUT to a mutmut 3 binary to run")
class TestEndToEnd(unittest.TestCase):
    """prepare -> run-shard -> collect -> prove -> remeasure -> report on a
    real mutmut: the boundary mutant survives the original suite and is a
    proven kill after one new test."""

    def _h(self, repo: Path, *args: str, ok: bool = True) -> dict:
        tool = ["--mutmut", os.environ["ZEUGNIS_MUTMUT"]] if args[0] in ("run-shard", "collect", "prove") else []
        r = subprocess.run([sys.executable, str(SCRIPTS / "mutation_harden.py"), args[0], str(repo), *args[1:], *tool],
                           capture_output=True, text=True, timeout=600)
        if ok:
            self.assertIn(r.returncode, (0, 1), r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else {"stderr": r.stderr, "code": r.returncode}

    def test_survivor_becomes_proven_kill(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "src" / "shop").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "src" / "shop" / "__init__.py").write_text("")
            (repo / "src" / "shop" / "pricing.py").write_text(
                "def discount(total, is_member):\n    if is_member and total >= 100:\n"
                "        return round(total * 0.9, 2)\n    return total\n")
            (repo / "tests" / "test_pricing.py").write_text(
                "from shop.pricing import discount\n\n\ndef test_member():\n    assert discount(200, True) < 200\n")
            (repo / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["src"]\n')
            (repo / ".gitignore").write_text("analysis/\n")
            for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"]):
                subprocess.run(["git", "-C", str(repo), *cmd], check=True)
            common = ["--run-id", "e2e", "--shard", "core"]
            self._h(repo, "prepare", *common, "--source", "src/shop", "--test", "tests")
            self._h(repo, "run-shard", *common, "--time-box", "300")
            base = self._h(repo, "collect", *common)
            self.assertTrue(base["complete"])
            results = json.loads((repo / base["resultsFile"]).read_text())
            boundary = next(m for m in results["mutants"]
                            if m["status"] == "survived" and ">= 101" in m.get("diff", ""))
            (repo / "tests" / "test_boundary.py").write_text(
                "from shop.pricing import discount\n\n\ndef test_starts_at_100():\n"
                "    assert discount(100, True) == 90.0\n")
            weak = self._h(repo, "prove", *common, "--mutant", boundary["id"], "--test-file",
                           "tests/test_pricing.py", "--test-id", "tests/test_pricing.py::test_member")
            self.assertEqual(weak["verdict"], "survives")
            proof = self._h(repo, "prove", *common, "--mutant", boundary["id"], "--test-file",
                            "tests/test_boundary.py", "--test-id", "tests/test_boundary.py::test_starts_at_100")
            self.assertEqual((proof["verdict"], proof["cleanExit"], proof["mutantExit"]), ("killed", 0, 1))
            self._h(repo, "prepare", *common, "--kind", "remeasure", "--overlay", "tests/test_boundary.py")
            self._h(repo, "run-shard", *common, "--kind", "remeasure", "--time-box", "300")
            self._h(repo, "collect", *common, "--kind", "remeasure")
            triage = repo / "triage.json"
            triage.write_text(json.dumps({"lanes": [{"lane": "p", "module": "src/shop/pricing.py", "budget": {"mutants": 1},
                                                     "entries": [{"mutantId": boundary["id"], "disposition": "killed",
                                                                  "proof": proof["proofFile"]}]}]}))
            report = self._h(repo, "report", "--run-id", "e2e", "--triage", str(triage))
            self.assertGreaterEqual(report["kills"], 1)
            summary = json.loads((repo / "analysis/zeugnis/mutation_harden_summary.json").read_text())
            self.assertIn(boundary["id"], [k["mutantId"] for k in summary["kills"]])
            module = summary["modules"][0]
            self.assertGreater(module["after"]["score"], module["before"]["score"])
            self.assertEqual(subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "src"],
                                            capture_output=True, text=True).stdout, "", "source must be untouched")
            again = self._h(repo, "run-shard", *common, "--time-box", "60", ok=False)
            self.assertEqual(again.get("code"), 2, "a copy is never re-run or resumed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
