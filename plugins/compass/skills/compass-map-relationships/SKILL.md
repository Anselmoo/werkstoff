---
name: compass-map-relationships
description: |
  Structures entity/dependency/causal relationships as indexed RDF-style triples before reasoning over them, then traverses the resulting graph hop by hop, citing a triple index at every step. Primarily invoked by another compass-* skill or compass-solve's Explore/Execute phases when a branch's feasibility or a stage's deliverable turns on entity/dependency/causal structure — not usually a skill a user names directly. Also directly invocable on its own for multi-hop relationship-tracing: "who does X report to, ultimately", "what breaks if this service changes", "trace how this compliance requirement flows down through our vendor tiers" — an org reporting chain, a service/system/package dependency or ownership graph (including deployment-level, not just code-level), a causal or root-cause chain, or parent/subsidiary structure in an M&A deal. Skip for single-hop lookups with no chain to traverse.
---

Structure the relevant relationships as indexed triples before reasoning
over them, traverse the resulting graph step by step citing triple
indices at each hop, and state the final answer with its full traversal
path. Built directly on `graph-prompting.prompt.md` from
universal-creator: inject relationships as `(subject, predicate,
object)` triples, identify a start node, traverse citing triple indices,
answer with the path — generalized here from knowledge-graph queries to
any task whose relationships are entity/dependency/causal rather than
strictly RDF facts.

This is the same shape of problem `self-assess-stage-map` solves for
import graphs (cluster files into stages, confirm wires between them
before reporting a dependency) — generalized beyond code to org charts,
service dependency graphs, causal chains, and any other relationship
structure. Where `self-assess-stage-map` extracts an import graph from
source files, this skill extracts whatever relationship graph the task's
source material actually describes.

Reasoning directly over relationships buried in prose is the failure
mode this skill exists to patch: it's easy to miss a hop, take a wrong
branch, or state a conclusion without a checkable path back to the
source facts. Structured, indexed triples make every hop citable and
the whole traversal auditable. This is plain skill logic: no agent
file, no Workflow script — everything below runs directly in the
conversation.

## When to use

- Org structures: "who does X report to, ultimately" / "which team owns
  the service three hops downstream of Y".
- Dependency graphs: package/module/service dependencies, "what breaks
  if Z changes".
- Causal chains: root-cause analysis, "what led to this outcome",
  incident timelines.
- Any question requiring more than one hop across named entities and
  relationships, where the source material states those relationships
  as facts (docs, an org chart, a dependency manifest, a causal
  narrative) rather than requiring the relationships themselves to be
  discovered by exploration.

Skip this skill when the question is single-hop ("who is X's manager")
or has no chain to traverse — building a triple table for one fact is
overhead the task doesn't need. Skip it too when the relationships
aren't actually known yet and must be discovered step by step through
tool calls or file reads whose next action depends on the last one's
result — that's `compass-investigate-dynamically`'s job, not this
skill's; this skill traverses relationships already stated in the
source material, it does not go looking for them one action at a time.

## Step 1 — Extract indexed triples

Before reasoning about the question at all, pull every relationship
statement relevant to it out of the source material (org chart, README,
dependency manifest, incident report, causal narrative, codebase) and
write each as a numbered `(subject, predicate, object)` triple, exactly
matching the source template's format:

```
T1: (Alice, works_at, Acme Corp)
T2: (Acme Corp, located_in, Berlin)
T3: (Berlin, capital_of, Germany)
T4: (Bob, reports_to, Alice)
T5: (Bob, works_at, Acme Corp)
```

Extract only relationships actually relevant to the question at hand —
this is deliberate scoping, not exhaustive graph-building. If the full
set of extractable relationships exceeds roughly 50 triples, pre-filter
to the relevant subgraph before proceeding (a RAG-style relevance pass
over candidate triples, keeping only the ones plausibly on a path to
the answer) rather than injecting the entire graph — see
`../../references/constraints.md` on context rot: a long, mostly
irrelevant triple table degrades traversal accuracy the same way a long
irrelevant context window does anywhere else.

Never skip straight to reasoning about the relationships in prose. The
triple table must exist, numbered, before Step 2 starts.

## Step 2 — Identify the start node

State which entity the question should begin from, and why — usually
the subject named or implied in the question itself.

```
Start node: <entity>
Reason: <why this entity is the traversal's starting point>
```

## Step 3 — Traverse the graph, citing triple indices at each hop

Follow only the edges relevant to reaching the answer, one hop at a
time. Cite the triple index used for every hop — never state a
relationship as true without pointing at the numbered triple it came
from:

```
Start: Bob
→ via T5: works_at → Acme Corp
→ via T2: located_in → Berlin
→ via T3: capital_of → Germany
Reached: Germany
```

If a hop requires numeric aggregation over multiple graph nodes (e.g.
"how many services depend on the auth package, transitively") rather
than a simple edge-follow, hand that count off to
`compass-reason-verify`'s PAL tier — offload the counting to code
instead of hand-tallying triples in prose, the same escalation the
source template names for this exact case.

## Step 4 — State the answer with its full path

Close with the answer and the complete citation path in one line — this
is the artifact that must never end up buried in a prose paragraph:

```
Answer: <value> (path: T5 → T2 → T3)
```

If the traversal cannot reach an answer — no path connects the start
node to anything resolving the question — say so explicitly and name
the last triple reached, rather than guessing past where the cited
relationships actually run out. An unreachable answer is itself a
valid, citable result.

## Output contract for downstream skills

| Field | Shape | Consumed by |
|---|---|---|
| `triples` | numbered `{index, subject, predicate, object}` list | any `compass-*` skill needing the same relationship facts without re-extracting them |
| `start_node` | entity name + reason | re-traversal if the question changes |
| `traversal` | ordered `{hop, triple_index, predicate, to}` list | audit trail for the stated answer |
| `answer` | value + `path` (ordered triple indices) | `compass-solve`'s Explore phase, when a branch's feasibility turns on entity/dependency structure; `compass-draft-revise`, when a criterion asks "is this relationship claim actually traceable" |

Any relationship claim in the extracted triples that isn't directly
backed by the source material (inferred, assumed, or from prior
knowledge rather than the given facts) needs the same citation
discipline `compass-ground-evidence` applies to factual claims
generally — flag it rather than presenting an inferred edge as a
sourced one.

Source technique (vendored locally, no external repo dependency):
`../../references/knowledge/graph-prompting.md` — see `../../references/knowledge/index.md`.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified guardrails that apply to every `compass-*` skill,
including this one — keep the triple table scoped to what's actually
relevant to the question, and keep every hop citation checkable against
a real triple rather than a plausible-sounding one.
