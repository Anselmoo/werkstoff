# werkstoff

My personal Claude Code plugin workshop (`.claude-plugin/marketplace.json`
at root). Six plugins currently:

- `plugins/self-assess/` — docs-vs-code drift and stage/wire mapping for a live repo, plus a reporting→plan bridge (`self-assess-transform-brief` turns file:line findings into a prioritized, phased code-change plan with a per-phase behavior contract), a static UI/accessibility audit (`self-assess-ui-audit`), and a check→plan→fix→validate conductor (`self-assess-autopilot`).
- `plugins/confab/` — catches where AI-authored code confabulates (dependency-hallucination/assertion/contract-drift/agentic-reliability audits); its audit sidecars publish per-finding arrays the self-assess bridge ingests.
- `plugins/compass/` — prompt-engineering technique library + `compass-solve` orchestrator for complex/ambiguous tasks.
- `plugins/cupertino/` — Steve-Jobs-grounded design/craft discipline for a project's whole lifecycle.
- `plugins/andon/` — self-optimizing hardening loop over a project's value stream (services + wires); `andon-loop`'s ingest mode (`gap_source: self-assess-brief`) is the auto-pilot's fix+validate half, driving off self-assess's `MODERNIZATION_BRIEF.md`.
- `plugins/cli-scaffold/` — five-pillar CLI architecture doctrine + per-language scaffold generation.

See each plugin's own `README.md` for what it does in full.

**Cross-plugin auto-pilot (division of labor).** `self-assess-autopilot`
conducts check → plan → fix → validate without a new loop: self-assess owns
check+plan (all read-only audits, incl. confab's, → `transform-brief` →
`MODERNIZATION_BRIEF.md`), and `andon-loop` (ingest mode) owns fix+validate
(applies gated fixes via the Edit skills, proves each with `andon-verify`'s
`{wire, contract, fixDiff}` entry point). compass and cli-scaffold are
orthogonal to this stream.

## Spec-driven development convention

Non-trivial changes to a plugin go through `.superpowers/sdd/`, not ad hoc
edits:

- **Brief**: `.superpowers/sdd/<prefix>-task-N-brief.md` — written via the
  `superpowers:writing-plans` skill. `<prefix>` is short per work-stream
  (e.g. `sa-` for self-assess, `cf-` for confab, `c-` for compass). Format:
  Files / Scope / numbered checkbox Steps / manual-verify / commit.
- **Report**: `.superpowers/sdd/<prefix>-task-N-report.md` — written after
  a task completes (implementation notes, review outcome).
- **Log**: `.superpowers/sdd/progress.md` — one line per completed task,
  append-only, e.g. `Task 8: complete (commits abc..def, review clean - approved)`.

Read the existing `<prefix>-task-*-brief.md` files for a work-stream before
writing a new one — match their exact structure, don't reinvent it.
`.superpowers/sdd/` is untracked scratch, not committed to git.

## Verifying plugin changes

Plugin content is markdown/JS skill definitions, so verification has two tiers.

**Tier 1 — static checks** (fast, no API, run on every change):

```bash
node --check plugins/self-assess/workflows/<file>.js   # workflow scripts parse
python3 -c "import yaml; yaml.safe_load(open('plugins/self-assess/skills/<skill>/SKILL.md').read().split('---')[1])"  # SKILL.md frontmatter parses
```

For workflow post-processing logic (clustering, ranking, attribution), a quick
`node --input-type=module` script exercising the pure functions against
fixture data catches shape/logic bugs statically — but it can't confirm a skill
actually *triggers* or produces the right finding.

**Tier 2 — headless behavior tests** (`test/plugins/`): the harness that does.

Key constraint: **Claude Code builds its skill/agent registry once, at session
start.** A skill or agent you just authored is invisible until a reload — so it
cannot be exercised in the session that wrote it (you'll get "Unknown skill" /
"agent type not found"). Workflows are the exception (the Workflow tool reads
the `.js` from disk at call time), but anything routing to a **new agentType**
still needs a fresh process. So behavior testing must run in a fresh
`claude --print` process, which loads the plugin clean:

```bash
test/plugins/run.sh            # run all cases (each: fresh claude --plugin-dir vs a seeded fixture)
test/plugins/run.sh ui-audit   # one case by id
```

