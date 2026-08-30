---
task: "Publish a multi-repo portfolio sweep as a living, shareable status page"
category: surface
summary: "Grade a portfolio of repos worst-signal-wins first, then hand the verdicts to a page that stays current on re-runs instead of republishing a wall of unshareable local HTML each time."
external: ["claude-plugins-official"]
beats:
  - skill: "self-assess:self-assess-portfolio"
    why: "Grades every repo in an explicit portfolio directory Red/Amber/Green/Gray by worst-signal-wins, refuses to synthesize a placeholder grade for an unassessed repo, and writes a one-shot self-assess-portfolio.html into the portfolio directory itself -- local, unshareable, and with no memory of the previous sweep."
    prompt: "sweep every repo under ~/LocalDocuments/GitHub_Forks and grade each one's self-assess health"
  - skill: "project-artifact:project-artifact"
    why: "Turns that one-shot local file into a living claude.ai page -- status pills, an Attention tab for what's blocked, and a delta-only refresh that reads the previous render's embedded state block -- none of which self-assess-portfolio's own static HTML does on its own."
    prompt: "publish that portfolio sweep as a shareable status page I can send the team, and keep it current when I re-run the sweep"
grounding: "the user's own ~/LocalDocuments/GitHub_Forks directory holds roughly 150 git repositories, including werkstoff itself -- exactly the shape of \"explicit portfolio directory\" self-assess-portfolio's own Step 1 scope gate requires, since it refuses to infer a git repo's parent as the portfolio."
---

self-assess-portfolio's own output is deliberately narrow: one grade per repo, worst-signal-wins,
written once to a local file with no sharing and no delta tracking across sweeps.
project-artifact adds exactly what that file lacks -- a shareable URL, status pills, an
Attention tab for what's blocked, and a refresh that reports only what changed since the
last sweep instead of re-narrating every repo. Run the sweep first; a Gray verdict means
"not yet assessed," and the status page must not smooth that over into an invented grade.
