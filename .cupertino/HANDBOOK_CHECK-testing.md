# Handbook check — testing

Checked against `.cupertino/testing-handbook.md`'s 6 dimensions. 14 finding(s) survived independent re-verification (1 mechanical, 13 needing design judgment).

**Resolved since this report** (not re-run through the check workflow; noted by hand):
- `test/plugins/fixtures/ui-missing-alt/index.html:40` (test-data-management) — the inline answer key was extracted to a checked-in `_EXPECTED.md`; `run.sh:139` already strips exactly that filename.
- `test/plugins/fixtures/confab-burndown-pseudo-ledger/analysis/confab/ledger.json:1` (test-data-management) — this fixture was never referenced by `cases.tsv`, `run.sh`, or `test_build_burndown_html.py` (which builds its own inline ledger via `tempfile.TemporaryDirectory()`). It was dead code from commit `821a14a`, not an incomplete fixture, so it was removed rather than given an `_EXPECTED.md`.

| Severity | Mechanical | Dimension | Location | Title |
|---|---|---|---|---|
| High | no | test-naming | `plugins/compass/scripts/test_build_branch_comparison_html.py:1` | Test file has zero pytest-discoverable test functions |
| High | no | test-naming | `plugins/compass/scripts/test_compass.py:1` | Test file has zero pytest-discoverable test functions |
| High | no | test-naming | `plugins/lehre/hooks/test_lehre_guard.py:1` | Test file has zero pytest-discoverable test functions |
| High | no | test-naming | `plugins/lehre/scripts/test_lehre_core.py:1` | Test file has zero pytest-discoverable test functions |
| High | yes | test-data-management | `test/plugins/fixtures/ui-missing-alt/index.html:40` | Answer key embedded inline in the audited file itself, not in a stripped _EXPECTED.md |
| High | no | coverage-expectations | `test/plugins/lint-frontmatter.py:1` | lint-frontmatter.py has no companion calibration test |
| High | no | coverage-expectations | `test/plugins/lint-plugin-authors.py:170` | lint-plugin-authors.py has no companion calibration test |
| Medium | no | fixture-and-mocking-policy | `test/docs/test_docs_ux_audit.py:152` | mock.patch.object used to redirect a module-internal path constant instead of exercising a real missing-file path |
| Medium | no | fixture-and-mocking-policy | `test/docs/test_docs_ux_audit.py:190` | mock.patch.object used to swap module globals DOCS and src_exclude rather than injecting the real fixture path |
| Medium | no | fixture-and-mocking-policy | `test/docs/test_docs_ux_audit.py:204` | mock.patch.object used to swap module globals DOCS and src_exclude rather than injecting the real fixture path |
| Medium | no | test-naming | `test/plugins/test-lint-release-wiring.py:1` | Calibration script named with a hyphen, not `test_<subject>.py`, and has no `def test_*` functions |
| Medium | no | test-naming | `test/plugins/test-lint-tag-releases.py:1` | Calibration script named with a hyphen, not `test_<subject>.py`, and has no `def test_*` functions |
| Medium | no | fixture-and-mocking-policy | `tools/surface-index/test_build_surface_index.py:381` | Test manually overwrites and restores module-internal globals (REPO/PLUGINS/OUTPUT) instead of injecting paths |
| Low | no | test-data-management | `test/plugins/fixtures/confab-burndown-pseudo-ledger/analysis/confab/ledger.json:1` | Seeded-defect-shaped fixture has no checked-in _EXPECTED.md |

## Details

### `test/plugins/lint-frontmatter.py:1` — lint-frontmatter.py has no companion calibration test

**Dimension:** coverage-expectations · **Severity:** High · **Mechanical:** False

**Evidence:** test/plugins/lint-frontmatter.py is a real gate ("Gate 0 — every skill/agent frontmatter must parse as YAML", CLAUDE.md lists it first in the mandatory static-check sequence run on every change) but no test-lint-frontmatter.py, cases in cases.tsv, or fixtures under test/plugins/fixtures/ exercise it at all. A repo-wide search for any reference to its logic (`grep -rn "lint_frontmatter\|lint-frontmatter" test/plugins/`) turns up only the script itself. There is no fabricated-fixture case proving it goes red (e.g. malformed YAML, missing `---` header, or a missing `description` key), and no case exercising the silent-pass branch at line 17-21 (`except ImportError: ... sys.exit(0)`), which is itself exactly the kind of "looks correct, does nothing" defect this repo's own CLAUDE.md warns about.

