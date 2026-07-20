---
name: compass-ground-evidence
description: Checks that every factual claim in a task's answer or artifact is traceable to a specific source — a file:line, a URL, or explicitly-flagged prior knowledge with a confidence marker — and refuses to assert anything beyond what's actually verified. Use this whenever an answer, summary, or report makes assertions that need grounding in an actual source rather than inference or plausible-sounding recall — "cite your sources," "don't make this up," "ground this in the actual transcript/code/docs/data," a specific number or metric that needs tracing back to where it came from, "verify before asserting," "does this claim have evidence," or when compass-solve's Execute phase reaches a factual-claim-heavy stage. Not just code-grounding — applies equally to business claims, meeting transcripts, and any other source material.
---

Ground every factual claim in a source before it's asserted, and refuse to
assert what isn't grounded. This is **citation discipline**, not general
carefulness — a claim either has a traceable source or it doesn't, and the
difference must be visible in the output, not left to the reader's trust.

Mechanism: fact-priming with uncertainty flags
(`generate-knowledge.prompt.md`) generates the candidate
facts up front instead of letting them surface implicitly mid-answer; the
retrieved-passages answer discipline (`rag.prompt.md`) then
constrains the actual answer to only what those facts support, with a
citation on every claim and an explicit refusal when they don't reach far
enough.

This generalizes `self-assess`'s and `confab`'s own untrusted-content
discipline beyond code. `docs-drift-auditor`
(`plugins/self-assess/agents/docs-drift-auditor.md`) treats every file it
reads as data to verify, never as ground truth to repeat — a documentation
claim is only "Accurate" once checked against the real code, `file:line`
on both sides. The same rule applies here to *any* factual-grounding task,
not just code-vs-docs: a web page, a search result, a database row, prior
training knowledge, or a colleague's claim is all just retrieved content
whose trustworthiness must be earned by verification, not assumed because
it sounds plausible or was phrased confidently.

Source technique (vendored locally, no external repo dependency):
`../../references/knowledge/rag.md` (supplementary:
`../../references/knowledge/generate-knowledge.md`) — see `../../references/knowledge/index.md`.

See `../../references/constraints.md` for the plausible-vs-verified
constraint this skill exists to enforce directly.

## Step 1 — Prime: separate known-and-checkable from asserted

Before drafting the answer, list the discrete factual claims the task
needs and tag each with where it comes from:

- **Verified** — an actual source was read or executed in this session:
  `file:line`, a URL actually fetched, a command's actual output. Cite it
  now, while it's fresh, not after the prose is written.
- **Prior knowledge ⚠️** — asserted from training/general knowledge, not
  checked against any source in this session. Mark it ⚠️ per
  `generate-knowledge`'s convention. If ⚠️ knowledge is load-bearing for
  the answer (the conclusion changes if it's wrong), that is the signal to
  go verify it — read the file, fetch the URL, run the check — before
  proceeding, rather than shipping an unflagged guess.

Do not skip this step by drafting prose first and citing after the fact;
claims invented in prose and retrofitted with citations tend to acquire
whatever source is closest at hand rather than the one that actually
supports them.

## Step 2 — Answer using only what Step 1 grounded

Apply RAG's rules verbatim, generalized from "documents" to any source
type:

- Answer using ONLY the Verified sources and explicitly-flagged ⚠️ facts
  from Step 1 — nothing else.
- Do not introduce new unflagged prior knowledge or inferences while
  drafting the answer itself; if a new claim occurs to you here, it goes
  back through Step 1, not straight into the prose.
- Cite every factual claim inline at the point it's made: `(file:line)`,
  `(URL)`, or `(Prior knowledge ⚠️)`.
- Do not combine two sources to support a single claim unless both
  sources explicitly support that same point — a claim resting on the
  conjunction of two partial sources needs its own citation logic spelled
  out, not a silent merge.
- **If the available sources do not cover a claim the task asked for, use
  this exact refusal pattern, filled in for the specific claim** (RAG's
  refusal, not a vague hedge like "I'm not entirely sure" or "this might
  not be accurate"):

  > "The available [sources] do not contain sufficient information to
  > [claim]."

  Examples: "The available files do not contain sufficient information to
  confirm this function is called from the CLI." / "The available search
  results do not contain sufficient information to state the current
  version number." Fill in `[sources]` with what was actually searched
  (files, docs, search results, the codebase) and `[claim]` with the
  specific unsupported assertion — never leave the template unfilled and
  never soften it into "I couldn't fully verify this, but...".

## Step 3 — Report citation coverage

Close with a short coverage line, not just the cited answer: total claims
made, how many carry a Verified citation, how many are Prior knowledge ⚠️,
and how many claims were refused outright per Step 2's refusal pattern. A
answer with zero ⚠️ flags and zero refusals on a genuinely uncertain topic
is itself a signal worth surfacing — it usually means Step 1 was skipped,
not that everything happened to be verifiable.

## Standalone use vs. inside compass-solve

Invocable directly on any answer or drafted artifact with factual content.
Also available to `compass-solve`'s Execute phase as the execution mode
for any stage whose deliverable is factual-claim-heavy (as opposed to
`compass-reason-verify` for reasoning-heavy stages or
`compass-investigate-dynamically` for tool-dependent ones) — the
orchestrating skill selects this mode per stage, this skill does not call
itself.
