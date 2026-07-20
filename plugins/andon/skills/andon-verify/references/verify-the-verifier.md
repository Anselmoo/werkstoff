# Strategy g — Verify the verifier

Closes a real gap the other six strategies leave open: without this
strategy, a passing wired test = proof, full stop. Strategy g asks "but
is that test actually asserting anything meaningful" — two cross-plugin
dispatches to `plugins/confab/` that audit the *proof itself*, not the
code the proof is about.

## Two dispatch targets

### `confab:confab-contract-drift`

Checks whether the stage-boundary contract (types/signatures/schemas)
still matches what's actually consumed on the other side of the wire —
i.e., did the wired test pin down the *current* contract, or a stale one
that has since drifted. Confirm invocation shape against
`plugins/confab/skills/confab-contract-drift/SKILL.md` before
dispatching (it expects `args: {repoPath, contractSources, houseRules?,
skipVerification?}` when Workflow-orchestrated — this strategy passes
the wire's two stage-boundary files as `contractSources`, scoped
narrowly to this one wire, not a whole-repo sweep).

**Fires when:** the wire's proof rests on a type/signature/schema match
between two stages, and the concern is drift since that contract was
last checked.

### `confab:confab-assertion-audit`

Mutation-tests the wired test that "proved" this wire — off-by-one,
boundary flip, condition negation — to check the test would actually
catch a regression, not just execute the code path. Confirm invocation
shape against
`plugins/confab/skills/confab-assertion-audit/SKILL.md` before
dispatching (it expects `args: {repoPath, targetFiles, testFiles,
mutationTool?}` when Workflow-orchestrated — this strategy passes the
wire's implementation file(s) as `targetFiles` and the wired test file(s)
as `testFiles`).

**Fires when:** the wire's proof rests on a test that passed, and the
concern is whether that pass is meaningful (asserts real behavior) or
hollow (executes the code, asserts nothing that would catch a mutation).

## Workflow

1. **Identify what kind of proof is being audited.** If the wire's
   existing evidence doc names a contract-shaped proof (types/schemas
   matching), dispatch `confab-contract-drift`. If it names a test-shaped
   proof (a wired test that passed), dispatch `confab-assertion-audit`.
   Both, if the wire's proof mixes the two.
2. **Confirm `confab` is installed.** If neither skill resolves, degrade
   gracefully: report strategy g as unavailable for this wire — never
   hard-fail `andon-verify`'s overall run, and never silently treat the
   original proof as unaudited-but-still-green without saying so.
3. **Dispatch, scoped to this one wire** — not a whole-repo contract or
   mutation sweep. Pass only the files the wire's proof actually
   touches.
4. **Map the result to a verdict on the ORIGINAL wire, not a new one.**
   - `confab-contract-drift` finds a confirmed mismatch on this wire's
     boundary → the original wire's proof is now suspect; downgrade its
     status to ⚪ (re-proof needed) rather than leaving it 🟢 on stale
     evidence.
   - `confab-assertion-audit` finds the wired test would not catch a
     plausible mutation → same downgrade to ⚪ — a test that executes but
     doesn't assert is not proof, so the wire reverts to unproven, not
     immediately 🔴 (the underlying code might still be correct; only the
     *proof* is now known to be weak).
   - No confirmed drift and the test would catch the mutations tried →
     the original 🟢 stands, now with a strategy g "audited, holds"
     annotation in its evidence doc.

## This is additive, never a replacement

Strategy g never runs standalone as a wire's *only* proof — there must
already be a contract or test-shaped proof from some other strategy to
audit. Record both the original evidence doc and the strategy g audit
result, linked, in the wire's evidence chain (see
`okf-ledger-schema.md`'s `type: evidence` — a strategy g evidence doc's
`resource` field can point at the evidence doc it audited).
