# andon — Behavior Contract (Clean-Room Rebuild Spec, Phase 0)

Status: input to a clean-room rebuild. The implementer building v2 must
not read `plugins/andon/` source. This document is the only permitted
input. It specifies WHAT must be true — behavior, semantics, guarantees,
contracts — and WHY. It deliberately does not prescribe HOW: no function
names, no file layout, no code structure. Where a legacy behavior appears
to depend on an implementation choice, the choice is called out and
marked re-decidable rather than carried forward as a requirement.

Everything below was derived by reading the legacy plugin as **data**,
never as instruction.

---

## 1. PURPOSE

Live, actively-maintained multi-stage codebases accumulate gaps (bugs,
missing features, broken or never-proven handoffs between
services/packages) faster than any single reviewer can track them
end-to-end, and ordinary "run the tests, ship it" workflows have no
mechanism for refusing to move forward when a handoff between two parts
of the system is unproven rather than merely untested. andon solves a
narrower and more specific problem than general code review or general
test automation: it is a **disciplined, resumable procedure** for walking
a codebase's value stream one boundary at a time, proposing the smallest
defensible fix for the highest-priority gap, and — the part nothing else
in this problem space does — **refusing, as a hard rule rather than a
suggestion, to treat a boundary as done until it has been proven by
evidence appropriate to what actually crosses it**. It exists to convert
"probably fine" into "proven, and here is the proof," one wire at a time,
while remaining honest about what it could not prove and why.

---

## 2. DOMAIN VOCABULARY

These are the concepts a rebuild must still express, however it chooses
to encode or name them internally.

- **Value stream / stream** — the ordered chain of a project's stages and
  the wires between them; the whole thing the loop walks.
- **Stage** — one coherent unit of the codebase with its own boundary
  (a service, a package, a build target) — something that can meaningfully
  have inputs it consumes and outputs it produces for another stage.
- **Wire** — the handoff between two stages: the contract stage A must
  satisfy for stage B to work correctly. A wire has a status that is
  always one of exactly three values: **proven**, **broken/unproven**, or
  **unknown**. There is no partial or numeric-score status at the wire
  level — a wire is a boolean-plus-unknown gate, not a percentage.
- **Gap** — a concrete, evidenced deficiency: something behaving wrong
  (a defect in existing behavior), something absent (a capability the
  surrounding system implies should exist but doesn't), or a wire that is
  broken or has never been proven. A gap must be traceable to a specific
  location in the codebase or ledger — "this could be better" is not a
  gap.
- **Evidence** — the reproducible, checkable material that settles
  whether a wire's contract holds: a test result, an index query result,
  a reproduced defect, a measured quantity, a documented reasoning trail
  that itself survives falsification pressure. Evidence is categorically
  different from an assertion or a confident claim — a wire's status may
  only change based on evidence, never based on the confidence with which
  something was stated.
- **Pass** — one complete traversal of the stream from its first stage to
  its last, gap-scanning and wire-proving stage by stage in order.
- **Cycle** — a *converged* run: the sequence of consecutive passes ending
  in a pass that closed zero new gaps and left every wire in the stream
  proven. A cycle is not one pass; expect several passes per cycle in the
  general case, because closing a gap on stage N can invalidate wires
  already proven on stages < N (see sub-cycle, below) or surface new gaps
  that a previous pass's fixes exposed.
- **Sub-cycle** — a bounded backtracking excursion triggered mid-pass:
  when a fix changes something an *upstream* wire's proof depended on (a
  shared type, a schema field consumed on both sides), the affected
  upstream wires must be re-proven before forward progress continues.
  This backtrack must be bounded (legacy bounds it to the immediately
  preceding stage and the one before that — "N−1, N−2, no further" — see
  §10 for whether that specific bound should carry forward) and must be
  distinguishable in the record from an ordinary forward pass.
