---
task: "Investigate a fix that did not stick"
category: defect-work
summary: "Re-prove a supposedly-fixed bug from scratch, blind to the prior verdict, rather than trusting it was ever really fixed."
openingPrompt: "This bug was supposedly fixed and it's back -- before we touch anything, list what we're assuming about that prior fix, re-verify it completely from scratch with reviewers who never saw the original fix or its verdict, and check whether any test would actually catch it if it came back again."
external: []
beats:
  - skill: "compass:compass-verify-assumptions"
    why: "\"It was fixed in the last pass\" is an assumption; re-implementing on top of it repeats the original mistake."
    prompt: "this was supposedly fixed last week and it's back. What are we assuming about that fix that might not be true?"
  - skill: "andon:andon-verify"
    why: "Its tribunal agents are dispatched \"never authored or influenced by the session that proposed or built the fix under review.\""
    prompt: "re-verify this fix from scratch — don't read the previous verdict, and don't let whoever wrote the fix judge it"
  - skill: "confab:confab-assertion-audit"
    why: "A fix that no test guards is a fix scheduled to un-stick again."
    prompt: "if this bug came back tomorrow, would anything in the test suite go red?"
grounding: "re-proving the \"Verify vendored artifacts match their committed lock\" check by removing one `plugins/*/assets/inline-d3.html` in a disposable worktree and confirming `rrt artifacts --check --strict` actually goes red, rather than trusting that it would."
dos:
  - "List what the prior 'it was fixed' claim is actually assuming, before building on top of it."
  - "Re-verify the fix from scratch with a tribunal that never saw the previous verdict and wasn't authored by whoever built the fix."
  - "Check whether any test in the suite would actually go red if the bug came back -- a fix nothing guards is scheduled to un-stick again."
donts:
  - "Don't re-implement on top of a fix whose 'it was fixed' claim was never actually verified -- that repeats the original mistake."
  - "Don't let whoever wrote the fix judge whether it holds -- the tribunal has to be blind to that session's own report."
  - "Don't trust that a prior pass would have caught the regression without actually checking it -- confirm the check itself would go red, don't assume it."
---

# Investigate a fix that did not stick

A bug reported fixed and then seen again means one of three things: the fix addressed a
symptom, the fix regressed, or the fix was never proven in the first place. All three are
verification failures, not coding failures.
