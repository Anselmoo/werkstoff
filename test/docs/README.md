# Docs UX test suite

Three layers, testing three different failures a documentation site can have. Only the
first two exist yet.

| Layer | What it checks | Cost | Status |
|---|---|---|---|
| 1. `docs_ux_audit.py` | Do the docs' own CLAIMS (counts, orderings, category sets) match the filesystem? | Free, instant, no LLM | Built |
| 2. `journeys.tsv` + `run-journeys.sh` | Given a real user goal in plain language, does the site LEAD a reader to the right page? | Real tokens, one `claude --print` process per case | Built (this directory) |
| 3. DOM tests | Does the rendered VitePress site actually navigate the way the source implies (sidebar, search, links render and click through)? | Real browser automation | Not yet built |

Layer 1 audits the docs against themselves. Layer 2 audits the docs against a reader who
has never seen them before. Neither one can catch what the other catches: a claim can be
internally consistent and still fail to route a real question to the right page, and a
page can be perfectly findable while stating a wrong count.

## Layer 1 -- static claim audit

```bash
python3 test/docs/docs_ux_audit.py            # all checks
python3 test/docs/docs_ux_audit.py --list     # show check ids and exit
python3 test/docs/docs_ux_audit.py --only C1  # run one check
```

Free and instant -- no LLM, no network. See its own docstring for what it checks and why
the four existing gates (`validate_catalog.py`, `buildCatalogSidebar()`,
`ignoreDeadLinks`, regenerate-and-diff) all check referential integrity and none of them
check a claim.

## Layer 2 -- journey tests (this directory)

### What a journey test is

Each case in `journeys.tsv` is a user's goal, stated the way a real person would say it
-- deliberately avoiding the docs' own vocabulary ("beat", "wire", "leaf",
"orchestrator", skill ids) -- plus an oracle regex asserting which page a correct answer
must land on. 17 cases span all 7 catalog categories, the orchestration reference set,
and 2 of the catalog's 3 documented "No werkstoff fit" recipes (see below).

### Isolating the model from prior knowledge (the load-bearing design decision)

If the model under test can answer a goal from its own training/session knowledge of
werkstoff's plugins, the test measures the MODEL, not the DOCS. `run-journeys.sh` closes
that gap three ways, in decreasing order of strength:

1. **A docs-only cwd.** Each case runs in a fresh temp directory containing nothing but
   an `rsync`'d copy of `docs/` (with the generated `.vitepress/dist/` build output
   excluded -- copying the pre-rendered site would hand the model a search index and nav
   tree it should have to derive itself from source prose). No `CLAUDE.md`, no
   `plugins/`, no `analysis/` -- none of this repo's other prose exists in that cwd.
2. **The clean box.** The exact `test/plugins/make-clean-box.py` settings `run.sh`
   already uses: every installed plugin disabled, every personal skill turned off. This
   matters even here, where no `--plugin-dir` is ever passed: without it, a real
   werkstoff/andon/self-assess install already on the machine running this suite would
   let the model answer the goal by *running* a skill instead of by reading the copied
   `docs/` prose -- exactly the confound `make-clean-box.py`'s own docstring documents
   for the plugin-behavior suite, reused verbatim here for a different reason.
3. **An explicit prompt instruction** forbidding prior knowledge and requiring the model
   to cite the exact file path it read (see `PROMPT_PREFIX`/`PROMPT_SUFFIX` in
   `run-journeys.sh`).

**Residual weakness, stated honestly:** lever 3 is instruction-following, not a sandbox.
The `claude --print` process still has full filesystem read access in principle; nothing
mechanically stops it from reading outside the temp cwd if it chooses to ignore the
instruction, the way nothing stops any other headless case in `test/plugins/` from doing
the same. Levers 1 and 2 are what actually matter: even if the model wandered outside the
temp cwd, the transcript is saved (see below) and a human can check whether the cited
path was genuinely read from the copy or fabricated from memory. A second, smaller
residual gap: the machine's own global `~/.claude` user-level memory/rules still load
regardless of cwd (this is a Claude Code product behavior, not something this harness
can suppress) -- on this machine that memory is about an unrelated `context7` workflow
and says nothing about werkstoff, so it is not believed to leak an answer, but that is a
belief about this one machine's config, not a proof.

### Running it

