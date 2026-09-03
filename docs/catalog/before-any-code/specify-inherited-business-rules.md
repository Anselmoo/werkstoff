---
task: "Specify an inherited codebase's business rules"
category: before-any-code
summary: "Two independently-authored extractors emitting the same Given/When/Then shape, so disagreement between them is signal rather than noise."
openingPrompt: "Extract this inherited codebase's real business rules -- read it structurally and behaviorally first, map its real module boundaries rather than trusting directory names, mine the rules from the executable code as Given/When/Then specs, then run a second independent extractor afterward as a genuine cross-check, and pin the agreed behavior down with characterization tests before any rewrite starts."
external: ["claude-plugins-official"]
beats:
  - skill: "code-modernization:legacy-analyst"
    why: "Structural and behavioral read plus dead-code detection, before anyone asserts what the system actually does."
    prompt: "read this inherited codebase and build a structural and behavioral map before we assert anything about what it does"
  - skill: "self-assess:self-assess-stage-map"
    why: "Clusters by shallowest package boundary, never by manifest directory — the correction a directory-shaped read of an inherited repo needs first."
  - skill: "self-assess:self-assess-extract-rules"
    why: "Mines rules from executable code, never comments; loops to convergence; requires a two-judge panel for any P0-rated rule."
    prompt: "extract this codebase's real business rules as Given/When/Then specs, from the executable code, not from comments or docs"
  - skill: "code-modernization:business-rules-extractor"
    why: "An independent second extractor with the same output shape — what the business requires, not how the old code happened to implement it. Run after the first extractor so it's a cross-check, not an anchor."
  - skill: "code-modernization:test-engineer"
    why: "Characterization tests pin the behavior down before any transformation starts; useless once the rewrite has already begun."
grounding: "This is the exact scope overlap docs/orchestration/references/routing.md governs: this recipe dispatches code-modernization leaves directly and must not be run alongside a signed /modernize-* brief, which owns the same territory as a whole pipeline."
dos:
  - "Build a structural and behavioral map of the inherited code before asserting anything about what it does."
  - "Cluster the real module boundaries by shallowest package boundary, not by manifest directory, before mining rules."
  - "Mine rules from the executable code itself, never from comments or docs."
  - "Run the second extractor after the first, specifically so it can disagree with it, not repeat it."
  - "Pin the agreed behavior down with characterization tests before any transformation starts -- they're useless once the rewrite has already begun."
donts:
  - "Don't assert what an inherited system does before reading it structurally and behaviorally."
  - "Don't run both extractors expecting them to reconcile automatically -- the value is in an independent second read that can disagree."
  - "Don't run this recipe alongside a signed /modernize-* brief -- it dispatches code-modernization leaves directly and the two own the same territory."
  - "Don't wait until after the rewrite starts to write characterization tests -- by then they're useless."
---

<RecipeHeader />

Specifying an inherited codebase's rules only works if the second extractor runs after
the first, not instead of it — the cross-check needs an independent read to disagree
with, not a second pass over the same output. Characterization tests then pin down what
both extractors agree the code does, before any transformation gets a chance to
invalidate the read.

<RecipeBeats />
