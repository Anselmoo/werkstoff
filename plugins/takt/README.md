# takt

**Enforces declared beat order at the tool-call layer, so sequencing is a gate rather
than a sentence.**

## Why this exists

Several skills in this marketplace already declare where in a build they belong.
`cupertino-council` says to use it "at UI/frontend build-time, before writing any code
... Always run before code, never after — retrofitting the council onto finished code
defeats the purpose." `cupertino-backwards` says "Use FIRST." `compass-clarify-scope`
scopes a task "before any work begins."

Nothing enforces any of it. A declaration written as prose is a sentence a model may
skip under load, and this repository has measured what that costs: a rule stated as
prose in a SKILL.md is the baseline, a guard behind a fenced `python3` block is invoked
about one run in three, and a `PreToolUse` hook of `type: "command"` blocks on the first
attempt. takt is the difference between a documented beat order and an enforced one.

It owns no skills and no agents. It is one hook and a declaration format, because the
beats it enforces span plugins — a council from one, an audit from another, a proof from
a third — and no single plugin honestly owns that order.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install takt@werkstoff
```

takt is inert until a repository declares its beats, so installing it changes nothing
until `.claude/takt.local.md` exists.

## Declaring beats

Create `.claude/takt.local.md` with one fenced `json` block:

````markdown
```json
{
  "beats": [
    {
      "id": "ui-before-council",
      "tools": ["Write", "Edit", "MultiEdit"],
      "paths": ["*.tsx", "*.jsx", "*.vue", "*.svelte", "src/ui/*"],
      "require": ".takt/council-done",
      "reason": "cupertino-council runs before UI code, never after."
    }
  ]
}
```
````

| Field | Meaning |
|---|---|
| `id` | Name reported in the denial |
| `tools` | Tool names the beat applies to; defaults to `Write`, `Edit`, `MultiEdit` |
| `paths` | `fnmatch` globs matched against the edited file, for the edit tools |
| `skills` | `fnmatch` globs matched against the dispatched name, for `Skill`/`Task`/`Agent` |
| `require` | Marker path that must exist before the call is allowed |
| `reason` | Sentence included in the denial, explaining the order |

Whatever performs the beat creates the marker — `mkdir -p .takt && touch
.takt/council-done`. takt never writes files; it only reads and refuses.

A single call can touch several files: a `MultiEdit` may carry its paths in an `edits`
array rather than one top-level `file_path`. Every path a payload exposes is collected,
and a beat is violated if **any** of them is gated.

Matching is `fnmatch`, never regex. Every silent-failure regex form this repository has
been burned by is a regex-only failure mode that a glob cannot express.

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Declare the beats for a repository

````prompt
"set up takt so UI code can't be written before the design council has run"
````

> Writes a `.claude/takt.local.md` beat with the UI globs and a `require` marker, after
> which the hook refuses a matching edit until that marker exists.

##### Understand a refusal

````prompt
"takt just blocked my edit — what beat am I running ahead of?"
````

> The denial names the beat id, the reason, and the missing marker; the escape hatch is
> `TAKT_DISABLE_GUARD=1` when the order genuinely does not apply.

## Hooks

One `PreToolUse` hook, `type: "command"`, matching
`Skill|Task|Agent|Write|Edit|MultiEdit`. Never `type: "prompt"` — a prompt hook asks a
model to decide, which is the model-mediated path this plugin exists to replace.

- **Inert** when `.claude/takt.local.md` is absent: the call is allowed before it is
  even inspected.
- **Fail-closed** once that file exists: any internal error denies rather than silently
  allowing, naming the escape hatch. So does an *indeterminate* payload — if a beat gates
  the call but no file path (or, for a dispatch, no skill or agent name) can be
  determined from it, takt refuses. A call that cannot be checked against a gate the
  repository opted into is precisely the bypass this plugin exists to prevent.
- **Escape hatch**: `TAKT_DISABLE_GUARD=1`, or remove the declaration file.

## Testing

```bash
python3 test/plugins/verify-hooks-deny.py plugins/takt
```

The fixture at `test/plugins/fixtures/hook-violation-takt/` is plugin-specific because
takt is scope-conditional: probed with the generic fixture the hook correctly allows,
which the harness would otherwise report as a hook that does nothing.

## Related

For which beats are worth declaring, and where each plugin belongs in a build, see
[`docs/orchestration/README.md`](../../docs/orchestration/README.md) and
[`docs/orchestration/references/claude-md-block.md`](../../docs/orchestration/references/claude-md-block.md).
