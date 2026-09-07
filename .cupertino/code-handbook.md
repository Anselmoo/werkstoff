# code handbook

Drafted by `cupertino-handbook-draft` (domain: `code`) via one dimension-analyst dispatch per
dimension, each independently re-verified by a second, blind dispatch of the same agent type.

## Dimensions

### error-handling — CONFIRMED

**Rule:** Every PreToolUse/hook guard script must wrap its top-level logic in a broad try/except that fails closed on any unexpected exception (deny the action, exit non-zero) rather than failing open or crashing silently, and the denial message must both name the internal error and point to a specific, named escape-hatch mechanism (e.g. an env var or config flag) for overriding it. **Exception:** see "Documented fail-open carve-out" under Exceptions & waivers below — this rule does not apply to the one narrowly-scoped `ImportError`/`ModuleNotFoundError` path in `self-assess`'s and `confab`'s edit-scope guards.

**Source:** `analyzed`

**Evidence:** plugins/andon/hooks/andon_enforce.py:236-240 (`except Exception as exc: # fail CLOSED` -> deny with `enforcement: off` override); plugins/cupertino/hooks/pretooluse_guard.py:298-332 (`except Exception as e: deny(f"cupertino: internal guard error ({e}); failing closed. {ESCAPE_HATCH}")`, plus separate stdin-parse and OSError catches with the same pattern); plugins/confab/scripts/hooks/guard_edit_scope.py:166-167 (`except Exception as exc: # noqa: BLE001 - fail-closed handler, intentionally broad` -> `deny(...failing closed. {ESCAPE_HATCH}")`); plugins/self-assess/hooks/guard_target_edit.py:204-205 (identical pattern); plugins/takt/hooks/takt_guard.py:279-283 (`except Exception as exc: # fail-closed, per the module docstring`)

**Verification verdict:** `confirmed`

**Verification note:** All five cited file:line locations were read and match exactly what the candidate quotes: andon_enforce.py:236-240, pretooluse_guard.py:298-332, guard_edit_scope.py:166-167, guard_target_edit.py:204-205, takt_guard.py:279-283 each wrap main-level logic in a broad except that calls deny() with the exception type/message plus a named escape hatch (env var or config key), and deny() itself emits both exit-2/stderr and the hookSpecificOutput JSON with hookEventName, matching CLAUDE.md's own documented enforcement requirements. I additionally checked plugins/lehre/hooks/lehre_guard.py (not cited by the candidate) and found the identical pattern at lines 240-254 and 371-373, so the convention holds across all six plugins that ship PreToolUse command hooks with zero counterexamples found. sourceMode 'analyzed' is honest, not fabricated. The rule is concrete and mechanically checkable: for any hooks/*.py registered as a type:command PreToolUse hook, verify a top-level try/except Exception around main(), verify the except branch denies (non-zero exit) rather than allowing, and verify the denial message names both the internal error and a specific override mechanism.

### naming — CONFIRMED

**Rule:** Every skill's SKILL.md frontmatter `name:` field must be identical, character-for-character, to the kebab-case name of its containing skill directory (e.g. `plugins/<plugin>/skills/<skill-name>/SKILL.md` must declare `name: <skill-name>`).

**Source:** `analyzed`

**Evidence:** Confirmed across all 70 SKILL.md files in the repo with zero exceptions, e.g. plugins/andon/skills/andon-loop/SKILL.md:2 (`name: andon-loop`), plugins/self-assess/skills/self-assess-arch-health/SKILL.md:2 (`name: self-assess-arch-health`), plugins/cli-scaffold/skills/scaffold-cli/SKILL.md:2 (`name: scaffold-cli`), plugins/lehre/skills/lehre-brief/SKILL.md:2 (`name: lehre-brief`) — directory name and frontmatter name field match in every one of the 70 skills across all nine plugins.

**Verification verdict:** `confirmed`

