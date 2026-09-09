---
name: cupertino-council
description: "Use at UI/frontend build-time, before writing any code, whenever a user-facing interface or screen is being designed. Trigger on 'design this screen', 'build this UI', 'make this feel premium', 'this feels generic', or any request to design or implement a user-facing surface. Applies to any stack (HTML, React, Vue, native, etc.). Always run before code, never after — retrofitting the council onto finished code defeats the purpose. Not for a not-yet-scoped new feature where customer experience and technology are both still undecided — run cupertino-backwards first to establish the experience statement. Not for reviewing an interface that already exists: for accessibility, semantic-markup or hardcoded-design-value problems in shipped source use self-assess-ui-audit, and for a full-lifecycle design pass over an existing project use cupertino-review."
---

Convene exactly five lenses before writing a line of UI code. This is not decoration on top of your own design instinct — it is the design process.

This skill is gated: a PreToolUse hook blocks it until `cupertino-backwards` has run in this repo (it checks for `.cupertino/flags/backwards-done`). If you see a denial for that reason, run `cupertino-backwards` first — do not work around the gate.

## The five lenses (exactly five, no fewer, no more)

1. **Reduction** — what can be removed without losing function?
2. **Craft** — what does obsessive attention to detail (spacing, motion, materials) demand here?
3. **Hierarchy** — what system of consistent visual weighting makes this legible at a glance?
4. **Usability** — what does the person actually need to accomplish, with the least friction?
5. **Metaphor** — what human-familiar concept makes this interface make intuitive sense?

## Steps

1. **Council Brief**: an audit table with one row per lens — what that lens observes about this specific interface, not generic platitudes.
2. **Validate lens count mechanically**:
   ```bash
   echo '{"lenses": ["Reduction", "Craft", "Hierarchy", "Usability", "Metaphor"]}' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" council-lenses
   ```
3. **Tension Log**: wherever two lenses pull in different directions, resolve using the **fixed precedence order — Usability > Reduction > Craft > Hierarchy > Metaphor** — and no other ordering. State each resolution as: `"[Lens A] wanted [X], [Lens B] required [Y] — resolved as [Z]"`.
4. **Validate the resolution order mechanically** — list the lenses in the order their tensions were actually resolved (higher-precedence lens's requirement winning first) and check it never violates the fixed order:
   ```bash
   echo '{"resolvedOrder": ["Usability", "Reduction", ...]}' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" tension-order
   ```
   If it exits non-zero, the resolved order violated the fixed precedence — return to step 3 and re-resolve the offending tension using the fixed precedence order, then re-run this check. Do not proceed to step 5 until it passes.
5. **Design Identity**: one sentence naming what each lens contributed, and one sentence naming the resulting design identity as a whole.
6. **Only now, write the code** — production-grade, matched to the actual stack in use. Code without a preceding Council Brief and Tension Log is not this technique; if you find yourself about to write UI code with neither, stop and go back to step 1.

## Example

A Council Brief for a settings screen with 14 toggles on one page, and the Design Identity it led to:

| Lens | Observation |
|---|---|
| Reduction | 14 toggles on one screen; 5 are advanced options fewer than 3% of users touch — they don't belong at this level. |
| Craft | Toggle rows have inconsistent vertical rhythm (12px/16px/20px gaps) — no shared spacing unit. |
| Hierarchy | Every row uses the same weight and size; nothing signals which settings are consequential (data deletion) versus cosmetic (theme). |
| Usability | Users scanning for one setting must read all 14 labels — there's no grouping or search. |
| Metaphor | Toggles alone don't convey that some changes are reversible and others aren't; nothing borrows a familiar real-world cue for "this one's permanent." |

Design Identity: *Reduction* cut the screen to 9 primary toggles and moved the 5 advanced options behind a disclosure; *Craft* fixed the rhythm to a single 16px unit; *Hierarchy* gave destructive settings a distinct weight and a warning color; *Usability* added a grouped, searchable layout; *Metaphor* marked irreversible settings with a lock icon, borrowing the familiar "locked = can't undo" cue. Resulting design identity: **a settings screen that reads as a short, trustworthy checklist rather than a control panel.**

## Output format

Council Brief → Tension Log (with mechanical validation) → Design Identity → code. Never code first with a brief bolted on after.
