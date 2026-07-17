# NOTICE

Every file under `examples/` in this directory is vendored from Anselm
Hahn's `universal-creator` project
(https://github.com/Anselmoo/universal-creator, `skills/shared/`), MIT
License, same author as this plugin. Copied here (rather than referenced
by external path) so `compass` is self-contained and installable without
depending on that repo's local presence.

The original 18 `examples/*.prompt.md` files are copied verbatim from
`universal-creator/skills/shared/examples/`. Three more —
`rewoo.prompt.md`, `self-ask.prompt.md`, `lats.prompt.md` — are original
to this repo, not vendored from `universal-creator`, added to extend
`compass-investigate-dynamically`'s escalation ladder. `compass` has no
JSON technique registry of its own — each skill's `SKILL.md` embeds the
methodology it needs directly, and `references/knowledge/*.md` documents
each of the 21 techniques in prose rather than as machine-readable
config.
