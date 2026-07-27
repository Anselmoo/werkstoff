---
name: cupertino-integrate
description: "Use at architecture-decision time, together with cupertino-longevity, to decide whether one specific seam — a boundary between layers, APIs, or ownership — is worth owning tightly versus delegating to a vendor or framework. Trigger on 'should we build or buy this', 'own vs delegate', 'vendor this piece or not', 'tight integration vs pluggable', or any decision about a single named boundary. Never apply as a blanket policy across a whole system — one seam per invocation."
---

Evaluate exactly one named seam per invocation. This technique never produces a blanket "always integrate" or "always delegate" default — if asked to apply it system-wide, ask which seam to start with and evaluate that one first.

## Steps

1. **Name the seam** precisely: which two layers, APIs, or ownership boundaries meet here, stated concretely enough that someone else could point at the exact boundary in the codebase.
2. **Friction analysis**: is there friction today (bugs, workarounds, slow iteration at this boundary), or is the friction anticipated (a foreseeable future need this seam will have to absorb)? Be specific — vague friction is not evidence.
3. **Apply the diagnostic heuristic, don't default**: it is tempting to assume customer-facing seams always favor tight integration ("this is what the user touches, so we must own it"). That is not automatically true — a customer-facing seam with low differentiation value and a mature vendor option can still favor delegation; conversely, an internal seam that is genuinely core to the product's advantage can favor tight ownership even though no customer ever sees it directly. Judge this seam on its own friction evidence, not on its visibility.
4. **Verdict**: integrate or delegate, with the trade named explicitly — not "it depends" but the actual thing being traded away by choosing this path.
5. **What changes as a result**:
   - If integrate: name what becomes harder to swap out later — the lock-in cost of ownership.
   - If delegate: name what stays friction-prone — the cost you are choosing to keep paying to a vendor/framework rather than own.

## When paired with cupertino-longevity

If `cupertino-longevity` is also evaluating architecture decisions in the same conversation, present both readouts side by side, explicitly attributed ("integrate says X, longevity says Y"). Never collapse them into a single averaged recommendation — a seam being right to delegate on integration grounds can still be a longevity risk (vendor lock-in, no exit path), and that tension is the useful signal, not something to smooth away.
