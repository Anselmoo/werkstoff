# Design table schema (`design/1`)

The contract for `design.json`: the node-by-node design `arbeitsplan-design` builds before
anything runs (#107), and the plan table `arbeitsplan-waves` installs and executes when its
nodes carry `wave` (#106). `scripts/design_spec.py` is the validator, and
`compile_spec.py --design` runs it. Each rule below says what that script does, not what it
would be nice to do.

**Contents** — [why a design table](#why-a-design-table) · [top level](#top-level) ·
[nodes](#nodes) · [commands and toolchains](#commands-and-toolchains) · [waves](#waves) ·
[rejections](#rejections) · [worked instance](#worked-instance)

## Why a design table

Each node answers four questions before it runs:

- **what** it does (`goal`, `output_schema`);
- **where** it runs (`primary`, `worktree` or `scratch`);
- **when** it runs (`depends_on`, and a human gate *between* runs);
- **how** it runs (`kind`, `model`, `agentType`, `writeScope`, the declared commands).

A hand-written multi-wave prototype made all four decisions ad hoc, in prose. Three of the
bugs found afterwards came from that: a wrong worktree base, state passed as a JSON string,
and a gate that ran where untracked files exist.

**Language-neutral by construction.** Both issues were written after observing one project,
and nothing here assumes its ecosystem. Every command the design runs names a
[toolchain](#commands-and-toolchains). Gates and smoke steps are declared by the design, not
supplied by a default.

## Top level

| key | rule |
|---|---|
| `schemaVersion` | `"design/1"` |
| `name` | `[a-z][a-z0-9-]{0,39}` — it names every generated file |
| `runId` | a path component, as in `workflow.json` |
| `problemRef` | the path of the approved problem statement |
| `offLimits` | globs no generated agent may edit; **empty is allowed, absent is not** |
| `toolchains` | optional; extends or overrides the built-in toolchains |
| `budget` | optional `{totalDispatches}`. **Absent means no cap** (#106 R9): subscription limits stop the run, and resume makes that cheap |
| `integration` | wave designs only: `{branch, target, preflight}`. Neither branch is inferred, because `main` is a convention, not a fact about the repository |
| `gates` | wave designs only: `[{id, runtime, command}]`, run by every final merge-gate |
| `nodes` | the design |

## Nodes

| key | rule |
|---|---|
| `id`, `goal`, `depends_on` | what the node does, and the graph. A cycle or an unknown id is rejected |
| `kind` | `agent` · `script` (a fixed command) · `referee` (blind) · `merge-gate` (merge, then gate) · `human-gate` (**between** runs only: a Workflow run cannot pause for input) |
| `where` | `primary` · `worktree` · `scratch`. Never inherited from the session's cwd |
| `model`, `effort` | `model` is **explicit on every dispatched node**: an alias (`haiku`, `sonnet`, `opus`, `fable`) or a full `claude-...` id. A script node gets the smallest model only when the design says so |
| `agentType`, `skills`, `tools`, `role` | the agent definition; `role` is one of `builder`, `referee`, `merger`, `integrator`, `smoke`, `reviewer`, `fixer`, `runner` |
| `writeScope` | globs this node owns. Present on every dispatched node (`[]` means it writes nothing), and non-empty on a worktree agent |
| `inputs` | **ids and paths only**, never a sibling's content (#106 R8) |
| `output_schema` | type `object`, **strict**: `additionalProperties: false` at every object level, and no JSON-in-a-string field |
| `script` | script and merge-gate nodes: `{runtime, command, expectExit[], parse?}` |
| `acceptance`, `setup` | `[{runtime, command}]`; each must exit 0 |
| `when` | `{node, field, equals}` over a node this one depends on (the fix round runs only on a blocking review) |
| `retries` | int 0..3 |

## Commands and toolchains

Every command is a declared step, `{runtime, command}`, and each `runtime` names a toolchain.
That covers a script node's `script`, a row's `acceptance` and `setup`, a wave `gate`, and a
smoke node's `steps`.

A toolchain is `{executables[], version}`. The executables are fnmatch patterns, matched
against the command's argv[0] basename, so `.venv/bin/python`, `python3.12` and `./gradlew`
resolve without special cases. `version` is the one probe `arbeitsplan-preflight` runs, and
**exit 0 is the whole test**: `go version` and `java -version` share no output convention.

The built-in set is a starting set, not a whitelist. It covers these toolchains:

| family | toolchains |
|---|---|
| shells | `shell`, `powershell`, `cmd` |
| Python | `python`, `uv`, `poetry` |
| JavaScript | `node`, `deno`, `bun` |
| compiled | `go`, `rust`, `haskell`, `java`, `kotlin`, `scala`, `dotnet`, `swift`, `zig`, `c-cpp` |
| other languages | `ruby`, `julia`, `r`, `elixir`, `erlang`, `ocaml`, `perl`, `php`, `lua`, `dart` |
| build and environment tools | `make`, `cmake`, `bazel`, `nix`, `docker` |

Anything else is declared by the design itself:

```json
"toolchains": {"gleam": {"executables": ["gleam"], "version": "gleam --version"}}
```

**One command, not a chain.** An unquoted `;`, `|`, `&`, backtick, `$(` or newline is refused
(`AP-SCRIPT-NO-COMMAND`). That includes `2>&1`: redirect inside the script instead. Quoted text
is inert, so `julia -e 'using Pkg; Pkg.test()'` is one command. The runner guard matches the
rendered command **exactly**. A `{placeholder}` slot takes only `[A-Za-z0-9._/,=:@+-]`, so a
value can never become a second command.

**How a script node executes.** A Workflow script cannot exec anything, so a script node
compiles to one runner dispatch:

1. The runner is a small model whose only tool is `Bash`.
2. Its guard allows exactly the declared command, once per dispatch.
3. It returns `{exit, stdout_digest, parsed}`.
4. The interpreter checks `exit` against `expectExit`, then validates `parsed` against the
   node's `output_schema`. Either failure halts with `SCRIPT CONTRACT`.

This is the narrow form of a script-applied phase that ADR 0001 accepted for #83.

## Waves

A design whose nodes carry `wave` is a multi-wave plan. On top of the node rules above, it
must meet each of the following.

**Wave structure**

- Waves are numbered `1..N`.
- Each wave has at least one agent row and **exactly one merge-gate**, which comes after every
  row of its wave (`AP-WAVE-NO-GATE`).

**Rows**

- Each row runs `where: worktree`.
- A row's `output_schema` requires `branch` and `baseSha`.
- A wave `n > 1` row comes after the wave `n-1` merge-gate (`AP-WAVE-NO-BASE`). Its worktree
  starts with `git merge --ff-only <wave base>`, and the interpreter halts when the returned
  `baseSha` differs.
- **Concurrent rows own disjoint files** (`AP-WAVE-SCOPE-OVERLAP`). "Concurrent" means neither
  depends on the other. The check is `land_candidate.scope_overlap`: conservative and
  case-folded, it may call a disjoint pair overlapping but never the reverse.
- A row that depends on other rows of its wave, the **integrator**, may own the shared files
  most ecosystems edit per new module: `lib.rs`, a `.cabal` or `.csproj`, `CMakeLists.txt`, a
  barrel `index.ts`, and lockfiles. It runs as a second **stage**, on the merge of the first.
- A swarm row (`swarm: N`) needs `acceptance` steps and a `referee {model, agentType}`
  (`AP-SWARM-INCOMPLETE`).

**Gates**

- `integration.preflight` names a script node that runs before every wave. Its output requires
  `linkedWorktree`, `dirty` and `head`.
- A merge-gate runs `where: primary` (`AP-GATE-NOT-PRIMARY`).
- Its command takes `{wave}`, `{stage}`, `{final}`, `{branches}` and `{discard}`.
- Its output requires `green`, `integrationSha`, `targetMoved`, `findings` and `kept`.
- `gates` are declared (`AP-GATES-UNDECLARED`).

**After the waves**

- A node outside the waves runs before them all or after the last merge-gate
  (`AP-WAVE-ORDER`).
- A smoke node runs `where: scratch` (`AP-SMOKE-NOT-SCRATCH`). It declares its own `steps` —
  build, install, run, whatever this artefact needs — or a `skip` with its reason
  (`AP-SMOKE-UNDECLARED`).

**The placeholders the interpreter fills:** `name`, `runId`, `wave`, `stage`, `final`,
`branches`, `discard`, `base`, `integration` and `target`. A slot outside that set is refused.

## Rejections

Every tagged rule has a committed red fixture under `scripts/fixtures/red/*.design.json`,
listed in `MANIFEST.json` with args `["--design"]` and proved by `test_red_fixtures.py`. Each
fixture fails for its own id and no other. The rules are not *recorded-red*: no baseline
ever compiled a design, so `--baseline` skips them.

| id | issue | rejects |
|---|---|---|
| `AP-NODE-NO-MODEL` | 107 | a dispatched node without a valid model |
| `AP-NODE-NO-SCHEMA` | 107 | a dispatched node without an object `output_schema` |
| `AP-NODE-NO-SCOPE` | 107 | a dispatched node without `writeScope`, or a worktree agent with an empty one |
| `AP-SCHEMA-NOT-STRICT` | 106 | a missing `additionalProperties: false`, or JSON-in-a-string |
| `AP-SCRIPT-NO-RUNTIME` | 107 | a step whose runtime names no toolchain |
| `AP-SCRIPT-NO-COMMAND` | 107 | a missing command, a chained one, or a script without `expectExit` |
| `AP-SCRIPT-RUNTIME-MISMATCH` | 107 | a command whose argv[0] is not the toolchain's |
| `AP-WAVE-SCOPE-OVERLAP` | 107 | concurrent rows that may write the same file |
| `AP-INPUT-CONTENT` | 106 | an input that is content rather than an id or path |
| `AP-HUMAN-GATE-INSIDE` | 107 | a human gate that does not cut the graph in two |
| `AP-DEPENDS-UNKNOWN`, `AP-DEPENDS-CYCLE` | 107 | a dependency on nothing, or a cycle |
| `AP-WAVE-NO-GATE`, `AP-WAVE-NO-BASE`, `AP-WAVE-ORDER` | 106 | the wave structure above |
| `AP-GATES-UNDECLARED` | 106 | a wave design with no declared gates |
| `AP-SWARM-INCOMPLETE` | 106 | a swarm row without acceptance steps or a referee |
| `AP-GATE-NOT-PRIMARY`, `AP-SMOKE-NOT-SCRATCH`, `AP-SMOKE-UNDECLARED` | 106 | where a gate and a smoke node run, and what smoke runs |

Shape errors are untagged, like `compile_spec.py`'s own. They cover a bad `name`, an unknown
`kind`, a missing `goal` or `where`, an agent without `agentType`, a missing `integration`, and
the interpreter-contract checks. `design_spec.py --selftest` plants each one.

## Worked instance

`scripts/fixtures/design/waves.design.json` is a two-wave Go design:

1. A preflight.
2. Two concurrent rows, `internal/parse/**` and `internal/render/**`.
3. The wave-1 merge-gate.
4. A wave-2 row on `cmd/tool/**`.
5. The wave-2 merge-gate.
6. Smoke steps `go build` and `go run`.
7. A review, and a fix round conditional on a blocking review.

`scripts/fixtures/design/integrator.design.json` is a Rust design:

- two rows;
- an integrator that owns `src/lib.rs`, `Cargo.toml` and `Cargo.lock`;
- a swarm row with a blind referee;
- a smoke node that declares `skip` (a library crate has nothing to run).

A single row, abbreviated:

```json
{
  "id": "w1-parse", "kind": "agent", "role": "builder", "wave": 1,
  "goal": "Move argument parsing into internal/parse behind the existing public entry point",
  "depends_on": ["preflight"], "where": "worktree", "model": "opus", "effort": "high",
  "agentType": "rebuild-cli-builder", "inputs": ["preflight"],
  "writeScope": ["internal/parse/**"],
  "setup": [{"runtime": "go", "command": "go mod download"}],
  "acceptance": [{"runtime": "go", "command": "go test ./internal/parse/..."}],
  "output_schema": {"type": "object", "additionalProperties": false,
    "required": ["branch", "baseSha", "notes"],
    "properties": {"branch": {"type": "string"}, "baseSha": {"type": "string"},
                   "notes": {"type": "array", "items": {"type": "string"}}}}
}
```
