---
type: knowledge-bundle-index
title: compass prompting-technique knowledge bundle
description: 21 prompting techniques compass's skills apply as internal mechanism, each grounded in a concrete worked example from this repo's own plugins.
timestamp: 2026-07-16T00:00:00Z
---

# compass knowledge bundle

An [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle: one markdown concept doc per prompting technique, each with a
`resource` field pointing at its vendored worked template under
`../examples/`, and a body `# Examples` section grounding the technique
in real code from this repo — not just the abstract external template.
This is the active knowledge layer `compass`'s 13 skills are built on;
`../examples/*.prompt.md` is the raw asset store each doc's `resource`
field references.

Consumers (any `compass-*` skill, or a human reading this bundle) should
tolerate unknown frontmatter fields and follow cross-links by
bundle-relative path, per OKF's permissive-consumption model — nothing
here assumes a rigid schema beyond `type`.

## Techniques, by escalation rung

| Rung | Technique | Doc | Primary compass skill |
|---|---|---|---|
| 0 | Zero-shot | [zero-shot.md](zero-shot.md) | compass-reason-verify |
| 1 | Few-shot | [few-shot.md](few-shot.md) | compass-calibrate-format |
| 2 | Chain-of-Thought | [cot.md](cot.md) | compass-reason-verify |
| 3a | Self-Consistency | [self-consistency.md](self-consistency.md) | compass-reason-verify |
| 3b | PAL | [pal.md](pal.md) | compass-reason-verify |
| — | Multimodal-CoT | [multimodal-cot.md](multimodal-cot.md) | compass-reason-verify (triggered mode) |
| — | Tree-of-Thoughts | [tree-of-thoughts.md](tree-of-thoughts.md) | compass-explore-branches |
| — | Generate-Knowledge | [generate-knowledge.md](generate-knowledge.md) | compass-clarify-scope |
| — | Active-Prompt | [active-prompt.md](active-prompt.md) | compass-clarify-scope |
| — | RAG | [rag.md](rag.md) | compass-ground-evidence |
| — | Reflexion | [reflexion.md](reflexion.md) | compass-draft-revise |
| — | DSP | [dsp.md](dsp.md) | compass-decompose-chain |
| — | Prompt-Chaining | [prompt-chaining.md](prompt-chaining.md) | compass-decompose-chain |
| — | Graph-Prompting | [graph-prompting.md](graph-prompting.md) | compass-map-relationships |
| — | ReAct | [react.md](react.md) | compass-investigate-dynamically |
| — | ART | [art.md](art.md) | compass-investigate-dynamically |
| — | ReWOO | [rewoo.md](rewoo.md) | compass-investigate-dynamically |
| — | Self-Ask | [self-ask.md](self-ask.md) | compass-investigate-dynamically |
| — | LATS | [lats.md](lats.md) | compass-investigate-dynamically |
| — | APE | [ape.md](ape.md) | compass-optimize-instruction |
| — | Meta-Prompting | [meta-prompting.md](meta-prompting.md) | compass-optimize-instruction |

## Cross-reference map

[`../../assets/knowledge-map.html`](../../assets/knowledge-map.html) is a
self-contained, interactive chord diagram of every technique-to-grounding-target
relationship extracted from this bundle's 21 `### In werkstoff` sections — the
21 technique docs on one arc, the 15 distinct entities they cite (mostly
`self-assess-*`/`confab-*` skills, `code-modernization`, or this repo's own
`superpowers` usage) on the other. Click a technique to see its doc description
and citations; click a grounding target (e.g. `self-assess-stage-map`) to see
every technique that cites it. Open it directly in a browser — no server, no
build step.
