---
description: Scaffold a headless behavior test for a werkstoff plugin skill — a seeded-defect fixture plus a case in test/plugins/cases.tsv, so `test/plugins/run.sh` can prove the skill catches its known bug in a fresh Claude Code process.
argument-hint: <plugin>/<skill> [behavior to test]
---

You are scaffolding a **headless behavior test** for a werkstoff plugin skill.
Context on why this exists: Claude Code loads its skill/agent registry once at
session start, so a newly-authored skill can't be exercised in the same
session — only a fresh `claude --print` process (which `test/plugins/run.sh`
spawns per case) picks it up. See CLAUDE.md "Verifying plugin changes".

Target: **$ARGUMENTS**

Do this, asking the user only for what you genuinely can't infer:

1. **Identify** the plugin, the skill, the artifact it writes (e.g.
   `analysis/self-assess/UI_AUDIT.md`), and the single behavior to test.
   Read the skill's `SKILL.md` to confirm the artifact path and how the skill
   is triggered — don't guess.
2. **Design one seeded defect** — the smallest fixture that carries exactly one
   known problem the skill must catch, plus (ideally) one correct case that
   would be a false positive if flagged. Look at the existing fixtures under
   `plugins/*/test-fixtures/` for the house style (a README stating the seeded
   defect + expected finding, next to the defect file).
3. **Scaffold** by running:
   `test/plugins/scaffold-test.sh <id> <plugin-name> <fixture-name> [artifact]`
   Then write the actual defect file into the new fixture dir and finish its
   README.
4. **Complete the case row** the script appended to `test/plugins/cases.tsv`:
   replace the `TODO-prompt...` with a prompt that triggers exactly this skill,
   and `TODO-regex...` with an `egrep -i` pattern that proves the seeded defect
   was caught (match on the finding's own words, not on line numbers).
5. **Tell the user how to run it:** `test/plugins/run.sh <id>` — and remind
   them it needs a Claude Code CLI on PATH and (for a just-authored skill) a
   fresh process, which the harness already provides. Do NOT run it yourself if
   the user's session is rate-limited; just hand over the command.

Keep the fixture minimal and the assertion a true golden oracle — the point is
"does the skill catch the bug it's supposed to," not a fuzzy string match.
