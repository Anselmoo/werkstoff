---
task: "Convert a documented rule you keep breaking into an immediate personal guard"
category: quality-verification
summary: "Confirm a documented rule is actually being violated before authoring a fast, local, personal guard against it -- not the plugin-wide, code-reviewed hook a shipped enforcement policy needs."
external: ["claude-plugins-official"]
beats:
  - skill: "self-assess:self-assess-lint-audit"
    why: "Extracts discrete, checkable rules from CLAUDE.md (falling back from house-rules.md, which this repo doesn't have, and labeling every rule \"CLAUDE.md (best-effort)\") and dispatches convention-auditor to confirm real violations by reading the code -- never invents a rule the doc doesn't state, and by its own stated scope never auto-fixes what it finds."
    prompt: "extract the discrete, checkable rules this repo's CLAUDE.md states, and confirm which ones are actually being violated in the code"
  - skill: "hookify:hookify"
    why: "Turns one confirmed, repeatedly-broken rule into a live regex-pattern guard in `.claude/hookify.<name>.local.md` -- active on the very next tool use, no restart -- the fast personal counterpart to the plugin-wide, reviewed hook `make-strategy-enforced-not-documented` builds."
    prompt: "I keep forgetting the rrt-over-raw-git rule -- warn me immediately, right now, the next time I run a bare git commit or push in this repo"
grounding: "CLAUDE.md's own rule \"Prefer rrt over raw git for repo-level operations\" is exactly the shape of rule a contributor could keep forgetting; hookify's own hooks.json wires real `type: \"command\"` hooks for PreToolUse/PostToolUse/Stop/UserPromptSubmit, but its `pretooluse.py` fails OPEN on any exception (\"allow operation and log error\"), the opposite of this repo's fail-closed doctrine for shipped enforcement -- so a hookify rule is a fast personal nudge, not a substitute for the fail-closed plugin hook the other recipe produces."
---

self-assess-lint-audit is explicitly read-only and never auto-fixes a violation it finds --
that's deliberate, and it leaves a gap for whoever keeps tripping the same rule. hookify
fills exactly that gap, but at a different scope and strength than
`make-strategy-enforced-not-documented`: a `.claude/*.local.md` rule is gitignored,
personal, and immediate, and its own dispatcher fails open on error, unlike the fail-closed
doctrine a plugin-shipped hook has to meet. Use this recipe for a contributor's own habit;
use the cupertino/plugin-dev recipe when the rule needs to hold for everyone who installs
the plugin.