**Verification note:** Independently re-verified via Glob(plugins/*/skills/*/SKILL.md) + Grep(^name:) across all skill-bearing plugins (andon, cli-scaffold, compass, confab, cupertino, self-assess, lehre). Every one of the SKILL.md files' `name:` frontmatter matches its containing directory's basename exactly, with zero exceptions — e.g. plugins/andon/skills/andon-loop/SKILL.md:2 (name: andon-loop), plugins/self-assess/skills/self-assess-extract-rules/SKILL.md:2, plugins/cli-scaffold/skills/scaffold-cli/SKILL.md:2 all confirmed by direct read/grep. The candidate's specific file:line citations are all real and accurate. One flaw: the candidate's total count of '70' is wrong — the actual count is 72 (andon 5 + cli-scaffold 5 + compass 14 + confab 8 + cupertino 15 + self-assess 16 + lehre 9). This is a miscount in the evidence summary, not fabricated evidence (the qualitative 'zero exceptions' claim still holds at the correct count of 72), so sourceMode: analyzed is honest in substance though imprecise in the stated total — worth correcting to '72' or dropping the specific number. codebase-consistency (agents/commands only, no skills/) and takt (hooks only, no skills/) are correctly out of scope, consistent with CLAUDE.md's own description of those two plugins. The rule itself is concrete and mechanically checkable (compare frontmatter name: to parent directory basename for every SKILL.md).

### testing-coverage — NEEDS REVISION

**Rule:** Every test_*.py file committed under plugins/ or tools/ must be invoked by at least one automated CI workflow step in .github/workflows/ (e.g., via `python3 -m unittest <name>` or a pytest run whose working-directory/rootdir actually reaches it) before the PR that adds it merges; a test file that exists on disk but that no workflow step names is not counted as coverage.

**Source:** `analyzed`

**Evidence:** .github/workflows/cicd.yml:31-33,108-109 (defaults.run.working-directory: tools/werkstoff-cli, so `uv run pytest -q` only ever discovers tools/werkstoff-cli/tests/test_core.py and test_cli.py) and .github/workflows/plugin-checks.yml:130-134,146-157 (the only other two test files wired in, via explicit `python3 -m unittest test_build_symbol_index -v` and `python3 -m unittest test_docs_ux_audit -v`); no other workflow file references any other test_*.py by name or path