**Suggested fix:** Add test/plugins/test-lint-frontmatter.py that builds fabricated plugin-dir fixtures (valid frontmatter, malformed YAML, missing `---`, missing `description`) in a tempdir, invokes lint()/main() against them, and asserts both a passing case and at least one case that produces a nonzero exit / failure line. Also add a case that simulates the `ImportError` path to make the silent-pass behavior an explicit, asserted decision rather than an untested one.

### `test/plugins/lint-plugin-authors.py:170` — lint-plugin-authors.py has no companion calibration test

**Dimension:** coverage-expectations · **Severity:** High · **Mechanical:** False

**Evidence:** lint-plugin-authors.py is wired directly into CI as a gating step (.github/workflows/plugin-checks.yml, step id `plugin_authors`, line ~107: `run: python3 test/plugins/lint-plugin-authors.py`), and its own docstring recounts the real drift it was written to catch (three plugins shipping scaffold placeholder authors). Despite that, no test-lint-plugin-authors.py exists anywhere under test/plugins/, and no cases.tsv/fixtures entry exercises it — a repo-wide grep for `lint_plugin_authors`/`lint-plugin-authors` outside the script itself returns nothing. The guard's `lint()` function (line 170) also reads hardcoded module-level paths (`PLUGINS_DIR`, `MARKETPLACE_PATH`, lines 57-59) rather than accepting an injectable root, so it cannot currently be pointed at fabricated fixtures without a refactor — compounding the missing-calibration gap.

**Suggested fix:** Refactor discover_plugin_manifests()/load_marketplace_entries()/lint() to accept an injectable plugins_dir/marketplace_path (defaulting to the real repo paths), then add test/plugins/test-lint-plugin-authors.py that builds fabricated marketplace.json + plugin.json fixtures covering: matching authors (pass), a disk-only plugin with no marketplace entry (red), a marketplace-only entry with no disk plugin (red), a placeholder author name/email (red), and a name mismatch between the two files (red) — mirroring the sabotage-tested style of test-lint-tag-releases.py.

### `plugins/lehre/hooks/test_lehre_guard.py:1` — Test file has zero pytest-discoverable test functions

**Dimension:** test-naming · **Severity:** High · **Mechanical:** False

**Evidence:** The whole file (260 lines) is a flat script: helper functions `run()` (line 55), `make_repo()` (line 65), `expect_deny()` (line 78), `expect_allow()` (line 100), `write()` (line 105) are called at module level to drive assertions. `grep -c '^def test'` returns 0 -- there is not a single function named `def test_<behavior>`.

**Suggested fix:** Restructure into individually named pytest functions (e.g. `def test_bare_except_denies():`, `def test_layering_violation_denies():`, `def test_clean_file_allows():`), one per current expect_deny/expect_allow call, so pytest's default discovery collects and reports each case independently instead of pytest finding 0 tests in a file literally named test_lehre_guard.py.

### `plugins/compass/scripts/test_build_branch_comparison_html.py:1` — Test file has zero pytest-discoverable test functions

**Dimension:** test-naming · **Severity:** High · **Mechanical:** False

**Evidence:** 141-line file driven entirely by module-level calls to the local `ok(label, cond)` helper (defined line 20) and `_write_state()` (line 57); no function anywhere is named `def test_...`. Under pytest's default discovery this file would be collected (it matches `test_*.py`) but yield zero test items.

**Suggested fix:** Convert each `ok("label", cond)` call into its own `def test_<snake_case_label>():` function containing a plain `assert cond`, so pytest reports each check individually instead of silently collecting no tests.

### `plugins/compass/scripts/test_compass.py:1` — Test file has zero pytest-discoverable test functions

**Dimension:** test-naming · **Severity:** High · **Mechanical:** False

**Evidence:** 292-line file whose assertions all run through module-level calls to `ok(label, fn)` (line 20) and `refuses(label, fn)` (line 30), e.g. `ok("dag 2 stages", lambda: C.validate_dag(...))` at line 49. No `def test_...` function exists anywhere in the file.

**Suggested fix:** Turn each ok()/refuses() call site into a dedicated `def test_<snake_case_condition>():` function using plain asserts (or pytest.raises for the refuses() cases), so the file's test cases are individually named and discoverable.

### `plugins/lehre/scripts/test_lehre_core.py:1` — Test file has zero pytest-discoverable test functions

**Dimension:** test-naming · **Severity:** High · **Mechanical:** False

