# `matrix.json` — the headless sweep

The input to `scripts/run_matrix.sh`. One fresh `claude -p` process per cell, over the
cartesian product of `cases × models × plugin_states × repeats`.

Kept deliberately close to `quo-warranto`'s `tools/run_matrix.py` schema so results from the two
stay comparable. arbeitsplan adds exactly three keys: `repeats`, `ablation`, `expected_tools`.

**Contents** — [why a skill cannot run this](#why-a-skill-can-never-run-this) · [top-level keys](#top-level-keys) · [ablation](#ablation--two-modes-that-answer-different-questions) · [the allowedTools trap](#the-trap---allowedtools-does-not-restrict-anything) · [the five outcomes](#the-five-outcomes) · [worked instance](#worked-instance) · [output](#output)

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
