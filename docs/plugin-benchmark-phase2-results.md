# Phase 2 results: executed-chain benchmark

Executes Phase 2 of [docs/plugin-benchmark-plan.md](plugin-benchmark-plan.md). Every named chain
was actually invoked — real Skill/Agent tool calls, real files written — each in its own isolated
git worktree so nothing landed in the working checkout. HANDOFF_WORKED/FAILED is scored strictly
from raw tool-call payloads (per the plan's definition), never from a transcript's self-report.

---

## 1. Hook-enforced family (andon, confab, self-assess, cupertino)

| Plugin | Chain | Verdict |
|---|---|---|
| andon | AND-1 preflight → loop | FAILED |
| andon | AND-2 loop → verify | **WORKED** |
| andon | AND-3 status → loop | FAILED |
| confab | CON-1 dependency-audit → cycle | FAILED |
| confab | CON-2 assertion-audit → cycle | FAILED |
| confab | CON-3 cycle → status | **WORKED** |
| self-assess | SA-1 stage-map → autopilot | FAILED |
| self-assess | SA-2 stage-map → status | FAILED |
| self-assess | SA-3 autopilot → status | N/A (autopilot itself has no schema — excluded per denominator discipline) |
| cupertino | CUP-1 handbook-check → review | FAILED |
| cupertino | CUP-2 council → review | FAILED |
| cupertino | CUP-3 review internal (backwards→focus, focus→longevity/integrate) | FAILED (both transitions) |

Per-plugin ratio against the plan's fixed asymmetric thresholds (PASS ≥ 0.50, FAIL ≤ 0.25, else INCONCLUSIVE):

| Plugin | Ratio | Verdict |
|---|---|---|
| andon | 1/3 = 0.33 | INCONCLUSIVE |
| confab | 1/3 = 0.33 | INCONCLUSIVE |
| self-assess | 0/2 = 0.00 | **FAIL** |
| cupertino | 0/3 = 0.00 | **FAIL** |

**Claim 1 is confirmed, not falsified.** 9 of 11 scored chains failed the handoff test even though
Phase 1 found a real schema present in every upstream step. This is the single most consistent
result in the whole benchmark, and it recurs for a *specific, mechanical* reason, not a vague one:

- **andon**: `andon-loop`'s topology-detection and `init-or-resume` steps don't reference
  `preflight_summary.json`'s fields at all (AND-1 FAILED); `init-or-resume`'s actual CLI signature
  (`repo_root ledger_dir`) has **no parameter slot to receive a cursor value even if it wanted to**
  (AND-3 FAILED, structurally, not incidentally). The one clean pass, AND-2, works because
  `andon-propose`'s entire JSON output is copied byte-for-byte into `andon-verify`'s dispatch
  prompt — the one place in the plugin where a handoff is coded, not just documented.
- **confab**: `cycle_engine.py`'s `plan-next-pass` — read directly from source — **has no code
  path that ever opens a domain's `*_summary.json` sidecar**. Domain selection on a fresh run is a
  hardcoded fallback list (`dependency_audit` first), confirmed live twice: once where it
  coincidentally matched the audit that had just run, once where it picked the wrong domain
  entirely against 3 real, cited findings sitting unread in the sidecar next to it. CON-3 works
  because `status_dashboard.py` does directly open `ledger.json` and the domain summaries.
- **self-assess**: two separate, confirmed-by-source design decisions, not model mistakes —
  `self-assess-autopilot` always re-derives the stage graph from scratch (no staleness/existence
  check on `stage_graph.json`), and `status.py`'s `SIDECAR_FILES` dict is a hardcoded 7-entry list
  whose docstring explicitly excludes stage-map's artifacts ("progress/synthesis artifacts, not
  findings domains"). A real, separate hook-scoping bug also surfaced live: `guard_target_edit.py`
  denies *any* absolute-path Write once `analysis/self-assess/` exists, even to paths entirely
  outside the repo.
- **cupertino**: every internal review-stage dispatch (backwards→focus, focus→longevity/integrate)
  re-sent the **verbatim original human prompt**, with zero trace of the prior stage's real,
  substantive output (a validated experience statement, a cut list, lens verdicts). A second,
  independent finding: `cupertino-council` as a literal first move — exactly as named in the
  plan's own CUP-2 chain — is **not runnable** once `.cupertino/` exists; the hook denies it with a
  real `sys.exit(2)` requiring `cupertino-backwards` first. This benchmark's own premise (that a
  user can start with council) doesn't survive contact with the actual guard.

**Named divergence finding, exactly as the plan anticipated**: `self-assess-stage-map` and
`cupertino`'s schemas score fully positive on Phase 1 (real, validated JSON contracts) and exactly
**0.00** on Phase 2 across every executed chain. Documented contract; nothing downstream parses.

---

