# Rights grading

Every reference gets a rights grade alongside its reliability grade. They are
**orthogonal**, and conflating them is the trap this file exists to close.

Reliability asks: *how much can this source's values be trusted?*
Rights asks: *what may actually be reproduced from it?*

A published design reference under a NoDerivatives licence is **grade A and R3 at the
same time** — completely trustworthy as a source of values, and forbidden as a source of
reproduced prose. One question does not answer the other.

| Grade | Typical source | What may be reproduced |
|---|---|---|
| **R1** | Public domain, a permissive licence (MIT/Apache/CC0/CC BY), or the user's own material | Values and prose both |
| **R2** | CC BY-SA, CC BY-NC, most published design guidelines | Values and rules extracted and **restated in your own words**; brief quotation with attribution; text never bundled or adapted wholesale |
| **R3** | CC BY-ND / CC BY-NC-ND, all-rights-reserved, unlicensed pages | Values measured and cited; **nothing reproduced** |

## Establish the licence — do not assume one

Absence of a licence is **not** permission. An unlicensed page is R3, not R1: default
copyright is all-rights-reserved in every Berne signatory. Check, in this order:

1. a `LICENSE` / `LICENCE` file, or a licence field in the package metadata
2. a footer, `/about`, `/info`, `/terms`, or `llms.txt` on the site
3. the licence named in the repository the assets come from

Record **where** the licence was found, not just what it says. "MIT, per `LICENSE` at
the repo root" is provenance; "MIT" is a claim.

## What copyright does not cover, and why that matters here

Copyright protects **expression**, not ideas, facts, or names. So from an R2 or R3
source you may still legitimately take:

- the **name** of a principle or a technique
- the **underlying finding** — a measured threshold, a published experimental result
- a **fact about the source** — that its body text sits at a given ratio, that its
  primary action colour fails AA at body size

What you may not take is the author's **sentences**, their illustrations, their
ordering-as-creative-selection, or their assets.

A worked example, because it is the one this plugin actually depends on: the Laws of UX
index is CC BY-NC-ND. Its prose may not be bundled or rewritten. Its **law names** are
not copyrightable, and the findings behind them (Fitts 1954, Miller 1956, Hick 1952)
predate the site by decades and are not its property. So
`references/principle-vocabulary.md` carries names, links and vorbild's own one-line
notes — and fetches the site at read time when the full statement is needed, because
reading is not redistribution.

## The rule that has teeth

> `emit` refuses to write reference prose into an output whose source is R2 or R3.

And mechanically, upstream of that: the `PreToolUse` guard denies every write and edit
under the design root's `references/`. That is invariant I1 — references are read-only —
and it is the same boundary seen from the other side. You cannot edit a reference into a
derivative in place, because you cannot edit a reference at all.

## The self-test

This plugin's own first reference corpus is R2/R3 material. If vorbild ever bundles it,
vorbild has violated its own invariant on its very first run. Treat that as the
calibration case: when a design seems to require copying a reference's text, the design
is wrong, not the invariant.
