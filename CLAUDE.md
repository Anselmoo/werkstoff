# werkstoff

My personal Claude Code plugin workshop (`.claude-plugin/marketplace.json`
at root). Three plugins currently:

- `plugins/self-assess/` — docs-vs-code drift and stage/wire mapping for a live repo.
- `plugins/quality/` — AI-generated-code quality auditing (dependency/assertion/contract/agentic-reliability audits).
- `plugins/compass/` — prompt-engineering technique library + `compass-solve` orchestrator for complex/ambiguous tasks.

See each plugin's own `README.md` for what it does in full.

## Spec-driven development convention

Non-trivial changes to a plugin go through `.superpowers/sdd/`, not ad hoc
edits:

- **Brief**: `.superpowers/sdd/<prefix>-task-N-brief.md` — written via the
  `superpowers:writing-plans` skill. `<prefix>` is short per work-stream
  (e.g. `sa-` for self-assess, `q-` for quality, `c-` for compass). Format:
  Files / Scope / numbered checkbox Steps / manual-verify / commit.
- **Report**: `.superpowers/sdd/<prefix>-task-N-report.md` — written after
  a task completes (implementation notes, review outcome).
- **Log**: `.superpowers/sdd/progress.md` — one line per completed task,
  append-only, e.g. `Task 8: complete (commits abc..def, review clean - approved)`.

Read the existing `<prefix>-task-*-brief.md` files for a work-stream before
writing a new one — match their exact structure, don't reinvent it.
`.superpowers/sdd/` is untracked scratch, not committed to git.

## Verifying plugin changes

No test suite exists (plugin content is markdown/JS skill definitions, not
application code). Verification used across prior tasks:

```bash
node --check plugins/self-assess/workflows/<file>.js   # workflow scripts parse
python3 -c "import yaml; yaml.safe_load(open('plugins/self-assess/skills/<skill>/SKILL.md').read().split('---')[1])"  # SKILL.md frontmatter parses
```

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
`quality`, `compass`). Bump one plugin's version with:

```bash
rrt bump <major|minor|patch> --group <plugin-name>
```

Requires **rrt >= 1.13.1** — anything older fails with "Multiple version
groups configured" on a valid `--group` (fixed in
[anselmoo/repo-release-tools#176](https://github.com/Anselmoo/repo-release-tools/pull/176),
reported as [#175](https://github.com/Anselmoo/repo-release-tools/issues/175)).

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
