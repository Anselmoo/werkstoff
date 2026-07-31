# werkstoff

Personal Claude Code plugin workshop. `.claude-plugin/marketplace.json` at root.

## Layout

`plugins/<name>/` — six plugins: `andon`, `cli-scaffold`, `compass`, `confab`,
`cupertino`, `self-assess`. Each is independently versioned; `marketplace.json`
and `.rrt.toml` both point here.

All six were regenerated from behavior specifications rather than hand-edited —
see `docs/plugin-rebuild-findings.md` for what that measured, including which
rebuilds gained enforcement and which lost rules.

## Use the MCPs — they are faster and more accurate than grep

**serena** (connected) — symbol-level navigation. Prefer it over grep whenever
the question is about code structure:
- `find_symbol` / `get_symbols_overview` — locate a function without reading files
- `find_referencing_symbols` — "who actually calls this guard?" This repo has
  been burned repeatedly by guards that exist and are never called; a grep for
  the name finds prose mentions, `find_referencing_symbols` finds call sites.
- `replace_symbol_body` — edit one function without rewriting a file

**mcp-server-analyzer** (connected) — `ruff-check`, `ty-check`, `biome-check`,
`vulture-scan`. Free static verification of the Python tooling under `tools/`.

**rrt** (global) — `rrt_version_overview`,
`rrt_doctor_dashboard`, `rrt_locks_overview`. Useful for the seven-version-group
setup below. Note the binary is `rrt-mcp`; there is no `rrt mcp` subcommand, so
`rrt --help` will not mention MCP.

**context7** — for any library/CLI question including rrt's own command surface
(`/anselmoo/repo-release-tools`). Do not answer from memory.

## Think before deciding — this repo punishes assumption

Six defects in one session all had the same shape: **code that looks correct and
silently does nothing.** None raised an error.

| defect | how it hid |
|---|---|
| `[^.]{0,80}` in a regex | cannot span `report/build.py` — filenames contain dots |
| `[^\n]` in a bracket expression | means "not backslash, not the letter **n**" |
| `\b!==\b` | no word character is adjacent to `!` |
| `Path.glob()` on an unreadable dir | swallows `PermissionError` → "nothing found" |
| hook JSON without `hookEventName` | runtime discards the decision; hook runs, is ignored |
| `PROMPT % (...)` with a literal `%` in the text | `TypeError`; stale output then read as a fresh result |

Consequences that follow, and are not optional here:

- **A failed run leaves the previous output in place.** Re-running a check
  after a failed generation measures the *old* files. Always confirm the thing
  you are grading was actually produced by the run you think produced it.
- **Verify the instrument before trusting its verdict.** Every tool here
  asserts itself: the enforcement auditor is hand-checked against three known
  answers, oracles are calibrated against fabricated transcripts before first
  use, `lint-oracles.sh` bans the regex forms that fail silently.
- **A tally cannot tell a real pass from a lucky one.** Read the transcript of
  any single-pass result before believing it.

## Verifying plugin changes

**Static (instant, free) — run all of these on every change:**

```bash
python3 test/plugins/lint-frontmatter.py plugins/<name>   # YAML that would load with EMPTY metadata
claude plugin validate plugins/<name> --strict            # manifest + structure
python3 tools/enforcement-audit/audit_enforcement.py --rules analysis/rebuild/<name>.behavior.json plugins/<name>
bash test/plugins/lint-oracles.sh                         # silent-failure regex forms in cases.tsv
node --check plugins/<name>/workflows/<file>.js
rrt docs inject --check                                   # README shared blocks (see below) haven't drifted
rrt artifacts --check --strict                            # vendored files (build_symbol_index.py, lib/ canaries) match their lock
```

`rrt artifacts --check` matters for the same reason as everything else in
this section: it's the only thing that would have caught issue #24 on the
next fresh checkout. `plugins/{self-assess,confab}/scripts/lib/` -- real,
hand-written source packages, not build output -- were silently excluded
from every commit by an unanchored `lib/` line in the root `.gitignore`
(same failure shape as `/analysis/`'s existing anchoring comment already
warns about), invisible to `git status` on any machine that already had
the uncommitted files sitting locally. Every plugin with a `scripts/lib/`
package now vendors a canary `README.md` there via `.rrt.toml`'s
`artifact_targets` (`tools/plugin-lib-canary/README.md`); add a matching
entry when a new plugin gains one of its own.

`lint-frontmatter.py` matters more than it looks: frontmatter that fails to
parse still **loads, with no description and no tools**, so the skill never
triggers and nothing reports an error.

Every plugin README's `## Example Prompts` heading and framing sentence is a
`[[tool.rrt.docs.shared_blocks]]` entry in `.rrt.toml` (`anchor_id =
"example-prompts-intro"`), injected into the `<!-- rrt:auto:start:... -->` /
`<!-- rrt:auto:end:... -->` markers by `rrt docs inject` — only that frame is
enforced identical across the six; the example bullets below each anchor stay
plugin-specific and hand-written. Never hand-edit text between those markers —
the next `rrt docs inject` overwrites it silently.

**Behavioral (`test/plugins/`, 3–4 min per run, real tokens):**

```bash
bash test/plugins/verify-clean-box.sh          # ALWAYS first — see below
bash test/plugins/run.sh <case-id>
N=5 bash test/plugins/determinism.sh <case-id> # a pass rate, not a verdict
```

