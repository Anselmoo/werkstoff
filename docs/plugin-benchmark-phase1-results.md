# Phase 1 results: static structural audit

Executes Phase 1 of [docs/plugin-benchmark-plan.md](plugin-benchmark-plan.md). Every file below was
read directly (werkstoff plugins from the local checkout; the three reference repos from fresh
shallow clones of their real current source — never from memory or from this environment's
locally-installed `prp-core:*`/`code-modernization:*`/`superpowers:*` skill copies, per the plan's
explicit caution). Scores are per-file, 0–4, against four dimensions:

- **SCHEMA** — a fenced/typed output contract, not prose describing output.
- **NEXT** — a literal next-skill/command identifier, not "then continue."
- **SIDECAR** — a concrete, specifically-shaped state artifact the chain reads/writes.
- **EXIT** — a hook/script tying pass/fail to a machine-checkable exit code, not a prose self-check.

Phase 1 answers "does a machine-parseable contract exist at all." It does **not** answer whether
anything downstream actually consumes it — that's Phase 2, not yet run.

---

## 1. werkstoff — hook-enforced family (andon, confab, self-assess, cupertino)

Fixed threshold (from the plan): **PASS** needs median ≥ 3 **and** every scored file at EXIT = 1.
A plugin at median exactly 3 with any file at EXIT = 0 is still FAIL — the exit-code dimension is
a hard gate for this family, not something the median can average over.

| Plugin | n | min | median | max | Every file EXIT=1? | Verdict |
|---|---|---|---|---|---|---|
| andon | 8 | 0 | 1 | 4 | No (4 tribunal agents = 0) | **FAIL** |
| confab | 7 | 2 | 2 | 4 | No (3 files = 0) | **FAIL** |
| self-assess | 4 | 1 | 3 | 4 | No (`stage-mapper` agent = 0) | **FAIL** |
| cupertino | 12 | 0 | 2 | 4 | No (5 files = 0) | **FAIL** |

**All four hook-enforced plugins fail the plan's own fixed structural bar.** Not narrowly — in
every case the failure is driven by the same recurring shape: **the entry-point SKILL.md that
owns the hook-gated write scores well (3–4/4); the read-only analysis/tribunal agents it
dispatches score at or near 0/4** because they have no Write/Edit tool grant, so the plugin's own
`Write|Edit` hook has nothing to gate on them by construction:

- andon: all 4 tribunal agents (`andon-defender/challenger/verifier/adjudicator`) score **0/4** —
  no schema, no next-field, no sidecar, no exit-code coverage (`tools: [Read, Grep, Glob(, Bash)]`,
  explicitly "Refuse to edit, create, or modify any files").
- self-assess: `stage-mapper` agent scores **1/4** — has a schema block but is Read/Glob/Grep/Bash
  only, no hook coverage.
- cupertino: 4 of 9 internal review stages (`prototype`, `elevate`, `unbox`, `reveal`) score
  **0/4** — no schema beyond a single string wrapper, no hook gate at all (confirmed absent from
  `pretooluse_guard.py`'s own gating logic, contradicting `validators.py`'s comment that scope
  containment is "enforced at the hook layer" — another documentation/code mismatch, same shape
  as the family-classification one already found).
- confab: the two Find/Verify-only agents (`dependency-auditor`, `assertion-auditor`) and the
  standalone audit skills score 2/4 each — real schema blocks, but no next-skill field (they
  report to whoever called them, never naming a successor themselves).

**This is a genuine, evidence-grounded version of the original vague complaint** — not "files are
too short," but specifically: *read-only agents in the audit/tribunal role systematically carry no
machine-parseable handoff, even inside plugins whose hook layer is otherwise real.*

---

## 2. werkstoff — advisory-only family (compass, cli-scaffold)

Fixed threshold: **PASS** needs median ≥ 2, no exit-code requirement (by design — this family has
no hook).

| Plugin | n | min | median | max | Verdict |
|---|---|---|---|---|---|
| compass | 4 | 1 | 1 | 3 | **FAIL** |
| cli-scaffold | 7 | 1 | 2 | 2 | **PASS** |

