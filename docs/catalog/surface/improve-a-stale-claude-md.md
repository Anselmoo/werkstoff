---
task: "Improve a stale CLAUDE.md without trusting its own claims"
category: surface
summary: "Verify CLAUDE.md's existing claims against the code before grading its coverage and drafting additions — extending a file that's already lying about the codebase compounds the drift."
external: ["claude-plugins-official"]
beats:
  - skill: "self-assess:self-assess-docs-drift"
    why: "Reads CLAUDE.md by name among its four source files and verifies every falsifiable claim against the cited code by static comparison, never by executing an example — the citation-by-citation check claude-md-improver's own Phase 2 doesn't do."
    prompt: "check whether CLAUDE.md's claims still match the code before you touch anything in it"
  - skill: "claude-md-management:claude-md-improver"
    why: "Grades commands, architecture clarity, and currency A-through-F and proposes targeted diffs — but its own \"Currency\" row is a graded eyeball check, not a citation-by-citation static verification, so it should run against a file whose claims are already known-accurate rather than merely plausible."
    prompt: "now grade CLAUDE.md's quality and propose targeted additions — treat every claim the drift check just confirmed as stale as something to fix, not just extend around"
grounding: "this repo's own CLAUDE.md, which is unusually dense with falsifiable claims — \"rrt-doctor's own hook manifest pins it to stages: [manual]\", the six-defect table, the tool-grant anomaly note — exactly the shape of claim self-assess-docs-drift is built to check and that claude-md-improver's currency criterion only grades impressionistically."
---

A CLAUDE.md that claude-md-improver extends without first checking its existing claims
against the code risks reinforcing content that's already wrong — its own quality rubric
grades currency on a letter scale, not claim by claim. self-assess-docs-drift closes that
gap first, with file:line evidence on both the doc side and the code side, so the
improvement pass starts from a verified baseline instead of a plausible-looking one.
