---
name: cupertino-council
description: "Use at UI/frontend build-time, before writing any code, whenever a user-facing interface or screen is being designed. Trigger on 'design this screen', 'build this UI', 'make this feel premium', 'this feels generic', or any request to design or implement a user-facing surface. Applies to any stack (HTML, React, Vue, native, etc.). Always run before code, never after — retrofitting the council onto finished code defeats the purpose."
---

Convene exactly five lenses before writing a line of UI code. This is not decoration on top of your own design instinct — it is the design process.

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
5. **Design Identity**: one sentence naming what each lens contributed, and one sentence naming the resulting design identity as a whole.
6. **Only now, write the code** — production-grade, matched to the actual stack in use. Code without a preceding Council Brief and Tension Log is not this technique; if you find yourself about to write UI code with neither, stop and go back to step 1.

## Output format

Council Brief → Tension Log (with mechanical validation) → Design Identity → code. Never code first with a brief bolted on after.