```bash
# Free -- run this FIRST, always, before spending any tokens:
bash test/docs/lint-journey-oracles.sh      # bans the same silently-failing regex
                                             # forms as test/plugins/lint-oracles.sh
bash test/docs/calibrate-oracles.sh         # fabricated-transcript calibration

# Costs real tokens:
bash test/docs/run-journeys.sh              # all 17 cases
bash test/docs/run-journeys.sh ci-red-jobs  # one case by id
```

Every case writes its full transcript to `test/docs/.runs/` (gitignored -- see
`.gitignore`), named `<id>.<epoch>.<pid>.stdout` plus a `.meta` file recording the goal,
oracle, and expected path, so a human can read exactly what the model said for any
single case without re-running it.

**Rough cost of a full sweep:** `docs/` (excluding the generated `.vitepress/dist/`) is
~700KB across 59 markdown files, ~63,000 words. A case does not read all of it -- it
globs/greps to the relevant category directory and reads a handful of files -- so a
realistic per-case budget is on the order of 10-25k tokens including tool-call overhead,
call it 250-450k tokens total for all 17 cases. At current Sonnet-tier pricing that is
low single digits of dollars for a full sweep, not a per-run rounding error but not
expensive either. Run `test/docs/lint-journey-oracles.sh` and
`test/docs/calibrate-oracles.sh` first every time, since both are free and either one
catching a problem saves the whole token spend.

