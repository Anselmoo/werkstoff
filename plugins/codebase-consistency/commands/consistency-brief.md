---
description: Synthesize discovery into a phased Consistency Brief — the approved plan /consistency-align executes against
argument-hint: <area-dir>
---

Synthesize everything in `analysis/$1/` into a **Consistency Brief** — the
document a maintainer approves before anything gets rewritten.

Read `analysis/$1/consistency.json`, `analysis/$1/matrix.json`, and
`analysis/$1/PATTERN_CARDS.md`/`CANON.json` first. If any are missing, say
so and stop — they come from `/consistency-scan`, `/consistency-map`, and
`/consistency-canonize` respectively. Read `analysis/$1/PREFLIGHT.md` too,
if it exists — its Check 0 answers (prior attempts, off-limits areas) and
Check 3 result (whether verification can be executable or only structural)
constrain this plan more than anything derivable from the source.

**Staleness check:** if any input is newer than an existing
`CONSISTENCY_BRIEF.md`, regeneration is expected. If an existing brief is
newer than all inputs and the user re-ran this anyway, ask what changed.
Note input timestamps in the brief's header either way.

## The Brief

Write `analysis/$1/CONSISTENCY_BRIEF.md`:

### 1. Objective
One paragraph: what's inconsistent, roughly how much of the area it
touches, why fix it now.

### 2. Canon Summary
Table: dimension, provenance (documented/derived-majority/synthesized-new/
needs-human-decision), canonical form (one line), sites to align,
confidence. Pull `needs-human-decision` dimensions into their own
called-out block — **the plan does not include a phase for these until a
person answers the open question.**

### 3. Phased Sequence
Order phases **dependency-first, not size-first**: if dimension A's
canonical form is a shared base class, interface, or utility that
dimension B's alignment depends on (e.g. "unify the error type" must land
before "unify how call sites handle errors"), A's phase comes first,
regardless of which has more sites. Otherwise, order by blast radius,
smallest first — smallest-first here (not largest-first, unlike a
legacy-modernization plan) because the goal is to bank early, reversible
wins and calibrate `/consistency-align`'s batch behavior on low-risk
dimensions before spending it on the biggest one.

For each phase:
- Scope (which dimension(s), which modules)
- Entry criteria (what must be true to start — e.g. "Phase 1's shared
  error type is merged and its own tests pass")
- Exit criteria (what `/consistency-verify` must show)
- Relative scale (site count, not a duration estimate)
- Risk + top risk + mitigation (a `derived-majority` phase with High
  confidence is low-risk; a `synthesized-new` phase is inherently higher —
  say so plainly)

Render as a Mermaid `flowchart LR` showing phase sequence and
dependencies. No `gantt` chart — this plan makes no time claims.

**Phase 1 is a pilot.** Whichever phase's dimension has the most divergent
sites gets **one representative module** aligned first, in-session, before
`/consistency-align`'s batched fan-out runs on the rest. Say explicitly
that what the pilot surfaces (a divergent site the scan missed, a canonical
form that doesn't actually fit one module's constraints) is expected to
revise this brief, and a regenerated brief after the pilot is normal.

### 4. Per-Dimension Detail
For each in-scope dimension: the full basis from its Pattern Card
(frequency/maturity/recency), the phase it belongs to, and one worked
example diff (before → after) so a reviewer can see exactly what changes.

### 5. Validation Strategy
State what `/consistency-verify` will run per phase: full test suite,
targeted subset, or structural-diff-only (if `/consistency-preflight`
Check 3 came back red). Justify per phase if it differs.

### 6. Open Questions
Every `needs-human-decision` dimension from Pattern Cards, each as a
checkbox the approver must resolve before its phase can be added to a
future brief.

### 7. Approval Block
```
Approved by: ________________  Date: __________
Approval covers: Phase 1 only | Full plan
```

## Present

Present a summary and **stop — write nothing further until the user
explicitly approves** (use plan mode if the session supports it). This
gate is the human-in-the-loop control point; silence is not approval.
