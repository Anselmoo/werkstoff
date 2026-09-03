# werkstoff plugin benchmark: problem statement and execution plan

Produced via `compass:compass-solve` (Clarify → Decompose → Execute → Revise) to sharpen the
thesis "our plugins are off industry standards; skills/agents are too short and don't provide
enough feedback for follow-up tasks" into two falsifiable claims (one per plugin family) plus a
two-phase benchmark plan against `Wirasm/prp`, `anthropics/claude-plugins-official`'s
code-modernization plugin, and `obra/superpowers`. **This document is the plan — Phase 1 and
Phase 2 have been executed; see
[docs/plugin-benchmark-phase1-results.md](plugin-benchmark-phase1-results.md) and
[docs/plugin-benchmark-phase2-results.md](plugin-benchmark-phase2-results.md).**

Headline finding from this pass: `cupertino` has a real, fail-closed `PreToolUse` hook
(`hooks/pretooluse_guard.py`) that contradicts this repo's own [CLAUDE.md](https://github.com/Anselmoo/werkstoff/blob/main/CLAUDE.md), which
calls it advisory-only. See "Classify plugin families by literal hooks/ presence" below.

---

## Collect verbatim README Example Prompts per plugin [ground-evidence]
Execution mode: ground-evidence — this stage is pure extraction (verbatim quotes tied to file locations), not reasoning/verification, dynamic investigation, or format calibration, so the right mode is to pull exact text from each plugin's README `## Example Prompts` section and cite it, inventing nothing.

Source read for each: `plugins/<name>/README.md`, `## Example Prompts` section, in
the repository root.

