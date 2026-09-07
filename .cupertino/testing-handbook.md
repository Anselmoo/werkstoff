# testing handbook

Drafted by `cupertino-handbook-draft` (domain: `testing`) via one dimension-analyst dispatch per
dimension, each independently re-verified by a second, blind dispatch of the same agent type.

## Dimensions

### coverage-expectations — CONFIRMED

**Rule:** Every guard, oracle, or lint script that gates CI or a hook (e.g. test/plugins/lint-*.py, test/docs/*oracle* checks) must ship a companion calibration test, written against fabricated fixtures/cases before the guard is ever pointed at real repo data, that includes at least one case proving the guard actually goes red (not only cases proving it passes) — a guard with no such calibration test, or one whose cases are all pass-only, does not satisfy this project's testing bar regardless of how much of the guard's code a coverage percentage would report as exercised.

**Source:** `analyzed`

**Evidence:** CLAUDE.md:69-77 ("Verify the instrument before trusting its verdict... oracles are calibrated against fabricated transcripts before first use"; "test-lint-tag-releases.py... is sabotage-tested: blank out the guard's `missing` list and 4 of its 13 cases go red"); test/plugins/test-lint-tag-releases.py:1-9 ("Calibration for lint-tag-releases.py: prove it goes red before trusting it... Written against fabricated tag/release lists BEFORE the guard was pointed at the real repository"); test/docs/README.md:121-132 ("The calibration rule, made concrete... calibration.tsv copies each regex/antiregex verbatim from journeys.tsv and asserts what verdict it must produce against each fixture. calibrate-oracles.sh fails loudly on any mismatch"); test/plugins/lint-release-wiring.py:88 and test/plugins/test-lint-release-wiring.py:118; grep across the repo for coverage/fail-under/pytest-cov/codecov found no line-coverage percentage target anywhere in .github/workflows, pyproject.toml files, or any config.

**Verification verdict:** `confirmed`

**Verification note:** Re-derived independently and it holds. Evidence is real and accurately quoted: CLAUDE.md's "Verify the instrument before trusting its verdict" section (lines ~79-82) states the calibrate-before-first-use principle; test/plugins/test-lint-tag-releases.py (header, lines 1-9) and test/plugins/test-lint-release-wiring.py (its explicit fail-loudly cases and final tally around lines 100-120) are real calibration harnesses containing cases that must produce a red/failing verdict, not just pass-only cases; test/docs/README.md:121-138 documents the identical discipline for the docs oracles, backed by real files (test/docs/calibration/fixtures/*.txt, calibration.tsv, calibrate-oracles.sh, and test/docs/*oracle* scripts which do exist as named). A repo-wide grep for coverage-percentage tooling (fail-under, pytest-cov, codecov) found nothing in .github/workflows or any config, confirming coverage-expectations here really is calibration-based rather than a line-coverage-percentage target, as claimed. One caveat worth flagging for whoever applies this rule going forward rather than a reason to revise it: the convention is not yet universally satisfied by every existing guard — test/plugins/lint-plugin-authors.py is wired into CI (.github/workflows/plugin-checks.yml:107) but has no test-lint-plugin-authors.py calibration companion, and lint-frontmatter.py also has none (though it isn't currently wired into CI or a hook, so it falls outside the rule's stated scope). That gap doesn't make the sourceMode claim dishonest — the principle is directly and repeatedly stated in CLAUDE.md's own words and demonstrated concretely by two real, inspected artifacts — but it means the rule describes an aspirational/enforceable-going-forward bar rather than 100%-already-achieved current practice, and a drift audit applying it today would immediately find at least one non-compliant CI-gating guard (lint-plugin-authors.py). The rule itself is concrete and mechanically checkable: for any script identified as gating CI (via a workflow file) or a hook (via hooks.json), check for an existing companion test file with fabricated fixtures and at least one case whose expected verdict is a failure/red exit code.</note>
</invoke>


### test-naming — NEEDS REVISION

**Rule:** Every test file must be named `test_<subject>.py` and every test function within it must be named `def test_<snake_case_behavior_or_condition>(...)`, describing the specific behavior/condition being verified (e.g. `test_missing_blast_radius_denies`, not `test_case_1` or `test_it_works`), matching pytest's default discovery convention with no custom `python_files`/`python_functions` override.

**Source:** `analyzed`

**Evidence:** plugins/andon/hooks/test_andon_enforce.py:149 (`def test_missing_blast_radius_denies(self):`) and tools/enforcement-audit/test_audit_enforcement.py:57 (`def test_control_flow_guard_is_code(self):`); the same test_*.py filename + test_<behavior> function pattern holds across plugins/self-assess/scripts/lib/test_staleness.py, plugins/lehre/scripts/test_lehre_core.py, tools/werkstoff-cli/tests/test_cli.py, and test/plugins/test-lint-release-wiring.py's own test_*.py suite — with no pytest.ini/pyproject.toml override of python_files or python_functions anywhere in the repo (only tools/werkstoff-cli/pyproject.toml:39 sets `testpaths = ["tests"]`, leaving name discovery at pytest's default).

**Verification verdict:** `revise`

**Verification note:** The candidate's two primary citations check out exactly as claimed: plugins/andon/hooks/test_andon_enforce.py:149 does define `def test_missing_blast_radius_denies(self):`, and tools/enforcement-audit/test_audit_enforcement.py:57 does define `def test_control_flow_guard_is_code(self):`. The "no pytest.ini/pyproject.toml override" claim is also confirmed — there is no pytest.ini anywhere, and the only pyproject.toml with a `[tool.pytest.ini_options]` block is tools/werkstoff-cli/pyproject.toml:39, which sets only `testpaths = ["tests"]`, no `python_files`/`python_functions` override.

However, two of the four supporting citations the candidate lists as corroboration do NOT actually support the pattern, and one directly contradicts it:

1. `plugins/lehre/scripts/test_lehre_core.py` has a compliant *filename* but contains zero `def test_...` functions anywhere in the file — it uses a `check(label, actual, expected)` call-based structure instead (e.g. line 99: `check("misplaced test flagged", ...)`). The candidate cited this file as proof the "test_<behavior> function pattern holds," but it does not.

2. `test/plugins/test-lint-release-wiring.py` is cited as "its own test_*.py suite," but the file's actual name uses a hyphen (`test-lint-release-wiring.py`), not the underscore form the rule mandates (`test_<subject>.py`), and it contains zero `def test_...` functions — it is a standalone calibration script built around a `case(label, mutate, want_rc, want_text)` helper, run directly via `python3 test/plugins/test-lint-release-wiring.py`, not pytest-discovered at all. `test/plugins/test-lint-tag-releases.py` is the same shape (hyphenated name, no `def test_` functions).

So the repo actually contains two distinct, real conventions: pytest/unittest-style suites (`test_<subject>.py` + `def test_<behavior>(self)`, which the andon and enforcement-audit citations genuinely demonstrate) and a separate class of non-pytest "calibration" scripts (hyphenated `test-<subject>.py` names or underscore names with a `check()`/assertion-helper body instead of `def test_` functions) that CLAUDE.md itself refers to by name (e.g. "Its calibration, `test-lint-tag-releases.py`, is sabotage-tested"). The candidate's rule states an unqualified universal ("every test file," "every test function") and its own evidence list quietly includes files that violate that universal, without disclosing the exception. That overstates the consistency of the convention and would make the rule mechanically fail against real, intentional files in this repo the moment a drift audit ran it as literally written.

Recommend revising the rule to scope it explicitly to pytest-discovered suites (e.g. files under `tests/`, `scripts/`, or plugin `hooks/` directories that are collected by `pytest`), or to carve out the standalone `test-*.py` calibration-script category by name, rather than claiming the pattern is universal across every file matching `test_*.py`/`test-*.py` in the repo.

### fixture-and-mocking-policy — NEEDS REVISION

**Rule:** Tests must exercise real filesystem/git state (via tmp_path or a throwaway git repo) rather than mocking filesystem or module internals; unittest.mock/monkeypatch may only patch genuine external-process boundaries (e.g. shutil.which, subprocess exit codes), and process calls under test must be injected as a plain callable (dependency injection, e.g. a hand-written fake `run` function) rather than patched via mock.patch.

**Source:** `analyzed`

**Evidence:** test/docs/test_docs_ux_audit.py:7 ("assert on real files -- no mocking of the filesystem calls themselves"); tools/catalog-validator/test_validate_catalog.py:7 (same sentence); plugins/self-assess/scripts/lib/test_staleness.py:9-11 ("exercise the real logic ... against a real git repo -- commit timestamps and file mtimes are both genuine, not mocked"); tools/werkstoff-cli/tests/test_core.py:19-26,95-96,145-146,151-152 (monkeypatch limited to core.shutil.which; subprocess calls injected via hand-written `_fake_run`, not mock.patch)

**Verification verdict:** `revise`

**Verification note:** The general thrust is real and well-cited: test/docs/test_docs_ux_audit.py:6-7, tools/catalog-validator/test_validate_catalog.py:7, and plugins/self-assess/scripts/lib/test_staleness.py:9-11 do document a convention of exercising real tmp_path/git-repo state instead of mocking filesystem calls, and tools/werkstoff-cli/tests/test_core.py:19-26/96/117/146/152 do confirm monkeypatch limited to core.shutil.which plus a hand-written _fake_run callable injected for subprocess — that part of the sourceMode="analyzed" claim holds up.

However the rule's specific, narrower clause -- "unittest.mock/monkeypatch may only patch genuine external-process boundaries (e.g. shutil.which, subprocess exit codes)" -- is contradicted by the very file the candidate cites as evidence. test/docs/test_docs_ux_audit.py:152 (`mock.patch.object(AUDIT, "CONFIG", absent)`), :190-191 (`mock.patch.object(AUDIT, "DOCS", docs)`, `mock.patch.object(AUDIT, "src_exclude", list)`), and :204-205 (`mock.patch.object(AUDIT, "DOCS", docs)`, `mock.patch.object(AUDIT, "src_exclude", lambda: [...])`) all use mock.patch.object to swap out module-level path constants and even a function -- none of these are external-process boundaries like shutil.which or a subprocess exit code. They are internal module state used as a substitution seam, in the same file whose docstring the candidate quotes. A mechanical drift audit built on the rule as worded would flag this repo's own existing, apparently-sanctioned pattern (patching module constants/functions to point at a fixture directory) as a violation, which is not the intent evidenced by the surrounding tests.

The rule needs to be loosened or re-scoped -- e.g. explicitly allow patching module-level path/config constants and pure functions as a substitution seam (as seen in test_docs_ux_audit.py) in addition to the shutil.which/subprocess carve-out -- before it is accurate and mechanically checkable against the codebase as it actually exists today.

### flakiness-tolerance — CONFIRMED

**Rule:** Any behavioral test harness invoking a non-deterministic (LLM-backed) run must classify a run that produced no real output — empty stdout, a known CLI refusal/rate-limit banner, a mid-response truncation marker, or stdout below the substantive-length floor — as a distinct ERROR verdict that is never counted as either PASS or FAIL, and must never treat a single-run PASS as proof a rule holds; only an N/N pass rate across repeated runs (with 0 errors) may be cited as evidence a prose-enforced behavior is reliable, with anything less reported explicitly as "a tendency, not a rule."

**Source:** `analyzed`

**Evidence:** test/plugins/run.sh:154-190 (four-guard vacuous-output detection producing a separate `VERDICT $id ERROR`, never tallied as pass/fail) and test/plugins/determinism.sh:9-13,80,128-132 ("a guard worth the name is N/N; anything less is a tendency, not a rule"; "Any error count above 0 invalidates that case's rate")

**Verification verdict:** `confirmed`

**Verification note:** Evidence re-verified directly: test/plugins/run.sh:154-190 contains exactly the described four-guard ERROR-classification cascade (empty stdout, refusal/rate-limit banner regex, truncation-marker regex, MIN_STDOUT_BYTES floor), tallied separately from pass/fail. test/plugins/determinism.sh:9-13,80,128-132 contain the quoted lines verbatim ('a guard worth the name is N/N; anything less is a tendency, not a rule'; 'Any error count above 0 invalidates that case's rate'). Additionally found the identical pattern independently replicated in test/docs/run-journeys.sh (lines 39-40, 151, 197-211, which explicitly says 'identical criteria to test/plugins/run.sh'), confirming this is a real cross-file convention rather than an isolated snippet. sourceMode 'analyzed' is honest. The rule is concrete and mechanically auditable: specific detection triggers, a named distinct verdict, a numeric reliability threshold (N/N, 0 errors), and a required reporting phrase for anything less.

### assertion-strength — NEEDS REVISION

**Rule:** Every test/calibration case in test/plugins/ and test/docs/ that shells out to a script or hook must assert both the exact expected exit/return code and a specific expected output substring (e.g. `want_rc`/`want_text`, or `rc_v == 2`), never a bare truthy/non-zero/success check alone — because a case that only checks pass/fail can pass for the wrong reason and get "fixed" by silencing the wrong thing.

**Source:** `analyzed`

**Evidence:** test/plugins/test-lint-tag-releases.py:24-26 ("Each case is (label, tags, releases, grace, expected exit, expected substring). The substring matters as much as the code: a guard that fails for the wrong reason gets \"fixed\" by silencing the wrong thing.") and its `run_case` at lines 47-79 (`want_rc`, `want_text`, `problems.append` on either mismatch); the identical pattern and near-identical rationale in test/plugins/test-lint-release-wiring.py:17-19 and its `case()` at lines 58-71 (`ok = proc.returncode == want_rc and want_text.lower() in out.lower()`); and test/plugins/verify-hooks-deny.py:207 (`ok = (rc_v == 2) and (rc_i == 0)`, exact codes for both the violating and inert probe, not just "one succeeded, one failed").

**Verification verdict:** `revise`

**Verification note:** The three citations check out verbatim: test/plugins/test-lint-tag-releases.py:24-26 and its run_case (lines 47-79) do assert want_rc + want_text together; test/plugins/test-lint-release-wiring.py:17-19 and case() (lines 58-71) do the same (`ok = proc.returncode == want_rc and want_text.lower() in out.lower()`); test/plugins/verify-hooks-deny.py:207 does check `(rc_v == 2) and (rc_i == 0)` — exact codes for both probes. So sourceMode "analyzed" is honestly grounded for those three files.

But the rule as written claims this is the practice for "every test/calibration case in test/plugins/ ... that shells out to a script or hook," and that claim is false. test/plugins/verify-takt-payload-shapes.py shells out to plugins/takt/hooks/takt_guard.py for 16 cases (lines 35-77) and asserts only `actual == expected` exit code (line 104) — no output-substring check anywhere in the file. test/plugins/verify-contested-fixture.py's probe() (lines 55-59) is even weaker: it only checks `r.returncode != 0` (a bare non-zero check, not even an exact-code comparison) with no substring assertion. Both are real, current test/calibration files in the same directory the rule claims universal coverage over, and both directly contradict "never a bare truthy/non-zero/success check alone." test/docs/ contributes no counter-evidence either way — test/docs/test_docs_ux_audit.py never shells out to a script (it imports the module in-process via importlib), so the rule's scope there is vacuous, not supporting.

This is exactly the "genuine convention in some places, contradicted elsewhere" case the propose-mode instructions say should not be labeled a clean analyzed universal rule. The fix is to either (a) narrow the rule's scope to the guard-calibration family it actually holds for (files like lint-tag-releases/lint-release-wiring's test-*.py companions, i.e. TSV/CSV-style oracle calibrations with want_rc/want_text tuples) rather than "every test/calibration case ... that shells out," or (b) keep the broad aspiration but drop the "analyzed" sourceMode and instead flag it as a partial/contested convention with the counter-examples named, since a later drift audit run against the rule as stated would immediately fail on verify-takt-payload-shapes.py and verify-contested-fixture.py despite those files being intentional, reviewed test harnesses, not oversights.

The rule is otherwise concrete and mechanically checkable (grep for `want_rc`/`want_text` pairing vs. bare `returncode ==`/`!= 0` checks) — the checkability is not the problem, the overreaching universality claim is.</note>
</invoke>


### test-data-management — CONFIRMED

**Rule:** Any fixture that seeds a defect for a headless behavioral test case must live under test/plugins/fixtures/ (never nested inside the plugin it exercises, so fixtures stay arm-independent and reusable across legacy/rebuilt/official arms of the same case), must document the seeded defect and expected finding in a checked-in `_EXPECTED.md` in that fixture directory, and the harness that copies the fixture into the subject-under-test's working directory must strip `_EXPECTED.md` before invoking the tool, so the answer key is never handed to the system being graded.

**Source:** `analyzed`

**Evidence:** CLAUDE.md:167 ("Fixtures live in `test/plugins/fixtures/` (arm-independent — deliberately *not* under any plugin, so moving a plugin does not break the tests)"); test/plugins/run.sh:134-139 (comment: "A fixture dir IS the target repo the plugin reads, so any file in it describing the seeded defect is an answer key handed straight to the subject under test... Keep that documentation in _EXPECTED.md and strip it from the copy" followed by `rm -f "$tmp/_EXPECTED.md"`); confirmed present across fixtures e.g. test/plugins/fixtures/thrash-escalation/_EXPECTED.md, test/plugins/fixtures/contested-wire-halts/_EXPECTED.md, test/plugins/fixtures/lehre-fidelity-gap/_EXPECTED.md; and cases.tsv:44-60 showing the same fixture directory (e.g. test/plugins/fixtures/contested-wire-halts) reused unchanged across legacy_plugins/andon, pilot-armc/andon-official, and plugins/andon arms.

**Verification verdict:** `confirmed`

**Verification note:** Independently re-verified all cited evidence: CLAUDE.md:167 states fixtures live under test/plugins/fixtures/ arm-independent; test/plugins/run.sh:134-139 contains the exact comment and the rm -f "$tmp/_EXPECTED.md" line stripping the answer key before invoking the CLI; 17 fixture directories (confirmed via glob) actually contain _EXPECTED.md, including the three cited (thrash-escalation, contested-wire-halts, lehre-fidelity-gap); and cases.tsv lines 51/54/57/60 show fixtures/thrash-escalation and fixtures/contested-wire-halts reused unchanged across legacy_plugins/andon, pilot-armc/andon-official, and plugins/andon rows, matching the claimed cross-arm reuse. sourceMode 'analyzed' is honest -- this is a real, load-bearing convention, not fabricated. The rule's three clauses (location, _EXPECTED.md documentation, strip-before-invoke) are each mechanically checkable by grep/glob against cases.tsv and run.sh.

## Exceptions & waivers

_None recorded yet._

## Change log

- 2026-09-07: Drafted via `cupertino-handbook-draft` (domain: `testing`). 3/6 dimensions confirmed on independent re-verification; the rest are flagged `NEEDS REVISION` above and should be tightened (narrower scope, corrected evidence) before being treated as enforceable.