**Evidence:** 189-line file consists of module-level calls to `check(label, got, want)` (line 28) and `expect_raises(label, exc, fn, *a)` (line 33), e.g. `check("basename glob on nested path", C.matches(...), True)` at line 52, with a bare `if FAILS: ... sys.exit(1)` at line 185-188 run at import time. No function is named `def test_...`.

**Suggested fix:** Split the check()/expect_raises() call sites into named functions such as `def test_basename_glob_on_nested_path():`, `def test_unparseable_python_raises():`, using plain asserts / pytest.raises, so pytest discovers and reports each case rather than finding no tests in this file.

### `test/plugins/test-lint-release-wiring.py:1` — Calibration script named with a hyphen, not `test_<subject>.py`, and has no `def test_*` functions

**Dimension:** test-naming · **Severity:** Medium · **Mechanical:** False

**Evidence:** Filename is `test-lint-release-wiring.py` (hyphen, not underscore) and is invoked directly via `python3 test/plugins/test-lint-release-wiring.py` (see .github/workflows/plugin-checks.yml:190), never through pytest. Its cases are driven by a `case(label, mutate, want_rc, want_text)` helper (line ~54) appending to a module-level `FAILURES` list, not by `def test_*` functions. Because the name doesn't match pytest's default `test_*.py`/`*_test.py` glob, pytest would never even attempt to collect it -- which appears to be intentional (it's documented in CLAUDE.md as a standalone calibration script run by hand/CI, not as part of the pytest suite), but it still diverges from the rule's literal naming requirement for a file whose purpose is testing.

**Suggested fix:** Either rename to `test_lint_release_wiring.py` and convert each `case(...)` call into a `def test_<snake_case_mutation>():` function so it becomes a real pytest module, or, if it must stay a standalone CLI calibration script outside pytest by design, rename off the `test` prefix entirely (e.g. `calibrate_lint_release_wiring.py`) to avoid the ambiguous half-matching name.

### `test/plugins/test-lint-tag-releases.py:1` — Calibration script named with a hyphen, not `test_<subject>.py`, and has no `def test_*` functions

**Dimension:** test-naming · **Severity:** Medium · **Mechanical:** False

**Evidence:** Filename is `test-lint-tag-releases.py` (hyphen, not underscore) and is invoked directly via `python3 test/plugins/test-lint-tag-releases.py` (see .github/workflows/plugin-checks.yml:237), never through pytest. Cases are driven by a `run_case(label, tags, releases, grace, want_rc, want_text, baseline=())` helper (line ~46) appending to a module-level `FAILURES` list, not by `def test_*` functions.

**Suggested fix:** Either rename to `test_lint_tag_releases.py` and convert each `run_case(...)` call into a `def test_<snake_case_case>():` function, or rename off the `test` prefix (e.g. `calibrate_lint_tag_releases.py`) if it is meant to stay a standalone script outside pytest discovery.

### `test/docs/test_docs_ux_audit.py:152` — mock.patch.object used to redirect a module-internal path constant instead of exercising a real missing-file path

**Dimension:** fixture-and-mocking-policy · **Severity:** Medium · **Mechanical:** False

**Evidence:** absent = AUDIT.DOCS / ".vitepress" / "config.deleted.mjs"
        self.assertFalse(absent.exists())
        with mock.patch.object(AUDIT, "CONFIG", absent):
            with self.assertRaises(AUDIT.DocsAuditError) as caught:
                AUDIT.src_exclude()

**Suggested fix:** Instead of patching the module's CONFIG global, give src_exclude() (or a thin wrapper) an injectable path parameter defaulting to the real CONFIG, and call it with a tmp-directory path that genuinely does not exist -- exercising real filesystem state rather than redirecting a module internal via mock.patch.object.

### `test/docs/test_docs_ux_audit.py:190` — mock.patch.object used to swap module globals DOCS and src_exclude rather than injecting the real fixture path

**Dimension:** fixture-and-mocking-policy · **Severity:** Medium · **Mechanical:** False

**Evidence:** with mock.patch.object(AUDIT, "DOCS", docs), \
                 mock.patch.object(AUDIT, "src_exclude", list):
                published = {p.relative_to(docs).as_posix() for p in AUDIT.published_pages()}

**Suggested fix:** Refactor published_pages() to accept a docs-root and an exclude-list as parameters (defaulting to the module globals), then call it directly with the tmp_path fixture and a literal exclude list, instead of patching AUDIT.DOCS/AUDIT.src_exclude via mock.patch.object.

### `test/docs/test_docs_ux_audit.py:204` — mock.patch.object used to swap module globals DOCS and src_exclude rather than injecting the real fixture path

**Dimension:** fixture-and-mocking-policy · **Severity:** Medium · **Mechanical:** False

**Evidence:** with mock.patch.object(AUDIT, "DOCS", docs), \
                 mock.patch.object(AUDIT, "src_exclude", lambda: ["superpowers/**"]):
                published = {p.relative_to(docs).as_posix() for p in AUDIT.published_pages()}

**Suggested fix:** Same as the prior occurrence: make published_pages() take docs-root/exclude-list as explicit arguments and call it directly with the tmp_path tree and a literal exclude list, rather than patching module internals.

### `tools/surface-index/test_build_surface_index.py:381` — Test manually overwrites and restores module-internal globals (REPO/PLUGINS/OUTPUT) instead of injecting paths

**Dimension:** fixture-and-mocking-policy · **Severity:** Medium · **Mechanical:** False

**Evidence:** self._orig_repo = INDEXER.REPO
        self._orig_plugins = INDEXER.PLUGINS
        self._orig_output = INDEXER.OUTPUT
        INDEXER.REPO = self.repo
        INDEXER.PLUGINS = self.plugins
        INDEXER.OUTPUT = self.repo / "docs" / ".vitepress" / "data" / "surface.json"
        self.addCleanup(self._restore_globals)  -- class docstring at line 371-373 self-describes this as "monkeypatching the module's REPO/PLUGINS/OUTPUT globals"

**Suggested fix:** Have discover_plugins()/build_surface() accept repo/plugins/output paths as parameters (defaulting to the module globals for CLI use), and call them directly with the tmp_path fixture in tests instead of saving/overwriting/restoring the module's internal globals.

### `test/plugins/fixtures/ui-missing-alt/index.html:40` — Answer key embedded inline in the audited file itself, not in a stripped _EXPECTED.md

**Dimension:** test-data-management · **Severity:** High · **Mechanical:** True

**Evidence:** Lines 1-11 and 40-49 of index.html contain an HTML comment block titled 'SEEDED-DEFECT FIXTURE ... EXPECTED FINDINGS (the harness asserts the audit surfaces these): - a11y img-no-alt ... - semantics div-onclick ... - a11y input-no-label ... EXPECTED NON-FINDINGS ...'. This fixture has no _EXPECTED.md at all (confirmed: `ls test/plugins/fixtures/ui-missing-alt/` shows only index.html). The fixture is actively used by the live case `new-ui-audit` in test/plugins/cases.tsv:70, which points self-assess-ui-audit at this exact directory. run.sh (line 139) only does `rm -f "$tmp/_EXPECTED.md"` before invoking the CLI -- it never touches index.html -- so the literal answer-key comment ('EXPECTED FINDINGS ... the harness asserts the audit surfaces these') is handed straight to the tool being graded, the exact hand-the-answer-key-to-the-system-under-test failure the rule exists to prevent.

**Suggested fix:** Move the 'SEEDED-DEFECT FIXTURE' / 'EXPECTED FINDINGS' / 'EXPECTED NON-FINDINGS' commentary out of index.html into a new test/plugins/fixtures/ui-missing-alt/_EXPECTED.md, leaving index.html containing only the seeded HTML defects (and non-defects) with no narration of what is expected, since run.sh only strips a file literally named _EXPECTED.md.

### `test/plugins/fixtures/confab-burndown-pseudo-ledger/analysis/confab/ledger.json:1` — Seeded-defect-shaped fixture has no checked-in _EXPECTED.md

**Dimension:** test-data-management · **Severity:** Low · **Mechanical:** False

**Evidence:** The fixture directory test/plugins/fixtures/confab-burndown-pseudo-ledger/ contains only analysis/confab/ledger.json (a ledger whose per-finding statuses -- e.g. 'agentic-2': status 'open', 'code-1': status 'escalated' with reopenCount 4 -- look deliberately inconsistent with a clean burndown, i.e. a 'pseudo' ledger) and no _EXPECTED.md. A repo-wide grep for 'confab-burndown-pseudo-ledger' and for its content elsewhere (e.g. in test/plugins/cases.tsv or any test_*.py under the checked paths) returns zero references, so this fixture is not currently wired to any test case that would exercise it, but it is shaped and named exactly like a seeded-defect fixture the rule targets.

**Suggested fix:** Either add a test/plugins/fixtures/confab-burndown-pseudo-ledger/_EXPECTED.md documenting the seeded pseudo-ledger inconsistency and the expected finding once a case wires this fixture in, or remove the orphaned fixture if it is dead weight left over from a retired case.