**ERROR is a third verdict, distinct from FAIL**, with the identical meaning
`test/plugins/run.sh` gives it: empty stdout, a CLI refusal banner ("hit your usage
limit", "not logged in", etc.), or a reply under `MIN_STDOUT_BYTES` (default 200) means
the run never really happened. That is evidence about the harness or the account, never
about the docs, and `run-journeys.sh`'s summary refuses to print a pass rate at all when
any case errored -- see its final `if [[ "$err" -gt 0 ]]` block. Per CLAUDE.md: "a case
with any errors has no rate, only missing data."

### The calibration rule, made concrete

CLAUDE.md states the repo's non-negotiable directly: *"Never retune an oracle after the
thing it grades exists"* and *"oracles are calibrated against fabricated transcripts
before first use."* Concretely, for this suite, that means:

- `test/docs/calibration/fixtures/*.txt` are hand-written, fabricated model transcripts
  -- never output from a real `claude --print` run -- created and checked in **before**
  `run-journeys.sh` was ever executed against the real docs site.
- `test/docs/calibration/calibration.tsv` copies each regex/antiregex **verbatim** from
  `journeys.tsv` (see its own header comment) and asserts what verdict it must produce
  against each fixture. `calibrate-oracles.sh` fails loudly on any mismatch.
- **What "retuning after the fact" would look like, concretely, so it's recognizable if
  it starts happening:** running `run-journeys.sh` for real, seeing that `ci-red-jobs`
  scored FAIL because the model wrote "the CI diagnosis page" instead of the literal
  slug `pipeline-red-across-jobs`, and then loosening that case's regex in `journeys.tsv`
  to accept "CI diagnosis page" too. At that point the oracle has stopped measuring
  whether the docs led the reader to the right page and started measuring whatever the
  one observed transcript happened to say -- it would pass that specific run by
  construction, which is not evidence about the docs, it's evidence about itself. The
  correct response to that FAIL is to read the transcript in `test/docs/.runs/` and ask
  whether the DOCS failed to make the destination identifiable (a real docs bug, worth
  fixing in the docs) or whether the oracle was already too narrow on inspection **before
  any real run existed** (fix it now, before running again, and note in the commit that
  it was never run against the loosened version). A regex may legitimately be found too
  strict during initial authoring and fixed via `calibrate-oracles.sh` -- what's
  forbidden is discovering that strictness via a real run's outcome and loosening it in
  response to that outcome.
- This is also why `calibration.tsv` includes **two distinct FAIL fixtures** for the
  conjunctive (`@@AND@@`) oracle style used by the two negative cases:
  `conjunctive-fail-overclaim` (cites the right file, then invents a werkstoff fit the
  page itself disclaims -- the over-claiming failure mode the negative cases exist to
  catch) and `conjunctive-fail-ungrounded` (says "no fit" but never actually locates the
  page -- an ungrounded guess dressed as honesty). A single-regex oracle that only
  checked for the phrase "no werkstoff fit" would pass both of those wrongly; the
  conjunction is what makes the oracle only credit an answer that is BOTH grounded and
  honest.

### Case list

15 positive cases plus 2 negative cases. `expected_path` is documentation for a human
reading a failure; the actual oracle is the `regex`/`antiregex` columns in
`journeys.tsv`.

| id | category | destination |
|---|---|---|
| `vague-ask` | before-any-code | `catalog/before-any-code/scope-ambiguous-task.md` |
| `new-cli` | before-any-code | `catalog/before-any-code/scaffold-new-project-or-cli.md` |
| `return-type-migrate` | change-existing-code | `catalog/change-existing-code/migrate-return-shape-or-type.md` |
| `parallel-plan` | change-existing-code | `catalog/change-existing-code/execute-plan-across-parallel-workstreams.md` |
| `ci-red-jobs` | ci-release | `catalog/ci-release/pipeline-red-across-jobs.md` |
| `green-but-nothing` | ci-release | `catalog/ci-release/job-reports-success-but-changed-nothing.md` |
| `tests-lie` | defect-work | `catalog/defect-work/tests-pass-while-code-is-broken.md` |
| `fix-recurring` | defect-work | `catalog/defect-work/fix-that-did-not-stick.md` |
| `new-skill-authoring` | plugin-authoring | `catalog/plugin-authoring/author-a-new-skill-or-agent.md` |
| `convention-clash` | quality-verification | `catalog/quality-verification/audit-against-documented-conventions.md` |
| `stale-readme` | surface | `catalog/surface/documentation-drift-after-a-change.md` |
| `ui-design-review` | surface | `catalog/surface/ui-and-design-system-work.md` |
| `which-orchestrator` | orchestration | `orchestration/README.md` ("Orchestrators and leaves") |
| `pairing-check` | orchestration | `orchestration/references/pairings.md` |
| `model-tiering` | orchestration | `orchestration/references/delegation.md` |
| `rehearse-release` (negative) | ci-release | `catalog/ci-release/release-path-never-succeeded.md` |
| `incident-now` (negative) | defect-work | `catalog/defect-work/incident-triage-under-time-pressure.md` |

`ci-red-jobs` and `green-but-nothing` are a deliberately confusable pair -- both are
CI-shaped complaints in the same category ("jobs went red" vs "job stayed green but did
nothing"), so each carries the other's slug as an `antiregex`: a correct answer must
distinguish the two, not just recognize "something CI-shaped."

### The three "No werkstoff fit" recipes

The catalog's own index states: *"Three recipes are marked 'no werkstoff fit' in their
body text."* Confirmed by:

```bash
grep -rli "no werkstoff fit" docs/catalog/
```

which returns exactly:

- `docs/catalog/ci-release/release-path-never-succeeded.md`
- `docs/catalog/defect-work/incident-triage-under-time-pressure.md`
- `docs/catalog/quality-verification/incorporate-external-review-feedback.md`

(`docs/catalog/index.md` itself also matches the grep, since it names the count in
prose -- it is not a fourth recipe.)

Two of the three are exercised as negative cases (`rehearse-release`,
`incident-now`). **`incorporate-external-review-feedback.md` is deliberately left
untested** -- see "What was deliberately not tested" below.

### What was deliberately not tested, and why

- **The third "No werkstoff fit" recipe** (`incorporate-external-review-feedback.md`).
  Two negative cases already exercise both fixed regex sub-styles this suite uses for
  the "no fit" shape (see calibration above); a third would repeat the same mechanism on
  a third page rather than test anything new about the harness. If this suite is
  extended, that recipe is the obvious next case to add, not because it is
  higher-risk than the other two, but because it is the one gap left uncovered by
  the two most different available goals.
- **Layer 3 (DOM/rendered-site tests).** Not built. `journeys.tsv` tests whether the
  SOURCE prose leads a reader to the right page; it says nothing about whether the
  rendered sidebar, `<CatalogGrid />` filter UI, or search actually surfaces that page in
  the live site. That is a materially different failure mode (a docs bug vs. a
  VitePress/theme bug) and needs real browser automation, not a `claude --print` process.
- **Ambiguous-on-purpose goals with more than one defensible destination.** Several
  catalog recipes genuinely overlap (e.g. `refactor-for-maintainability.md` vs
  `collapse-duplication-across-n-sites.md`). None of the 17 cases here target a goal
  where two different pages would both be defensible answers, because a golden-file
  regex oracle cannot express "either of these two is acceptable" without weakening into
  something that would also accept a wrong answer. That is a real category of docs UX
  question this suite does not currently answer.
- **Running the real suite.** This task built and calibrated the harness; it does not
  run `run-journeys.sh` for real. See "Running it" above for the exact command and cost
  estimate.
