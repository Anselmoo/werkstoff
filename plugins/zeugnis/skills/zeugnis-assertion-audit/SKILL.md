---
name: zeugnis-assertion-audit
description: "Use when the user asks whether their test suite would actually catch bugs, wants a mutation-testing pass over target source and test files, asks to check for weak or tautological assertions, or wants zeugnis's assertion audit run. Not for proving that a specific change, fix, wire, or numeric claim is correct -- use andon:andon-verify for adversarial verification of a change; this skill judges only the tests. Every finding is labeled real-tool or llm-reasoned."
---

Check whether the given test files would actually catch plausible
mutations to the given target source files. This skill's Verify phase is
NOT optional — there is no `--skip-verification` flag on this domain's
writer script, and `scripts/assertion_audit.py` requires a `--verify-json`
argument it will refuse to run without. Do not look for a way to make
this run faster by skipping it; the capability does not exist.

## Steps

1. Determine `repo_root`, the target source files and the test files. If
   the user wants a real mutation tool (e.g. `mutmut`), run it through the
   harness first. The agent cannot run it: the tool writes mutants into
   its working directory, and the Bash hook denies it outside a harness
   copy. Run `scripts/mutation_harden.py prepare`, `run-shard` and
   `collect`, exactly as steps 2-4 of `zeugnis-mutation-harden` describe,
   or reuse a results file a run already produced. With no real tool, the
   agent falls back to llm-reasoned findings with a `fallbackReason`.
2. Optionally build (or reuse, if `zeugnis-cycle` already built one this
   invocation — see "Shared symbol index" below) a symbol index of the
   target files for the agent to use as evidence.
3. Dispatch the `assertion-auditor` agent in **Find mode**: give it the
   target files, test files, the harness results file (if step 1 produced
   one), and the symbol index (if built) — if step 2 was skipped, tell the
   agent no symbol index exists and it should read the target files
   directly instead. Ask for `{"findings": [...]}` where each finding has
   `toolSource` set: `"real-tool"` with `resultsFile` and `mutantId` for a
   mutant read from that results file, `"llm-reasoned"` with an explicit
   `fallbackReason` otherwise. Write its output to a scratch JSON file.
4. Dispatch the `assertion-auditor` agent AGAIN, in **Verify mode**, once
   per Find-phase finding (or as a batch if your dispatch prompt makes the
   per-finding independence explicit) — a fresh, independent read of the
   source and tests, not a rubber stamp of step 3's description. Write
   `{"findings": [{"evidence": "...", "confirmed": true|false}, ...]}` to
   a second scratch JSON file.
5. Run:
   ```
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/assertion_audit.py" <repo_root> \
       --find-json <path-from-step-3> \
       --verify-json <path-from-step-4> \
       [--requested-tool <name>]
   ```
   This reconciles Find against Verify in three buckets: `confirmed: true`
   survives, `confirmed: false` is dropped as refuted, and anything else
   (key missing, non-boolean, no record for a finding) is an abstain that is
   kept as `verification: "unverified"`, warned about on stderr and counted
   in the summary's `unverifiedCount` (an abstain is never a pass), drops
   every real-tool finding whose `resultsFile`/`mutantId` citation does not
   re-derive from the tool's own sidecar,
   forces every surviving finding's `fixability` to `"advisory"`, and
   writes `analysis/zeugnis/reports/ASSERTION_AUDIT.md` (real-tool and llm-reasoned
   findings in clearly separate sections — never blended) and
   `analysis/zeugnis/assertion_audit_summary.json`.
6. Report the finding count, split by `toolSource`, to the user.

## Shared symbol index

If this skill is running as one pass inside `zeugnis-cycle`, do not build
your own symbol index from scratch — call
`scripts/lib/symbol_index.get_or_build_snapshot` (or the CLI wrapper the
cycle skill points you at) with the SAME `invocation_id` the cycle
provided. Building it twice inside one cycle invocation violates the
single-flight rule the rest of the plugin relies on.

## What NOT to do

- Do not present findings without having run step 4 — a Find-only result
  is not a valid assertion-audit output, and the writer script will
  refuse to run without `--verify-json` regardless.
- Do not mark any finding `fixability: "fixable"` — ask the agent to
  always use `"advisory"`; the writer script forces it regardless, but a
  request that already respects the rule wastes less of the agent's
  effort correcting itself.
- Do not run `mutmut run` or `mutmut apply` in the working tree to get a
  real-tool label: the hook denies it, and a real-tool finding is only
  accepted with a harness citation anyway. To also write the tests that
  kill the survivors, use `zeugnis-mutation-harden` instead.
- Do not silently merge real-tool and llm-reasoned findings into one
  table when reporting to the user — keep the same separation the
  Markdown report uses.
