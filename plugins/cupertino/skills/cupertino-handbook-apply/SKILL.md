---
name: cupertino-handbook-apply
description: "Use before starting new work in a domain that already has a drafted handbook, to pull in only the constraints and exceptions relevant to the upcoming task rather than dumping the whole document. Trigger on 'what does our handbook say about this', 'apply our code standards to this task', or naturally at the start of any task in a domain where cupertino-handbook-draft has already run."
---

Pull only what's relevant. A handbook dumped in full at the start of every task is noise; the point of this skill is targeted retrieval.

## Steps

1. **Parse the domain** from the first argument.
2. **Check the handbook exists** at `.cupertino/<domain>-handbook.md`. A PreToolUse hook also enforces this: it denies dispatching this skill for a domain with no handbook file present. If it's missing, **stop and ask the user to run `cupertino-handbook-draft` for this domain first** — do not improvise constraints from general best practice as a substitute; that's a different skill's job, not this one's.
3. **Read the handbook** and select only the dimensions that actually bear on the described upcoming task. Skip dimensions with no plausible connection to the task rather than listing all of them "for completeness."
4. **Surface applicable exceptions alongside the constraints they modify** — read the `## Exceptions & waivers` section and, for each selected dimension, note any waiver that changes how the constraint applies here. Don't present a constraint without checking whether an exception already carves out this exact situation.
5. **Remind, don't promise**: note that `cupertino-handbook-check` can verify compliance once the work actually exists — this skill only surfaces what applies before the work starts, it doesn't check anything yet.

## Output format

Domain and handbook confirmation → the filtered, task-relevant constraints (with any modifying exceptions inline) → the reminder about `cupertino-handbook-check`. Never the full handbook dump.