## 2. Advisory-only family (compass, cli-scaffold)

| Plugin | Chain | Verdict |
|---|---|---|
| compass | CMP-1 clarify-scope → solve | FAILED |
| compass | CMP-2 explore-branches → solve | FAILED |
| compass | CMP-3 Decompose → Execute (internal) | **WORKED** |
| cli-scaffold | CLI-1 rust → python (negative control) | FAILED *(expected — no cross-talk found)* |
| cli-scaffold | CLI-2 python → bash (negative control) | FAILED *(expected — no cross-talk found)* |
| cli-scaffold | CLI-3 generate → verify (internal) | **WORKED** |

Against the advisory family's fixed thresholds (PASS ≥ 0.75, FAIL ≤ 0.40):

| Plugin | Ratio (in-scope chains only) | Verdict |
|---|---|---|
| compass | 1/3 = 0.33 | **FAIL** |
| cli-scaffold | 1/1 = 1.00 (n=1 — single chain, flagged as thin evidence) | **PASS** |

**compass-solve's orchestrator (`workflows/solve.js`) has no code path capable of consuming a
prior standalone skill's run at all** — no `run_id` parameter, no `state-read` call anywhere in
Clarify or Explore; `grep -rn "state-read|run_id"` across every compass `SKILL.md` returns nothing.
This is a self-contained-pipeline design choice, not a bug where the model "forgot" — worth stating
plainly since it changes how a maintainer should read the FAIL: the practical implication is that
following the README's own suggested pattern (run `compass-clarify-scope` standalone, then
separately ask `compass-solve` to think it through) produces **no continuity at all** — `solve`
silently redoes Clarify/Explore from the raw question, with no signal to the user that their first
answer didn't carry over. CMP-3 (the one WORKED case) is a fundamentally easier problem: it's the
same script's own loop reading back a variable it wrote three lines earlier, not a cross-invocation
handoff.

**cli-scaffold's one in-scope chain (CLI-3) is a clean, source-confirmed pass**: `verify_scaffold.py`
reads `cli-scaffold.manifest.json` and keys every check function off its declared fields
(`core_files`, `entry_file`, `flags`, etc.) — never off filename pattern-matching, confirmed both
by the dispatched verifier agent's own tool-call trace and by direct source read. The CLI-1/CLI-2
negative control came back clean (no incidental shared state between independently generated
scaffolds), which is the *correct*, expected result for that pre-registered check, not a defect.

---

## 3. Cross-cutting findings worth a maintainer's attention

1. **The environment this benchmark ran in has no `Workflow` tool.** `cupertino-handbook-check` and
   `compass-solve`/`compass-explore-branches` all document a `Workflow({...})` call as their real
   execution path; none of it ran as written. Every plugin's documented mechanism silently fell
   back to a manual/direct-`Agent`-dispatch substitute. This is a real gap between what the
   SKILL.md files describe and what a live Claude Code session (at least this one) can execute.
2. **Two real, previously-unknown defects surfaced as a byproduct of just running these chains**,
   independent of the handoff question itself:
   - `plugins/andon/hooks/andon_enforce.py` never imports `plugins/andon/scripts/andon_core.py` —
     the plugin's two Python surfaces don't share code, contradicting CLAUDE.md's framing of
     `andon_enforce.py` as "the reference."
   - `plugins/self-assess/hooks/guard_target_edit.py` denies any absolute-path Write once its
     output dir exists, with no check that the target is even inside the repo — it will block
     writes to unrelated locations on disk (reproduced live against a scratchpad path).
   - `plugins/confab`'s `assertion-auditor` agent returned lowercase severity values
     (`"medium"`/`"low"`) that violate its own shared schema's enum (`{"Low","Medium","High"}`) —
     would have been silently dropped by the writer script with only a stderr warning.
3. **CUP-2's chain, as named in the plan itself, is not runnable as written** once cupertino has
   been used in a repo before — `cupertino-council` is hook-gated behind `cupertino-backwards`.
   This is worth fixing in the plan's own chain list for any re-run, not just a finding about the
   plugin.

---

## Bottom line against the sharpened thesis

The original vague complaint ("not enough feedback for follow-up tasks") turns out to be **true,
but for a specific and fixable reason**: it is not that these plugins' skills lack schemas — Phase 1
found real, often well-designed ones. It's that **the orchestrating skill/script that runs next
almost never reads the schema back**, across every hook-enforced plugin and one of the two
advisory plugins. The one chain type that reliably works everywhere it was tested (andon's
propose→verify, confab's cycle→status, compass's Decompose→Execute, cli-scaffold's generate→verify)
shares one property: **the same file/script that produces the output is the one that consumes it
one step later**, in a tight, single-orchestrator loop — not a separate skill invocation reading
another skill's sidecar file cold. That's the concrete, falsifiable gap a fix should target.