Each case in `test/plugins/cases.tsv` copies a **seeded-defect fixture** (under
`plugins/*/test-fixtures/`) into a temp cwd, runs one plugin against it via
`claude --plugin-dir plugins/<name> --print "<prompt>"`, and asserts the
produced artifact contains the finding the plugin is supposed to catch (a
golden oracle, not a fuzzy match). Needs the Claude Code CLI on PATH; costs
real tokens (spawns the skill's subagents), so it is not a Tier-1 check.

- **Scaffold a new case:** `/scaffold-plugin-test <plugin>/<skill>` (project
  slash command) or `test/plugins/scaffold-test.sh <id> <plugin> <fixture>` —
  creates the fixture skeleton + a `cases.tsv` row to complete.
- **"Does the change work better?" (A/B):** run the same case against the old
  plugin (a `git worktree` at the prior commit) and the new one; diff the
  outputs. Objective "better" = the new one catches a seeded defect the old
  missed, or emits a section the old couldn't.

## Git workflow

Prefer `rrt` (repo-release-tools, this user's own CLI — `/Users/hahn/.local/bin/rrt`)
over raw git for repo-level operations. Check context7 (`/anselmoo/repo-release-tools`)
for its current command surface rather than assuming from memory — it has many
subcommands beyond git (`bump`, `release`, `sync`, `doctor`, `drift`, `branch`, ...).

- **Reinitializing to a single "Initial commit"** (this repo's own established
  pattern, used twice): `rrt git rebootstrap --yes-i-know-this-destroys-history
  --allow-remote --branch main --message "<msg>"` — backs up the old `.git`
  (moved aside, not deleted) before reinitializing, unlike a manual `rm -rf .git
  && git init`. Still requires a manual `git push` (`--force` if history was
  actually rewritten) afterward — rebootstrap doesn't push.
- For an ordinary incremental fix (untracking a file, adding a `.gitignore`,
  etc.) on top of existing history, use plain `git add`/`commit`/`push` — don't
  reach for `rebootstrap` unless history genuinely needs to be destroyed again.

### Plugin versioning (`.rrt.toml`)

Each plugin has its own independently-versioned
`plugins/<name>/.claude-plugin/plugin.json` + `plugins/<name>/CHANGELOG.md`,
wired up as a separate `rrt` version group in `.rrt.toml` (`self-assess`,
`confab`, `compass`, `cupertino`, `andon`, `cli-scaffold`). The
`tools/werkstoff-cli` installer tool is wired up the same way, but targets
its own `pyproject.toml` (`kind = "pep621"`) + `tools/werkstoff-cli/CHANGELOG.md`
instead of a `plugin.json`. Bump one group's version with:

```bash
rrt bump <major|minor|patch> --group <group-name>
```

Requires **rrt >= 1.13.1** — anything older fails with "Multiple version
groups configured" on a valid `--group` (fixed in
[anselmoo/repo-release-tools#176](https://github.com/Anselmoo/repo-release-tools/pull/176),
reported as [#175](https://github.com/Anselmoo/repo-release-tools/issues/175)).

### Tagging & publishing

`.github/workflows/cicd.yml` triggers a full build → TestPyPI → verify →
PyPI-publish → GitHub-release pipeline on **any** pushed tag matching
`v*.*.*`, and that pipeline always operates on `tools/werkstoff-cli`
(hardcoded `working-directory`/`PACKAGE_DIR`) regardless of what the tag was
actually for — it has no concept of `.rrt.toml`'s version groups. `rrt tag
create` defaults to a bare `v<version>` tag with no group name embedded, and
rrt has no per-group tag-prefix config field (confirmed against the
`repo-release-tools` docs — this is genuinely unsupported, not just unused
here). So tag naming has to carry the distinction by convention:

- **Plugins** tag as `<group>-v<version>`, e.g. `confab-v0.1.0`:
  `rrt tag create --group <name> --prefix '<name>-v' --push`. GitHub's tag
  trigger glob is prefix-anchored, so a `<group>-v...` tag never matches
  `v*.*.*` and never fires the werkstoff-cli publish pipeline.
- **`werkstoff-cli`** is the only group that uses the bare `v<version>`
  scheme (`rrt tag create --group werkstoff-cli --push`), since that's the
  one tag pattern `cicd.yml` actually reacts to.

Never `rrt tag create` a plugin group without `--prefix`, or its default
`v<version>` tag will collide with werkstoff-cli's namespace and spuriously
trigger a PyPI publish.

## Gotchas

- Workflow scripts (`plugins/self-assess/workflows/*.js`) run in the
  Workflow tool's sandbox and have **no filesystem access** — any data a
  workflow needs (settings, house-rules content, file lists) must be
  passed in via `args` by the calling `SKILL.md`, never read directly.
- `plugins/self-assess/` explicitly models itself on
  `anthropics/claude-plugins-official`'s `code-modernization` plugin
  (Ready/Ready-with-gaps/Not-ready preflight taxonomy, parallel-finder +
  adversarial-verify Workflow pattern, `fence()`/`UNTRUSTED` untrusted-data
  wrapping). When extending self-assess, check code-modernization's actual
  source first rather than assuming — a prior pass found self-assess's
  docs claimed more mirroring than the code actually did (missing
  code-modernization's second-tier "independent confirm" pass for
  High-severity findings; since fixed in `docs-drift-scan.js` and
  `lint-audit-scan.js`, deliberately not in `ci-topology-scan.js` or
  `stage-map-scan.js` — see the rationale comments in those two files).
