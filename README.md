<p align="center">
  <img src="docs/public/logo.svg" alt="werkstoff" width="96" height="96">
</p>

# werkstoff

My personal workshop for Claude Code plugins — a marketplace
repo (`.claude-plugin/marketplace.json`) holding one plugin per directory
under `plugins/`, the same layout `anthropics/claude-plugins-official`
uses.

## Plugins

Each plugin catches or enforces one distinct thing — pick by problem, not by
feature list. Every plugin README opens with the same block: one sentence on
what it is for, what its (mostly German) name means, **Use when / Not when**
naming the neighbour to use instead, and one worked **Use case** with a real call
and a real excerpt of its output.

| plugin | what it is for | pick it when | neighbours |
|---|---|---|---|
| [`befund`](plugins/befund/README.md) | Makes a codebase describe its own health, with every finding tied to file:line evidence, and edits source only behind an authorization recorded on disk. | you need a diagnosis of the whole codebase before deciding what to change | `passung`, `zeugnis`, `andon` |
| [`zeugnis`](plugins/zeugnis/README.md) | Audits code that looks right and is not, and counts a finding only after an independent pass has re-checked it. | tests pass, signatures match, manifests resolve — and you do not believe it | `befund`, `andon` |
| [`andon`](plugins/andon/README.md) | Hardens a repository stage by stage, proving each handoff between stages and halting rather than advancing past one it cannot prove. | you want gaps fixed in order, each fix proven before the next | `befund`, `zeugnis` |
| [`passung`](plugins/passung/README.md) | Finds a convention your codebase follows two or more valid ways, picks the one that should become canon, and aligns every divergent site to it with a provable equivalence check. | the code is modern but every module does the same thing differently | `befund`, `lehre` |
| [`lehre`](plugins/lehre/README.md) | Researches a code style, pattern and architecture doctrine, then denies the write that would violate it. | the rules should hold while the code is being written, not be found afterwards | `passung`, `befund` |
| [`zirkel`](plugins/zirkel/README.md) | Makes sure a complex or ambiguous task is clarified, explored and decomposed before anyone starts executing it. | the task is vague or has several viable approaches | `arbeitsplan` |
| [`cupertino`](plugins/cupertino/README.md) | A design and craft discipline rooted in Steve Jobs' documented decisions, run as a fixed lifecycle of stages from experience to ship, not a menu of design techniques. | you are about to design a screen, feature or product line | `matrize` |
| [`matrize`](plugins/matrize/README.md) | Derives a design system once from reference exemplars you admire, names every element, and emits it to any target. | every project re-guesses its colours, type and spacing | `cupertino` |
| [`cli-scaffold`](plugins/cli-scaffold/README.md) | Generates a production-grade command-line application in one of 12 languages, built against one five-pillar architecture doctrine and checked against it before you see it. | you are starting a command-line tool | — |
| [`arbeitsplan`](plugins/arbeitsplan/README.md) | Turns a described change into a budgeted workflow, builds it several independent ways at once, and lands exactly one result. | a change is big enough to orchestrate rather than do serially | `takt`, `zirkel` |
| [`takt`](plugins/takt/README.md) | Refuses an edit or dispatch that runs ahead of a step the repository said must come first. | an order between skills or plugins must hold, not just be written down | `arbeitsplan` |
| [`nacharbeit`](plugins/nacharbeit/README.md) | Reviews a Claude Code plugin against the official Anthropic standard, then reworks the mechanical and local-rewrite share of what falls short. | the thing under review is a plugin, not an application | `befund` |

`befund`, `zeugnis`, `andon` and `passung` all work on a live codebase, and they
are the four most often confused. `befund` diagnoses; `zeugnis` distrusts what
looks verified; `andon` fixes in order and proves each fix; `passung` resolves
variants nobody wrote down. Each README's **Not when** line says which one to
use instead.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install befund@werkstoff
```

Swap `befund` for any plugin name above (`zeugnis`, `zirkel`,
`cupertino`, `andon`, `arbeitsplan`, `cli-scaffold`, `passung`,
`takt`, `lehre`, `nacharbeit`, `matrize`) to install
a different one — each is independent and can be installed on its own.

Or for local development, point Claude Code straight at a plugin
directory without registering the marketplace:

```
claude --plugin-dir /path/to/werkstoff/plugins/befund
```

## Docs

- **[Orchestration](docs/orchestration/README.md)** — how these plugins compose
  with each other, with `superpowers`, and with the official Anthropic plugins.
  Includes a task-indexed
  [prompt catalog](docs/catalog/), a
  [routing table](docs/orchestration/references/routing.md) for the pipelines
  that overlap, and the
  [composition hazards](docs/orchestration/references/hazards.md) of running
  several hook-bearing plugins in one session.
- **[Plugin authoring](docs/plugin-authoring/README.md)** — the craft standards
  to read before writing or editing a `SKILL.md` or agent file.

## Adding a new plugin

Scaffold it under `plugins/<name>/` (own `.claude-plugin/plugin.json`,
own `README.md`) and add an entry to the root
`.claude-plugin/marketplace.json`'s `plugins` array with
`"source": "./plugins/<name>"`. Then run
`python3 plugins/nacharbeit/scripts/nacharbeit_lint.py plugins/<name> --docs-root docs`:
its `P-*` and `D-*` rules name every other place a plugin has to be
registered (`.rrt.toml` version group and field target, the two release
workflows' allowlists, the docs stub, sidebar and grid, this README, the
count words, the orchestration references) and fail loudly for each one
still missing. Each plugin is independent — no shared code between them
beyond convention. The root `LICENSE` (MIT) covers it;
add a plugin-local `LICENSE` only if it carries forward a different
license, as `passung` does (see License below).

## License

MIT for the repo and every plugin except `passung`, which
is Apache-2.0 — it's a Derivative Work of Anthropic's `code-modernization`
plugin and carries that plugin's license forward; see
`plugins/passung/LICENSE` and `NOTICE`. See the repo-root
`LICENSE` for everything else.
