# A paste-in CLAUDE.md block

The block below states this catalog's sequencing rules as standing instructions in a
project's own `CLAUDE.md`, rather than leaving them to be rediscovered each session.
None of the five bullets is invented: each restates a constraint its source skill
already states about itself.

- `cupertino-council`'s own frontmatter: "Always run before code, never after —
  retrofitting the council onto finished code defeats the purpose."
- `compass-clarify-scope`'s own frontmatter: to be used "before any work begins".
- `confab-assertion-audit` and the gate it fills are documented together in
  [`gates.md`](gates.md)'s "Reviewers that drop in with no setup" table — nothing
  about the audit itself requires the extra sentence, only where it slots in.
- `andon-verify` routes among seven strategies by reading "the wire's contract" —
  a dispatch with no stated contract has nothing to route against, per
  [`gates.md`](gates.md)'s "Reviewers that need one more input" section.
- The three briefs (`/modernize-brief`, `self-assess-transform-brief`,
  `/consistency-brief`) are declared mutually exclusive in
  [`routing.md`](routing.md)'s "competition is at the brief, not the plugin" —
  each is an approval gate whose downstream executor reads it as an entry
  criterion, so signing two leaves the executor with two disagreeing orderings.

## The block

```markdown
## Orchestration sequencing

- Before writing any user-facing UI code, run `cupertino-council` first. Never run it
  after code already exists — retrofitting it defeats the purpose.
- Before starting an ambiguous task, scope it with `compass-clarify-scope`. Do this
  before any other planning step, not after you've already picked an approach.
- At each review gate (after a task, before a PR), run `confab-assertion-audit` over
  the tests you just wrote, in addition to the general reviewer. See
  `references/gates.md` for what else to route by what the diff touched.
- Before merge, prove — don't just review — the contract the change claims to
  satisfy, with `andon-verify`. State the contract in the dispatch prompt; it will
  not infer one from the diff.
- Pick exactly one brief before starting discovery: `/modernize-brief`,
  `self-assess-transform-brief`, or `/consistency-brief`. Never sign two — see
  `references/routing.md` for which one owns a given task shape.
```

## Why prose, and what it buys

This repository's own `CLAUDE.md` measures, rather than assumes, how reliably an
instruction actually runs. The "Enforcement: only hooks actually enforce" section
states the method directly — measured over roughly 40 runs, asking "does the guard
*run*", not "does it exist" — and reports this ladder:

|layer|invocation|
|---|---|
|prose in a `SKILL.md`|baseline|
|a fenced `python3 ...` command in a skill|1 run in 3|
|a guard inside the Workflow script|workflow dispatched 1 run in 14|
|`PreToolUse` hook, `type: "command"`|blocks, first attempt|

The block above sits at the baseline rung — it is prose in a project's `CLAUDE.md`,
read and, ideally, followed, with nothing computing whether it actually was. Placed
in `SKILL.md` prose the same instruction measured the floor of that ladder; nothing
about pasting it into `CLAUDE.md` instead moves it any higher, since both are text a
model reads and may or may not act on under pressure. That is stated plainly here,
not glossed over: the block is chosen anyway, for this purpose, because it needs no
code, installs by pasting five bullet points into a file a project already reads
every session, and works across any combination of installed plugins without a hook
author first having to anticipate every sequence a session might need. It buys
convenience and portability. It does not buy enforcement, and nothing below this
line should be read as claiming that it does.

Consider the same rule at each rung, using the block's own first bullet as the
running case. As baseline prose, "run `cupertino-council` before UI code" sits in a
`CLAUDE.md` a session may or may not re-read once it is several tasks deep. Moved
into a `SKILL.md` behind a fenced `python3` guard, the measured rate rises only to 1
run in 3 — a model can still narrate past a command it was asked to run rather than
actually running it. Moved into a Workflow script's guard, the rate falls further,
to 1 in 14, because a Workflow dispatch is itself something a model can choose not
to reach for. Only the fourth rung changes the mechanism rather than the wording:
`cupertino`'s hook does not ask anything to run `cupertino-council` first, it makes
running `cupertino-focus` or `cupertino-council` itself fail outright until the
marker exists. That is the qualitative difference between "more forcefully worded
prose" and "enforcement" — the first three rungs are all still prose, at different
depths; only the fourth stops being prose at all.

## The rung above

The enforced version of the same idea is a `PreToolUse` hook that inspects which
skill is about to run and denies the call outright when its prerequisite has not.
`plugins/cupertino/hooks/pretooluse_guard.py` already proves the pattern inside this
repository: its `GATED_AFTER_BACKWARDS` set names the skills — `cupertino-focus`,
`cupertino-longevity`, `cupertino-integrate`, `cupertino-council` — that the hook
refuses to dispatch until a `.cupertino/flags/backwards-done` marker shows
`cupertino-backwards` ran first in that scope. That is the same ordering constraint
the block's first bullet states in prose ("run `cupertino-council` first ... never
run it after"), enforced instead of merely requested.

The deny sits at the top rung of the ladder above because it satisfies this
repository's own non-negotiables for a hook that must hold "regardless of model
cooperation": `type: "command"`, not `type: "prompt"` — a prompt hook still asks a
model to decide, which reintroduces the same cooperation problem the hook exists to
remove; a deny that emits both a non-zero exit with the reason on stderr and a
stdout JSON payload carrying `hookEventName` and `permissionDecisionReason`; inertness
unless the repository actually uses the plugin the hook belongs to; and failing
closed, with a named escape hatch rather than a silent bypass — `cupertino`'s own
escape hatch is the `CUPERTINO_DISABLE_GUARD=1` environment variable.

A project that outgrows the prose block above and wants the "before UI code, run
`cupertino-council`" rule enforced rather than requested should read that file
before writing its own equivalent hook, rather than reinventing the deny/marker
shape from scratch. The trade this reference makes explicit: the prose block installs
in seconds and travels with a `CLAUDE.md` file everyone already reads; the hook
installs with a plugin, gates one specific tool call, and is the only rung of the
four that this repository has actually measured as blocking on the first attempt.

The enforced rung already exists as a plugin. `takt` gates exactly the ordering this
block states in prose: it denies an edit or a dispatch that runs ahead of a beat the
repository declared, and is inert until `.claude/takt.local.md` exists. Installing it
turns these five bullets from instructions into refusals.

Four other werkstoff plugins hold a `PreToolUse` hook of their own — `andon` and
`self-assess` gate write tools, `confab` gates `Edit`/`Write` and `Bash`, and
`cupertino` enforces its own internal ordering through `GATED_AFTER_BACKWARDS`. All
are inert until the repository actually uses the owning plugin. See
[`hazards.md`](hazards.md) for what happens when several are installed at once.
