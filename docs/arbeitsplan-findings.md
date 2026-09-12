# arbeitsplan: what this build actually established

A record of the defects found while building `arbeitsplan` and extending `takt`, written
because the root cause of a defect is only findable if the reasoning that produced it survives
the transcript. Every row below was **run**, not reasoned.

## The headline: five silent failures, all reporting success

Every one of these produced clean, confident output. None raised an error. Four of the five
lived in the same ~10 lines of one bash function.

| # | defect | what it silently did | how it was found |
|---|---|---|---|
| 1 | tab as the field separator in `read` | tab is an IFS **whitespace** char, so a run of tabs collapses and empty fields vanish. The disabled arm's empty `plugin_dir` disappeared and every later field shifted left — **swapping the two ablation arms** | asserting on argv per arm |
| 2 | `printf '%s'` with no trailing newline | `read` hit EOF, the loop body never ran, so the **enabled** arm got no `--plugin-dir` at all | the same assertion, after #1 |
| 3 | `tr '\x1f' '\n'` | `tr` takes **octal**, not hex. `'\x1f'` parsed as the character set `{\, x, 1, f}` — every `f`, `x` and `1` in a path became a newline, shredding `/…/werkstoff/…` into five fragments | a path that reported as "does not exist" |
| 4 | `claude -p` inherits the loop's stdin | the child consumed the remaining cell list. A 2-cell sweep ran **one** and reported `PASS 1/1` | running a **real** `claude`; no stub could |
| 5 | comparing `plugin:skill` against `plugin` | the delegation cycle check compared a dispatch id (`"compass:compass-solve"`) against ledger plugin names (`"compass"`). Never matched, so every cycle passed | the guard's own calibration |

**The transferable lesson is narrower than "test more".** #4 is the one that matters: a stub
that does not exercise the same syscalls as the real binary is not a test of the harness. The
echo-only stub passed every time; a stub that merely adds `cat > /dev/null` reproduces the bug
instantly and for no tokens. That stub is now a permanent `--selftest` case.

## Three times the instrument was the defect, not the code

This repository's CLAUDE.md says *"verify the instrument before trusting its verdict."* It was
needed three times in one session, and in each case the instrument was **mine**:

1. **A sabotage test that passed for the wrong reason.** Two of three `STALE` cases in takt's
   guard calibration stayed green with the fix removed, because a bare `require: "built"`
   resolved to a path nothing had created. Planting the stale marker at *every* location an
   earlier run could have left one is what made them real.
2. **An imported measurement treated as a law.** The matrix runner refused to run whenever it
   detected a nested Claude Code session, on the strength of a measurement made in a different
   repository on a different day (*"a nested `claude -p` fails: OAuth session expired"*). It
   does not reproduce here — a nested `claude -p` returns cleanly. The refusal was also
   **redundant**: a cell that hits an auth banner is already scored `UNMEASURED` with the
   reason, which is more information than never starting. Replaced with a one-call probe that
   prints what it actually got.
3. **An audit that reported four phantom findings.** A grep for cross-plugin references flagged
   4 dead ids. All four were false positives: `andon_core.py`'s `STRATEGY_D_REJECTED_TYPOS`
   denylist (andon already validates these), the andon reference doc *documenting* that typo,
   and `lehre:hooks`, a `batchKey` tuple in a JSON example. **Genuine dead references: zero.**

## The cross-plugin linkage audit

148 real skill/agent ids across 12 plugins; 36 cross-plugin references in 7 of them.

| source | ordering | hard dispatch | optional | boundary prose |
|---|---|---|---|---|
| `self-assess` | 0 | 4 | 2 | 1 |
| `andon` | **2** | 2 | 0 | 1 |
| `arbeitsplan` | 0 | 0 | 4 | 3 |
| `nacharbeit` | 0 | 1 | 0 | 0 |
| `confab` / `cupertino` / `lehre` | 0 | 0 | 0 | 1 each |
| `takt` | 0 | 0 | 0 | 0 |

> **CORRECTED IN ROUND 3.** What stood here claimed this dependency was unenforced and that a
> takt beat had fixed it. Both halves were wrong, and how the error survived is the most useful
> thing on this page — the sentence *"Duplicated in `andon_core.py`"* was already written
> **here**, in round 2. The evidence was in this document. It was read as duplicated *prose*
> rather than as *enforcement*, because the audit that produced this section classified by
> keyword over SKILL.md text and never opened a script.

`plugins/andon/skills/andon-loop/SKILL.md:51-54` states the rule in prose. But
`plugins/andon/scripts/andon_core.py:741-754` — `check_ingest_prereqs` — **has enforced it in
code all along**, and better than the beat did:

| | `check_ingest_prereqs` | the beat that was shipped |
|---|---|---|
| files checked | **both** `MODERNIZATION_BRIEF.md` *and* `transform_brief_summary.json` | one |
| existence test | `os.path.isfile` | `os.path.exists` — a directory satisfies it |
| when it fires | **only** when `gap_source == "self-assess-brief"` | **always** |

