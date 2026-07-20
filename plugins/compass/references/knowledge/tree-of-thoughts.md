---
type: prompting-technique
title: Tree-of-Thoughts
description: Generate genuinely distinct branches, score each on explicit dimensions, then select and expand the strongest — rather than anchoring on the first idea.
resource: ../examples/tree-of-thoughts.prompt.md
tags: [compass-explore-branches]
timestamp: 2026-07-15T00:00:00Z
---

# Tree-of-Thoughts

For decisions with multiple viable, meaningfully different paths:
generate 3 genuinely distinct branches (not variations of one idea),
score each on Feasibility/Impact/Risk, then select the strongest and
identify what would need to happen next.

## Mechanism

Phase 1 — generate 3 named branches, each a genuinely different
direction. Phase 2 — score each 1-10 on Feasibility, Impact, Risk, plus
name the biggest unknown/blocker. Phase 3 — select the highest scorer
(ties broken toward lower risk), list first concrete actions.

## When to apply

- Decisions with multiple viable, meaningfully different paths
- Strategic/architectural choices where anchoring on the first idea is
  a real risk

## Examples

### In `../examples/tree-of-thoughts.prompt.md`

A 20-person startup choosing a market-entry strategy: niche
specialization vs. distribution partnership vs. price disruption.

### In werkstoff

**This very session's own `superpowers:brainstorming` process is a live
Tree-of-Thoughts instance**: "Propose 2-3 different approaches with
trade-offs... lead with your recommended option" is Phase 1+2 in prose
form, applied to every design decision in this repo (e.g. the "Approach
A/B/C" scope choice for the `confab` plugin, or the
skill-count/architecture options presented for `compass` itself).
`compass-explore-branches` (`plugins/compass/workflows/explore-branches-scan.js`)
formalizes this exact process — parallel branch-proposer agents pinned
to distinct angles, deterministic scoring/selection in plain JS — as a
reusable skill instead of ad hoc brainstorming prose.
