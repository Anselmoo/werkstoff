# Handbook dimensions — Testing

Apple-engineering-craft framing: clarity, restraint, consistency — a test
suite is itself a designed artifact, not just an enforcement mechanism.
Every dimension below is new material (no existing `cupertino` reference
covers testing conventions). `cupertino-handbook-draft` reads this table
to know what to analyze in an existing test suite, or scaffold as a
sensible default for a project with no tests yet.

| Dimension id | Title |
|---|---|
| `test-pyramid` | Test-pyramid / level balance |
| `test-structure` | Naming & structure of test files |
| `fixture-discipline` | Fixture/mock discipline |
| `flakiness-bar` | Flakiness & determinism bar |
| `coverage-philosophy` | Coverage philosophy |
| `test-as-docs` | Test-as-documentation clarity |
| `ci-gating` | CI gating philosophy |

## `test-pyramid` — Test-pyramid / level balance

**Rationale**: Reduction applied to test suites: a suite top-heavy with
slow end-to-end tests is a suite that costs more attention than it returns
in confidence per run.

**What the draft step analyzes/scaffolds**: the project's actual mix of
unit/integration/end-to-end tests (or the intended mix, for a project with
none yet), and any stated preference for where new coverage should land by
default.

**Detection signal**: a new end-to-end test added for behavior that a unit
or integration test could have covered just as well, at a fraction of the
runtime cost.

## `test-structure` — Naming & structure of test files

**Rationale**: Hierarchy applied to tests: a consistent naming/structure
convention lets a reader predict where a test for a given piece of code
lives, without searching.

**What the draft step analyzes/scaffolds**: the project's existing test
file naming and directory-mirroring convention (or Given/When/Then vs.
Arrange/Act/Assert structure within a test body), codified as the stated
house convention.

**Detection signal**: a new test file that doesn't follow the codebase's
own established naming/location convention relative to the code it tests.

## `fixture-discipline` — Fixture/mock discipline

**Rationale**: A test that mocks away the real contract it's supposed to
verify can pass while the real integration is broken — over-mocking hides
exactly the kind of drift this handbook lifecycle exists to catch.

**What the draft step analyzes/scaffolds**: how much of the current test
suite relies on mocks/stubs vs. real collaborators, and whether any stated
project convention exists about when mocking is and isn't appropriate. If
`confab` (or specifically `confab-assertion-audit`) is present in the
current session's Skill list, name it as complementary here — it audits
whether existing tests would actually catch a plausible mutation, a deeper
check than this handbook's dimension attempts.

**Detection signal**: a new test that mocks the exact boundary the test's
own name claims to be verifying (e.g. a test named "database round-trip"
that mocks the database).

## `flakiness-bar` — Flakiness & determinism bar

**Rationale**: A test that fails intermittently trains engineers to ignore
red CI — the opposite of the trust a test suite exists to build.

**What the draft step analyzes/scaffolds**: whether the project has any
stated policy on time-based waits, network calls, or shared mutable state
in tests, and codifies the project's actual determinism bar.

**Detection signal**: a new test containing an unconditioned `sleep`/fixed
delay, a real network call with no mock/fixture, or reliance on test
execution order.

## `coverage-philosophy` — Coverage philosophy

**Rationale**: Reduction applied to a metric: line-coverage percentage is
easy to game and easy to over-value; this dimension exists to state the
project's actual philosophy explicitly rather than leave "more coverage is
always better" as an unexamined default.

**What the draft step analyzes/scaffolds**: whether the project already
states a coverage philosophy (behavior-coverage over line-coverage, a
minimum threshold, or an explicit "no threshold, judgment call" stance),
scaffolding a stated default (behavior-coverage over line-coverage,
restraint against vanity metrics) if none exists yet.

**Detection signal**: new production code with no corresponding behavior
test at all — the philosophy this dimension states matters only once it
has a concrete non-zero-coverage case to apply to.

## `test-as-docs` — Test-as-documentation clarity

**Rationale**: A well-named test is executable documentation of intended
behavior — the same "clarity over cleverness" principle the code domain's
`comment-philosophy` dimension states, applied to test names and
structure.

**What the draft step analyzes/scaffolds**: whether existing test names
already read as a specification of behavior ("returns empty list when no
matches") vs. implementation detail ("test_function_2"), and states the
target convention.

**Detection signal**: a new test named generically (`test1`, `test_edge_case`)
with no indication in the name of what behavior it verifies.

## `ci-gating` — CI gating philosophy

**Rationale**: What blocks a merge is itself a design decision — too
strict and velocity suffers for marginal gains, too loose and the suite's
signal degrades.

**What the draft step analyzes/scaffolds**: the project's actual CI
configuration (which checks are required vs. advisory) and states that as
the handbook's convention, rather than inventing a policy the project
hasn't chosen.

**Detection signal**: a new CI-relevant check added without being wired
into the required/advisory gating the handbook states — silently
non-blocking when it should be required, or vice versa.
