---
name: spur-trace
description: "Runs a project's pipeline or test suite once under a tracer and renders one static HTML page per run: per step the command, a call tree of the project's own functions, every file read and written with its sha256, which step's output fed which, and a hash-chain check; also exports W3C PROV-JSON. Use when a reviewer asks how a result was produced, which files a step read, or whether one step's output is really the next step's input — 'trace this pipeline', 'show provenance for this run', 'which step wrote this file', 'prove the outputs chain'. Writes only under analysis/spur/ (one directory per run) and never edits the traced code. Not for whether tests would catch a bug (zeugnis-assertion-audit) or for proving and fixing a handoff between stages (andon-verify)."
---

Record one run of the pipeline as it actually happened. This skill changes no source
file: the tracer is loaded beside the program, never into it.

The rule above the others: **the traced run must behave exactly like an untraced one.**
If a traced run fails where a plain run succeeds, stop and report it as a spur defect —
do not work around it by editing the project.

## Steps

1. **Detect the stack.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spur_trace.py" detect
   ```

   Exit `0` names each stack found and the adapter it gets; exit `4` found none. Python is
   traced in-process. Rust, Node and Go have no in-process adapter: read
   [`references/adapters.md`](../../references/adapters.md) before tracing one, and say
   to the user which parts of the record will be missing.

2. **Find the one command that runs the pipeline**, in this order: a documented pipeline
   command in the README, a `Makefile`/`justfile` target, a driver script, the test suite
   (`pytest`, `cargo test`, `npm test`). Ask the user only when none of these names it.
   One command, run once: every step must be a process that command starts.

3. **Run it under the tracer** from the project root.

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spur_trace.py" run -- <command> [args...]
   ```

   Exit codes, which decide the next step:

   | exit | meaning | next |
   |---|---|---|
   | `0` | the command succeeded and every link verified | step 4 |
   | `3` | a link is **broken**: a file changed between producer and consumer | step 4, lead with it |
   | `4` | incomplete (an input is unverified) or empty (no step read another's output) | step 4; never call it a pass |
   | `2` | usage or instrument error | fix the invocation, rerun step 3 |
   | other | the command's own exit code: the pipeline failed | step 4, lead with the failing step |

   On stderr it prints the summary and the run directory:

   ```text
   spur: 6 step(s), chain broken (2 verified, 1 broken, 1 unverified, 1 source)
   spur: wrote analysis/spur/20261030T183037Z/{trace.json,prov.json,spur-report.html}
   ```

4. **Report from `trace.json`, not from memory.** Read
   `analysis/spur/<runId>/trace.json` (the format is in
   [`references/trace-format.md`](../../references/trace-format.md)) and tell the user:
   - the chain verdict in one sentence, naming each `broken` input as
     `producer → path@version → consumer` with its `note` (it names any untraced step that
     ran in between);
   - every `unverified` input, and every untraced step with its `why`;
   - any step whose `exit.code` is non-zero, and the run's `dropped` count if it is not 0;
   - the path of `spur-report.html` to open, and `prov.json` for PROV tools.

   Show two or three inputs with their sha256 and status as evidence, verbatim from the
   record. Never round a `broken` or `unverified` input into "mostly fine".

5. **Only if the user asks whether the outputs are still the ones the run produced**, run

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spur_trace.py" verify analysis/spur/<runId>
   ```

   Exit `0` every final output matches its recorded hash; `3` names each `DRIFT` file. Drift
   after the run is not a chain break — the run was fine, the files changed since.

## What the record holds, and what it does not

- **Recorded:** argv of every process, the project's own function calls (code under the
  root; the interpreter, site-packages and the tracer itself are excluded), sha256 of every
  data file read and written, the code files it loaded (hashed, kept out of the chain),
  renames and removals.
- **Never recorded:** environment values, file contents, anything under the home directory
  in readable form (it becomes `~`). The raw per-process fragments hold absolute paths and
  are deleted after the merge unless `--keep-fragments` is passed.
- **Not observable:** a process started with `python -I`/`-E`, or given its own `env=`
  without `PYTHONPATH`, and any non-Python program. Each still appears as an untraced step.