The last row made the beat actively harmful. `gap_source: self-scan` is **the default** and
needs no brief at all, so the beat denied `andon-loop` in its ordinary mode — escapable only by
`TAKT_DISABLE_GUARD=1`, which disables every other beat too. The beat has been removed; the
requirement now carries `alreadyEnforcedBy`, and the compiler refuses to re-create it.

**The transferable rule:** a rule enforced in code reads, to a prose scanner, exactly like a
rule enforced by nothing. Any future run of that audit must grep the executable surface.

## Why `takt` was kept

`compass:compass-reason-verify` returned **3/3 unanimous** for
`KEEP_TAKT_BUT_GENERALIZE_DELEGATION`, by forward deduction, backward-from-options and
constraint mapping independently. The decisive argument, which none of them needed prompting
for:

> **Delegation and ordering are different axes.** A delegation registry records *who dispatched
> whom, and how deep* — a call graph. takt gates *"has beat X's marker been written"* — an order
> that also gates raw `Write`/`Edit` calls with **no dispatch in them at all**. takt's canonical
> beat ("no `*.tsx` write until `.takt/council-done` exists") has no dispatch to record.

Two claims made earlier in the session did **not** survive checking, and are corrected here:

- *"takt is inert because nothing authors its declaration"* — too strong. Its test fixtures are
  hand-written declarations and its README documents that path. takt is **under-adopted**, not
  structurally dependent on arbeitsplan.
- *"takt-v0.1.0 may be a tag that published nothing"* — it is a real published GitHub Release
  (2026-08-30, signed zip + SBOM, not a draft). Both assets show `download_count: 0`.

**The counter-argument nobody could dismiss, recorded so it is not lost:** only `emit_beats.py`
has ever auto-authored a declaration. Keeping takt separate pays a full plugin surface for a
generality nothing has yet used. That is grounds for a re-audit if no second author appears — 
not grounds for deletion.

## Design consequences that came out of building it

- **A guard's ledger must be the guard's own.** A guard that checks a list some skill was
  supposed to append to fails open exactly when the skill misbehaves — the case it was written
  for. arbeitsplan's re-dispatch denial is an `O_CREAT|O_EXCL` create failing with `EEXIST`: no
  read-modify-write, race-free across parallel candidates, and dependent on nothing cooperating.
- **JSONL over JSON for anything parallel writers append to**, with a size cap: `O_APPEND` of
  one line is atomic under `PIPE_BUF` (512 POSIX, 4096 Linux); a longer record can interleave.
- **A depth cap and cycle detection are not redundant.** A cap bounds `A→B→C→D`; `A→B→A` is
  depth 2 and sails under any cap. The sabotage tests prove independence: unbound the cap and
  only `DEPTH` goes red; disable the cycle check and only `CYCLE` does.
- **Compare against the dispatching source, not the run's owner.** Using the owner classified
  `arbeitsplan → compass → arbeitsplan` as fan-out and skipped the cycle check on precisely the
  shape it exists for.
- **A `.takt/`-prefixed marker is repo-level and must not be namespaced by `runId`.** One
  compiled declaration has to carry both durable facts and per-run markers; namespacing a
  durable fact makes something true read as false in every later run. The split falls along
  takt's existing convention, so no prior declaration changes meaning.

## Does markdown formatting reduce model confusion? Measured, and: no evidence

The question was "standardize markdown width and notation — will it help?" Rather than assert,
it was run through the ablation matrix this session built. Two rounds, 30 `claude -p` cells,
one fresh process each.

**Design.** Three arms of the *same content* from `references/patterns.md`, differing only in
form, with a question whose answer is known and checkable:

| arm | form |
|---|---|
| **A structured** | as the repo writes it — tables, code fences, headings, ~100-col hard wrap |
| **B unstructured** | tables flattened to prose, no fences, no headings, no hard wrap |
| **C cosmetic** | identical structure to A, reflowed to 55 cols |

C exists to separate the *cosmetic* claim from the *structural* one, so an effect could not be
attributed to the wrong cause.

**Round 1** — one fact from ~1 KB. All three arms: **5/5 correct, identical every repeat.** A
ceiling: the task was too easy to discriminate, and a null result at a ceiling is weak evidence.

**Round 2** — four facts from four different sections of a ~10 KB document, one of them in the
*rejected* list so it could not be answered by skimming the top:

| arm | facts correct | all four correct | identical across 5 repeats |
|---|---|---|---|
| A structured | 19/20 | 4/5 | no (2 distinct answers) |
| B unstructured | **20/20** | **5/5** | **yes** |
| C cosmetic | 18/20 | 3/5 | no (2 distinct answers) |

**The unstructured arm scored best.** That is the opposite of the expected direction — and with
n=5 per arm and a spread of two errors out of twenty, it is **noise, not a finding**. The honest
reading is that no arm was measurably better, and the only fact anything got wrong was the
*count* of accepted patterns, which is a known model weakness independent of formatting.

