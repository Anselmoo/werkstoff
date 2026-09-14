# `matrix.json` — the headless sweep

The input to `scripts/run_matrix.sh`. One fresh `claude -p` process per cell, over the
cartesian product of `cases × models × plugin_states × repeats`.

Kept deliberately close to `quo-warranto`'s `tools/run_matrix.py` schema so results from the two
stay comparable. arbeitsplan adds `repeats`, `ablation`, `expected_tools`, plus the opt-in
`subrun` runner keys below (`runner`, `transcript`, `max_budget_usd`, and per-case `fixture`,
`expect_skills`, `forbid_skills`).

**Contents** — [top-level keys](#top-level-keys) · [ablation](#ablation--two-modes-that-answer-different-questions) · [the allowedTools trap](#the-trap---allowedtools-does-not-restrict-anything) · [the subrun runner](#the-subrun-runner-a-thin-per-cell-executor) · [the five outcomes](#the-five-outcomes) · [worked instance](#worked-instance) · [output](#output)

## Authentication is probed, not assumed

An earlier version of this runner refused outright whenever `CLAUDECODE` or
`CLAUDE_CODE_ENTRYPOINT` was set, on the strength of a measurement made in a different
repository: *"a nested `claude -p` fails with OAuth session expired."* **That does not reproduce
here** — a nested `claude -p` authenticates fine. Importing another repo's measurement as a law,
without running it, is the exact error this repository's CLAUDE.md warns about.

The refusal was redundant as well as wrong: a cell that hits an auth banner is already scored
`UNMEASURED` **with the reason**, which is strictly more information than never starting.

So the runner **asks instead of guessing**: one cheap `claude -p` call before the sweep. If it
authenticates, the sweep runs. If it does not, the runner refuses **and prints what the probe
actually got back** — something a blanket refusal could never do. `--skip-probe` bypasses it;
`--allow-nested` is kept as a deprecated alias so older commands still work.

A sweep whose every cell returns `UNMEASURED` for the same reason is an expensive way to learn
one fact. The probe costs one call.

**What "does not reproduce here" actually measured, corrected.** The banner a nested session
prints — `Failed to authenticate: OAuth session expired and could not be refreshed` — reads as a
nesting problem. It is not one. The measured cause, reproduced with a bare logged-out CLI outside
any nested session, is simply **not being logged in**. `subrun.py`'s own preflight (below) asks
`claude auth status` before ever invoking `-p`, specifically so this stops being inferred from a
banner and starts being asked directly.

## Top-level keys

| key | type | required | default | meaning |
|---|---|---|---|---|
| `cases` | object[] | yes | — | `{id, prompt, expect_exit?}`. Unique ids |
| `models` | string[] | yes | — | alias or full name, passed per cell as `--model` |
| `plugin_states` | object[] | yes | — | `{id, plugin_dir}` — string, list of strings, or `null` for the plugin-absent arm |
| `repeats` | int | no | `1` | identical cells per combination. **This is the swarm shape**: `1×1×1×N` is N independent candidates |
| `ablation` | string | no | `isolated` | `isolated` or `installed` — see below |
| `expected_tools` | string[] | no | `["Skill","ToolSearch"]` | post-hoc assertion; a cell reaching outside this is `UNMEASURED` |
| `permission_mode` | string | no | `plan` | |
| `timeout_s` | int | no | `900` | per cell |
| `output_format` | string | no | `json` | |
| `strict_mcp_config` | bool | no | `true` | |
| `disallowed_tools` | string[] | no | built-in list | see the trap below |
| `runner` | string | no | *(unset)* | opt-in; only `"subrun"` is accepted. Unset means the matrix is byte-identical to before this key existed |
| `transcript` | bool | no | `false` | opt-in; requires `runner: "subrun"`. See [the subrun runner](#the-subrun-runner-a-thin-per-cell-executor) |
| `max_budget_usd` | number | no | *(unset)* | opt-in; requires `runner: "subrun"`. Passed through as `--max-budget-usd` |
| `cases[].fixture` | string | no | *(unset)* | opt-in; requires `runner: "subrun"`. A directory copied into the cell's temp dir before it runs |
| `cases[].expect_skills` | string[] | no | `[]` | opt-in; requires `runner: "subrun"`. Every name must appear in `skills_fired` or the cell is `FAIL` |
| `cases[].forbid_skills` | string[] | no | `[]` | opt-in; requires `runner: "subrun"`. Any name appearing in `skills_fired` makes the cell `FAIL` |

## `ablation` — two modes that answer different questions

Neither replaces the other:

| mode | question | mechanism |
|---|---|---|
| `isolated` | does the plugin's description fire **at all**, with no competitor? | empty temp cwd + `--setting-sources project` + `--strict-mcp-config`, `--plugin-dir` on the enabled arm only |
| `installed` | does it win in the environment **users actually have**? | the real installation, untouched |

*"A case that fails the first and passes the second is a routing loss, not a description gap"* — and
that distinction is the whole reason both exist. The matrix declares which; the runner never picks.

`isolated` mutates nothing global, so cells are safe to run concurrently and a crash leaves no
residue. It is the default for that reason.

## The trap: `--allowedTools` does not restrict anything

`--allowedTools` is a **permission** allowlist — it names the tools that need no approval prompt. It
does **not** reduce the tool surface. `--disallowedTools` is the flag that restricts.

This was measured the expensive way elsewhere: a single `--allowedTools Skill` invocation ran `pwd`,
`ls` and three `find`s — one reaching outside its working directory — before firing anything, and
left orphaned processes to kill by hand. `run_matrix.sh` passes `--disallowedTools`, never
`--allowedTools`, and a matrix that tries to set `allowed_tools` is **rejected** with that
explanation rather than being quietly honoured.

## Denying is best-effort; the assertion is the gate

The disallow list *will* go stale — a new tool ships and no one updates it. That is not a flaw to be
fixed by curating harder, which is why `expected_tools` exists: after a cell runs, the tools it
actually used are checked against that allowlist. A cell that reached outside it is **`UNMEASURED`,
never `FAIL`** — because the case was never fairly measured.

## The `subrun` runner: a thin per-cell executor

`runner: "subrun"` is the only opt-in that changes what actually happens to a cell. Everything
above this line — argv assembly, the `cases × models × plugin_states × repeats` loop, the
`--plugin-dir` resolution, `--dry-run`, the summary — stays in this script, unchanged, whether or
not `runner` is set. A matrix that never sets it produces **byte-identical argv** to before this
runner existed; `run_matrix.sh --selftest` asserts this directly (`legacy argv unchanged`).

What `runner: "subrun"` hands to `scripts/subrun.py` is ONE cell's already-built argv plus a small
config, and gets back a scored cell — the same shape (`case`, `model`, `plugin_state`, `outcome`,
`stdout_sha256`, ...) the legacy path already writes, so the summary generator does not know or
care which path produced a row. `subrun.py` owns exactly six things a single cell needs, and
nothing about the sweep:

1. **Auth preflight.** `claude auth status` (JSON: `loggedIn`/`authMethod`) before ever invoking
   `-p`. `loggedIn: false` is reported as *"not logged in -- run `claude auth login`"* and exits
   3 — never inferred from the `OAuth session expired` banner text, which is what a logged-out
   CLI actually prints and which reads like a nesting failure it is not.
2. **Clean box.** A per-cell settings JSON — `enabledPlugins: false` for every installed plugin,
   `skillOverrides: "off"` for every personal skill under `~/.claude/skills` — passed via
   `--settings` alongside `--setting-sources project` and `--strict-mcp-config`, for every cell
   whose ablation is `isolated`. Modeled on, and deliberately not importing,
   `test/plugins/make-clean-box.py`: this plugin stays standalone.
3. **Isolation self-check.** One sentinel `claude -p` call per arm, asking the model to list every
   Skill it can invoke. A name the arm's `--plugin-dir` set cannot supply makes the cell
   `UNMEASURED` with that name in the reason — this *is* the matrix's own verify-clean-box, run
   automatically rather than by hand before each sweep.
4. **Fixture seeding.** `cases[].fixture` is copied into the cell's own temp dir, `git init` +
   committed as a baseline, then the cell runs there. `git diff` afterward is the cell's diff
   evidence, written to the scored cell JSON's `"diff"` key. A fixture that does not exist on disk
   is a refusal (exit 2, no summary) — the same invariant as a missing `plugin_dir`.
5. **Transcript parsing.** `transcript: true` swaps the cell to
   `--output-format stream-json --verbose --include-hook-events --no-session-persistence` (plus
   `--max-budget-usd` when `max_budget_usd` is set) and parses `skills_fired` (ORDER preserved,
   never sorted), `hook_denials`, `cost_usd`, and the final text — real per-line JSON, not a regex
   over raw bytes.
6. **`score_cell()`.** `PASS` / `FAIL` / `UNMEASURED` from `expect_skills` / `forbid_skills` /
   exit code, in that priority: a sentinel reason or an unmeasurable transcript short-circuits to
   `UNMEASURED` before either skill list is even consulted. `UNMEASURED` is excluded from every
   denominator here exactly as it is everywhere else in this document.

Run `python3 plugins/arbeitsplan/scripts/subrun.py --selftest` on its own to exercise steps 1–6
in isolation (pure Python, stub CLIs, no real `claude` binary reached); `run_matrix.sh --selftest`
calls it as one of its own checks, plus five further end-to-end cases against a stub `claude`
covering the auth/clean-box/sentinel/fixture behaviors above.

## The five outcomes

| outcome | meaning |
|---|---|
| `PASS` | the cell ran cleanly and matched `expect_exit` |
| `FAIL` | the cell ran cleanly and did not |
| `FALSE_POSITIVE` | the plugin-absent arm behaved as though the plugin were present |
| `UNMEASURED` | the cell never ran fairly — auth failure, timeout, empty output, a tool outside `expected_tools` |
| `UNSTABLE` | `repeats` of one combination disagreed |

**`UNMEASURED` is excluded from every denominator.** It is not a rejection, and it never triggers a
retry. This is the same rule as `test/plugins/run.sh`'s `ERROR` ("a case whose error count is above
zero has no rate, only missing data") and matrize's `readable: false`; three independent derivations
in this codebase, which is why it is an invariant here rather than a convention.

`UNSTABLE` is a **finding, not a retry trigger**. Repeats disagreeing means the prompt is
underdetermined; the answer is a better prompt, not more repeats.

## Worked instance

```json
{
  "cases": [
    { "id": "ratelimit", "prompt": "add a rate limit to the public search endpoint", "expect_exit": 0 }
  ],
  "models": ["sonnet"],
  "plugin_states": [
    { "id": "with",    "plugin_dir": "plugins/arbeitsplan" },
    { "id": "without", "plugin_dir": null }
  ],
  "repeats": 3,
  "ablation": "isolated",
  "expected_tools": ["Skill", "ToolSearch"],
  "permission_mode": "plan",
  "timeout_s": 600
}
```

That is 1 × 1 × 2 × 3 = **6 cells**: three independent candidates per arm.

## Output

`<out>/summary.json` plus one `<out>/cells/<case>__<model>__<state>__<n>.json` per cell, each
recording `argv`, `exit`, `duration_s`, `stdout_sha256`, `tools_used`, and `outcome`. The stdout
hash is what the divergence table is built from — identical hashes across repeats is the cheapest
possible stability signal.