**Note:** This is a gap, not a followed convention: at least 15 other test_*.py files exist in the repo (plugins/lehre/scripts/test_lehre_core.py, plugins/lehre/hooks/test_lehre_guard.py, plugins/confab/scripts/test_cycle_engine.py, plugins/confab/scripts/hooks/test_guard_edit_scope.py, plugins/confab/scripts/test_build_burndown_html.py, plugins/compass/scripts/test_compass.py, plugins/compass/scripts/test_build_branch_comparison_html.py, plugins/self-assess/scripts/test_build_stage_map_html.py, plugins/self-assess/scripts/lib/test_status.py, plugins/self-assess/scripts/lib/test_staleness.py, plugins/self-assess/hooks/test_guard_target_edit.py, plugins/cupertino/scripts/test_state.py, plugins/andon/hooks/test_andon_enforce.py, tools/enforcement-audit/test_audit_enforcement.py, tools/andon-ledger-validator/test_validate_ledger.py, tools/surface-index/test_build_surface_index.py, tools/catalog-validator/test_validate_catalog.py) and none of them is referenced anywhere in .github/workflows/ or in test/plugins/run.sh — they only run if a developer happens to invoke them by hand, which CLAUDE.md's own "Verifying plugin changes" checklist does not do for any of them either. Rather than infer a coverage-percentage threshold nobody has adopted, this rule targets the actual observed failure mode in this repo (guards/tests that exist but are never invoked, the same shape as the rrt-doctor pre-commit hook and the 21 unpublished release tags documented in CLAUDE.md) and makes it mechanically checkable: grep each new test_*.py's module name against .github/workflows/*.yml.

**Verification verdict:** `revise`

**Verification note:** The sourceMode:"analyzed" claim is honest and the cited evidence checks out exactly as described. Confirmed at /Users/hahn/LocalDocuments/GitHub_Forks/werkstoff/.claude/worktrees/angry-mcclintock-d4cd76/.github/workflows/cicd.yml:31-33 (defaults.run.working-directory: tools/werkstoff-cli) and :108-109 (`uv run pytest -q`, which given that working-directory only discovers tools/werkstoff-cli/tests/test_core.py and test_cli.py), and at .github/workflows/plugin-checks.yml:130-134 (`python3 -m unittest test_build_symbol_index -v`, working-directory tools/symbol-indexer) and :146-157 (`python3 -m unittest test_docs_ux_audit -v`, working-directory test/docs). I independently grepped every module name from the note's 17-item gap list against .github/workflows/*.yml and test/plugins/run.sh and found zero references, matching the claim exactly. A Glob for all test_*.py in the repo also turned up nothing the candidate missed among real, non-fixture files.

However, the rule as literally worded is imprecise in a way this repo's own culture (CLAUDE.md's whole "silent-failure" section, its emphasis on guards that fire on the wrong case) would flag: it says "Every test_*.py file committed under plugins/ or tools/" with no exception for fixtures, but plugins/cli-scaffold/scripts/fixtures/widgetctl/tests/test_core.py is under plugins/, matches test_*.py, and is never referenced in any workflow -- yet it is not a real coverage gap. I read it and plugins/cli-scaffold/scripts/selftest.py:179-206: the fixture directory is copied wholesale and fed to the architecture-tree-viewer builder as sample input to check the *rendered HTML output*; test_core.py inside it is never invoked by pytest or unittest anywhere, by design (it exists so the fixture behaves like a real project, not as a test to run). The candidate's own note correctly omits this file from its list of 15 (actually 17) genuine gaps, showing the author was aware of the distinction in practice, but the rule text itself contains no fixtures/ carve-out, so a later mechanical drift-audit applying the rule verbatim would misclassify this fixture as a violation and demand it be wired into CI, which would be wrong -- the exact "guard fires on a case it wasn't meant for" shape this repo has already been burned by. Recommend the rule add an explicit exclusion for paths containing a `fixtures/` (or similarly named test-data) directory segment before this is finalized.

### public-api-documentation — CONFIRMED

**Rule:** Every public (non-underscore) function and class in tools/werkstoff-cli/src/werkstoff/ — the repo's one PyPI-published package and its only genuine external "public API" — must carry a docstring describing what it does, its parameters, and its return value; enforce this by adding "D101","D102","D103" to that package's own `[tool.ruff.lint] select` list in tools/werkstoff-cli/pyproject.toml (scoped there only, not repo-wide).

**Source:** `scaffolded`


**Note:** No real convention governs public-API documentation anywhere in this repo. The only shipped/consumed artifact that qualifies as a genuine "public API" is tools/werkstoff-cli (published to PyPI per its pyproject.toml); inside it, docstring usage on public functions is inconsistent rather than patterned — some have them, some don't, with no discernible rule for which. Neither the root ruff.toml nor tools/werkstoff-cli/pyproject.toml selects any pydocstyle ("D") rule, so nothing currently checks this even mechanically. I also checked plugins/lehre/scripts/fixtures/sample_doctrine_ruleset.json, which names a "public-symbols-documented"/ruff-D103 rule — but that file is lehre's example OUTPUT for a hypothetical target codebase it might generate a doctrine for, not evidence of werkstoff's own practice, so I did not treat it as real convention evidence. This proposed rule is therefore a sensible default scoped to the one place a "public API" genuinely exists in this repo, not something observed as already being followed.

**Verification verdict:** `confirmed`

**Verification note:** Independently re-verified. tools/werkstoff-cli/src/werkstoff/core.py confirms the exact pattern cited: find_repo_root (line 51-53) and install_plugins (line 140, 146-148) carry docstrings, while load_marketplace (64), Marketplace.plugin (43), ensure_claude_cli (97), add_marketplace (112), update_marketplace (119), and install_plugin (126) do not -- genuinely inconsistent, no discernible rule. tools/werkstoff-cli/pyproject.toml:33 selects only ["E","F","I","UP","B"] and root ruff.toml:47 selects only ["E4","E7","E9","F"] -- neither includes any pydocstyle "D" code, so nothing mechanically enforces docstrings anywhere in the repo today. This is the one package in the repo with a genuine external public API (PyPI-published, per its own pyproject.toml project.scripts/build-system). sourceMode 'scaffolded' is honest: there is no existing convention to observe, only inconsistent usage, and the note says so plainly rather than fabricating a pattern. The rule itself is concrete and mechanically checkable later: it names an exact directory, an exact enforcement mechanism (add D101/D102/D103 to a specific config's select list), and a specific scope (that package only, not repo-wide) -- a drift audit can literally run ruff and check for zero D10x findings under that config.

### dependency-hygiene — NEEDS REVISION

**Rule:** Every dependency manifest in this repo (package.json, pyproject.toml) must have its corresponding lockfile (package-lock.json, uv.lock) committed to version control, not gitignored — a new manifest without a checked-in lockfile is a dependency-hygiene violation.

**Source:** `analyzed`

**Evidence:** .gitignore:127-131 (UV section deliberately comments out `# uv.lock` so it is NOT ignored, with the inline rationale "it is generally recommended to include uv.lock in version control... to ensure reproducibility"); tools/werkstoff-cli/pyproject.toml:1-26 paired with the committed tools/werkstoff-cli/uv.lock; root package.json:1-13 paired with the committed root package-lock.json; tools/d3-subset/package.json:1-15 paired with the committed tools/d3-subset/package-lock.json

**Verification verdict:** `revise`

**Verification note:** The cited evidence checks out and the sourceMode="analyzed" claim is honest: .gitignore:127-131 really is the "# UV" block with "# uv.lock" commented out (deliberately NOT ignored) alongside the "generally recommended to include uv.lock in version control" rationale text on line 128; the three named manifest/lockfile pairs are real and both sides are present — root package.json + package-lock.json, tools/d3-subset/package.json + tools/d3-subset/package-lock.json, tools/werkstoff-cli/pyproject.toml + tools/werkstoff-cli/uv.lock.

However the rule as worded ("Every dependency manifest in this repo … must have its corresponding lockfile committed") is broader than the evidence supports and would misfire under a mechanical audit. There are four other pyproject.toml/package.json files in the repo with no lockfile at all: test/plugins/fixtures/hallucinated-dependency/package.json (a confab test fixture whose sole dependency, "left-pad-definitely-not-real-9f3a", doesn't even exist on npm), test/plugins/fixtures/cli-doctrine-violations/pyproject.toml, test/plugins/fixtures/two-package-one-manifest/pyproject.toml, and plugins/cli-scaffold/scripts/fixtures/widgetctl/pyproject.toml. These are deliberately synthetic test-fixture manifests, not real installable dependency sets, so they are not actually a "dependency-hygiene violation" in spirit — but the rule's literal text ("every dependency manifest in this repo") does not exempt them, so a later drift-audit applying it mechanically would flag four false positives. To be genuinely checkable, the rule needs an explicit carve-out for test/fixture manifests (e.g. scope it to manifests outside test/plugins/fixtures/ and plugins/*/scripts/fixtures/), or otherwise state the exclusion the candidate silently assumed but never wrote down.

