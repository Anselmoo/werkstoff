---
name: arbeitsplan-patterns
description: Says which agentic pattern fits a problem and with what numbers — fan-out width, model tier, stop rule, cost — grounded in a frozen catalog of measured configurations. Use when the user asks what shape work should be run in, how many agents to use, whether to run something in parallel, or whether a named pattern is a good idea. Also use to explain why a pattern is rejected here. Read-only; it proposes, it never compiles.
argument-hint: "<the problem, or a pattern name>"
---

# Which pattern, and with what numbers

Advice like "use parallel agents" fails because it carries no numbers. This skill answers
with a width, a tier, a stop rule and a cost — or says plainly that nothing fits.

## Steps

1. **Read `references/patterns.md` first, every time.** Its machine-readable index is the
   authority on which ids exist and which are accepted. Do not answer from memory; the
   catalog carries measurements your recollection does not.

2. **Dispatch `arbeitsplan:pattern-researcher`** with the problem. It proposes from the
   catalog first and may only *add* an outside candidate with a citation.

3. **Report the evidence class for every number.** `measured-here`, `measured-elsewhere`, or
   `reasoned`. A `reasoned` default is fine and useful; presenting one as measured is not.

4. **If the user named a rejected pattern, say what was measured about it**, then offer the
   accepted pattern that covers the same need. Do not just refuse.

## Rules

- **Never propose a pattern in the rejected list**, however the request is phrased.
- **Never invent a pattern.** "No clean fit — here is the closest and what it costs" is a
  real answer.
- **Never write `workflow.json`.** That is `arbeitsplan-compile`'s job, and splitting the
  decision from the writing is what lets a human see the shape before it is enforced.
- Delegate rather than reimplement: `self-consistency-vote` is `compass:compass-reason-verify`
  and `tribunal` is `andon:andon-verify` when those plugins are installed.

## Output format

```
arbeitsplan patterns — "add rate limiting without changing the response shape"
  shape  change

  build    best-of-n           fanOut 3, sonnet, one pass, 3 dispatches
           measured-here — references/patterns.md#best-of-n
           Three plausible implementations exist and the criteria are checkable, so
           redundancy buys a comparison one attempt cannot.
           angles: middleware-layer / decorator-per-route / reverse-proxy-config

  referee  blind-referee       one per candidate, sonnet, allowlist, 3 dispatches
           measured-here — matrize/agents/decode-referee.md:18-20
           The builders hold the case for their own diffs; only a starved judge can disagree.

  land     select-then-synthesize   1 writer, gated on beating the winner on >=1 criterion

  total    7 dispatches

not proposed
  serial-fix-loop — you asked for "retry until the reviewer passes". The catalog records
  superpowers' own admission that past the cap those rounds do not converge; up to 10
  dispatches per task to reach that conclusion. best-of-n above covers the same need.
```

## Resources

- `references/patterns.md` — the catalog, its index, and the rejected patterns with the
  measurement behind each rejection.
