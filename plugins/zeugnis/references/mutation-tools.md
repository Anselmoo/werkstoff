# Mutation tools: what each one writes, and what zeugnis drives

Read by `zeugnis-mutation-harden` in step 1, when it detects the stack. Every
row here was checked against the tool's own documentation through context7
(or, for mutmut, by running it) on 2026-10-30. A flag or path that is not in
this table is not one the harness or the guard knows about, and must be
looked up before anyone encodes it.

| stack | tool | default working copy | in-place mode the guard denies outside a copy | per-mutant results | driven by `mutation_harden.py` |
|---|---|---|---|---|---|
| Python | mutmut 3 (3.8.1 checked) | none: `run` writes `./mutants/` in the cwd and resumes state left there | `run`, `apply` (rewrites the source file), `browse` (key `a` applies a mutant) | `mutants/<source>.meta`, key `exit_code_by_key` | **yes** |
| Python | cosmic-ray | none: `exec` with the local distributor writes each mutant to the module on disk, then restores it | `exec`, `apply` | session database | no |
| Rust | cargo-mutants | a copy of the tree in a temp directory | `cargo mutants --in-place` | `mutants.out/outcomes.json`; `caught.txt`, `missed.txt`, `timeout.txt`, `unviable.txt` (format "subject to change", per its docs) | no |
| JavaScript / TypeScript | StrykerJS | a sandbox copy in a temp directory | `stryker run --inPlace` | `reports/mutation/mutation.json` (the `jsonReporter` default) | no |

Sources: mutmut `src/mutmut/__main__.py`, `stats.py`, `configuration.py` and
`ui/browse.py` (3.8.1); cargo-mutants book, chapters `in-place.md`,
`cautions.md` and `mutants-out.md`; stryker-mutator.io configuration page,
entries `inPlace` and `jsonReporter`; cosmic-ray
`src/cosmic_ray/distribution/local.py` and `mutating.py`.

## mutmut 3 facts the harness depends on

- `run` writes no `mutmut-cicd-stats.json`. Only `export-cicd-stats` does,
  so the harness reads the `.meta` sidecars and never the stats file.
- The status of each exit code is `stats.py`'s `status_by_exit_code`: 0
  survived; 1 and 3 killed; 5 and 33 no tests; `None` not checked (what a
  time-boxed run leaves); 24, 36, -24, 152 and 255 timeout; 34 skipped;
  37 caught by type check; -9 and -11 segfault; anything else suspicious.
- `pyproject.toml`'s `[tool.mutmut]` wins over `setup.cfg`'s `[mutmut]`.
  `paths_to_mutate` and `tests_dir` are deprecated in favour of
  `source_paths` and `pytest_add_cli_args_test_selection`. `do_not_mutate`
  takes globs ending in `*` or `.py`.
- mutmut loads its config on import, so even `mutmut --version` fails
  outside a configured directory.
- `show NAME` prints a hunk relative to the mutated function, not to the
  file. The harness takes the file line from the source itself.

## Other tools: not driven, and what driving one would take

Each needs an adapter in `scripts/mutation_harden.py` and a parser in
`scripts/lib/mutation_results.py`, written against that tool's documented
result file and checked by running it. Until one exists, the skill stops
for that stack and says so; it never reasons out a score instead. The
guard rows above already hold for these tools, because their in-place
modes write into the working tree whether or not zeugnis drives them.

Not checked at all, so neither guarded nor driven: Stryker.NET, PIT
(Java/Kotlin), gremlins and go-mutesting (Go), Mull (C/C++).
