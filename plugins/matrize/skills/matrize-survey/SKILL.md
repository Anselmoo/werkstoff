---
name: matrize-survey
description: "Use to scan the current state of the art in design-system delivery — token formats and tooling, build and bundler conventions per target, component distribution, the accessibility baseline, and how systems are actually documented today — because a design handbook does not go stale on style, it goes stale on the delivery chain. Trigger on 'what's the current state of the art for design tokens', 'is our delivery chain out of date', 'resurvey the tooling', 'matrize survey'. Every named package, tool, spec or API is verified to exist before the file is written; an unverifiable name is removed and logged, never softened into a hedge."
argument-hint: "[domain]"
---

Answer the question a reference cannot: not *what should this look like*, but *how are
systems actually delivered right now*. Re-runnable, because the answer decays.

## What it covers

- **token format and tooling conventions** — which spec revision is current, which tools
  claim support, and where that support is uneven rather than absent
- **build and bundler conventions** per target in play
- **component distribution** conventions
- **the current accessibility baseline**, and what changed in it
- **how systems are documented today** — which is *not* a 13-page landscape PDF, and the
  survey should say when that still wins anyway: it wins for approval by a
  non-technical decision-maker, and loses for developer consumption. Both halves are
  findings; recording only one is advocacy

## The confabulation gate

> Every named package, tool, specification or API is verified to exist **before** the
> file is written.

Verify by resolving the thing itself — a registry entry, the spec's own URL, the
repository. Not by recalling it, and not by finding it mentioned somewhere.

A name that cannot be verified is **removed and logged** in a "could not verify" list.
It is never softened into a hedge: "possibly `some-tool`" reads as a real option to the
next reader, and a hedge is how a confabulated dependency survives review. Dispatch
`fact-checker` for the existence checks — they are mechanical and verifiable by
construction.

## Per-claim volatility, and an expiry derived from it

Each claim carries: **source URL**, **retrieval date**, and a **volatility flag** —
`stable` (a convention that moves on a multi-year cadence) or `moving` (tooling support,
version coverage, anything mid-adoption).

The file's expiry is the **earliest** of its claims' horizons: roughly 365 days for a
stable claim, roughly 90 for a moving one. A survey made entirely of stable conventions
should not expire on a calendar that assumes churn; one resting on a single fast-moving
tooling fact should not look fresh for a year.

`matrize-status` names **which claim** forces the expiry, so a re-survey can be targeted
rather than total.

## The delta section

If a previous `STATE-OF-THE-ART.md` exists, end with what changed since it: claims that
held, claims that moved, and claims that turned out to be wrong. A survey with no delta
against its predecessor has not been compared to it.

## Worked example of why this phase exists

Uneven support for a *stable* specification is the characteristic shape of this domain:
a spec can reach a stable revision while the major implementations are still catching up
to it, so "tool X supports the spec" and "tool X supports the revision you are targeting"
are different claims. That distinction was not true a year earlier and will not stay
true — which is the whole argument for re-running this rather than writing it once.

Record the revision you actually target, per tool, with its retrieval date.
