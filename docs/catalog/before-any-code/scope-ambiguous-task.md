---
task: "Scope an ambiguous task"
category: before-any-code
summary: "Pin down a fuzzy request into a written plan before any work starts, so later decisions don't inherit the ambiguity."
openingPrompt: "This request is ambiguous -- pin down the actual scope before anyone starts, score a few genuinely different readings of it before committing to one, settle any tradeoff between them while both are still live, and turn the agreed scope into a written plan before touching any code."
external: ["superpowers"]
beats:
  - skill: "compass:compass-clarify-scope"
    why: "Declared for use \"before any work begins\"; run afterwards it merely renames a finished decision."
    prompt: "the scope of this request is fuzzy — pin it down before anyone starts"
  - skill: "compass:compass-explore-branches"
    why: "Scoring alternatives after one has been built anchors on the built one."
    prompt: "before we commit to an approach, give me a few genuinely different readings of this request and score them"
  - skill: "compass:compass-negotiate-tradeoffs"
    why: "Hybrids are only checkable while both source branches are still scored and live."
  - skill: "superpowers:writing-plans"
    why: "A scope that never becomes a written plan is re-litigated at every subsequent step."
    prompt: "we've agreed the scope — turn it into a written plan with steps before touching code"
grounding: "\"make the plugins consistent\" splits on a documented boundary: `plugins/codebase-consistency/README.md` lines 28-47 are headed \"Scope - read this before installing both this and self-assess\", and route documented conventions and version-deprecated idioms out of `codebase-consistency` and into `self-assess`. Which of the two owns the request is a scoping answer, not an implementation detail."
dos:
  - "Pin down scope before any work begins -- done afterward, it only renames a decision that's already been made."
  - "Score genuinely different readings of the request before committing to one -- scoring after something is built anchors on the built version."
  - "Settle any tradeoff between readings while both are still live and scored, not after one has already won by default."
  - "Turn the agreed scope into a written plan immediately -- an unwritten scope gets re-litigated at every later step."
donts:
  - "Don't treat scoping as done once a decision has already been made -- that's renaming, not scoping."
  - "Don't skip straight to a plan on an ambiguous request without scoring alternatives first."
  - "Don't leave an agreed scope unwritten -- it will be re-litigated at every subsequent step."
---

<RecipeHeader />

"Make the plugins consistent" is not a task; it is four tasks wearing one coat. Scoping
work belongs strictly before anything else, because every later decision inherits the
ambiguity unchanged.

<RecipeBeats />
