# Prompt catalog

The werkstoff plugin READMEs index their example prompts by plugin — useful once you
already know which plugin you need. This catalog is the other door: the same capability
surface, indexed by development task.

Each card below is one recipe: a task, the beats that fire in order, why each beat earns
its position rather than sliding earlier or later, and the literal prompt that triggers
it. Filter by category — before any code, CI & release, defect work, changes to existing
code, quality & verification, or surface work — or by whether a recipe pairs werkstoff
with Superpowers, with an official Anthropic plugin, or uses werkstoff alone.

A recipe with an empty `external` filter is werkstoff-only. One tagged `superpowers`
combines a werkstoff beat with a Superpowers skill in the same task. One tagged
`claude-plugins-official` reaches into `pr-review-toolkit`, `code-modernization`,
`frontend-design`, or `plugin-dev`.

Three recipes are marked "no werkstoff fit" in their body text — honest gaps where
Superpowers alone is the better answer, not a forced pairing.

<CatalogGrid />

## How to read a recipe

Each recipe's frontmatter names a `task`, a `category`, and a one-line `summary`, then
lists its **beats** in order — each an ordered moment where a skill or agent earns its
place, given as `skill`, `why` (what is lost if the beat slides to a different position),
and an optional literal `prompt` that fires it. A closing `grounding` field gives a
worked example drawn from this repository.

Three conventions hold throughout the catalog.

**Leaves only.** Beats name leaf skills and dispatchable agents. Orchestrators —
`andon:andon-loop`, `self-assess:self-assess-autopilot`, `compass:compass-solve`,
`cupertino:cupertino-review`, `confab:confab-cycle`, the `/consistency-*` command chain,
`code-modernization`'s eight-stage pipeline — each own a whole task and must never be
wedged in as a step inside another workflow. Choosing between them is a routing question;
see [`routing.md`](/orchestration/references/routing).

**Declared position is binding.** A skill whose own frontmatter says "before any code"
does not get retrofitted afterwards. `cupertino:cupertino-council` states it directly:
"Always run before code, never after — retrofitting the council onto finished code
defeats the purpose." `compass:compass-clarify-scope` declares itself for use "before any
work begins". `codebase-consistency` is the mirror case: genuinely post-hoc, and wrong as
a preamble.

**Honest gaps.** Three recipes are marked **No werkstoff fit**. Those tasks are better
served by Superpowers alone, and saying so is more useful than a forced pairing.

`takt` never appears in a recipe's `beats:` list — it ships no skills, only a
`PreToolUse` hook (`plugins/takt/hooks/hooks.json`) that denies an edit or a dispatch
running ahead of a beat the repository declared it depends on, and stays inert until
`.claude/takt.local.md` exists. It has nothing to contribute as a step because it isn't
one; it's the mechanism that turns "these beats fire in this order" from documentation
this catalog states into a constraint the runtime actually enforces.

Where a recipe dispatches several agents at once, one rule from
`superpowers:subagent-driven-development` applies verbatim: "Always specify the model
explicitly when dispatching a subagent. An omitted model inherits your session's model —
often the most capable and most expensive — which silently defeats this section."
Mechanical fan-out goes to the cheap tier; integration and judgment to the standard tier;
architecture and any final whole-branch review to the most capable tier.

## How many plugins

The count follows the shape of the task, not the ambition of the prompt.

| Task shape | Plugins | Rationale |
|---|---|---|
| One clear feature | 2-3 | One before-code beat, one build beat, one gate. More beats than that spend attention on coordination rather than on the feature |
| A larger task | 4-5 | Enough for a scope beat, a mapping beat, a build beat, and two distinct gates that fail for different reasons |
| Genuinely parallel work | Split into independent workstreams | Each workstream carries its own 2-3 plugins |

For the parallel case, one condition is not optional: **the workstreams must not depend on
each other.** A workstream that waits on another's output is a sequential step wearing a
parallel label, and dispatching it in parallel produces a partial result that reads as a
complete one. Split on genuine independence — core implementation, tests and validation,
docs and rollout notes — or do not split at all.

Two mechanical rules govern the dispatch itself. From
`superpowers:dispatching-parallel-agents`: "Multiple dispatch calls in one response =
parallel execution. One per response = sequential." And from
`superpowers:subagent-driven-development`: "Always specify the model explicitly when
dispatching a subagent. An omitted model inherits your session's model - often the most
capable and most expensive - which silently defeats this section." Mechanical fan-out
takes the cheap tier, integration and judgment the standard tier, architecture and the
final whole-branch review the most capable tier, and any fix round that has already failed
three times moves at least one tier up.

Choosing *which* orchestrator owns a whole task — rather than which leaves fill a beat
inside one — is a separate question; see
[`routing.md`](/orchestration/references/routing).