compass's failure is concentrated the same way as the hook-enforced family: `compass-solve`
(the orchestrator) scores 3/4 — real sidecar (`.compass/runs/<id>/state.json`) and explicit
per-phase next-skill invocations — but `compass-clarify-scope`, `compass-explore-branches`, and
the `branch-proposer` agent each score only 1/4: they define real output schemas but never name a
literal next skill in their own body text (that naming only happens one level up, in
`compass-solve`'s own dispatch instructions). `cli-scaffold` passes cleanly: every one of its 7
chain-relevant files scores 2/4, driven by a consistent manifest-handoff pattern
(`cli-scaffold.manifest.json`, read by all three paradigm skills and the verifier agent).

---

## 3. Reference repos (scored for comparison — no PASS/FAIL label, per the plan)

| Repo | Grouping | n | min | median | max |
|---|---|---|---|---|---|
| Wirasm/prp @ `development` | single unit | 10 | 1 | 2.5 | 4 |
| code-modernization (anthropics/claude-plugins-official) | single unit | 16 | 1 | 2 | 3 |
| obra/superpowers @ `main` | single unit | 18 | 0 | 1 | 3 |

None of the three reference repos has a `PreToolUse` (or any tool-call-gating) hook — all EXIT
scores are 0 across all three, confirmed by direct inspection, not assumed:
- prp's only hook (`prp-research-team-stop.sh`) is a `Stop` hook scoped to one unrelated skill and
  always exits 0.
- code-modernization has no `hooks/` directory anywhere in its tree.
- superpowers' only hook fires on `SessionStart` (context injection), always exits 0.

**The single strongest file across all four codebases is `prp-core`'s `prp-loop`** (4/4) — the only
file anywhere in this audit backed by a real script with `sys.exit(1)` on ten distinct named
failure conditions and a JSON verdict file it writes and validates itself. Everything else in
`prp-core`'s own chain (including its richly-templated `prp-prd`/`prp-plan`/`prp-implement`) relies
on prose "GATE: wait for user" / "must pass with zero errors" self-checks — the same enforcement
tier CLAUDE.md's own measurements call unreliable.

**code-modernization's strongest contracts live in its `workflows/*.js` files** (real JSON-Schema
objects + literal `agentType:` targets passed to `agent()` calls), but those only fire when the
Workflow tool path is taken — the `commands/*.md` fallback to direct subagent dispatch carries no
such schema at all. Structurally weaker than werkstoff's median in 3 of the 4 hook-enforced
plugins.

**superpowers has the lowest median of the three references (1)** — 6 of its 18 chain-relevant
files score 0/4 (`dispatching-parallel-agents`, `finishing-a-development-branch`,
`receiving-code-review`, `test-driven-development`, `using-git-worktrees`,
`verification-before-completion`). Its one standout is `subagent-driven-development`'s
`progress.md` ledger contract (3/4, plus its three prompt templates at 2/4 each) — genuinely the
best sidecar-file design found anywhere in this audit, but it's one skill in a set of fourteen, not
representative of the whole repo.

---

## 4. Claim 2 (advisory-only family) — assessable now from Phase 1 alone

Claim 2's falsifier: "off industry standard" is confirmed only if the werkstoff plugin's median is
strictly lower than the matched reference median in ≥ 2 of 3 repos.

| werkstoff plugin | median | vs prp (2.5) | vs code-modernization (2) | vs superpowers (1) | Claim 2 |
|---|---|---|---|---|---|
| compass | 1 | lower | lower | tied | **CONFIRMED** (2 of 3 strictly lower) |
| cli-scaffold | 2 | lower | tied | higher | **FALSIFIED** (only 1 of 3 strictly lower) |

So of the two advisory-only plugins, the original thesis holds for `compass` and is **falsified**
for `cli-scaffold` — a uniform "advisory plugins are behind industry standard" claim would have
been wrong for half this family.

## 5. Claim 1 (hook-enforced family) — NOT resolvable from Phase 1 alone

Claim 1's falsifier requires inspecting an actual downstream `tool_call_input` payload on an
executed chain — that's Phase 2, not yet run. What Phase 1 *does* establish, comparably across all
four codebases: werkstoff's hook-enforced plugins' median scores (andon 1, confab 2, self-assess
3, cupertino 2) are **not obviously worse** than the three references' medians (2.5, 2, 1) — two of
werkstoff's four plugins tie or beat two of the three references on raw structural score. The
recurring failure mode (read-only agents scoring near-0) is also present in the references
(superpowers: 6 files at 0; code-modernization: fallback path at 0 on EXIT). This suggests the
"off industry standard" framing may not survive Phase 2 for this family in the way the original
thesis assumed — but that's exactly what Phase 2 exists to test, not something Phase 1 can settle.

---

## Next step

Phase 2: execute the named chains (AND-1..3, CON-1..3, SA-1..3, CUP-1..3, CMP-1..3, CLI-1..3 from
[the plan](plugin-benchmark-plan.md)) and inspect the raw `tool_call_input` payloads for
HANDOFF_WORKED/FAILED per the plan's mechanical, self-report-blind test.