**What this does and does not license:**

- It does **not** support enforcing cosmetic rules (line width, list markers) on a
  comprehension claim. Nothing here shows they help, and C — the cosmetic-only arm — scored
  lowest.
- It does **not** refute structural markup either. The effect, if any, is smaller than this
  design can see.
- It does **not** contradict this repo's own 9-of-11 handoff benchmark, because **that is a
  different claim**: `compile_spec.py` *parses* the machine-readable index in `patterns.md`.
  That is machine consumption, where structure is not a preference but a precondition. This
  experiment tested *model* comprehension, and found nothing.

**Recommendation:** adopt `markdownlint-cli2` for diff hygiene and for the structural rules a
*tool* depends on — fenced blocks with language tags, machine-readable JSON blocks, heading
hierarchy. Justify it on reviewability and machine-parseability, which are demonstrated, and
**not** on reduced model confusion, which is not. Cosmetic rules stay warnings.

Raw cells are under `analysis/md-experiment/` (gitignored). The matrices are reproducible:
`analysis/md-experiment/matrix.json` and `matrix2.json`.

## Round 3: the beat graph was wired on one side only

`beats.json` shipped in round 2 across all twelve plugins. The `requires` half worked. The
`produces` half **did not exist as code** — not one plugin writes a `.takt/` marker anywhere,
and the round-2 end-to-end demo passed only because the marker was created by hand.

Three defects in the marker indirection, not one:

| # | defect | fails | consequence |
|---|---|---|---|
| 1 | nothing writes any marker | **closed** | denies forever, loudly. Annoying, visible, safe |
| 2 | `.takt/` was not gitignored | **open** | a committed marker satisfies its gate for every clone, silently |
| 3 | a marker written because a SKILL.md says to `touch` it | either | ~1 run in 3 by this repo's own table |

Defect 2 is the serious one: every guard here fails closed on purpose, and a committed marker
is the exact opposite.

### Seven of eleven steps cannot be evidenced at all

- `cupertino-council` and `andon-verify` write **nothing**. The council produces a brief, a
  tension log and code, all in conversation; `andon-verify` is explicitly forbidden to write
  ("`andon-loop` persists it").
- `compass`'s two markers persist to `.compass/runs/<uuid>/…` — predictable directory,
  unpredictable leaf, and takt's `require` has no glob.
- `lehre-pin` and `matrize-emit` write to caller-chosen paths.
- `consistency-canonize` writes to `analysis/<area>/`, where `<area>` is the command's argument.

Four have real artifacts: self-assess's `stage_graph.json` and `MODERNIZATION_BRIEF.md`,
confab's `contract_drift_summary.json`, nacharbeit's `run.json`.

**Existence still under-specifies completion.** `MODERNIZATION_BRIEF.md` is written *even on
self-assess's degraded "Ready-with-gaps" path*. Two patterns here already solve that and are the
model for any future evidence rule: `nacharbeit/scripts/write_results.py:115` writes `run.json`
**last**, commented "its presence means the other three are complete"; and `build_report.py`
refuses when a `FAILED-*` marker is **newer** than `run.json`'s mtime.

### What replaced it

- `evidence` is required on every `produces`. **`kind: "none"` is legal to declare and
  impossible to depend on** — the compiler refuses any beat requiring it, quoting the recorded
  `why`, so the step stays in the registry with its reason instead of being re-derived by
  someone shipping the same broken marker.
- **`alreadyEnforcedBy`** on a `requires` makes the compiler refuse a duplicate of an existing
  in-code enforcement. Two enforcements of one rule is drift waiting to happen, and the second
  is usually the weaker one.
- Where an artifact exists, a beat gates on **the real path** with `requireKind: "file"`,
  closing the `mkdir <path>` bypass plain `os.path.exists` allowed. Omitting `requireKind` is
  byte-identical to the old behaviour.
- `/.takt/` is gitignored. The deliberate contrast: `.cupertino/<domain>-handbook.md`,
  `.lehre/ruleset.json` and `.design/` stay **tracked**, because they are durable project facts
  that should be shared. An artifact carries its own lifecycle; a marker has no defensible
  default either way.

**Net result: zero beats compile.** `emit_beats --repo-only` writes nothing and says so. That is
the correct state — every cross-plugin ordering rule this repository has is either already
enforced in code or cannot be evidenced.

### The instrument was the defect, for the fourth time

Two guard calibrations passing for the wrong reason; an imported measurement never re-run
locally; four phantom dead references; and now a prose-only audit that missed enforcement
sitting in a script the same document already cited. Four instruments, one session, one shape:
each looked right and measured the wrong thing. That is the strongest argument this repository
has for its own rule — **verify the instrument before trusting its verdict** — and the reason
every guard added here ships with a sabotage test that must go red.
