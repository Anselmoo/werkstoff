# Rebuilding six plugins from behavior specs — what was measured

Supersedes the enforcement conclusions in `docs/andon-pilot-findings.md`, which
were drawn before the hook layer was tested and are wrong in one important way
(see §2).

## 1. The pipeline

```
legacy_plugins/<p>/  --[haiku]-->  <p>.behavior.json   (obligations, no legacy wording)
                     --[python]->  <p>.inventory.json  (ids + counts, gate input ONLY)
                     --[sonnet]->  plugins/<p>/        (via /plugin-dev:create-plugin)
                     --[static]->  gates 0-3, instant
```

The inventory is computed from the filesystem, never by an LLM, and is withheld
from the generator. If the same model wrote the inventory and the rebuild, a
dropped skill could be matched by the same omission in both and the gate would
pass a plugin that silently lost a capability.

Behavior JSON carries obligations, not implementations: verbatim 8-gram overlap
with legacy is 2.3% (andon) and 4.0% (cli-scaffold), and the residue is
unavoidable domain phrasing.

## 2. The enforcement ladder — measured, not argued

Roughly 40 runs across four layers, asking not "does the guard exist" but "does
it run":

| layer | invocation |
|---|---|
| rule as prose in a SKILL.md | baseline |
| rule as code that raises | 19 rules enforced; behavior moved 1 case in 5 |
| guard behind a fenced `python3` block | invoked **1 run in 3** |
| guard inside the Workflow script | workflow dispatched **1 run in 14** |
| **PreToolUse hook (`type: "command"`)** | **blocked on the first attempt** |

Each layer is deterministic *once entered*, and entering it is a sentence the
model chooses to follow. Moving a guard down a level moves the prose problem
down with it.

**The earlier conclusion "a plugin cannot enforce" was wrong.** Plugins ship
hooks; hooks are auto-discovered from `hooks/hooks.json`, and the runtime
invokes them unconditionally. Verified end-to-end in a fresh session on a tmp
worktree, with the plugin loaded only via `--plugin-dir`:

> The edit was blocked by an `andon` enforcement hook: it requires a
> human-supplied blast-radius classification for this change before it will
> allow source edits, and explicitly states this value must not be inferred.

The file was unchanged, and the run asked a human to classify rather than
guessing — closing the pilot's original open question (*is inferring a missing
blast-radius a silent data repair?*) structurally rather than by policy.

`type: "prompt"` hooks ask a model to decide, which is the model-mediated path
this replaces. Only `type: "command"` enforces.

## 3. Enforcement is only available to plugins that gate actions

| plugin | model | gates 0/1 | legacy → rebuilt (code/prose/absent) | keep |
|---|---|---|---|---|
| andon | opus | pass | `0/27/4` → **`20/10/1`** | rebuild |
| self-assess | sonnet | pass | `3/27/3` → **`18/10/5`** | rebuild |
| cli-scaffold | opus | pass | `0/19/12` → **`14/6/11`** | rebuild |
| confab | sonnet | pass | `4/13/2` → **`12/5/2`** | rebuild |
| compass | opus | pass | `1/44/4` → `1/37/11` | **legacy** |
| cupertino | sonnet | — | `0/19/1` → `0/12/8` | **legacy** |

The four that gained enforcement gate *operations* — advance past a wire, apply
a fix, write a record, exit with a code. As measured in this pass, compass and
cupertino were both treated as **advisory**: compass shapes reasoning, cupertino
shapes design judgment, and there is no tool call to deny when the rule is
"explore branches independently before scoring." That still holds for compass.
It no longer holds for cupertino, whose hand-edited legacy code — kept over the
rebuild — does register a real `type: "command"` PreToolUse hook; see `CLAUDE.md`'s
"Enforcement: only hooks actually enforce".

Opus could not raise compass either (1 → 1), which rules out model capability as
the explanation.

**Cost the green gates hide:** `absent` rose in both advisory rebuilds (4→11,
1→8) — rules from the plugin's own spec with no implementation. Gates 0, 1 and 3
all pass them, because every skill and agent is present. Only gate 2 sees
rule-level loss. Keeping legacy for those two avoids shipping a regression that
looks green.

## 4. Model tier: sonnet is sufficient

Both sonnet failures were one YAML trap, not capability:

```yaml
argument-hint: [repo-path] [--skip-verification]   # two flow sequences: INVALID
```

`[` opens a YAML flow sequence, so conventional CLI-usage notation collides with
it. A file whose frontmatter fails to parse still loads — **with empty metadata,
no description, no tools** — so the skill silently never triggers. This killed
8 of 8 confab skills and 3 compass agents.

Fixed in the generator prompt and **verified**: confab regenerated on sonnet,
gate 0 clean, gate 1 passed, `argument-hint: "[repo-path] [--skip-verification]"`
quoted as instructed, enforcement `4/13/2` → `12/5/2`, and it shipped a hook on
requirement 6's first outing.

Opus bought nothing the prompt fix does not.

## 5. Six silent failures — the real lesson

Every one looked like working code doing nothing:

| defect | how it hid |
|---|---|
| `[^.]{0,80}` in an oracle | cannot span `report/build.py` — filenames contain dots |
| `[^\n]` in a bracket expression | means "not backslash, not the letter **n**" |
| `\b!==\b` | no word character is adjacent to `!` |
| `Path.glob()` on an unreadable dir | swallows `PermissionError` → "nothing to enforce" |
| hook JSON without `hookEventName` | runtime discards the deny; the hook runs and is ignored |
| `PROMPT % (...)` with a literal `%` in the text | `TypeError`; the gate then ran on stale files and looked like the fix had failed |

Plus two at the harness level: rate-limit banners scored as clean FAILs (10
runs), and 33 installed plugins + 43 personal skills leaking into every "clean"
test run — caught only because Arm C passed a case by quoting a rule its own
source did not contain.

Hence the standing rule in this repo: **every instrument asserts itself.** The
enforcement auditor is hand-checked against three known answers; oracles are
calibrated against fabricated transcripts before first use;
`test/plugins/lint-oracles.sh` bans the regex constructs that fail silently;
`verify-clean-box.sh` proves isolation before a sweep spends tokens; hook tests
assert exit code *and* JSON shape.

## 6. Not done

- gate 4 (behavioral, clean box) has not run against the four keepers
- as originally written here (2026-07-27, commit `0c10fa0`) this bullet claimed
  the PreToolUse hook "exists only in `plugins/andon`" while granting in the same
  sentence that confab has one too, and further claimed self-assess had none —
  that second claim was already wrong the day it was written: the same commit
  also added `hooks/hooks.json` to `confab`, `cupertino`, and `self-assess`.
  Current inventory (checked 2026-09-03 via `ls plugins/*/hooks/hooks.json`):
  `andon`, `confab`, `cupertino`, `self-assess`, and `takt` each have one;
  `cli-scaffold`, `codebase-consistency`, and `compass` do not
- compass/cupertino rebuilds are retained under `plugins/` but should not be
  promoted over `legacy_plugins/` — moot as written: `legacy_plugins/` was since
  deleted (see the note below), and both plugins kept their hand-edited legacy
  code rather than being promoted

Done since: `.claude-plugin/marketplace.json` and `.rrt.toml` no longer point
at `legacy_plugins/` — both now source every plugin straight from
`plugins/<name>/` (confirmed 2026-09-03: `grep -n legacy_plugins
.claude-plugin/marketplace.json .rrt.toml` returns nothing). `legacy_plugins/`
itself no longer exists — it was deleted, per `test/plugins/cases.tsv`'s
retirement comment.