### complexity-limits — NEEDS REVISION

**Rule:** Every Python function/method must have a cyclomatic complexity of at most 10 and every function/module must stay within an enforced size limit, checked by enabling ruff's `C901` (mccabe, max-complexity = 10) and `PLR0915`/`PLR0912`/`PLR0913` (too-many-statements/branches/arguments) rule codes in both `ruff.toml` and `tools/werkstoff-cli/pyproject.toml`'s `[lint].select`.

**Source:** `scaffolded`


**Note:** No complexity-limits convention exists in this project. Both ruff configs (ruff.toml:47 `select = ["E4","E7","E9","F"]` and tools/werkstoff-cli/pyproject.toml:33 `select = ["E","F","I","UP","B"]`) explicitly enumerate their enabled rule families -- the root config's own comments (ruff.toml:16-27) even document why the selection is spelled out deliberately -- yet neither ever includes mccabe (`C90`) or the pylint-style too-many-* codes (`PLR09xx`). There is no biome.json, .eslintrc, .pylintrc, or setup.cfg anywhere in the repo defining a complexity, nesting-depth, parameter-count, or function/file-length ceiling, and no comment in code or CLAUDE.md establishes an informal one either. This proposed rule (max-complexity 10, ruff's own conventional default) is a sensible scaffolded default, not an observed convention -- it should be validated against actual code before being treated as load-bearing.