- **The clean box is mandatory.** `--plugin-dir X` *adds* a plugin; it removes
  nothing already installed. Without `make-clean-box.py`'s settings, 33
  installed plugins and 43 personal skills leak into every "isolated" run —
  including a copy of the plugin under test, which will pass cases its own
  source cannot satisfy.
- **`ERROR` ≠ `FAIL`.** A rate-limit banner, empty stdout, or a sub-200-byte
  reply means the run never happened. `run.sh` scores these separately; a case
  with any errors has no rate, only missing data.
- Fixtures live in `test/plugins/fixtures/` (arm-independent — deliberately
  *not* under any plugin, so moving a plugin does not break the tests).
- Cases are `test/plugins/cases.tsv`. `regex` may be several patterns joined by
  `@@AND@@` (all must match); an optional 7th column is a must-NOT-match.
- **Never retune an oracle after the thing it grades exists.** Calibrate against
  fabricated transcripts first.

## Rebuild pipeline (`tools/plugin-serializer/`)

```
<source plugin>/ --[haiku]--> <p>.behavior.json   obligations only, no source wording
                 --[python]-> <p>.inventory.json  ids+counts, GATE INPUT ONLY
                 --[sonnet]-> plugins/<p>/        via /plugin-dev:create-plugin
```

Specs for the current six are in `analysis/rebuild/*.behavior.json` — they are
what the enforcement audit grades against, so a rule missing from a spec is a
rule no gate will look for.

- The inventory is computed from the filesystem, never by an LLM, and is
  withheld from the generator — otherwise the same model could drop a skill in
  both the rebuild and the checklist and the gate would pass it.
- **sonnet is sufficient.** Its only failures were YAML frontmatter traps, now
  named in the generator prompt and verified. opus bought nothing.
- Artifacts land in `analysis/rebuild/` (gitignored).

## Enforcement: only hooks actually enforce

Measured over ~40 runs, asking "does the guard *run*", not "does it exist":

| layer | invocation |
|---|---|
| prose in a SKILL.md | baseline |
| a fenced `python3 ...` command in a skill | 1 run in 3 |
| a guard inside the Workflow script | workflow dispatched 1 run in 14 |
| **PreToolUse hook, `type: "command"`** | **blocks, first attempt** |

So a rule that must hold regardless of model cooperation belongs in
`hooks/hooks.json`. `plugins/andon/hooks/andon_enforce.py` is the reference.
Non-negotiables: `type: "command"` (a `"prompt"` hook asks a model to decide);
deny must emit **both** exit 2 with the reason on stderr **and** stdout JSON
with `hookEventName` + `permissionDecisionReason`; the hook must be inert unless
the repo actually uses the plugin; fail **closed** with a named escape hatch.

This only helps plugins whose rules gate *actions*. `compass` and `cupertino`
are advisory — there is no tool call to deny for "explore branches before
scoring" — which is why their rebuilds gained nothing.

## Git & release

Prefer `rrt` over raw git for repo-level operations; check context7
(`/anselmoo/repo-release-tools`) for its current surface rather than memory.

Seven independent version groups in `.rrt.toml` (6 plugins + `tools/werkstoff-cli`).
There is **no aggregate werkstoff version** — this is deliberate.

```bash
rrt bump <major|minor|patch> --group <name>          # requires rrt >= 1.13.1
rrt tag create --group <name> --prefix '<name>-v' --push   # plugins
rrt tag create --group werkstoff-cli --push                # ONLY this one uses bare v<version>
```

**Never tag a plugin group without `--prefix`.** `.github/workflows/cicd.yml`
fires on any `v*.*.*` tag and always publishes `tools/werkstoff-cli` regardless
of intent, so a bare tag on a plugin triggers a spurious PyPI publish.
`<group>-v...` tags instead fire `plugin-release.yml` (a scoped GitHub Release).

Branch names must follow rrt's conventional format, `<type>/[<scope>-]<kebab-case-description>`
(e.g. `feat/rrt-branch-naming`, `fix/api-timeout`) — use `rrt branch new <type>
"<description>"` (or `rrt branch rename`) rather than naming branches by hand.
This is enforced twice: locally via the `rrt-branch-name` pre-commit hook
(`.pre-commit-config.yaml`), and in CI via the "Validate branch name" step in
`.github/workflows/plugin-checks.yml`, which runs `rrt-hooks check-branch-name`
against the PR's head branch on every pull request.

## Gotchas

- **Workflow scripts have no filesystem access.** Anything a workflow needs
  (settings, file lists, ledger state) must arrive via `args` from the calling
  `SKILL.md`.
- **A guard predicated on its own input existing is not a guard.**
  `if (gap.blastRadius) assertWithinAuthorization(...)` skips exactly when the
  field is missing — the case it was written for.
- **Never infer a missing gating value.** Reject and surface it. A halt that
  depends on a value the code invented is not a halt.
- **The rebuilt andon ledger schema is not backward compatible.** It wants
  `(type, id, stage, status, kind)` as frontmatter keys; every real ledger,
  including 101 production records, encodes them in `tags: ["kind:wire", ...]`.
  Read tolerantly: frontmatter key, then the tags array, then absent.
- `self-assess` models itself on `anthropics/claude-plugins-official`'s
  `code-modernization`. Check that plugin's actual source before extending, not
  its description — a prior pass found the docs claimed more mirroring than the
  code did.
