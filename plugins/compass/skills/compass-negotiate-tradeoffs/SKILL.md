---
name: compass-negotiate-tradeoffs
description: This skill should be used after compass-explore-branches has already selected a winning approach, when the user wants to combine strengths from two or more of the branches rather than accept the single winner as-is — "can we get the best of both", "is there a middle ground between these", "combine the speed of A with the safety of B", or when the winning branch's own blocker is something a losing branch's approach would have avoided. Not a replacement for compass-explore-branches's selection step, and not for generating branches in the first place — this skill only synthesizes a hybrid from branches that already exist and have already been scored.
---

Synthesize a hybrid approach from 2-3 already-scored branches — combining
the resource efficiency of one with the ambition of another, for
example — rather than treating branch selection as strictly
winner-take-all. Built on two techniques from this plugin's own technique
set, generalized from their original domains:

- `graph-prompting.prompt.md`'s indexed-triple mechanism
  (`../../references/knowledge/graph-prompting.md`): map each branch's
  claims and constraints as numbered `(subject, predicate, object)`
  triples, identify which nodes are compatible across branches (shared
  goals) and which conflict (resource trade-offs), then traverse only
  the conflicting edges to find resolution points — generalized here
  from entity-relationship traversal to reconciling competing approaches.
- `reflexion.prompt.md`'s score-against-criteria mechanism
  (`../../references/knowledge/reflexion.md`): score the resulting
  hybrid against each source branch's own Feasibility/Impact/Risk
  profile to confirm it actually outperforms every source branch on at
  least one axis — generalized here from draft-quality scoring to
  hybrid-vs-source comparison.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified constraints that apply across every `compass-*`
skill.

**This skill does not replace `compass-explore-branches`'s selection.**
It runs strictly *after* a winner is already selected, as an optional
additional deliverable — never instead of picking a winner, and never as
a way to avoid committing to one.

## Step 0 — Confirm inputs

This skill needs:
- A **scoped problem** (the same one the branches were generated against).
- **2-3 branch descriptions**, each in `compass-explore-branches`'s own
  output shape: `{name, description, angle, scores: {feasibility,
  impact, risk}, total, blocker}` (see
  `../../references/pipeline-cheatsheet.md`'s Branch-shape section for
  the exact contract). Usually the already-selected winner plus its 1-2
  closest runners-up by total score — do not synthesize from branches
  that scored far apart, since a hybrid combining a strong branch with a
  genuinely weak one rarely beats the strong branch alone.

If invoked standalone with fewer than 2 branches available, say so
plainly and suggest running `compass-explore-branches` first — there is
nothing to synthesize from a single branch.

## Step 1 — Map claims and constraints as indexed triples

For each branch, extract its load-bearing claims and constraints as
numbered triples, per `graph-prompting.md`'s convention
(`B1-T1: (branch-name, requires, constraint)`, `B1-T2: (branch-name,
achieves, outcome)`, …). Do this for every branch being synthesized, not
just the winner.

Then classify node relationships across branches:
- **Compatible nodes** — the same goal or constraint appears (possibly
  phrased differently) in more than one branch's triples. These are
  free: the hybrid can adopt them from whichever branch states them most
  concretely.
- **Conflicting nodes** — branches make incompatible claims about the
  same resource or constraint (e.g. one requires a dependency the other
  explicitly avoids; one assumes sequential work the other assumes
  parallel). These are the actual negotiation surface.

## Step 2 — Traverse conflict edges to find resolution points

For each conflicting node pair, traverse the specific triples on both
sides (citing `B1-T?` / `B2-T?`) and ask: is there a resolution that
keeps most of what each side was optimizing for, even if neither side
gets it exactly as originally stated? Not every conflict resolves — some
are genuinely exclusive (e.g. "build" vs. "buy" for the same
subsystem). Where a conflict is genuinely exclusive, the hybrid must
pick one side explicitly and say so, rather than blur the two branches
together into something incoherent.

Draft the hybrid approach from: every compatible node (adopted directly)
plus every resolved conflict (stated as the resolution, citing which
triples it kept from which branch) plus an explicit call-out of any
unresolved, genuinely-exclusive conflict and which side the hybrid
picked.

## Step 3 — Score the hybrid against its source branches

Score the hybrid on the same Feasibility/Impact/Risk rubric
`compass-explore-branches` uses (1-10 each), then compare directly
against each source branch's own scores:

| Axis | Branch A | Branch B | Hybrid |
|---|---|---|---|
| Feasibility | | | |
| Impact | | | |
| Risk | | | |

The hybrid must outperform every source branch on **at least one axis**
to be worth presenting as a distinct option — if it doesn't (a hybrid
that's merely feasible-average across all three axes, beating nothing),
say so plainly rather than presenting it as if it were strictly better.
A hybrid that loses on every axis to its strongest source branch is a
finding, not a failure to hide: report it and recommend sticking with
the original winner instead.

## Step 4 — Present

Present, in this order:

1. **Trade-off matrix** — what each source branch gives up in the
   hybrid, and what the hybrid preserves from each.
2. **The hybrid approach** — name and description, same shape as a
   regular branch.
3. **Score comparison** (Step 3's table) and the verdict — does the
   hybrid outperform its sources on at least one axis, and which one.
4. Any unresolved, genuinely-exclusive conflicts and which side the
   hybrid picked for each.

## Relationship to `compass-explore-branches`

Invoked only after `compass-explore-branches` has already selected a
winner — never as a substitute for that selection, and never run
automatically. `compass-solve/SKILL.md`'s Step 2 offers this skill to the
user after presenting the winning branch, as an optional refinement the
user can decline.