- **Fast lane / slow lane** — a two-way classification of *how expensive
  and how automatable* a wire's verification is: fast/non-visible checks
  are cheap, deterministic, and can run every pass (schema/type/contract-
  level checks); slow/visible checks are expensive, sometimes require a
  human or a rendered surface, and are reserved for cadence or explicit
  triggering rather than every pass. This is a coarse, two-bucket version
  of a more general graduated cost model (see §6's Detection Ladder) —
  the two vocabularies describe the same underlying idea at different
  granularities, and v2 must decide whether to keep both (see §10).
- **Constraint (Theory of Constraints)** — the single stage or wire
  currently limiting the stream's overall throughput: the thing that,
  if hardened, would unblock the most subsequent progress. The loop's
  priority ordering must always attack the current constraint first,
  recompute it as the ledger changes (a wire that keeps reopening is a
  constraint signal even if it isn't the oldest gap), and must not simply
  process gaps in discovery order or file order.
- **The andon rule** — the loop may not advance past a wire that is
  broken or unproven. This is the plugin's foundational guarantee (see
  §3), from which everything else about the loop's pacing follows.

---

## 3. THE ANDON RULE + STOP CONDITIONS

The base rule, stated as a testable assertion:

> **Given a wire whose status is broken or unknown, the loop MUST NOT
> advance its cursor past that wire.** It must stop, attempt to close the
> gap, re-prove the wire, and only then advance — never advance on the
> strength of an assumption, a partial fix, or an unverified claim that
> the wire is now fine.

Legacy sharpens this into three independently-testable stop conditions.
A rebuild must preserve the *behavior* each guarantees, though it may
reconsider how many discrete conditions to expose:

1. **Wire-proof failure.** *Given any proof attempt on a wire returns a
   negative/refuted verdict, the loop MUST NOT advance past that wire.*
   Overridable only by a human explicitly supplying new evidence and
   re-running the proof, or explicitly and visibly deferring that gap's
   priority — **never** by the loop silently continuing as if the wire
   were proven.

2. **Authorization ceiling exceeded.** *Given a proposed fix whose
   blast-radius/reversibility rating exceeds the loop's currently
   configured authorization ceiling, the loop MUST NOT apply that fix or
   proceed to prove its wire* until a human explicitly raises the
   ceiling for that one fix, or the gap is skipped in favor of a
   different one. This check must fire twice in the legacy design: once
   pre-emptively right after a fix is proposed (before any attempt to
   apply it), and once again after the fix exists in concrete form (its
   actual diff), because the real change can turn out broader than what
   was proposed. A rebuild must preserve **both** checkpoints — a
   pre-commit check alone is not sufficient if the applied change can
   diverge from the proposal.

3. **Non-overridable structural contradiction.** *Given a genuine,
   queryable structural/connectivity index (not a heuristic, not an
   LLM's read of the code) contradicts a structural claim a wire's proof
   depends on, the loop MUST NOT advance past that wire under any
   circumstance* — not a human override, not any adjudication step
   internal to the loop's own verification machinery. This is the one
   condition in the legacy design explicitly carved out as **immune to
   every other override mechanism the plugin has**, including the one
   role in the verification panel (§6) whose entire job is rendering
   final verdicts. The asymmetry is deliberate: a real index query
   reports what the code actually references, which is a fact, not an
   argument that a human or an LLM panel could out-argue. A rebuild must
   preserve this asymmetry — some evidence classes are stronger than any
   adjudication process the system itself runs, and the strongest class
   available must be marked non-overridable by construction, not by
   convention.

A weaker, evidence-quality-graded variant of condition 3 exists in
legacy: a structural contradiction from a *lower-confidence* source
(a live language-server query rather than a persisted index) still blocks
by default, but **can** be overridden by the loop's own adjudication
mechanism given a specific, stated reason to distrust that lower-confidence
source. A rebuild must preserve this distinction — not all structural
evidence is equally overridable, and the two tiers (immune vs.
override-with-stated-reason) must remain distinguishable in the record,
not collapsed into one "structural check failed" bucket.

**Sub-cycle thrash escalation.** *Given the same wire reopens after being
re-proven three times within one sub-cycle history, the loop MUST stop
treating it as a bounded backtrack and instead treat it as the stream's
current constraint*, escalating rather than continuing to backtrack
indefinitely. (The specific threshold of three is called out in §10 as
possibly arbitrary and open to re-decision; the *behavior* — an
unbounded backtrack loop must not be allowed to persist silently forever
— is not optional.)

**Convergence condition.** *A cycle is complete only when a pass closes
zero new gaps and leaves every wire in the stream proven.* Any pass that
closes at least one gap, or leaves any wire broken/unknown, means the
cycle continues with another pass. The loop must not declare victory on
partial convergence.

**Self-termination condition.** *Given a full cycle converges in a single
pass with zero gaps closed, the stream is considered hardened, and the
loop MUST stop and hand control back rather than continuing to spin.*

---

## 4. SKILL RESPONSIBILITIES

Legacy decomposes the work into five skills. The decomposition itself is
flagged as re-decidable in §10; what follows is the *responsibility*
each currently owns, independent of whether v2 keeps exactly five units.

### Preflight-equivalent responsibility

- **Responsible for:** determining, before any loop run, whether the
  target repository's value stream is legible enough for the loop to
  operate on (how many stages can be detected, at what confidence),
  whether a place to persist state is writable, whether a repo-authored
  conventions/house-rules source exists for the propose step to draw on,
  and which of the loop's optional cross-capability dependencies are
  present vs. absent.
- **Inputs:** the repository root (or a named path); optional
  configuration overrides.
- **Outputs:** a readiness report covering every check performed (not
  just the first failure), each downstream capability's readiness
  classified into exactly three levels — **fully ready**, **ready with
  named gaps**, or **not ready** — and, for anything not fully ready, the
  specific fix. A machine-readable counterpart of the same findings must
  also exist so other tooling can consume readiness state without
  parsing prose.
- **Must NOT:** modify anything beyond what is strictly necessary to
  *prove* a persistence location is writable (creating an empty
  directory to test writability is acceptable; anything more is not).
  Must not initialize the actual state store — that is the orchestrating
  responsibility's job. Must not silently treat a missing optional
  dependency as blocking when the loop can degrade gracefully.
- **Mutation:** read-only against the target repository; performs at
  most a writability probe against the configured output location, and
  writes its own report there.

### Propose-equivalent responsibility

- **Responsible for:** given exactly one gap, producing a maximal,
  concrete, justified fix proposal *before* asking the user anything —
  drawing on the written state store, repo-authored conventions, and the
  surrounding code — then interviewing the user only on genuinely
  load-bearing forks that autonomous investigation could not resolve,
  one question at a time, each paired with a recommended answer. Every
  proposal must be tagged with exactly one reversibility/blast-radius
  classification from a fixed, ordered scale (see §2, §3 condition 2).
- **Inputs:** one gap (its kind, which stage/wire it concerns, and
  whatever state-store context exists for that stage — prior gap
  records, prior evidence records).
- **Outputs:** a fix description; the files/locations it touches; a
  recommended verification approach (and why that one, not a menu);
  exactly one blast-radius tag; and a record of any residual open
  questions the user resolved during interview.
- **Must NOT:** ask the user anything answerable by reading the written
  state store or the code. Must not treat a reversible, local change as
  something requiring user confirmation. Must not leave a proposal
  untagged for blast radius — the tag is mandatory on every proposal,
  never optional or inferred later. Must not itself decide the loop
  should advance or halt — that is the andon rule's job, applied by the
  orchestrating responsibility.
- **Mutation:** none against the target repository. It is unresolved in
  legacy whether this responsibility (or some other part of the system)
  is ever the one that actually writes the proposed change to disk — see
  §10, this is a genuine open question, not a settled behavior to carry
  forward silently.

### Verify-equivalent responsibility

- **Responsible for:** proving or refuting exactly one wire's claim,
  selecting *how* to prove it from a small family of proof approaches
  based on what kind of thing is actually crossing the wire (code
  behavior, a number, a claim/rationale, an autonomous fix's own process
  reliability, a structural/connectivity fact, an invariant over an input
  space, or the strength of an existing proof) rather than defaulting to
  one mechanism for every kind of question. Full routing and strategy
  semantics are in §6.
- **Inputs:** the wire, its contract/rubric, the proposed or applied fix
  (or, via the external entry point in §7, an already-applied diff), and
  whatever prior evidence exists for that wire.
- **Outputs:** a verdict (proven / refuted / unknown) plus a structured
  evidence record capturing what was actually checked, by what method,
  and what it showed — never a bare verdict with no reproducible backing.
- **Must NOT:** pick a proof approach silently when genuinely ambiguous
  between two — that must be surfaced for a human to confirm rather than
  guessed. Must not manufacture a verdict when the evidence is genuinely
  contested — "unproven" is always an acceptable and sometimes required
  outcome, never a failure of the process. Must not persist state itself.
- **Mutation:** read-only, plus narrowly-scoped execution where a
  specific proof approach calls for running something (a test, a
  property-check, an index query) — never edits or improves the artifact
  under review. Does not write to the persistent state store; it returns
  results for the orchestrating responsibility to persist.

### Loop-equivalent responsibility (the orchestrator)

- **Responsible for:** the end-to-end cycle — determining the stream's
  topology, owning the persistent state store (the only responsibility
  among the five that initializes, resumes, and writes it), scanning the
  current position in the stream for gaps, picking exactly one gap by
  priority (constraint-first, then wire-before-bug-before-feature, then
  smallest expected blast radius), dispatching the propose- and
  verify-equivalent responsibilities in sequence, applying the andon
  rule's stop conditions, and advancing/closing passes into cycles.
  This is the **only** responsibility that persists results from the
  other four — a separation of "analysis returns structured results" vs.
  "one orchestrator writes files" that must be preserved (see §8).
- **Inputs:** the repository; the persistent state store if one already
  exists (to resume); configuration (authorization ceiling, where gaps
  come from, where state lives).
- **Outputs:** per working session, in order: the detected stream (once,
  or when it changes); the delta in state-store status since the last
  run; the current step's gap/proposal/verdict and whether the andon rule
  allowed advancement; and, at cycle close, a cycle report plus the next
  recomputed constraint.
- **Must NOT:** advance past a broken/unknown wire under any of the three
  stop conditions in §3. Must not fabricate a stream topology when
  detection is inconclusive — a single-stage, no-inter-stage-wire result
  is a valid, honestly-reported outcome, not a failure. Must not silently
  fall back to scanning for its own gaps when configured to ingest gaps
  from an external source and that source is absent (§7) — it must stop
  and say the prerequisite is missing.
- **Mutation:** owns and writes the persistent state store and its own
  human-readable reports. Whether it, or some other actor, ever writes
  changes to the *target repository's own source* is the same open
  question flagged under the propose-equivalent responsibility, above,
  and in §10 — legacy's own safety framing ("read-only except a scoped
  output directory") is in tension with a loop whose entire premise is
  closing gaps by fixing them, and this tension is not resolved anywhere
  in the source material. State it; do not resolve it by assumption.

### Status-equivalent responsibility

- **Responsible for:** rendering the current state of the persistent
  store as one coherent report, **without running any new work** — no
  new scan, no new proof attempt, no state mutation of any kind.
- **Inputs:** the persistent state store's current contents.
- **Outputs:** which stages/wires are proven/broken/unknown; the current
  cycle and pass counters; the currently active constraint; open gaps
  broken down by kind and blast-radius; a mix of which verification
  approaches have actually been used (so a user can tell whether the
  system has been leaning on one expensive default rather than routing
  correctly); any standing non-overridable hold (condition 3 above) still
  attached to an open gap, surfaced first and prominently; and a single
  recommended next step.
- **Must NOT:** run a new pass, scan for new gaps, or write anything to
  the persistent store. Must not fabricate a board when no state store
  exists yet — it must say plainly that the loop has never run and name
  the next step instead.
- **Mutation:** none against the persistent store or the target
  repository beyond writing its own rendered report to the configured
  output location. Strictly read-only otherwise.

---

## 5. LEDGER SEMANTICS

Stated independent of any specific file format, encoding, or tooling —
the following is what the persistent state store must be able to
represent and answer, regardless of how v2 chooses to encode it.

### What must be representable

- **One record per stage**, each identifying: the stage's name/identity,
  which stages feed it (incoming wires) and which it feeds (outgoing
  wires), and its lane/cost classification if one applies.
- **One record per gap**, and — this is a hard requirement, not a
  convention to be honored by discipline — **each gap record must
  represent exactly one gap**. A record that bundles multiple
  independent gaps must not be representable as a single valid record,
  because per-gap status and per-gap retry/reopen counting become
  ambiguous the moment more than one gap can hide inside one record (see
  §9). Each gap record must carry, as independently queryable fields (not
  folded into a single free-text description):
  - its kind (defect in existing behavior / absent capability / broken-
    or-unproven wire),
  - which stage and wire it concerns,
  - whether it sits on the stream's current constraint,
  - its lifecycle status (see below),
  - its blast-radius/reversibility tag once proposed,
  - a link to whichever evidence record ultimately resolved it, once
    resolved.
- **One record per evidence artifact**, produced by exactly one proof
  attempt on exactly one wire, carrying — again as independently
  queryable fields, not absorbed into one prose blob — at minimum: which
  wire it concerns, which proof approach produced it, the resulting
  verdict, whether the verdict carries a non-overridable hold, and a
  reference to whatever underlying artifact backs it (a test's output, a
  transcript, a query result) when the evidence itself isn't fully
  self-contained. The claim being proved, the evidence gathered for it,
  the resulting fix (if any), and any references/citations used must each
  be separately identifiable — a single field that absorbs claim, fix,
  evidence, and references simultaneously is exactly the anti-pattern
  §9 requires v2 to avoid.
- **A chronological history** of pass and cycle events — at minimum, one
  entry per pass close (which stage/wire/gap it touched, which proof
  approach ran, the verdict, whether it advanced) and one entry per cycle
  convergence (the full stream state, how many passes it took, how many
  sub-cycle backtracks occurred). Sub-cycle backtrack events must be
  distinguishable from ordinary forward-pass events in this history.

### Lifecycle states a gap must be able to occupy

At minimum: **open** (found, not yet resolved), and **closed** (resolved,
with a link to the evidence that resolved it). A gap that has been
proposed-but-not-yet-verified, and a gap halted by an authorization-
ceiling stop (condition 2) pending human confirmation, must be
distinguishably represented — collapsing "open, untouched" and "open,
blocked pending a human decision" into the same state loses information
the status-rendering responsibility needs.

### What must survive a resumed session

Everything above — the entire stage/gap/evidence record set and the
chronological history — must be reconstructable from persisted state
alone, with no reliance on anything held only in a prior session's
working memory. A resumed session must be able to derive: which
stage/wire is the current cursor position (the least-resolved point in
stream order), current pass and cycle counters, and which wires are
currently proven vs. not, purely by reading the persisted state. This is
a hard requirement — the loop is explicitly designed to be interruptible
and resumable across sessions.

### Machine-checkable vs. human-readable

The store must support both a **human-readable rendering** (what a
person reads to understand where things stand) and a
**machine-checkable structure** (what tooling — including the store's
own consistency checks — can validate without parsing prose). Legacy
keeps these as a paired human-doc/machine-sidecar convention throughout
the plugin family this one belongs to; v2 must preserve the *split*
(both views must exist and stay consistent with each other) without
being bound to the specific pairing mechanism used.

### Required-field integrity

Whatever field is used to gate a downstream decision — most critically,
the blast-radius/reversibility tag that gates the authorization stop
condition — **must be structurally guaranteed present**, not merely
documented as required in a schema that nothing checks against. A
persisted gap or evidence record missing a field its own type declares
required must be detectable as invalid, ideally not even constructible,
rather than silently accepted and only discovered missing when a
downstream decision needs it and finds nothing there (see §9).

---

## 6. VERIFICATION SEMANTICS

### The proof-approach family

Legacy names seven distinct proof approaches (labelled a–g), selected by
what kind of thing is actually crossing the wire rather than defaulting
to one mechanism for everything. A rebuild must preserve the *routing
principle* — specificity beats a generic default, and the generic
default (adversarial deliberation, described below) is reserved for
genuinely subjective or multi-faceted questions with no cheaper
deterministic check available, never reached for first out of habit.
The seven kinds of question legacy distinguishes:

| Kind of question | What it proves |
|---|---|
| Does this code/artifact satisfy its contract? (no more specific match applies) | The general-purpose, most expensive default — used only when nothing more specific fits. |
| Is this number right, when there may be no known-correct answer to check against? | Techniques for testing numerical/scientific computation without an oracle: manufactured solutions, synthetic-parameter recovery, metamorphic invariants (conservation, symmetry, scaling), significant-digit/conditioning honesty, and cross-implementation differential checks where a peer implementation exists. |
| Is this claim (not code) falsifiable, general, and evidence-grounded? | An evidence-grounding rubric for prose claims/design rationale — falsifiability, generalization, evidence-grounding, honesty of framing, and accessibility of the plain-language claim. Two of these (falsifiability, evidence-grounding) are load-bearing: failing either fails the claim regardless of the other three. |
| Did an autonomous fix's own process stay reliable? | Whether an agentic change introduced an unbounded retry, left itself no escalation path, or granted itself excess tool scope — a process-reliability question, not a correctness question. |
| Does a structural/connectivity claim actually hold (does A's export really reach B, is this really the only caller)? | A confidence-graded, three-tier procedure (see below) — the plugin's one genuinely hard, non-overridable gate at its highest tier. |
| Does a contract hold as an invariant across an input space, not just one known example? | Generated-input property/invariant checking with automatic counterexample minimization — never a bespoke hand-rolled substitute for real property-testing tooling. |
| Did an existing "passing" proof actually prove anything? | Auditing an existing proof's own strength — has the contract it pinned down drifted, or would the check it relies on fail to catch a real regression. This approach never runs standalone; it always audits a proof some other approach already produced. |

**Tie-breaking principles that must be preserved:** a more specific
approach always wins over the generic default when its trigger condition
is met; among multiple numerically-flavored approaches, the more
domain-specific one wins; the "audit an existing proof" approach is
additive on top of another approach's result, never a replacement for
one; more than one approach can apply to the same wire over its
lifetime, and the choice is per proof-attempt, not a permanent label
frozen onto the wire; and when an ambiguity is genuine between two
non-default approaches, that ambiguity must be surfaced to a human
rather than resolved silently.

### Structural evidence's confidence tiers

The structural/connectivity approach must support (at minimum) a
three-level confidence gradient, ordered from strongest to weakest:

1. **Hard, non-overridable** — evidence from a genuine, queryable,
   persisted structural index. A contradiction at this tier is condition
   3 of the andon rule (§3) and cannot be waived by any adjudication
   step in the system.
2. **Blocking but revisable** — evidence from a live, in-session
   structural query tool rather than a persisted index. A contradiction
   here still blocks by default, but may be overridden by the system's
   own adjudication mechanism given a specific, stated reason to distrust
   this weaker source.
3. **Advisory only** — evidence from a heuristic, non-index-backed
   extraction. Must be explicitly and visibly labeled advisory; must
   never block on its own, and must never be presented as carrying the
   same confidence as tiers 1 or 2.

Tier selection must always attempt the strongest available tier first,
never skip to a weaker tier because it is more convenient, and must
record which tier actually produced a given piece of evidence so it
remains distinguishable later.

### The default (adversarial) approach's panel contract

For the general-purpose default approach, legacy specifies a four-role
adversarial panel. A rebuild must preserve the **guarantees** this panel
structure exists to provide, independent of whether v2 keeps exactly
four roles:

- **An advocate for "the fix satisfies the contract"** — must argue
  criterion by criterion, cite specific evidence for each, and honestly
  concede any criterion it cannot defend rather than defending
  everything indiscriminately.
- **An advocate for "the fix does not satisfy the contract"** — must be
  produced with **no visibility into the first advocate's case and no
  access to any prior verdict**, and — this is the single most important
  guarantee in the whole panel design — **must never be authored or
  influenced by whoever proposed or built the fix under review**. If the
  same reasoning that produced the fix also produces the case against
  it, the adversarial structure is theater; this independence is
  non-negotiable.
- **An evidence-gathering role** — turns claims from either advocate
  into checked facts by actually running/reproducing what can be
  reproduced (executing a check, searching the code, reproducing a
  claimed defect), rendering no verdict itself, and explicitly marking
  anything it could not check as unverifiable rather than guessing.
  Evidence this role confirms or refutes **outranks either advocate's
  unsupported assertion** in the final judgment.
- **An adjudicating role** — reads both cases and the evidence, decides
  **per contract criterion independently** (never collapsing the whole
  wire into one blended pass/fail), must weigh evidence over confidence
  or rhetorical strength, and **must be willing to return "neither side
  carries this"** for a genuinely contested criterion rather than
  manufacturing a winner. This role is also the one place condition 3's
  non-overridable hold must be explicitly respected: it may not
  adjudicate away a non-overridable structural contradiction, even if
  everything else about the wire looks fine.

**What makes a wire "proven" under this approach:** every criterion in
the wire's contract must reach a clean pass under adjudication. Any
criterion that fails, on its own, keeps the wire unproven — a wire is not
proven "on balance" or "mostly." A criterion adjudicated as contested
("neither") counts as unproven if that criterion is load-bearing; it is
not equivalent to a pass.

**Independence and non-persona guarantees that must be preserved:**
- The advocate/evidence/adjudicator roles are **functional roles**, not
  impersonation of any identified real person — nothing about their
  authority comes from a borrowed identity.
- Separately and more generally, **no verification approach in the
  system may treat "a named real person would agree with this" as
  evidence.** Every criterion any approach applies must trace to
  something objectively checkable — a test result, a measured cost, a
  mathematical/physical invariant, reproducibility — never an appeal to
  authority. This is a plugin-wide constraint, not limited to one
  approach; it required active rework of at least one approach's source
  material in legacy (the claim/rationale rubric) to convert a
  named-authority mechanic into an anonymous, criterion-named one, and a
  rebuild must apply the same discipline to any approach modeled on
  authority-bearing source material.

### The shared cost model

All proof approaches share one graduated cost discipline: cheap,
complete, deterministic checks (type/schema-level, static-structural,
executed-and-inspected) must be exhausted before reaching for expensive,
selective, or subjective checks (rendered/visual, LLM-judged). A
structural-connectivity claim, for instance, is a cheap-tier concern by
nature and must never be escalated to the expensive default approach
just because that approach exists. This graduated model and the
fast/slow lane vocabulary in §2 describe the same underlying idea at
different resolutions; §10 flags whether v2 should keep both.

---

## 7. EXTERNAL CONTRACTS (v2 must honor)

These are the surfaces other systems in the broader plugin family
depend on. A rebuild that changes their shape breaks those other
systems, so they are contracts, not implementation detail, and their
exact shapes are reproduced verbatim below rather than paraphrased.

### 7.1 Ingest mode — consuming an externally-produced modernization brief

The loop-equivalent responsibility must support an alternate mode where
it does **not** self-scan for gaps, but instead drives entirely off a
brief produced by an external planning process. When this mode is
configured:

- The loop must read a brief document (plus its machine-readable
  summary sidecar) from a configured location; **if that brief is
  absent, the loop must stop and say the ingest source doesn't exist
  yet — it must never silently fall back to self-scanning**, because
  that would silently change what "gap source" the user configured.
- The brief's **phases** (already topologically ordered, leaf-first) map
  one-to-one onto stream stages, in the brief's own order.
- Each phase's **exit criteria plus its Behavior Contract** becomes the
  wire contract entering that stage.
- Each phase's **Work Items** (file:line findings, each tagged with a
  domain and a named fix owner) become individual gap records,
  pre-classified by kind based on the work item's tag.
- Each phase's **Behavior Contract** rules (rules that must remain
  behaviorally equivalent across the phase's change, each with a stated
  validation strategy and a confidence level) become the wire's
  verification contract — the exact obligations the verify-equivalent
  responsibility must prove. **A rule flagged as a top-priority blocker
  whose confidence is below the brief's "High" level is a blocking
  entry-criterion gate for that phase, not an advisory note** — this
  must be preserved exactly, since it is how the external brief format
  expresses "do not let code change here until a human confirms this."
- The brief's **advisory notes** (findings that need human judgment) are
  recorded as stage context but are explicitly **not** turned into
  auto-fixable gap records.
- The current constraint, in this mode, is derived from the brief's own
  phase ordering (the earliest phase with open work items), not
  recomputed independently.

This is the documented "fix + validate" half of a two-system division of
labor: an external system owns check + plan (producing the brief), and
this system owns fix + validate (consuming it). Everything downstream of
gap ingestion — proposing a fix, applying the andon rule, running
cycles — is unchanged by which gap source is active; only where the
stream and the gaps come from differs.

### 7.2 Reuse of an external stage/wire detection capability

Topology detection (loop-equivalent responsibility, when not in ingest
mode) must prefer dispatching an **external, already-proven stage/wire
detection agent** (from a sibling system in the same family) over
re-deriving import/use-graph and package-boundary logic from scratch,
when that sibling system is installed. This preserves a specific
already-fixed correctness property in that external agent (a
package-boundary-collapse bug fix: a package boundary is keyed by the
*shallowest importable directory*, not by "wherever the nearest manifest
file happens to sit," so that two independently-importable packages
sharing one manifest are not incorrectly collapsed into one stage).
Falling back to a local heuristic when that capability is absent is
required and must be clearly flagged as reduced confidence — never
silently presented as equivalent.

### 7.3 The `{wire, contract, fixDiff}` entry point

The verify-equivalent responsibility must expose a named entry point
that other systems' fix-applying skills call directly, bypassing the
loop-equivalent responsibility, to get their own applied change
adversarially proven rather than self-reviewed. Its exact input shape:

```
{
  wire:     <the boundary the change touched — a stage-to-stage
             identifier for a cross-stage move, or a file:line plus the
             specific contract crossing it (a type, a signature, a
             schema, a rule) for a narrower mechanical fix>,
  contract: <the equivalence obligation to prove — for a structural move,
             "behavior is unchanged across the move" plus any imported
             Behavior Contract rules (§7.1) at their stated priority and
             confidence; for a narrower fix, "the rewrite is
             behavior-preserving">,
  fixDiff:  <the actual applied change — files plus diff, so verification
             proves what actually shipped, not what was merely proposed>,
}
```

Behavior this entry point must guarantee:
- Route to a proof approach the normal way (§6's routing principle),
  based on what the wire/contract actually is — never a fixed single
  approach regardless of input.
- Verify the **`fixDiff`** — the artifact that actually landed — never
  the pre-application proposal.
- Apply the full andon rule (§3) to the result: a refuted verdict, a
  non-overridable structural contradiction, or an unmet top-priority
  blocking rule all mean **not proven**, reported plainly enough that
  the calling system does not mistake "reported" for "cleared to
  proceed."
- When reached from the ingest-mode loop, persist an evidence record the
  same as an ordinary internally-driven proof attempt would; when called
  standalone by an external system with no loop session managing state,
  return the verdict and evidence without attempting to persist to a
  ledger that isn't being managed by anyone.

### 7.4 Settings surface

The following configuration fields are a public contract — other
tooling and human operators read and set them, so their names, types,
and defaults (or behaviorally equivalent replacements) must be
preserved:

| Field | Type | Default | Contract |
|---|---|---|---|
| `enabled` | bool | `true` | `false` must cause every entry point to stop immediately, before any other check, and say the system is disabled — never a partial no-op. |
| `house_rules_path` | path | a conventional default | Where repo-authored conventions are read from for the propose-equivalent responsibility's defaults pass. Absence must degrade to codebase-only defaults, clearly labeled — never fabricated. |
| `output_dir` | path | a conventional default | Where every human-readable report and machine sidecar is written. Every responsibility that reads back another's output must resolve this the same way, or artifacts silently look "missing." |
| `ledger_dir` | path | nested under `output_dir` by default | Where the persistent state store lives; independently overridable (e.g. a state store shared across multiple repositories). |
| `authorization_level` | ordered enum: `local+reversible` < `hard-to-reverse` < `shared-state-visible` | `local+reversible` | The authorization ceiling for stop condition 2 (§3). A proposed or applied fix whose blast-radius tag exceeds this ceiling halts the loop rather than auto-advancing. |
| `skip_verification` | bool | `false` | Trades precision for speed by skipping an approach's own independent adversarial/referee sub-pass where one exists. **Must never be able to suppress the non-overridable structural-contradiction hold (§3 condition 3, §6 tier 1)** — this is the one setting explicitly called out as unable to override the plugin's one hard gate, and that carve-out must be preserved exactly. |
| `lint_max_rules` | number | a conventional cap | Caps how many extracted convention rules the propose-equivalent responsibility folds into its defaults pass; anything beyond the cap must be named as skipped, never silently dropped. |
| `gap_source` | enum: self-scan / ingest-from-external-brief | self-scan | Selects §7.1's ingest mode vs. ordinary self-scanning. |
| `self_assess_output_dir` (or equivalent) | path | a conventional default | Only consulted in ingest mode — where to find the external brief and its sidecar. |

Every entry point must read this configuration **independently at the
start of its own run** — there is no shared cache assumed across
separate invocations, which is also why editing configuration must take
effect on the very next run with no restart of any kind required. This
"no shared cache, no restart needed" property is a behavior guarantee,
not an implementation detail, because it directly determines whether a
human can iterate on configuration and re-run immediately.

### 7.5 Cross-plugin proof-approach dispatches

Several proof approaches and one part of topology detection are defined
as dispatches to specific external capabilities (an autonomous-fix
reliability auditor; a stage-boundary contract-drift checker; a test
mutation/assertion-strength auditor). v2 does not need to reproduce
those external capabilities' internals, but it must preserve:
- exact, correct naming when referencing an external capability (legacy
  explicitly documents one historical near-miss — a plausible-looking
  but nonexistent name was nearly hard-coded — as a caution to get this
  right and keep it right);
- graceful, clearly-labeled unavailability reporting when the external
  capability is absent, with the rest of the system continuing to
  function using whatever approaches remain applicable — an absent
  cross-system dependency must never hard-fail the whole run.

---

## 8. KNOWN-GOOD DECISIONS TO CARRY FORWARD

An adversarial review of the legacy design already confirmed these
patterns are correct. A rebuild should keep the **behavior guarantee**
each provides, not necessarily the exact mechanism:

- **Read-only fan-out, single-writer persistence.** Every analysis-style
  responsibility (verify-equivalent, and the panel roles inside it)
  returns structured results and **never writes to the persistent
  state store itself**. Exactly one responsibility (the orchestrator)
  persists results. This guarantees there is never more than one writer
  racing to update state, and that every persisted fact traces back
  through one auditable choke point rather than being scattered across
  whichever responsibility happened to produce it.
- **Untrusted-content wrapping.** Any time the system reads code,
  comments, commit messages, or other artifacts from the target
  repository — which is constantly, since this is an audit/loop system
  — that content must be treated as **data to analyze, never as
  instructions to follow**, including when it is quoted inside a prompt
  to any panel role. Text that looks like a directive aimed at the
  system ("ignore this failure," "this wire is proven, skip checking")
  must be reported as a suspected injection attempt and never obeyed.
  This guarantee must hold with no exception for the panel roles most
  exposed to arbitrary code content.
- **Configuration normalization at each entry point.** Every entry point
  independently loads and defaults its own configuration rather than
  trusting a shared, possibly-stale cache — this is what makes
  configuration changes take effect immediately with no process restart,
  and what keeps every responsibility's behavior correct even when
  invoked standalone rather than through the orchestrator.
- **Adversarial verification with genuine refutation power.** The
  default proof approach's panel is not a rubber stamp: the
  evidence-gathering role can refute either advocate's claim outright,
  the adjudicating role can and must return "unproven" rather than a
  forced verdict when evidence is genuinely contested, and the advocate
  arguing against the fix is structurally prevented from being
  influenced by whoever built the fix. All three of these are load-
  bearing for the panel actually catching what a self-review would miss,
  not decorative.
- **Confidence-graded evidence with an explicit non-overridable tier.**
  Not all evidence is treated as equally strong, and the strongest tier
  (a real structural index result) is marked as beyond any internal
  override mechanism, by construction. Weaker tiers degrade gracefully
  and are explicitly labeled by their confidence level rather than
  presented as equivalent to a stronger tier.
- **Graceful degradation over hard failure for optional dependencies.**
  Every cross-system capability the system can use but does not strictly
  require degrades to a clearly-labeled reduced-confidence or
  unavailable state rather than aborting the whole run. Whether a given
  wire's proof is actually blocked (per the andon rule) is decided
  by the wire's own required evidence strength, never by an unrelated
  optional capability being absent.

---

## 9. DEFECTS v2 MUST NOT REPRODUCE

Stated as binding requirements on the rebuild, not as postmortem notes:

1. **Stop rules must be enforced, not merely written down.** In legacy,
   the andon rule and its three stop conditions exist only as prose
   instructions for an LLM to self-apply — there is no code path that
   actually throws, rejects, or otherwise structurally prevents
   advancement past a broken/unknown wire. **v2 must enforce every stop
   condition in a way that can actually fail/reject/refuse
   programmatically** — an LLM choosing to honor a written rule is not
   an enforcement mechanism, it is a best-effort convention that a
   sufficiently distracted or adversarially-prompted run can violate
   silently.

2. **Required fields must be structurally guaranteed, not just
   documented.** A real persisted record in the legacy design was
   observed missing its blast-radius value — the exact field that gates
   the authorization stop condition — with nothing in the system
   detecting the omission. **v2 must make it impossible (or, at minimum,
   immediately and loudly detectable) for a record to be persisted
   without the fields any downstream decision depends on.** A schema
   comment saying a field is "required" is not sufficient if nothing
   ever checks a written record against it.

3. **One record must represent exactly one gap.** Legacy's persisted
   record shape does not structurally prevent one record from describing
   more than one independent gap, which makes per-gap lifecycle status
   and per-gap reopen/retry counting ambiguous — you cannot cleanly ask
   "is *this* gap open" or "how many times has *this* gap reopened" if
   the record it lives in might also contain a second, unrelated gap
   with a different status. **v2 must make the one-record-one-gap
   invariant structural, not conventional.**

4. **Claim, evidence, fix, and references must be separately
   addressable fields, never one blob.** Legacy's evidence record shape
   allows a single free-text field to absorb the claim being proved, the
   evidence for it, a description of the fix, and any references, all
   at once — leaving the rest of the record nearly empty and nothing
   about the proof independently queryable (you cannot ask "what
   evidence backs this" separately from "what was the claim" if both
   live inside the same prose paragraph). **v2 must keep these as
   distinct, independently queryable fields.**

5. **Write-scope for any fix-applying capability must be validated
   before dispatch, not only described in prose.** Legacy documents
   which files/locations a fix-applying capability is expected to touch
   only as prose guidance, with no check run *before* dispatch to
   confirm the capability's actual target(s) fall within that declared
   scope. **v2 must validate a fix-applying capability's declared target
   scope against its actual write target(s) before the write happens**
   (or, for this system specifically, before accepting a `fixDiff` as
   in-scope for verification) — a scope stated only in prose is not a
   safety boundary, it is a suggestion.

---

## 10. OPEN QUESTIONS FOR v2

Things this spec deliberately leaves unsettled, plus places where
legacy's own choices look arbitrary or self-contradictory rather than
load-bearing. A rebuild should treat these as decisions to make
deliberately, not defaults to inherit silently.

- **Who actually applies a proposed fix to the target repository, and
  with what tool?** This is the most significant unresolved question,
  not a minor detail. Legacy's own text implies an "apply the fix" step
  exists in the normal (non-halted) path between proposing a fix and
  proving its wire — the authorization-ceiling stop condition is phrased
  as "do not apply the fix or proceed to [prove it]," which only makes
  sense if applying the fix is otherwise about to happen. Yet: none of
  the five responsibilities' agents/roles are ever granted a
  write/edit capability against the target repository, the propose-
  equivalent responsibility explicitly only describes a fix rather than
  applying one, and the system's own safety framing states it is
  "read-only against the target repo except [its own output
  location]." The default (non-ingest) path therefore appears to prove
  wires against a fix that nothing in the system ever actually writes to
  disk — versus the ingest-mode entry point (§7.3), where an *external*
  fix-applying capability clearly does the writing and hands the diff in
  for proof. **v2 must explicitly decide:** does the self-scan path also
  require an external fix-applier (making it structurally identical to
  ingest mode, just without an externally-supplied plan), does the
  system need its own fix-applying capability with the write-scope
  validation §9 requires, or is the self-scan path better reframed as
  producing an actionable, humanreviewable proposal that a human or
  another tool applies before re-invoking verification? Do not silently
  assume the legacy behavior (whatever it actually was) without deciding
  this.

- **Is five responsibilities the right decomposition?** Legacy's five
  units (readiness-check, propose, verify, orchestrate, status-report)
  is a reasonable but not obviously forced split — for instance, the
  "interview the user on residual forks" behavior inside propose could
  be its own unit, and "orchestrate" bundles topology detection, state
  ownership, priority selection, and stop-rule enforcement into one
  responsibility that a rebuild might choose to split further for
  testability.

- **Is the ledger's markdown-with-metadata encoding the right choice, or
  just the cheapest?** Legacy explicitly adopts a particular
  external open-format convention (files with structured header fields
  plus prose body, organized in a directory tree) as a hard requirement
  while treating that same external ecosystem's own tooling as
  optional/best-effort. The *format* choice itself — versus, say, a
  structured database, or line-oriented JSON records — is presented as
  chosen mainly for being trivial and dependency-free, not for being
  provably the best fit for the query patterns in §5 (e.g., "how many
  times has this wire reopened" requires scanning a chronological log
  rather than a direct query). v2 should re-derive the encoding from the
  actual query/durability requirements in §5, not assume prose-with-
  metadata is optimal just because it was convenient.

- **Do the Detection Ladder (five cost rungs) and the fast/slow lane
  (two-bucket) vocabularies both need to exist?** Legacy itself
  describes the two-bucket lane concept as a coarse simplification of
  the five-rung ladder, introduced first and then explicitly
  re-described as a special case of the second, more general concept
  introduced later. Carrying both forward means every stage/wire record
  potentially needs a two-bucket tag *and* individual proof attempts
  carry a five-rung classification that must stay consistent with it.
  v2 should decide whether one vocabulary subsumes the other cleanly
  enough to drop one.

- **Are the specific numeric/ordinal thresholds load-bearing or
  arbitrary?** At minimum: the sub-cycle backtrack depth bound (legacy:
  back exactly two stages, no further); the reopen count that escalates
  a wire to "the constraint" (legacy: three); and the three-level
  blast-radius scale's exact boundaries (mapped, somewhat by analogy,
  onto a general-purpose harness convention about reversible vs.
  hard-to-reverse actions, not derived from evidence about this
  system's own failure modes). None of these come with a stated
  rationale beyond "seemed reasonable." v2 should either derive them
  from an actual cost/risk model or explicitly mark them as tunable
  configuration rather than fixed constants.

- **Should the seven proof-approach families really be seven, or does
  the boundary between some of them blur in practice?** At least two
  pairs have documented overlap that the routing logic resolves by
  tie-breaking rule rather than by the categories being cleanly
  disjoint: the numerical-oracle approach and the general
  property/invariant approach both cover "an invariant that must hold
  without one known answer" for numerical code, distinguished only by
  which is "more specific"; and the claim-evidence-rubric approach and
  the proof-strength-audit approach both, in different ways, ask whether
  something claimed to be true actually earned that status. A rebuild
  should check whether these are genuinely distinct proof *techniques*
  or points on a smaller number of underlying axes (what kind of object
  is being checked × what evidence standard applies).

- **What exactly counts as sufficient reason to override a tier-2
  structural contradiction?** Legacy allows the adjudicating role to
  override a live-tool (non-persisted-index) structural contradiction
  "given a specific, stated reason to doubt the result," but does not
  define what makes a stated reason sufficient versus merely stated.
  This is a real gap between a hard, testable rule (tier 1 is never
  overridable, full stop) and a soft, judgment-call rule (tier 2's
  override standard) — v2 should either define the sufficiency bar
  concretely or accept explicitly that this override is a human-in-
  the-loop judgment call by design, not something the rebuild should try
  to make purely rule-based.

- **How should graceful degradation interact with the andon rule when
  a wire's *only* applicable proof approach is unavailable?** Legacy's
  general answer is "report that approach unavailable, try a different
  applicable one if any exists, otherwise mark the wire unknown" — which
  is consistent with the andon rule (unknown still blocks advancement)
  but leaves open whether a wire that can *never* be proven in a given
  environment (e.g., no property-testing library exists for an exotic
  language, ever) should have some distinct terminal status rather than
  perpetually recurring as "unknown, try again next pass." v2 should
  decide whether "permanently unprovable in this environment" deserves
  its own state distinct from "not yet proven."