**Verification verdict:** `revise`

**Verification note:** The sourceMode claim itself checks out: I independently confirmed ruff.toml:47 (`select = ["E4", "E7", "E9", "F"]`) and tools/werkstoff-cli/pyproject.toml:33 (`select = ["E", "F", "I", "UP", "B"]`) — neither enables C90x (mccabe) or PLR09xx (too-many-*). A repo-wide grep for max-complexity/C901/PLR091/mccabe/cyclomatic/too-many-* turns up hits only in plugins/self-assess's own complexity-scoring skill/agent (a SLOC-based `2.94 x (KSLOC)^1.10` attention-priority index it computes *about target repos*, unrelated to a per-function cyclomatic-complexity gate on werkstoff's own code) and an unrelated vitepress data file — nothing establishes an actual complexity-limit convention. No .pylintrc, biome.json, .eslintrc, or setup.cfg exists anywhere outside node_modules. So `sourceMode: "scaffolded"` is honest and the note accurately describes an absence rather than fabricating evidence.

However, the rule text itself has a real defect worth fixing before it's load-bearing: it says 'every function/module must stay within an enforced size limit' but none of the cited codes (C901, PLR0915/PLR0912/PLR0913) actually bound module/file size — they are all function-scoped (cyclomatic complexity, statement count, branch count, argument count). Ruff has no native file-length/module-size rule, so a drift-audit built to mechanically verify 'module size limit' against this rule set would find nothing to check and stall or misfire. Recommend narrowing the rule to function/method scope only (drop the module-size clause, or if a module-size ceiling is actually wanted, name a concrete mechanism for it, e.g. a line-count script/pre-commit hook, since ruff's select list alone can't provide it).

## Exceptions & waivers

### Documented fail-open carve-out — `error-handling`

**Scope:** `plugins/self-assess/hooks/guard_target_edit.py:125-139` and
`plugins/confab/scripts/hooks/guard_edit_scope.py:96-107` only. Both guards wrap the
`from lib... import ...` line for their own vendored `scripts/lib/` package in
`except (ImportError, ModuleNotFoundError)`, and on that specific exception print the
error to stderr and `return allow()` instead of denying.

**Why this is excepted rather than fixed:** both guards' own module docstrings
document this as a deliberate, reasoned trade-off tied to issue #24: a packaging
defect in the plugin's own shared library is not evidence that the edit under review
violates a rule, and denying every future edit in every repository because of a
broken import is judged a strictly worse failure than one missed enforcement check.
This is pre-existing, shared architecture (documented independently in both files
with matching language, and in `docs/orchestration/references/hazards.md`'s "All
five fail closed, with one shared exception"), not an oversight this handbook should
silently flag as non-compliant every time `cupertino-handbook-check` runs.

**What this exception does NOT cover:** every other exception path in both files
(including their own `main()`-level catch-alls) still fails closed per the rule as
written. A third guard proposing the same fail-open pattern is not automatically
covered by this waiver — it needs its own documented rationale and its own named
entry here, evaluated on its own evidence rather than inheriting this one.

**Recorded:** 2026-09-07, via `cupertino-integrate` evaluating the seam between this
rule and the guards' already-shipped behavior. Verdict: delegate to the existing
engineering decision rather than force the code to integrate (conform) to a uniform
fail-closed policy. See the session transcript for the full friction analysis.

## Change log

- 2026-09-07: Drafted via `cupertino-handbook-draft` (domain: `code`). 3/6 dimensions confirmed on independent re-verification; the rest are flagged `NEEDS REVISION` above and should be tightened (narrower scope, corrected evidence) before being treated as enforceable.
