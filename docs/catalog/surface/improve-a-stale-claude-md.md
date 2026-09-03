---
task: "Improve a stale CLAUDE.md without trusting its own claims"
category: surface
summary: "Verify CLAUDE.md's existing claims against the code before grading its coverage and drafting additions — extending a file that's already lying about the codebase compounds the drift."
openingPrompt: "Check whether CLAUDE.md's existing claims still match the code before you touch anything in it, and only once that's verified, grade its quality and propose targeted additions -- treat anything the drift check just flagged as stale as something to fix, not just extend around."
external: ["claude-plugins-official"]
beats:
  - skill: "self-assess:self-assess-docs-drift"
    why: "Reads CLAUDE.md by name among its four source files and verifies every falsifiable claim against the cited code by static comparison, never by executing an example — the citation-by-citation check claude-md-improver's own Phase 2 doesn't do."
    prompt: "check whether CLAUDE.md's claims still match the code before you touch anything in it"
  - skill: "claude-md-management:claude-md-improver"
    why: "Grades commands, architecture clarity, and currency A-through-F and proposes targeted diffs — but its own \"Currency\" row is a graded eyeball check, not a citation-by-citation static verification, so it should run against a file whose claims are already known-accurate rather than merely plausible."
    prompt: "now grade CLAUDE.md's quality and propose targeted additions — treat every claim the drift check just confirmed as stale as something to fix, not just extend around"
grounding: "this repo's own CLAUDE.md, which is unusually dense with falsifiable claims — \"rrt-doctor's own hook manifest pins it to stages: [manual]\", the six-defect table, the tool-grant anomaly note — exactly the shape of claim self-assess-docs-drift is built to check and that claude-md-improver's currency criterion only grades impressionistically."
dos:
  - "Verify CLAUDE.md's existing claims against the code, citation by citation, before grading or extending it."
  - "Grade quality and propose additions only once the existing claims are known-accurate, not merely plausible-looking."
  - "Fix anything the drift check flags as stale before treating the file as a stable base to extend."
donts:
  - "Don't extend a CLAUDE.md whose existing claims haven't been verified -- that reinforces content that's already wrong."
  - "Don't trust claude-md-improver's Currency grade as a citation-by-citation check -- it's an eyeball grade, not a static verification."
  - "Don't treat a stale claim the drift check found as something to build around instead of something to fix first."
---

<RecipeHeader />

A CLAUDE.md that claude-md-improver extends without first checking its existing claims
against the code risks reinforcing content that's already wrong — its own quality rubric
grades currency on a letter scale, not claim by claim. self-assess-docs-drift closes that
gap first, with file:line evidence on both the doc side and the code side, so the
improvement pass starts from a verified baseline instead of a plausible-looking one.

<RecipeBeats />