All six READMEs carry the identical shared-block framing sentence (enforced via `.rrt.toml`'s `example-prompts-intro` anchor): "Say any of these to Claude Code once the plugin is installed — they're plain-language prompts, not exact phrasing Claude has to match. Claude routes them to the skill below by intent." — omitted below per-plugin to avoid repetition; only the plugin-specific bullets (hand-written, not template-shared) are listed.

---

::: details andon (`plugins/andon/README.md`)

1. `"run andon-preflight against this repo"`
   → invokes **andon-preflight**. Downstream per its own annotation: "read-only readiness report (stage legibility, ledger writability, house-rules presence); never creates the ledger."

2. `"harden this repo, one gap at a time"`
   → invokes **andon-loop**. Downstream per its own annotation: "detects the value stream, proposes and verifies a fix for the current stage's gap, and halts rather than advancing past a broken or unproven wire" — implies dispatch into fix-proposal and verification for the current stage.

3. `"what does the andon board look like right now"`
   → invokes **andon-status**. Downstream per its own annotation: "read-only: stream table, cursor, pass/cycle counters, open gap counts; nothing advances."

4. `"prove this wire is actually proven"`
   → invokes **andon-verify**. Downstream per its own annotation: "routes the wire to one of seven evidence-grounded strategies and returns a structured green/red verdict."

(A fifth listed prompt, `"propose a fix for this gap, only ask where it actually matters"` → `andon-propose`, also appears in the README but is omitted here to stay within the 3-4 cap.)

:::

---

::: details cli-scaffold (`plugins/cli-scaffold/README.md`)

1. `/cli-scaffold rust called myapp`
   → "The slash command itself — skips straight to generation for a named language and app name." (No named skill dispatch beyond the command itself, per its own wording.)

2. `"scaffold a Python CLI named foo that fetches weather data"`
   → invokes **scaffold-cli** (interpreted paradigm). Downstream per its own annotation: "natural-language equivalent of the slash command: resolves the language, loads the doctrine, generates, then verifies."

3. `"scaffold a bash CLI called backup-tool"`
   → invokes **scaffold-cli** (shell paradigm, `cli-scaffold-shell`). Downstream per its own annotation: "same five-pillar doctrine, plus POSIX-sh bashism checks."

(Only 3 prompts are listed in this README's Example Prompts section.)

:::

---

::: details compass (`plugins/compass/README.md`)

1. `"help me think through this, it's complex and I'm not sure of the right approach"`
   → invokes **compass-solve**. Downstream per its own annotation: "runs the full Clarify → Explore → Decompose → Execute → Revise pipeline."

2. `"before we commit to an approach, explore a few different ones"`
   → invokes **compass-explore-branches**. Downstream per its own annotation: "proposes and scores multiple viable approaches instead of anchoring on the first."

3. `"the scope of this request is fuzzy, help me pin it down first"`
   → invokes **compass-clarify-scope**. Downstream per its own annotation: "surfaces ambiguous phrasing and unstated success criteria before any work starts."

(Only 3 prompts are listed in this README's Example Prompts section.)

:::

---

::: details confab (`plugins/confab/README.md`)

1. `"check if any of our dependencies are hallucinated"`
   → invokes **confab-dependency-audit**. Downstream per its own annotation: "flags package names that don't exist in the real registry, independently re-verified before being reported."

2. `"would our tests actually catch a bug here?"`
   → invokes **confab-assertion-audit**. Downstream per its own annotation: "mutation-testing pass checking whether tests assert anything meaningful, not just execute the code."

3. `"run the confab cycle on this repo"`
   → invokes **confab-cycle**. Downstream per its own annotation: "bounded self-optimization loop: re-runs all four audits pass by pass, optionally applying fixes, until convergence."

4. `"where does confab stand on this repo"`
   → invokes **confab-status**. Downstream per its own annotation: "read-only dashboard: what's run, what's stale, what to run next."

:::

---

::: details cupertino (`plugins/cupertino/README.md`)

1. `"run the full cupertino review on this feature"`
   → invokes **cupertino-review**. Downstream per its own annotation: "runs all eight lifecycle stages end-to-end, backwards-compatibility check through reveal."

2. `"convene the cupertino council on this design"`
   → invokes **cupertino-council**. Downstream per its own annotation: "five-lens review (Reduction, Craft, Hierarchy, Usability, Metaphor), tensions resolved in a fixed precedence order."

3. `"check this codebase against our design handbook"`
   → invokes **cupertino-handbook-check**. Downstream per its own annotation: "flags drift from an already-drafted handbook rule, with file:line evidence."

(Only 3 prompts are listed in this README's Example Prompts section.)

:::

---

::: details self-assess (`plugins/self-assess/README.md`)

1. `"map this repo's architecture"`
   → invokes **self-assess-stage-map**. Downstream per its own annotation: "import-graph-based stage/wire detection, not naive directory guessing."

2. `"run the auto-pilot"`
   → invokes **self-assess-autopilot**. Downstream per its own annotation: "full check → plan → gate → fix/validate, gated behind explicit settings before anything is written."

3. `"where does self-assess stand"`
   → invokes **self-assess-status**. Downstream per its own annotation: "read-only board of what's been run and what's stale."

4. `"sweep our whole portfolio of repos"`
   → invokes **self-assess-portfolio**. Downstream per its own annotation: "multi-repo dashboard, graded worst-signal-wins."

:::

---

Notes on fidelity: every prompt string above is copied verbatim (including quote marks / slash-command syntax) from the corresponding README's fenced ` ```prompt ` block; no prompt was invented or reworded. Each "downstream dispatch" clause is quoted from that same prompt's own blockquote annotation in the README — no chain was inferred beyond what the README states. cli-scaffold, compass, and cupertino each have only 3 bulleted prompts in their READMEs (not 4); andon has 5, of which one (`andon-propose`) was dropped to respect the 3-4 cap. confab and self-assess each have exactly 4.

## Classify plugin families by literal hooks/ presence [ground-evidence]

**Execution mode:** ground-evidence — the stage demands a verified partition backed by direct file-read citations, with explicit instruction to distrust CLAUDE.md's own prose — a canonical evidence-grounding task, not reasoning, dynamic investigation, or format calibration. I read every plugin's actual `hooks/` presence and hook-script contents rather than trusting the repo's documentation.

### Partition

**hook-enforced: [andon, confab, self-assess, cupertino]**
**advisory-only: [compass, cli-scaffold]**

### Citations

#### andon — hook-enforced
- `plugins/andon/hooks/hooks.json` exists. `PreToolUse` matcher `"Write|Edit"`, `type: "command"`, invokes `${CLAUDE_PLUGIN_ROOT}/hooks/andon_enforce.py`.
- `plugins/andon/hooks/andon_enforce.py`: `deny()` (line 80) emits stdout JSON with `hookSpecificOutput.hookEventName: "PreToolUse"`, `permissionDecision: "deny"`, `permissionDecisionReason` (lines 96-98), writes reason to stderr, and `return 2` (line 102), propagated via `sys.exit(main())` (line 244). Comments at lines 84-92 document this exact belt-and-suspenders exit-2+JSON contract and note both are required.

#### confab — hook-enforced
- `plugins/confab/hooks/hooks.json` exists. Two matchers: `"Edit|Write"` → `scripts/hooks/guard_edit_scope.py`; `"Bash"` → `scripts/hooks/guard_bash_scope.py`. Both `type: "command"`.
- `guard_edit_scope.py` and `guard_bash_scope.py`: each has `deny()` returning `2` (lines 66 / 64) with the same `hookEventName: "PreToolUse"` / `permissionDecision: "deny"` / `permissionDecisionReason` stdout JSON (lines 59-61 / 57-59), reason on stderr, `sys.exit(main())` (lines 171 / 107).

#### self-assess — hook-enforced
- `plugins/self-assess/hooks/hooks.json` exists. Matcher `"Write|Edit|MultiEdit"`, `type: "command"`, invokes `hooks/guard_target_edit.py`.
- `guard_target_edit.py`: `deny()` returns `2` (line 75), same JSON contract (lines 68-70), `sys.exit(main())` (line 194). Docstring (lines 16-21) explicitly states the allow/deny contract.

#### cupertino — hook-enforced (**reclassified against CLAUDE.md's own prose**)
CLAUDE.md states: *"compass and cupertino are advisory — there is no tool call to deny for 'explore branches before scoring' — which is why their rebuilds gained nothing."* Direct file reads contradict this for cupertino:
- `plugins/cupertino/hooks/hooks.json` exists, with a description line stating it "enforces MUST-NOT rules... at the tool-call layer, regardless of whether a skill is followed." `PreToolUse` matcher `"Skill|Task|Agent|Write|Edit|Bash"` — the widest matcher of the four — `type: "command"`, invokes `hooks/pretooluse_guard.py`, `timeout: 15`.
- `plugins/cupertino/hooks/pretooluse_guard.py` (338 lines) implements all four required properties directly:
  - **Exit-2 + hookEventName-carrying stdout JSON**: `deny()` (lines ~57-65) prints `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}`, writes to stderr, `sys.exit(2)` (literal, not via return-code indirection like the other three).
  - **Inert-until-marker**: `main()` checks `os.path.isdir(state_dir(cwd))` i.e. `.cupertino/`; if absent, `allow()` immediately (docstring: "if this repository has never used cupertino... the guard allows everything immediately").
  - **Fail-closed**: docstring and code — any internal error after `.cupertino/` is confirmed to exist (malformed JSON, stdin parse failure, `OSError` on stat, unhandled exception in dispatch) calls `deny()` rather than allowing, each with the escape hatch named in the message (see `main()`'s try/except blocks around payload parsing, `cupertino_active` check, and the dispatch handlers).
  - **Escape hatch**: `CUPERTINO_DISABLE_GUARD=1`, checked first in `main()` before any other logic, unconditionally honored.
  - It also gates real actions beyond Write/Edit: `Skill` dispatch (ordering gate requiring `backwards-done` marker before `cupertino-focus`/`cupertino-longevity`/`cupertino-integrate`/`cupertino-council`; handbook-apply requires an existing handbook file; handbook-fix requires a `mode: fix` frontmatter setting), `Task`/`Agent` dispatch (one-marker-per-dispatch checks for four named subagents), and `Bash` (blocks mutating git/destructive rm during an active handbook pass).

  This is a full PreToolUse enforcement layer with a broader matcher and more distinct guarded behaviors than andon's. **CLAUDE.md's characterization of cupertino as advisory-only with "no tool call to deny" is factually wrong as of this checkout** — cupertino belongs in hook-enforced, not advisory-only.

#### compass — advisory-only (confirmed, consistent with CLAUDE.md)
- `plugins/compass/` top-level listing (`agents, references, scripts, skills, workflows, CHANGELOG.md, README.md`) has no `hooks/` directory at all. `ls -d plugins/compass/hooks` → "No such file or directory". No `hooks.json` anywhere under the tree (`find plugins/compass -iname '*hook*'` returned nothing). No PreToolUse mechanism exists to deny anything — confirmed absence, not inferred from prose.

#### cli-scaffold — advisory-only (not explicitly claimed by CLAUDE.md, confirmed independently)
- `plugins/cli-scaffold/` top-level listing (`agents, commands, references, scripts, skills, CHANGELOG.md, README.md`) has no `hooks/` directory. `ls -d plugins/cli-scaffold/hooks` → "No such file or directory". No `hooks.json` anywhere under the tree. CLAUDE.md doesn't name this plugin's enforcement status, but the same absence-of-hooks evidence places it in advisory-only alongside compass.

### Note on the reclassification's implication for CLAUDE.md's broader claim

CLAUDE.md's "Enforcement: only hooks actually enforce" section frames cupertino (with compass) as the counterexample proving "this only helps plugins whose rules gate *actions*." That framing needs revision: cupertino demonstrably does gate actions (Skill/Task/Agent/Write/Edit/Bash) via a real, fail-closed, escape-hatched PreToolUse hook. Whatever motivated the "gained nothing" claim (possibly a stale rebuild snapshot, or a distinction between "has a hooks/ dir" and "the hook fires in practice during the ~40 measured runs" — the latter not verified in this ground-evidence pass, which only confirms the hook's existence and code contract, not its live firing rate) is not visible from the current file tree and contradicts what's on disk today.


## Author (not execute) the Phase 1 static structural audit plan [calibrate-format]
### Phase 1 Static Structural Audit Plan (authored, not executed)

**Execution mode:** calibrate-format — this stage's job is to *author* a document that must satisfy a fixed output contract (three
named mandatory sections, four named checklist dimensions, explicit scoring rules, explicit
non-collapsing rules) and that must contain **zero** file content from the reference repos —
the contract says so explicitly. There is nothing to verify (nothing has been fetched yet),
nothing to investigate dynamically (execution is deferred by design), and no evidence to
ground (nothing has been read). What's being calibrated is the shape of the deliverable itself
against a spec handed down from the orchestrator. That is a format-calibration task, not
reasoning, investigation, or evidence-grounding — so this stage produces the plan document
below and nothing else. No GitHub MCP call, no WebFetch, no repo read happens in this turn.

---

### (a) Mandatory first fetch/read step per reference repo — deferred to execution time

None of the following has been done yet. At execution time, Phase 1 execution MUST perform
these as literal first actions, via `mcp__github__*` tools (preferred, per this project's
`get_file_contents` / `search_code` / `list_branches`) or `WebFetch` as fallback — **never**
from training memory and **never** by reading a locally-installed copy of the same-named skill
(e.g. a `superpowers` or `code-modernization` plugin already installed in this Claude Code
environment is not evidence about the upstream repo's current `main`/`development` state; it
may be stale, forked, or hand-edited). This caution applies identically and without exception
to all three repos below — none of the three gets its chain-relevant file names assumed in
advance, precisely because this environment happens to have same-named plugins already
installed and it would be too easy to silently substitute that local copy's shape for the
real upstream tree.

1. **Wirasm/prp @ `development` branch**
   - First call: `mcp__github__get_file_contents` (or `search_code`) scoped to
     `owner=Wirasm repo=prp ref=development`, listing the repository tree so the actual
     chain-relevant file set is discovered rather than assumed.
   - Chain-relevant files to locate and fetch: every skill/command definition that
     participates in the PRP execution chain (the files implementing the
     clarify → plan → implement → review flow — names TBD from the real tree, not guessed
     from this repo's local `prp-core` plugin, which is a *consumer*, not the source of truth).
   - Explicit deferral: no filenames are hard-coded here because the `development` branch's
     real tree has not been read; execution must resolve names from the fetched tree listing.

2. **anthropics/claude-plugins-official — `code-modernization` plugin**
   - First call: `mcp__github__get_file_contents` scoped to
     `owner=anthropics repo=claude-plugins-official path=<code-modernization plugin dir>`,
     to get the real subtree (skills, hooks, scripts) before anything else.
   - Chain-relevant files: every `SKILL.md` under the plugin's real `skills/` directory that
     hands off to another named skill — the actual chain shape (which skills exist, and in
     what order they hand off) is TBD from the fetched tree, not assumed here, plus any
     `hooks/hooks.json` and hook scripts the fetched tree shows.
   - Note for the executor: this project's own `self-assess` plugin models itself on this
     repo's actual source per CLAUDE.md — do not substitute the locally-installed
     `code-modernization` plugin skill copies for a live fetch, and do not use that local
     copy's skill names as a stand-in for what the fetch will find, even as a guess; a prior
     pass in this repo already found the docs/description text diverging from the real code,
     which is exactly the failure mode this fetch step exists to prevent. Resolve the real
     chain (names and handoff order) only from the fetched tree.

3. **obra/superpowers**
   - First call: `mcp__github__get_file_contents` (or `search_code`) against
     `owner=obra repo=superpowers` to get the real tree of skills.
   - Chain-relevant files: each skill's `SKILL.md` found in the fetched tree, since
     superpowers' whole design is a handoff chain — the specific skill set and which skill
     hands off to which is TBD from the fetched tree, not assumed here, plus any
     sidecar/state file the chain relies on (ledger-like files, plan files) if the fetched
     tree shows one.
   - Same caveat as above: do not read this environment's already-installed `superpowers`
     skill listing as a stand-in for the upstream repo's current source, and do not use that
     local listing's skill names as a preview of what the fetch will return — resolve the
     real skill set and handoff structure only from the fetched tree.

**Cross-cutting rule for execution:** each of the three fetch steps is independent and must
complete (or explicitly fail/report-unreachable) before that repo's files are scored — a
partial or failed fetch must not silently fall back to memory or to locally-installed skill
text. If GitHub MCP access to a repo fails, the executor reports the failure and that repo's
row is marked unscored, not zero-filled and not skipped silently.

---

### (b) Four fixed checklist dimensions and scoring method

Each dimension is scored **1 (present) or 0 (absent)** per individual chain-relevant file,
based only on what is directly observed in that file's fetched content — no inference from
a file's name, description, or reputation.

| Dimension | What counts as present (1) |
|---|---|
| `HAS_SCHEMA_BLOCK` | The file defines a structured output contract for what it produces — an explicit schema, typed frontmatter contract, or fenced spec of required output fields/shape that a downstream consumer could validate against. Prose that merely *describes* output in free text does not count. |
| `HAS_NEXT_SKILL_FIELD` | The file explicitly names the next skill/command/step in the chain (a literal identifier — e.g. a `next_skill`/`dispatch`-style field, or an unambiguous "invoke `X` next" instruction naming the exact next component) rather than a vague "then continue" without a named target. |
| `HAS_SIDECAR_FILE_CONTRACT` | The file specifies a concrete sidecar/state artifact it reads or writes to hand state across the chain (ledger, plan file, findings file, lock file) with enough specificity (path pattern, required keys, or format) that another file could be shown to honor or violate the same contract. A vague "keep track of progress" does not count. |
| `HAS_ENFORCEABLE_EXIT_CODE` | The file (or its accompanying hook/script) ties a pass/fail outcome to a machine-checkable exit code or equivalent hard gate (e.g. a `PreToolUse` hook with `type: "command"` that does `sys.exit(2)` plus the JSON deny contract) — not merely prose telling the model to check something itself. Matches this repo's own standard from `CLAUDE.md`'s enforcement table: prose and workflow-embedded guards do not count, only an actual command-invoked hard exit does. |

**Per-file score:** sum of the four 1/0 values → integer 0–4.

**Aggregation rule (fixed, decided now, before any execution):**
- Compute min / median / max of per-file scores **within each plugin** (for
  claude-plugins-official's `code-modernization`, since its fetched tree is already known from
  this project's own experience to contain multiple distinct skill groupings under one repo).
- For **Wirasm/prp** and **obra/superpowers**, the granularity of aggregation is deliberately
  **not fixed here**, because their real tree has not been fetched yet (per (a) above) and
  asserting now whether either repo is "one flat skill set" or "several internally distinct
  plugin-like groupings" would itself be a measurement commitment on an unconfirmed layout —
  exactly the mistake this plan exists to avoid. Instead, the rule to apply at execution time
  is fixed now, even though its outcome is not:
  - If the fetched tree shows a single coherent, undifferentiated skill/command set (no
    internal sub-grouping resembling a separate plugin), aggregate min/median/max across that
    whole repo as one unit — parallel to how a single-plugin repo would be treated.
  - If the fetched tree instead reveals multiple genuinely separate plugin-like groupings
    (e.g. distinct top-level directories each with their own skill set and no cross-calls
    outside the group), aggregate min/median/max **per grouping**, exactly as done for
    `code-modernization`'s individual plugins — and report each grouping's numbers
    separately, never merged into one repo-wide figure.
  - Which branch applies is determined solely by what the fetched tree shows; the executor
    records which branch was taken and why, so the choice is auditable rather than silent.
- **Never** collapse scores across different plugins, and **never** collapse scores across
  different repos into one aggregate number. Every reported statistic is scoped to exactly
  one plugin-or-repo (or one sub-grouping, per the branch above). A single combined "average
  across all three references" number is explicitly disallowed as an output of this audit.
- Report the three numbers (min/median/max) plus file count per plugin/repo/grouping — not
  just one summary statistic — so a low median hidden behind a high max (or vice versa) stays
  visible.

---

### (c) Fixed pass/fail thresholds per family, decided before execution

These thresholds are locked in now, prior to fetching or scoring anything, so they cannot be
retuned after seeing the results (this repo's own rule: "never retune an oracle after the
thing it grades exists").

**hook-enforced family** (`andon`, `confab`, `self-assess`, `cupertino` — per the upstream
family-classification stage):
- **PASS** requires: median per-file score ≥ 3 **and** every file in the plugin scores 1 on
  `HAS_ENFORCEABLE_EXIT_CODE` specifically (since that is the dimension that defines this
  family's classification — a hook-enforced plugin whose files don't individually chain to
  an enforced exit code has an enforcement gap the classification didn't catch).
- **FAIL** otherwise. A plugin landing exactly at median 3 but with any file scoring 0 on
  `HAS_ENFORCEABLE_EXIT_CODE` is a FAIL, not a borderline pass — the exit-code dimension is a
  hard gate for this family, not something the median can average away.

**advisory-only family** (`compass`, `cli-scaffold`):
- **PASS** requires: median per-file score ≥ 2, with no minimum requirement on
  `HAS_ENFORCEABLE_EXIT_CODE` (by definition this family has no tool call to deny, so scoring
  it 0 throughout is expected and not penalized).
- **FAIL** if median per-file score < 2 — i.e. even an advisory chain is expected to at least
  usually declare what it produces and what runs next (`HAS_SCHEMA_BLOCK` /
  `HAS_NEXT_SKILL_FIELD`), just not to enforce it mechanically.

**Reference repos (Wirasm/prp, code-modernization, superpowers)** — scored for comparison,
not judged pass/fail against werkstoff's own bar, since they are the external baseline this
audit measures werkstoff against:
- Each reference repo/plugin/grouping (per the aggregation branch chosen in (b)) gets the same
  min/median/max reported, tagged as *reference*, with no PASS/FAIL label applied. The
  subsequent phase (not this one) is expected to compare werkstoff's per-family PASS/FAIL
  outcome against where each reference repo's median falls, but that comparison is explicitly
  out of scope for this authoring stage.

**Threshold-integrity note:** if execution later finds these thresholds unworkable (e.g. every
single file in every repo scores 0 on `HAS_SCHEMA_BLOCK` because the checklist dimension was
misdefined), the correct response is to flag that as a finding about the checklist itself, not
to silently loosen the number after the fact.


## Sharpen thesis into one falsifiable claim per family [reason-verify]

**Execution mode:** reason-verify — this stage takes an already-verified partition (ground-evidence output, trusted as-is) and an unfalsifiable prose thesis, and must produce exactly two propositions each carrying its own falsifier. There is nothing left to discover in the filesystem (that was the prior stage) and no format ambiguity to resolve (the output contract is fully specified) — the task is to *construct* two claims and *verify* each one actually satisfies the Popperian bar (a stated observation that would prove it wrong, expressed in terms of data a caller can mechanically inspect: tool-call/tool-result JSON payloads, not vibes). Hence reason-verify, not ground-evidence (no new file reads needed), not investigate-dynamically (no unknown to chase), not calibrate-format (the shape is fixed by the contract, not negotiable).

### Claim 1 — hook-enforced family (andon, confab, self-assess, cupertino)

**Proposition:** For this family, any "insufficient feedback for follow-up tasks" defect cannot be located in the enforcement layer, because a PreToolUse hook firing already emits a machine-parseable contract on the tool-call payload — `hookSpecificOutput.hookEventName`, `permissionDecision` ∈ {allow, deny}, `permissionDecisionReason` — independent of whatever prose the invoked skill itself returns. The defect, if real, must therefore live in the *non-hook-mediated* return value: the `tool_result` a Skill/Task/Agent invocation produces on a run the hook allows, which is authored by the skill and is exactly what "too short" (redefined: lacking output-contract structure) is about.

**Falsifying observation:** Inspect the `tool_result` payload returned by a Skill or Task/Agent invocation for andon, confab, self-assess, or cupertino on a run where no hook denial fired (i.e., the allow path, not the deny path — the deny path's structure is already proven by the ground-evidence citations above and is not what's in dispute).
- Claim is **falsified** if that `tool_result` contains a typed, machine-parseable follow-up structure a caller could branch on without an LLM re-reading it — e.g., a JSON block with an explicit status enum, a next-stage/next-skill field, or a ledger/wire reference id.
- Claim **holds** if that `tool_result` is free-form prose with no such schema — i.e., a downstream caller has no field to `if`-branch on, only text to re-parse with another model call.

### Claim 2 — advisory-only family (compass, cli-scaffold)

**Proposition:** For this family, "insufficient feedback for follow-up tasks" is fully and only attributable to the skill's own output contract, because there is no PreToolUse hook at all (confirmed absence, both plugins) to supply a competing or compensating machine-parseable signal at the tool-call layer. Whatever structure a follow-up task needs must come entirely from the `tool_result` the skill itself returns — there is no second channel to blame or credit.

**Falsifying observation:** Inspect the `tool_result` payload returned by any compass or cli-scaffold skill invocation.
- Claim is **falsified** if that payload carries a typed, machine-parseable output-contract structure — e.g., explicit fields distinguishing "recommended next stage," "blocking condition," or a structured recommendation object a caller can consume without re-reading prose.
- Claim **holds** if the payload is unstructured natural-language recommendation text only, with nothing a calling workflow or script could deterministically key off of.

### Axis-separation statement (binding on both claims)

Phase 1 (structural score: does the `tool_result`/hook payload carry a machine-parseable output contract at all) and Phase 2 (handoff ratio: of the runs that do carry one, what fraction a downstream consumer actually acts on without re-invoking a model to reinterpret it) are reported as two separate, non-fungible axes for each claim above. They are never averaged, combined into a single index, or allowed to offset one another — a plugin scoring well on Phase 1 structure and poorly on Phase 2 handoff (or vice versa) is reported as exactly that, two numbers, not blended into one.

## Author (not execute) the Phase 2 executed-chain benchmark plan [reason-verify]

**Execution mode:** reason-verify — both inputs are already-finished, trusted artifacts (verbatim prompt extraction; two falsifiable claims with mechanical falsifiers). Nothing here needs new file discovery beyond a narrow grounding check, no format is up for negotiation (the output contract below is dictated verbatim by the stage spec), and the actual work is *construction under a bar*: pick chains that are legitimate (verifiably drawn from the given extraction, not invented), write a HANDOFF_WORKED/FAILED test that is verifiably mechanical (keyed to raw payload fields, not prose/self-report), and pick thresholds that are verifiably fixed-before-any-run and verifiably asymmetric. Each of those three constructions is checked against its own bar before being included — reason-verify.

One grounding check was done, because it bears directly on whether the thresholds below are assigned to the right family: I read `plugins/{andon,confab,self-assess,cupertino,compass,cli-scaffold}/hooks/hooks.json` on disk. All four named in thesis Claim 1 (andon, confab, self-assess, cupertino) have a `PreToolUse` hook with `"type": "command"` (cupertino's guard is literally named as enforcing "ordering gates" among other things). Neither compass nor cli-scaffold has a `hooks/` directory at all. This corroborates the thesis's two-family split against the actual repo, despite CLAUDE.md's own prose elsewhere calling cupertino "advisory" in a different, narrower context (a specific rule-type example, not a blanket claim the hook file is absent) — flagged here as a documentation-vs-code tension worth a maintainer's eye, but it does not change the family assignment below, which the file evidence supports.

**No chain below is executed. This stage only authors the plan.**

---

### 1. Chains per plugin (steps are prompts quoted verbatim from the example-prompts-collection input; nothing invented)

#### andon (hook-enforced family)
- **AND-1** `"run andon-preflight against this repo"` → `"harden this repo, one gap at a time"` (preflight → loop). Tests whether loop's invocation consumes preflight's readiness fields or re-derives readiness from a blank slate.
- **AND-2** `"harden this repo, one gap at a time"` → `"prove this wire is actually proven"` (loop → verify). andon-verify's own annotation states it is invoked "when andon-loop dispatches it to prove a wire" — this chain checks whether that internal dispatch carries a structured wire id or free prose.
- **AND-3** `"what does the andon board look like right now"` → `"harden this repo, one gap at a time"` (status → loop). Tests whether loop resumes from status's reported cursor or re-reads the ledger from scratch (relevant given CLAUDE.md's own note that the rebuilt ledger schema is not backward-compatible with `tags:`-based ledgers).

#### confab (hook-enforced family)
- **CON-1** `"check if any of our dependencies are hallucinated"` → `"run the confab cycle on this repo"` (dependency-audit → cycle). cycle's own annotation says it "re-runs all four audits pass by pass" — tests whether pass 1 shows an explicit carried-forward reference to the standalone audit's findings, or repeats it identically with no link.
- **CON-2** `"would our tests actually catch a bug here?"` → `"run the confab cycle on this repo"` (assertion-audit → cycle). Same test, second audit type — a replicate to rule out audit-type-specific behavior.
- **CON-3** `"run the confab cycle on this repo"` → `"where does confab stand on this repo"` (cycle → status). Tests whether status's fields (pass count, convergence) are traceable to cycle's own tool_result, or reconstructed via prose re-summary.

#### self-assess (hook-enforced family)
- **SA-1** `"map this repo's architecture"` → `"run the auto-pilot"` (stage-map → autopilot). Tests whether autopilot's CHECK phase consumes stage-map's graph object or recomputes the import graph independently.
- **SA-2** `"map this repo's architecture"` → `"where does self-assess stand"` (stage-map → status). Tests whether status's "what's been run" entry for stage-map carries a field/id lifted from stage-map's own tool_result.
- **SA-3** `"run the auto-pilot"` → `"where does self-assess stand"` (autopilot → status). Tests whether status exposes per-phase (CHECK/PLAN/GATE/FIX) structured fields keyed to autopilot's own emitted fields, vs. free-text re-summary.

#### cupertino (hook-enforced family)
- **CUP-1** `"check this codebase against our design handbook"` → `"run the full cupertino review on this feature"` (handbook-check → review). Tests whether review's backwards-compatibility stage reuses handbook-check's file:line drift list, or starts its 8-stage lifecycle from zero.
- **CUP-2** `"convene the cupertino council on this design"` → `"run the full cupertino review on this feature"` (council → review). Tests whether review's five-lens stage consumes council's per-lens verdict record, or re-runs the council internally.
- **CUP-3** `"run the full cupertino review on this feature"` alone, inspected across its own internal 8-stage handoff. Tests whether the single tool_result exposes stage-indexed structured fields (name/pass-fail/evidence) a caller could branch on, vs. one undifferentiated prose narrative.

#### compass (advisory-only family)
- **CMP-1** `"the scope of this request is fuzzy, help me pin it down first"` → `"help me think through this, it's complex and I'm not sure of the right approach"` (clarify-scope → solve). Tests whether solve's internal Clarify sub-stage consumes clarify-scope's structured ambiguity/success-criteria list, or re-runs Clarify from the raw chat history.
- **CMP-2** `"before we commit to an approach, explore a few different ones"` → `"help me think through this..."` (explore-branches → solve). Tests whether solve's Explore stage consumes the branch-scoring object, or re-explores from scratch.
- **CMP-3** `"help me think through this, it's complex..."` alone, inspected across its own internal Decompose→Execute handoff. Tests whether Decompose's task list is exposed as a structured, id-bearing object a script could feed to a separate Execute call, vs. inlined prose only the model can operationalize.

#### cli-scaffold (advisory-only family)
Note: this README's 3 prompts are three independent generation entry points (rust/python/bash), not a producer→consumer pair — unlike every other plugin above, there is no README-given prompt that consumes another's output. Two of the three possible chains are therefore deliberately built to test *whether any incidental cross-invocation state exists at all* (a legitimate, pre-registered "expect FAILED" chain, not a weak substitute):
- **CLI-1** `` /cli-scaffold rust called myapp`` → `"scaffold a Python CLI named foo that fetches weather data"`. Tests for any structural leakage (shared doctrine/version id, shared registry entry) between two nominally independent scaffolds.
- **CLI-2** `"scaffold a Python CLI named foo that fetches weather data"` → `"scaffold a bash CLI called backup-tool"`. Replicate of CLI-1 with a different pair, to rule out an order effect.
- **CLI-3** `` /cli-scaffold rust called myapp`` inspected across its own internal generate→verify handoff (cli-architecture doctrine: "generates, then verifies"). Tests whether the internal dispatch into verification carries a structured written-files manifest, or a free-text "please check this" prompt that forces the verifier to re-scan disk itself.

---

### 2. HANDOFF_WORKED / HANDOFF_FAILED — binary definition against the raw payload

For any two chained steps (or two internal sub-stages of one skill), let `tool_result(N)` be the raw JSON tool-result of the upstream call and `tool_call_input(N+1)` be the raw JSON arguments/prompt of the downstream Skill/Task/Agent tool call that follows it.

- **HANDOFF_WORKED** — `tool_call_input(N+1)` contains a value that is byte-identical (or an unambiguous structural sub-match, e.g. the same wire-id string, the same file:line tuple, the same stage name/enum value) to a value present in a machine-parseable field of `tool_result(N)` (a JSON block, an explicit `key: value`, an enum, an id). The match must be checkable by string/structural comparison of the two payloads alone — no model is asked whether it "used" the prior output.
- **HANDOFF_FAILED** — no such traceable value exists: `tool_call_input(N+1)` is the raw human prompt text only, or is free-composed text that merely paraphrases/re-summarizes `tool_result(N)`'s prose with no structural field carried over verbatim.

This is deliberately blind to self-report: a transcript in which the model *says* "I'm using the prior result" but the actual `tool_call_input(N+1)` payload contains no traceable field is scored FAILED. Only the two raw payloads are inspected.

Denominator discipline (binds every ratio computed downstream): Phase 2 is computed only over the subset of runs where Phase 1 already found a machine-parseable field present in `tool_result(N)` — i.e., Phase 2 asks "of the structured outputs that exist, how many are actually consumed," never "how many outputs exist," which is Phase 1's question alone.

---

### 3. Fixed asymmetric pass/fail thresholds per family (set now, before any chain runs)

Rationale for asymmetry: a false PASS is more expensive for the advisory-only family (compass, cli-scaffold) because there is no second channel — Claim 2 already established the `tool_result` is the *only* place a follow-up consumer could get structure from, so a wrongly-credited PASS there means a real downstream integration gets silently handed prose it can't branch on. For the hook-enforced family (andon, confab, self-assess, cupertino), Claim 1 already established the PreToolUse hook is a compensating control on the allow/deny axis regardless of skill-level handoff quality, so the cost of a false PASS at the skill-output layer is bounded by that backstop — the bar can be lower without under-protecting anything the hook already covers.

| family | PASS if ratio ≥ | FAIL if ratio ≤ | band (0.25–0.50 / 0.40–0.75) |
|---|---|---|---|
| hook-enforced (andon, confab, self-assess, cupertino) | 0.50 | 0.25 | INCONCLUSIVE — run remaining chains for that plugin before scoring |
| advisory-only (compass, cli-scaffold) | 0.75 | 0.40 | INCONCLUSIVE — same rule |

Both cutoffs are set now and are not to be moved after seeing results (per CLAUDE.md's own standing rule: never retune an oracle after the thing it grades exists). An INCONCLUSIVE result is reported as its own state, not rounded to PASS or FAIL.

---

### 4. Reporting rule (binding, carried over from the axis-separation statement)

For every plugin/skill/agent measured:
- **Phase 1 score** (structural: does a `tool_result`/hook payload carry any machine-parseable output contract) and
- **Phase 2 ratio** (handoff: of the Phase-1-positive runs, what fraction show HANDOFF_WORKED per §2)

are reported side by side as two separate numbers. They are never averaged, weighted into a composite, or allowed to offset each other — a plugin with high Phase 1 and low Phase 2 (or the reverse) is reported exactly as that pair, not as one blended score.

**Named divergence finding:** any plugin/skill/agent where Phase 1 = positive (a documented/observed schema exists in at least one `tool_result`) but the Phase 2 ratio across all of that plugin's executed chains is 0 (no run in the whole chain set ever shows a downstream `tool_call_input` actually carrying one of that schema's fields) is flagged as its own named finding — "documented contract, nothing downstream parses" — independent of and in addition to reporting the bare 0.00 ratio number, so a 0% result is never silently absorbed into "low score" without surfacing that the schema exists on paper/in-output but is provably unconsumed anywhere observed.

---

### Inputs consumed, discipline maintained

- Every chain step above is quoted from the example-prompts-collection output verbatim; no prompt text was invented, reworded, or drawn from re-reading the READMEs directly (the one prompt known to exist but omitted upstream for the cap — andon's `andon-propose` — is excluded from every chain here for the same reason it was excluded upstream: it is not in the given extraction).
- Family assignment (hook-enforced vs. advisory-only) is taken from thesis-sharpening's Claim 1 / Claim 2 grouping and corroborated, not overridden, by the `hooks/hooks.json` grounding check above.
- Nothing in this stage ran a chain, invoked a skill, or inspected an actual transcript — every HANDOFF_WORKED/FAILED test above is a specification of what Phase 2 execution must check, to be applied only once chains are actually run in a later stage.
