# Handbook check — code

Checked against `.cupertino/code-handbook.md`'s 6 dimensions. 62 finding(s) survived independent re-verification (4 mechanical, 58 needing design judgment).

**Resolved since this report** (not re-run through the check workflow; noted by hand): the 2 non-mechanical `error-handling` findings (`plugins/self-assess/hooks/guard_target_edit.py:125`, `plugins/confab/scripts/hooks/guard_edit_scope.py:96`) were evaluated via `cupertino-integrate` rather than fixed — verdict: delegate to the guards' existing, documented fail-open behavior (issue #24) rather than force the code to fail closed. A named exception is now recorded in `.cupertino/code-handbook.md`'s "Exceptions & waivers" section; the code itself is unchanged.

Independent empirical re-verification during review also found the LLM-based `complexity-limits` count understated: `ruff check --select C901,PLR0915,PLR0912,PLR0913 .` finds **88** real violations, not the 32 listed below. Treat this dimension's findings as a representative sample, not an exhaustive list.

| Severity | Mechanical | Dimension | Location | Title |
|---|---|---|---|---|
| High | no | testing-coverage | `plugins/andon/hooks/test_andon_enforce.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/compass/scripts/test_build_branch_comparison_html.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/compass/scripts/test_compass.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/confab/scripts/hooks/test_guard_edit_scope.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/confab/scripts/test_build_burndown_html.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/confab/scripts/test_cycle_engine.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/cupertino/scripts/test_state.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/lehre/hooks/test_lehre_guard.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/lehre/scripts/test_lehre_core.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/self-assess/hooks/test_guard_target_edit.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/self-assess/scripts/lib/test_staleness.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/self-assess/scripts/lib/test_status.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `plugins/self-assess/scripts/test_build_stage_map_html.py:1` | Test file not invoked by any CI workflow step |
| High | yes | complexity-limits | `ruff.toml:47` | Repo-root ruff config does not enable C901/PLR0915/PLR0912/PLR0913 |
| High | no | testing-coverage | `tools/andon-ledger-validator/test_validate_ledger.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `tools/catalog-validator/test_validate_catalog.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `tools/enforcement-audit/test_audit_enforcement.py:1` | Test file not invoked by any CI workflow step |
| High | no | testing-coverage | `tools/surface-index/test_build_surface_index.py:1` | Test file not invoked by any CI workflow step |
| High | yes | public-api-documentation | `tools/werkstoff-cli/pyproject.toml:33` | D101/D102/D103 not added to tools/werkstoff-cli's ruff select list |
| High | yes | complexity-limits | `tools/werkstoff-cli/pyproject.toml:33` | werkstoff-cli's own ruff select list does not enable C901/PLR0915/PLR0912/PLR0913 |
| Medium | no | complexity-limits | `plugins/andon/scripts/andon_core.py:1019` | Multiple functions exceed complexity/size limits (would fail C901/PLR0912/PLR0915/PLR0913 once enabled) |
| Medium | no | complexity-limits | `plugins/andon/scripts/build_symbol_index.py:370` | Functions exceed PLR0913 argument-count limit |
| Medium | no | complexity-limits | `plugins/cli-scaffold/scripts/selftest.py:36` | Function exceeds PLR0915 statement-count limit |
| Medium | no | complexity-limits | `plugins/cli-scaffold/scripts/verify_scaffold.py:469` | Function exceeds PLR0915 statement-count limit |
| Medium | no | complexity-limits | `plugins/compass/scripts/build_symbol_index.py:370` | Functions exceed PLR0913 argument-count limit |
| Medium | no | complexity-limits | `plugins/compass/scripts/compass_lib.py:249` | validate_dag exceeds complexity and branch limits |
| Medium | no | complexity-limits | `plugins/confab/scripts/agentic_reliability.py:56` | Function exceeds PLR0915 statement-count limit |
| Medium | no | complexity-limits | `plugins/confab/scripts/assertion_audit.py:65` | Function exceeds PLR0915 statement-count limit |
| Medium | no | complexity-limits | `plugins/confab/scripts/build_symbol_index.py:370` | Functions exceed PLR0913 argument-count limit |
| Medium | no | complexity-limits | `plugins/confab/scripts/code_change_review.py:74` | main exceeds complexity and statement limits |
| Medium | no | complexity-limits | `plugins/confab/scripts/cycle_engine.py:173` | Functions exceed complexity/branch limits |
| Medium | no | error-handling | `plugins/confab/scripts/hooks/guard_edit_scope.py:96` | Guard fails open (allow) on internal ImportError instead of denying |
| Medium | no | complexity-limits | `plugins/confab/scripts/hooks/guard_edit_scope.py:73` | run exceeds complexity limit |
| Medium | no | complexity-limits | `plugins/confab/scripts/lib/ledger.py:70` | Function exceeds PLR0913 argument-count limit |
| Medium | no | complexity-limits | `plugins/cupertino/hooks/pretooluse_guard.py:185` | handle_skill and main exceed complexity limit |
| Medium | no | complexity-limits | `plugins/cupertino/scripts/build_symbol_index.py:370` | Functions exceed PLR0913 argument-count limit |
| Medium | no | complexity-limits | `plugins/lehre/hooks/lehre_guard.py:236` | Multiple functions exceed complexity/branch/statement limits |
| Medium | no | complexity-limits | `plugins/lehre/scripts/build_doctrine_html.py:90` | build exceeds complexity limit |
| Medium | no | complexity-limits | `plugins/lehre/scripts/lehre_cli.py:162` | cmd_gauge exceeds complexity and branch limits |
| Medium | no | complexity-limits | `plugins/lehre/scripts/lehre_core.py:409` | Multiple functions exceed complexity/branch/argument limits |
| Medium | no | error-handling | `plugins/self-assess/hooks/guard_target_edit.py:125` | Guard fails open (allow) on internal ImportError instead of denying |
| Medium | no | complexity-limits | `plugins/self-assess/hooks/guard_target_edit.py:96` | run exceeds complexity and branch limits |
| Medium | no | complexity-limits | `plugins/self-assess/scripts/build_symbol_index.py:370` | Functions exceed PLR0913 argument-count limit |
| Medium | no | complexity-limits | `plugins/self-assess/scripts/lib/frontmatter.py:34` | parse_frontmatter exceeds complexity and statement limits |
| Medium | no | complexity-limits | `plugins/self-assess/scripts/lib/graph.py:4` | find_cycles exceeds complexity limit |
| Medium | no | complexity-limits | `plugins/self-assess/scripts/self_assess_cli.py:269` | build_parser exceeds PLR0915 statement limit |
| Medium | no | complexity-limits | `plugins/takt/hooks/takt_guard.py:195` | main exceeds complexity, branch, and statement limits |
| Medium | no | complexity-limits | `tools/catalog-validator/validate_catalog.py:217` | strip_non_rendering exceeds complexity limit |
| Medium | no | complexity-limits | `tools/enforcement-audit/audit_enforcement.py:268` | main exceeds complexity and branch limits |
| Medium | no | complexity-limits | `tools/plugin-serializer/extract_behavior.py:215` | main exceeds complexity limit |
| Medium | no | complexity-limits | `tools/prompt-index/build_prompt_index.py:45` | parse_readme exceeds complexity limit |
| Medium | no | complexity-limits | `tools/symbol-indexer/build_symbol_index.py:370` | Functions exceed PLR0913 argument-count limit |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:30` | Public class Plugin has no docstring |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:38` | Public class Marketplace has no docstring |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:43` | Public method Marketplace.plugin has no docstring |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:64` | Public function load_marketplace has no docstring |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:92` | Public function unknown_plugin_names has no docstring |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:97` | Public function ensure_claude_cli has no docstring |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:112` | Public function add_marketplace has no docstring |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:119` | Public function update_marketplace has no docstring |
| Medium | no | public-api-documentation | `tools/werkstoff-cli/src/werkstoff/core.py:126` | Public function install_plugin has no docstring |
| Low | yes | error-handling | `plugins/cupertino/hooks/pretooluse_guard.py:31` | Import failure is swallowed without capturing the exception, so the eventual denial cannot name the internal error |

## Details

### `plugins/self-assess/hooks/guard_target_edit.py:125` — Guard fails open (allow) on internal ImportError instead of denying

**Dimension:** error-handling · **Severity:** Medium · **Mechanical:** False

**Evidence:** try:
    from lib.settings import load_settings  # noqa: E402
    ...
except (ImportError, ModuleNotFoundError) as exc:
    print(f"guard_target_edit: internal error ({type(exc).__name__}: {exc}); ... Allowing this edit rather than denying every future edit in this repo ...", file=sys.stderr)
    return allow()

**Suggested fix:** This is inside the opted-in branch (a self-assess edit-scope lock is already confirmed open at this point), so an unexpected import/packaging failure here should deny (return deny(...)) with the exception named and the documented ESCAPE_HATCH, not silently allow the edit through. If the intentional fail-open-on-packaging-defect tradeoff (from issue #24) is to be kept, it needs an explicit, named escape hatch of its own and should be called out as a deliberate rule exception rather than silently contradicting the fail-closed contract.

### `plugins/confab/scripts/hooks/guard_edit_scope.py:96` — Guard fails open (allow) on internal ImportError instead of denying

**Dimension:** error-handling · **Severity:** Medium · **Mechanical:** False

**Evidence:** try:
    from lib.paths import UnsafeWritePathError, safe_repo_path  # noqa: E402
    from lib.remediation_scope import read_scope, mark_consumed  # noqa: E402
except (ImportError, ModuleNotFoundError) as exc:
    print(f"guard_edit_scope: internal error ({type(exc).__name__}: {exc}); ... Allowing this edit rather than denying every future edit in this repo ...", file=sys.stderr)
    return allow()

**Suggested fix:** This check runs only after confirming analysis/confab/ exists (i.e. the repo has opted into confab), so an unexpected import failure at this point should deny with the exception named and the documented ESCAPE_HATCH rather than allow. Keep the fail-open behavior only if it is intentionally scoped and documented as a named, separate exception to the fail-closed contract, not folded silently into the general 'internal error' path.

### `plugins/cupertino/hooks/pretooluse_guard.py:31` — Import failure is swallowed without capturing the exception, so the eventual denial cannot name the internal error

**Dimension:** error-handling · **Severity:** Low · **Mechanical:** True

**Evidence:** try:
    import validators  # type: ignore  # noqa: E402
except Exception:
    validators = None  # handled defensively below; schema checks degrade to "deny" on write, not "skip"
...
if validators is None:
    deny("cupertino: validator module failed to load; refusing to write unvalidated persisted state. " + ESCAPE_HATCH)

**Suggested fix:** Capture the exception at import time (e.g. `except Exception as exc: validators = None; _validators_import_error = exc`) and include `type(exc).__name__: exc` in the deny() message at line 135, so the denial names the actual internal error as the rule requires rather than a generic, uninformative statement.

### `plugins/andon/hooks/test_andon_enforce.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** File exists (269 lines, stdlib unittest-style, docstring says 'Run: python3 test_andon_enforce.py') but grep across .github/workflows/*.yml for 'test_andon_enforce', 'pytest', and 'unittest' shows no workflow step names or runs it.

**Suggested fix:** Add a step to .github/workflows/plugin-checks.yml that runs `python3 -m unittest test_andon_enforce -v` with working-directory: plugins/andon/hooks (mirroring the existing symbol-indexer test step at plugin-checks.yml:130-134).

### `plugins/self-assess/hooks/test_guard_target_edit.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 185-line test file for the PreToolUse target-edit guard; no .github/workflows/*.yml step references it, pytest, or unittest for this module.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_guard_target_edit -v` with working-directory: plugins/self-assess/hooks.

### `plugins/lehre/hooks/test_lehre_guard.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 260-line behavioural test file for lehre_guard's deny/allow behavior; not named by any workflow step, and only mentioned as a code comment in test/plugins/cases.tsv:82, not executed there.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_lehre_guard -v` with working-directory: plugins/lehre/hooks.

### `plugins/confab/scripts/hooks/test_guard_edit_scope.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 132-line test file for confab's PreToolUse edit-scope guard; absent from every .github/workflows/*.yml run: line.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_guard_edit_scope -v` with working-directory: plugins/confab/scripts/hooks.

### `plugins/compass/scripts/test_build_branch_comparison_html.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 141-line test file whose own docstring says 'Run: python3 scripts/test_build_branch_comparison_html.py', but no workflow step in .github/workflows/ runs it.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_build_branch_comparison_html -v` with working-directory: plugins/compass/scripts.

### `plugins/confab/scripts/test_build_burndown_html.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 181-line test file for confab-status's burndown chart builder; not named by any .github/workflows/*.yml step.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_build_burndown_html -v` with working-directory: plugins/confab/scripts.

### `plugins/self-assess/scripts/test_build_stage_map_html.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 153-line test file for self-assess-stage-map's HTML viewer builder; not named by any .github/workflows/*.yml step.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_build_stage_map_html -v` with working-directory: plugins/self-assess/scripts.

### `plugins/compass/scripts/test_compass.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 292-line self-contained test suite for compass_lib guards ('Run: python3 scripts/test_compass.py'); no workflow step names or runs it.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_compass -v` with working-directory: plugins/compass/scripts.

### `plugins/confab/scripts/test_cycle_engine.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 134-line test file for confab-cycle's constraint-domain picker; no workflow step in .github/workflows/*.yml runs it.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_cycle_engine -v` with working-directory: plugins/confab/scripts.

### `plugins/lehre/scripts/test_lehre_core.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 189-line known-answer test file for lehre_core's evaluator ('Run before trusting any verdict this plugin produces: python3 plugins/lehre/scripts/test_lehre_core.py'); not run by any CI workflow.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_lehre_core -v` with working-directory: plugins/lehre/scripts.

### `plugins/cupertino/scripts/test_state.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 121-line test file for cupertino's state.py flag store; not named or run by any .github/workflows/*.yml step.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_state -v` with working-directory: plugins/cupertino/scripts.

### `plugins/self-assess/scripts/lib/test_staleness.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 126-line test file for self-assess-autopilot's stage-map freshness check; not named or run by any .github/workflows/*.yml step.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_staleness -v` with working-directory: plugins/self-assess/scripts/lib.

### `plugins/self-assess/scripts/lib/test_status.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 99-line test file for self-assess-status's dashboard builder; not named or run by any .github/workflows/*.yml step.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_status -v` with working-directory: plugins/self-assess/scripts/lib.

### `tools/catalog-validator/test_validate_catalog.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 798-line unittest suite for validate_catalog.py; plugin-checks.yml only runs `python3 tools/catalog-validator/validate_catalog.py` (line 144, the validator itself, not its tests) -- the test_ file is never invoked by unittest or pytest in any workflow.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_validate_catalog -v` with working-directory: tools/catalog-validator (near the existing validate-catalog step in plugin-checks.yml).

### `tools/andon-ledger-validator/test_validate_ledger.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 181-line unittest suite ('Run: python3 tools/andon-ledger-validator/test_validate_ledger.py'); no .github/workflows/*.yml step names or runs it.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_validate_ledger -v` with working-directory: tools/andon-ledger-validator.

### `tools/enforcement-audit/test_audit_enforcement.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 159-line test suite for the enforcement auditor; no .github/workflows/*.yml step names or runs it, despite CLAUDE.md describing this auditor as hand-checked/calibrated.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_audit_enforcement -v` with working-directory: tools/enforcement-audit.

### `tools/surface-index/test_build_surface_index.py:1` — Test file not invoked by any CI workflow step

**Dimension:** testing-coverage · **Severity:** High · **Mechanical:** False

**Evidence:** 452-line unit test suite for build_surface_index.py; docs.yml invokes the builder script itself (`python3 tools/surface-index/build_surface_index.py`, docs.yml:61) but never its test_ file via unittest or pytest.

**Suggested fix:** Add a CI step invoking `python3 -m unittest test_build_surface_index -v` with working-directory: tools/surface-index.

### `tools/werkstoff-cli/pyproject.toml:33` — D101/D102/D103 not added to tools/werkstoff-cli's ruff select list

**Dimension:** public-api-documentation · **Severity:** High · **Mechanical:** True

**Evidence:** select = ["E", "F", "I", "UP", "B"]

**Suggested fix:** Change line 33 to select = ["E", "F", "I", "UP", "B", "D101", "D102", "D103"] (scoped to this package's own pyproject.toml only).

### `tools/werkstoff-cli/src/werkstoff/core.py:30` — Public class Plugin has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** @dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    source: str
    category: str | None = None

**Suggested fix:** Add a class docstring describing that Plugin represents one marketplace plugin entry and briefly note its fields (name, description, source, category).

### `tools/werkstoff-cli/src/werkstoff/core.py:38` — Public class Marketplace has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** @dataclass(frozen=True)
class Marketplace:
    name: str
    root: Path
    plugins: tuple[Plugin, ...]

**Suggested fix:** Add a class docstring describing that Marketplace represents a loaded marketplace manifest and its plugins.

### `tools/werkstoff-cli/src/werkstoff/core.py:43` — Public method Marketplace.plugin has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** def plugin(self, name: str) -> Plugin:
    for candidate in self.plugins:
        if candidate.name == name:
            return candidate
    known = ", ".join(p.name for p in self.plugins)
    raise WerkstoffError(f"unknown plugin '{name}' (known: {known})")

**Suggested fix:** Add a docstring documenting the `name` parameter, the returned Plugin, and that it raises WerkstoffError when the name is unknown.

### `tools/werkstoff-cli/src/werkstoff/core.py:64` — Public function load_marketplace has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** def load_marketplace(repo_root: Path) -> Marketplace:
    manifest_path = repo_root / MARKETPLACE_REL_PATH

**Suggested fix:** Add a docstring describing the repo_root parameter, the returned Marketplace, and the WerkstoffError cases raised for a missing/invalid manifest.

### `tools/werkstoff-cli/src/werkstoff/core.py:92` — Public function unknown_plugin_names has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** def unknown_plugin_names(marketplace: Marketplace, names: tuple[str, ...]) -> list[str]:
    known = {p.name for p in marketplace.plugins}
    return [n for n in names if n not in known]

**Suggested fix:** Add a docstring describing the marketplace/names parameters and that it returns the subset of names not present in the marketplace.

### `tools/werkstoff-cli/src/werkstoff/core.py:97` — Public function ensure_claude_cli has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** def ensure_claude_cli() -> str:
    path = shutil.which("claude")
    if path is None:
        raise WerkstoffError("the 'claude' CLI was not found on PATH")
    return path

**Suggested fix:** Add a docstring describing that it returns the resolved path to the claude CLI, raising WerkstoffError if not found on PATH.

### `tools/werkstoff-cli/src/werkstoff/core.py:112` — Public function add_marketplace has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** def add_marketplace(
    marketplace: Marketplace, run: Runner = subprocess.run
) -> subprocess.CompletedProcess[str]:
    claude = ensure_claude_cli()
    return _run([claude, "plugin", "marketplace", "add", str(marketplace.root)], run)

**Suggested fix:** Add a docstring describing the marketplace/run parameters and the returned CompletedProcess from `claude plugin marketplace add`.

### `tools/werkstoff-cli/src/werkstoff/core.py:119` — Public function update_marketplace has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** def update_marketplace(
    marketplace: Marketplace, run: Runner = subprocess.run
) -> subprocess.CompletedProcess[str]:
    claude = ensure_claude_cli()
    return _run([claude, "plugin", "marketplace", "update", marketplace.name], run)

**Suggested fix:** Add a docstring describing the marketplace/run parameters and the returned CompletedProcess from `claude plugin marketplace update`.

### `tools/werkstoff-cli/src/werkstoff/core.py:126` — Public function install_plugin has no docstring

**Dimension:** public-api-documentation · **Severity:** Medium · **Mechanical:** False

**Evidence:** def install_plugin(
    marketplace: Marketplace,
    plugin_name: str,
    scope: str = DEFAULT_SCOPE,
    run: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    plugin = marketplace.plugin(plugin_name)  # validates the name first
    claude = ensure_claude_cli()
    return _run(
        [claude, "plugin", "install", f"{plugin.name}@{marketplace.name}", "--scope", scope],
        run,
    )

**Suggested fix:** Add a docstring documenting marketplace/plugin_name/scope/run parameters and the returned CompletedProcess from `claude plugin install`.

### `ruff.toml:47` — Repo-root ruff config does not enable C901/PLR0915/PLR0912/PLR0913

**Dimension:** complexity-limits · **Severity:** High · **Mechanical:** True

**Evidence:** [lint]
select = ["E4", "E7", "E9", "F"]
-- no C901 (mccabe), PLR0915, PLR0912, or PLR0913, and no [lint.mccabe] max-complexity setting either.

**Suggested fix:** Add "C901", "PLR0915", "PLR0912", "PLR0913" to [lint].select (and optionally add a [lint.mccabe] max-complexity = 10 table, though 10 is ruff's default for C901).

### `tools/werkstoff-cli/pyproject.toml:33` — werkstoff-cli's own ruff select list does not enable C901/PLR0915/PLR0912/PLR0913

**Dimension:** complexity-limits · **Severity:** High · **Mechanical:** True

**Evidence:** [tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
-- no C901, PLR0915, PLR0912, or PLR0913 codes present.

**Suggested fix:** Add "C901", "PLR0915", "PLR0912", "PLR0913" to [tool.ruff.lint].select.

### `plugins/andon/scripts/andon_core.py:1019` — Multiple functions exceed complexity/size limits (would fail C901/PLR0912/PLR0915/PLR0913 once enabled)

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L132 _parse_scalar C901 (11>10); L163 parse_frontmatter C901 (11>10); L323 validate_doc C901 (19>10) + PLR0912 (19>12); L585 PLR0913 (7>5 args); L829 PLR0913 (9>5 args); L926 render_board C901 (12>10); L1019 main C901 (24>10) + PLR0912 (24>12) + PLR0915 (143>50 statements)

**Suggested fix:** Decompose main() and validate_doc() into smaller helper functions, reduce argument counts on the flagged functions via parameter objects/dataclasses, and simplify branching in _parse_scalar/parse_frontmatter/render_board.

### `plugins/andon/scripts/build_symbol_index.py:370` — Functions exceed PLR0913 argument-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L370 build_index PLR0913 (6>5 args); L542 artifact_manifest PLR0913 (6>5 args); L608 publish_snapshot PLR0913 (6>5 args)

**Suggested fix:** Group related parameters into a dataclass/NamedTuple to bring argument counts under the limit.

### `plugins/cli-scaffold/scripts/selftest.py:36` — Function exceeds PLR0915 statement-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L36 function body has 180 statements (>50, PLR0915)

**Suggested fix:** Split the test-running function into smaller helper functions grouped by test phase.

### `plugins/cli-scaffold/scripts/verify_scaffold.py:469` — Function exceeds PLR0915 statement-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L469 function has 54 statements (>50, PLR0915)

**Suggested fix:** Extract logical sections of the function into helper functions.

### `plugins/compass/scripts/build_symbol_index.py:370` — Functions exceed PLR0913 argument-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L370 build_index PLR0913 (6>5 args); L542 artifact_manifest PLR0913 (6>5 args); L608 publish_snapshot PLR0913 (6>5 args)

**Suggested fix:** Group related parameters into a dataclass/NamedTuple to bring argument counts under the limit.

### `plugins/compass/scripts/compass_lib.py:249` — validate_dag exceeds complexity and branch limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L249 validate_dag C901 (16>10) + PLR0912 (15>12)

**Suggested fix:** Extract the individual validation checks (cycle detection, orphan detection, etc.) into separate helper functions.

### `plugins/confab/scripts/agentic_reliability.py:56` — Function exceeds PLR0915 statement-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L56 function has 54 statements (>50, PLR0915)

**Suggested fix:** Split the function into smaller helpers by responsibility.

### `plugins/confab/scripts/assertion_audit.py:65` — Function exceeds PLR0915 statement-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L65 function has 54 statements (>50, PLR0915)

**Suggested fix:** Split the function into smaller helpers by responsibility.

### `plugins/confab/scripts/build_symbol_index.py:370` — Functions exceed PLR0913 argument-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L370 build_index PLR0913 (6>5 args); L542 artifact_manifest PLR0913 (6>5 args); L608 publish_snapshot PLR0913 (6>5 args)

**Suggested fix:** Group related parameters into a dataclass/NamedTuple to bring argument counts under the limit.

### `plugins/confab/scripts/code_change_review.py:74` — main exceeds complexity and statement limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L74 main C901 (12>10) + PLR0915 (51>50 statements)

**Suggested fix:** Extract argument parsing and each review step into separate helper functions.

### `plugins/confab/scripts/cycle_engine.py:173` — Functions exceed complexity/branch limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L105 _pick_constraint_domain C901 (13>10); L173 cmd_record_pass_result C901 (14>10) + PLR0912 (14>12)

**Suggested fix:** Extract branch-heavy logic in _pick_constraint_domain and cmd_record_pass_result into smaller helper functions.

### `plugins/confab/scripts/hooks/guard_edit_scope.py:73` — run exceeds complexity limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L73 run C901 (13>10)

**Suggested fix:** Extract the guard's decision branches into named helper predicates.

### `plugins/confab/scripts/lib/ledger.py:70` — Function exceeds PLR0913 argument-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L70 PLR0913 (6>5 args)

**Suggested fix:** Group related parameters into a dataclass/NamedTuple.

### `plugins/cupertino/hooks/pretooluse_guard.py:185` — handle_skill and main exceed complexity limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L185 handle_skill C901 (11>10); L283 main C901 (11>10)

**Suggested fix:** Extract branch groups in handle_skill/main into smaller helper functions.

### `plugins/cupertino/scripts/build_symbol_index.py:370` — Functions exceed PLR0913 argument-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L370 build_index PLR0913 (6>5 args); L542 artifact_manifest PLR0913 (6>5 args); L608 publish_snapshot PLR0913 (6>5 args)

**Suggested fix:** Group related parameters into a dataclass/NamedTuple.

### `plugins/lehre/hooks/lehre_guard.py:236` — Multiple functions exceed complexity/branch/statement limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L96 edit_targets C901 (11>10); L187 resulting_content C901 (12>10); L236 main C901 (25>10) + PLR0912 (24>12) + PLR0915 (68>50 statements)

**Suggested fix:** Decompose main() into helper functions per guard stage; simplify edit_targets/resulting_content branching.

### `plugins/lehre/scripts/build_doctrine_html.py:90` — build exceeds complexity limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L90 build C901 (12>10)

**Suggested fix:** Extract HTML-section builders into separate helper functions.

### `plugins/lehre/scripts/lehre_cli.py:162` — cmd_gauge exceeds complexity and branch limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L162 cmd_gauge C901 (17>10) + PLR0912 (17>12)

**Suggested fix:** Split cmd_gauge's per-option handling into smaller dispatched helpers.

### `plugins/lehre/scripts/lehre_core.py:409` — Multiple functions exceed complexity/branch/argument limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L149 validate_ruleset C901 (14>10) + PLR0912 (13>12) + PLR0915 (63>50); L344 _find_constructs C901 (17>10) + PLR0912 (16>12); L390 PLR0913 (6>5 args); L409 evaluate_file C901 (14>10) + PLR0912 (13>12)

**Suggested fix:** Decompose validate_ruleset, _find_constructs, and evaluate_file into smaller helper functions; group L390's parameters into a dataclass.

### `plugins/self-assess/hooks/guard_target_edit.py:96` — run exceeds complexity and branch limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L96 run C901 (15>10) + PLR0912 (14>12)

**Suggested fix:** Extract the guard's condition checks into named helper predicates.

### `plugins/self-assess/scripts/build_symbol_index.py:370` — Functions exceed PLR0913 argument-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L370 build_index PLR0913 (6>5 args); L542 artifact_manifest PLR0913 (6>5 args); L608 publish_snapshot PLR0913 (6>5 args)

**Suggested fix:** Group related parameters into a dataclass/NamedTuple.

### `plugins/self-assess/scripts/lib/frontmatter.py:34` — parse_frontmatter exceeds complexity and statement limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L34 parse_frontmatter C901 (13>10) + PLR0915 (56>50 statements)

**Suggested fix:** Split parsing of scalars/lists/nested blocks into separate helper functions.

### `plugins/self-assess/scripts/lib/graph.py:4` — find_cycles exceeds complexity limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L4 find_cycles C901 (12>10)

**Suggested fix:** Extract the Tarjan SCC inner steps (index assignment, lowlink update, stack pop) into helper functions.

### `plugins/self-assess/scripts/self_assess_cli.py:269` — build_parser exceeds PLR0915 statement limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L269 build_parser PLR0915 (133>50 statements)

**Suggested fix:** Split subparser registration into one helper function per subcommand group.

### `plugins/takt/hooks/takt_guard.py:195` — main exceeds complexity, branch, and statement limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L195 main C901 (20>10) + PLR0912 (20>12) + PLR0915 (58>50 statements)

**Suggested fix:** Decompose main()'s decision tree into named helper functions per gate.

### `tools/catalog-validator/validate_catalog.py:217` — strip_non_rendering exceeds complexity limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L217 strip_non_rendering C901 (13>10)

**Suggested fix:** Extract the per-line-type filtering rules into small helper predicates.

### `tools/enforcement-audit/audit_enforcement.py:268` — main exceeds complexity and branch limits

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L268 main C901 (13>10) + PLR0912 (14>12)

**Suggested fix:** Extract argument parsing and each classification step into helper functions.

### `tools/plugin-serializer/extract_behavior.py:215` — main exceeds complexity limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L215 main C901 (12>10)

**Suggested fix:** Extract argument parsing and extraction steps into helper functions.

### `tools/prompt-index/build_prompt_index.py:45` — parse_readme exceeds complexity limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L45 parse_readme C901 (12>10)

**Suggested fix:** Split README section detection and prompt-block extraction into separate helper functions.

### `tools/symbol-indexer/build_symbol_index.py:370` — Functions exceed PLR0913 argument-count limit

**Dimension:** complexity-limits · **Severity:** Medium · **Mechanical:** False

**Evidence:** L370 build_index PLR0913 (6>5 args); L542 artifact_manifest PLR0913 (6>5 args); L608 publish_snapshot PLR0913 (6>5 args)

**Suggested fix:** Group related parameters into a dataclass/NamedTuple.
