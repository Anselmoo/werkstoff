# Principle vocabulary

The anti-copying instrument. A lexicon entry's `purpose` must name **either** a measured
property of the target **or** one of the principles below. A `purpose` that can name
neither is a copy, and `design-critic` rejects it.

"The reference does it this way" is not a purpose. It is the absence of one.

## How this file is allowed to exist

The index these names come from — [Laws of UX](https://lawsofux.com), collected by Jon
Yablonski — is licensed **CC BY-NC-ND 4.0**: NonCommercial *and* NoDerivatives. Its
prose may not be bundled here, and may not be rewritten into a paraphrase either.

What this file carries instead: the **names** (not copyrightable), and vorbild's own
one-line note on which design decision each one bears on. The findings behind the named
laws — Fitts 1954, Miller 1956, Hick 1952 and their kin — are decades older than the
index and are nobody's property.

**When the full statement is needed, fetch `https://lawsofux.com/<law-slug>/` at read
time.** The site serves Markdown at every page URL. Reading is not redistribution;
vendoring would be. This plugin's own invariant I1 says values and rules may be
extracted while assets may not be copied — and this corpus is where vorbild is first
tested against its own rule.

## Grouping, and gestalt first

Why elements read as belonging together at all. Reach for these when a rule is about
spacing, grouping, borders or alignment — a spacing rule justified by "it looks
balanced" is a rule with no purpose.

| principle | bears on |
|---|---|
| [Law of Proximity](https://lawsofux.com/law-of-proximity/) | spacing steps between groups vs. within one; label-to-field distance |
| [Law of Common Region](https://lawsofux.com/law-of-common-region/) | when a border or a filled panel is doing work, and when it is decoration |
| [Law of Similarity](https://lawsofux.com/law-of-similarity/) | why one role gets exactly one treatment; the basis for "links look like links" |
| [Law of Uniform Connectedness](https://lawsofux.com/law-of-uniform-connectedness/) | connectors and shared containers as a stronger grouping signal than proximity |
| [Law of Prägnanz](https://lawsofux.com/law-of-pr%C3%A4gnanz/) | the radii series, icon keyline shapes, how much form an element needs |

## Cost of attention and memory

Reach for these when a rule limits a count — palette size, options per view, items
before chunking.

| principle | bears on |
|---|---|
| [Hick's Law](https://lawsofux.com/hicks-law/) | why a system caps choices per view rather than offering everything |
| [Miller's Law](https://lawsofux.com/millers-law/) | chunk sizes; why a category scale stops rather than growing |
| [Working Memory](https://lawsofux.com/working-memory/) | what a view may require the reader to hold |
| [Cognitive Load](https://lawsofux.com/cognitive-load/) | the general budget a density rule spends |
| [Chunking](https://lawsofux.com/chunking/) | content rules — character budgets per slot, where a block breaks |
| [Choice Overload](https://lawsofux.com/choice-overload/) | the count ceiling on a spread, and on a palette |
| [Selective Attention](https://lawsofux.com/selective-attention/) | why an alert cannot sit where a promotion usually sits |

## Emphasis, sequence and memory of an experience

Reach for these when a rule is about what stands out, or about order.

| principle | bears on |
|---|---|
| [Von Restorff Effect](https://lawsofux.com/von-restorff-effect/) | **the single dominant action colour.** Two dominants means neither is one |
| [Serial Position Effect](https://lawsofux.com/serial-position-effect/) | where the important item goes in a list or a nav |
| [Peak-End Rule](https://lawsofux.com/peak-end-rule/) | which moments deserve the motion and craft budget |
| [Zeigarnik Effect](https://lawsofux.com/zeigarnik-effect/) | progress indication; why a **loading** state is a required state |
| [Goal-Gradient Effect](https://lawsofux.com/goal-gradient-effect/) | progress treatment near completion |

## Time, input and simplicity

| principle | bears on |
|---|---|
| [Doherty Threshold](https://lawsofux.com/doherty-threshold/) | **the motion duration ceiling, and why feedback is a token not a nicety.** The reason a duration scale has an upper bound rather than a taste |
| [Fitts's Law](https://lawsofux.com/fittss-law/) | touch-target sizing, spacing around destructive actions |
| [Jakob's Law](https://lawsofux.com/jakobs-law/) | **why focus, disabled, loading and empty states are not optional** — a state a reader expects everywhere else and does not find here is the failure this law names |
| [Postel's Law](https://lawsofux.com/postels-law/) | input tolerance; what a field accepts vs. what it asks for |
| [Tesler's Law](https://lawsofux.com/teslers-law/) | where irreducible complexity is allowed to live |
| [Occam's Razor](https://lawsofux.com/occams-razor/) | removing an element that carries no role |
| [Pareto Principle](https://lawsofux.com/pareto-principle/) | which components earn full treatment first |
| [Parkinson's Law](https://lawsofux.com/parkinsons-law/) | flow length; not padding a process because there is room |
| [Aesthetic-Usability Effect](https://lawsofux.com/aesthetic-usability-effect/) | the caution: a handsome system hides its own usability faults, so contrast and states are **computed**, never eyeballed |
| [Flow](https://lawsofux.com/flow/) | interruption cost; when a modal is a real decision |
| [Mental Model](https://lawsofux.com/mental-model/) | naming in roles rather than appearances |
| [Paradox of the Active User](https://lawsofux.com/paradox-of-the-active-user/) | empty states doing teaching work, since documentation will not be read |
| [Cognitive Bias](https://lawsofux.com/cognitive-bias/) | the umbrella; prefer a specific named bias above when one fits |

## Using it honestly

A principle is a **reason**, not a citation to decorate a decision already made on
taste. Two failure modes to avoid:

- **Retrofitted justification.** Picking the value first and shopping for a law that
  sounds compatible. The check: would this principle have predicted this value, or only
  tolerate it?
- **Over-reach.** Fitts does not settle a typeface. If no principle genuinely bears on a
  decision, say the decision was made on measured evidence — or that it is an
  **opinionated default**, labelled as one. A default declared as a default is honest;
  a default dressed as a derived finding makes the whole artefact untrustworthy,
  including the parts that were derived.
