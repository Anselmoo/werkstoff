# Strategy b — Numerical/scientific wire: oracle-gap V&V

For wires where the question is "is this number right" and there may be
no trusted answer to check against — the **oracle problem**. Extracted
from the personal `ground-truth` skill. A passing test against a number
you picked yourself only proves the code matches what you expected, not
the truth; this strategy is a set of techniques for testing **without** a
known answer.

## When this strategy fires

Per `wire-classifier.md`: the wire crosses a numerical/scientific
computation — a solver, a fit/optimization, a simulation, an ML/surrogate
kernel, a data-transform pipeline with numeric output. Not for
type/compile-level checks (Rung 0, no strategy needed) and not for prose
claims (→ strategy c).

## Phase 1 — Name the oracle gap

For the quantity the wire produces, ask: is there a trusted answer to
check against (closed form, reference dataset, analytic limit)? If not,
that absence is the signal for *which* technique below to use, not a
reason to skip verification.

## Phase 2 — Pick the technique by code kind

| Kind | Signal | Primary technique |
|---|---|---|
| Solver / PDE / ODE | discretization, mesh, time step | **Method of Manufactured Solutions** — pick an analytic solution, derive the source term symbolically, refine the grid, assert the observed order of accuracy matches the theoretical one. Catches any bug that degrades the order, not just a few lucky cases. |
| Fitting / optimization / inverse | least-squares, likelihood, parameters | **Synthetic recovery** — generate data from known parameters + known noise, assert the fit recovers them within stated uncertainty. Add identifiability (Jacobian condition number, parameter correlations) and coverage (do 1σ bars contain truth ~68% of the time, via bootstrap). |
| Simulation / Monte Carlo | sampling, ensembles | Invariants + convergence in sample size + uncertainty quantification. |
| ML / surrogate model | training, inference | Metamorphic relations + hold-out + out-of-distribution checks. |
| Data pipeline / transform | parse → compute → emit | Property-based testing (see strategy f for the general mechanism) + metamorphic relations + schema/units checks. |

**Metamorphic relations** (any numerical kernel, when no oracle exists
at all): assert necessary properties that must hold without a known
answer — scaling, permutation invariance, additivity, superposition,
conservation laws, dimensional consistency, symmetry/equivariance, known
asymptotic limits.

**Numerical reliability layer** (always worth adding when it's cheap):
report the condition number and backward error for the core computation;
measure how many digits are actually significant. A wire can be
"numerically correct" and still carry only 3 trustworthy digits — say so
explicitly rather than reporting a bare pass/fail.

## Phase 3 — Differential/cross-implementation check (when a peer exists)

If an independent implementation of the same computation exists
(elsewhere in the repo, or a well-known reference implementation), run
both and compare — agreement bounds implementation error separately from
model error. Never treat a second implementation's agreement as proof of
correctness if both share the same conceptual bug; it bounds
*implementation* divergence only.

## Output: the trust ledger entry

Every wire proven via strategy b gets one trust-ledger line in its
evidence doc: `<quantity> → <technique used> → <status>` (have/partial/
missing), plus a one-line trust statement, e.g. *"recovers params to
1e-6; 11 significant digits; conserves energy to machine epsilon."* This
is what makes the wire's evidence doc (`okf-ledger-schema.md`'s `type:
evidence`) inspectable later without re-deriving the V&V plan from
scratch.

## Verdict → wire status

- Manufactured-solution order-of-accuracy matches theory, or synthetic
  recovery hits its stated tolerance with correct coverage → 🟢.
- Any metamorphic relation violated, or order-of-accuracy degrades below
  theoretical → 🔴.
- No oracle, no surrogate relation, and no invariant available at all
  (genuinely unverifiable as written) → ⚪, with an explicit note of the
  smallest change (a conserved quantity, a limiting case) that would
  create one — never silently pass an unverifiable numerical wire.

## Relationship to the Detection Ladder

Strategy b's techniques are mostly Rung 0–2 equivalents in numerical
terms (a manufactured solution is a deterministic, complete check, not a
sampled one) — reach for a full differential/cross-implementation study
(the numerical analog of Rung 3–4) only when a cheaper technique above
can't settle the question.
