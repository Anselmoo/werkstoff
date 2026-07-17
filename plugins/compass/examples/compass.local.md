---
branch_count: 3                # default for compass-explore-branches
max_branch_count: 6            # cap for explore-branches-scan.js's angle pool
revision_threshold: 3          # 1-5 scale, default for compass-draft-revise
always_render_trace: false     # skip the offer-and-wait, render reasoning-trace-viewer.html directly when a pipeline completes
match_skill_set: []            # compass-* skill ids to treat as always-relevant across every Execute-phase stage, e.g. ["compass-ground-evidence"]
---

# compass configuration

Copy this file to `.claude/compass.local.md` in the repo you're working
in, then edit or delete fields you want to override. Everything shown
here is already the default — delete a line to fall back to it, or
delete the whole file to use every default.

Remember to add `.claude/*.local.md` to this repo's `.gitignore`; this
file is per-project, user-managed, and not meant to be committed.
