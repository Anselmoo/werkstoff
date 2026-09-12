# Delegation — the registry, the ledger, and the loop breaker

How arbeitsplan reaches another plugin, how deep that may nest, and why the answer is a file
rather than a convention.

**Contents** — [two axes](#delegation-and-ordering-are-different-axes) ·
[the registry](#the-registry) · [the ledger](#the-ledger-analysisarbeitsplanrunidde) ·
[the loop breaker](#the-loop-breaker) · [worked chain](#a-worked-chain)

## Delegation and ordering are different axes

They look alike and are not, and conflating them is how one of them ends up unenforced.

| | **delegation** | **ordering** |
|---|---|---|
| the question | who dispatched whom, and how deep | has the required step run |
| the shape | a call graph | a marker on disk |
| lives in | this ledger, gated by arbeitsplan's hook | `.claude/takt.local.md`, gated by takt |
| covers a raw `Write`/`Edit`? | **no** — there is no dispatch to record | **yes** |

takt's canonical beat is *"no `*.tsx` write until `.takt/council-done` exists"*. No delegation
ledger can express it: nothing was dispatched. That is why generalizing delegation does **not**
subsume takt, and why both mechanisms exist.

## The registry

Every plugin declares what it offers and what it awaits, in
`plugins/<name>/.claude-plugin/beats.json`:

```json
{
  "$schema": "arbeitsplan/beats/1",
  "plugin": "andon",
  "produces": [
    { "marker": "wire-proven", "after": "andon-verify",
      "meaning": "one named wire has been proven against evidence, not asserted" }
  ],
  "requires": [
    { "marker": "transform-brief-written", "from": "self-assess", "before": "andon-loop",
      "optional": false, "reason": "andon-loop already says to STOP and run it first, in prose." }
  ]
}
```

`emit_beats.py --repo-only` compiles the union of every declaration into one
`.claude/takt.local.md`, and takt enforces it. Two refusals in that compiler are deliberate:

- an **optional** requirement whose producing plugin is absent is **dropped and reported** —
  enforcing an order against a plugin that cannot run would deny forever;
- a requirement naming a marker **no installed plugin produces** is **dangling**: reported and
  *not compiled*, because a beat whose marker nothing can create is an unconditional denial
  wearing an ordering costume.

### Why the file sits next to `plugin.json`

`M-REF-UNWIRED` requires every `references/*.md` to be named by a `SKILL.md`. **takt ships no
skills.** A beats file under `references/` would be permanently unwireable in the one plugin
that most needs one, so it lives in `.claude-plugin/` with the manifest, which is also where it
belongs conceptually: it is plugin metadata, not documentation.

## The ledger: `analysis/arbeitsplan/<runId>/delegation.jsonl`

One JSON object per line, append-only.

```json
{"id":"d-0003","runId":"ap-2026-09-12-a3f1","parent":"d-0001","depth":2,"source":"arbeitsplan","target":"compass:compass-explore-branches","pattern":"parallel","branches":["b1","b2","b3"],"merge":{"at":"arbeitsplan","strategy":"first_success","combine":"select_winner"},"status":"in_progress","timestamp":"2026-09-12T09:10:00Z"}
```

| key | meaning |
|---|---|
| `id`, `parent`, `depth` | position in the call graph; `parent: null` is a root |
| `source`, `target` | plugin, or `plugin:skill`. Compared **by plugin** — a cycle is a property of plugins, not of individual skills |
| `pattern` | `serial` (carries `chain`) or `parallel` (carries `branches`) |
| `merge` | `{at, strategy, combine}` — `wait_all`/`first_success`/`any` × `concat`/`select_winner`/`merge_fields`. `null` for serial |
| `status` | `pending`, `in_progress`, `completed`, `failed`, **`denied`** |

### Why JSONL and not JSON

The ledger is written by agents running **in parallel** — the plugin's whole premise. A single
JSON document needs read-modify-write: two writers read the same array, each appends its own
record, and one silently disappears. An `O_APPEND` write of one line is atomic under `PIPE_BUF`,
so parallel writers cannot lose each other's records. Same argument that made the dispatch
ledger one-file-per-signature.

**That guarantee has a size.** POSIX floors `PIPE_BUF` at 512 bytes; Linux sets it at 4096. A
longer record can interleave, so `MAX_RECORD_BYTES` is enforced on write and a long branch list
belongs in the spec, not here.

A **denied** delegation is recorded *before* the refusal. A denial nobody can see afterwards is
indistinguishable from a call that was never made, and the ledger is the only account of why a
run stopped where it did.

## The loop breaker

Two rules, both in `hooks/arbeitsplan_guard.py`, because prose is measured at baseline here.

| rule | catches | why the other one misses it |
|---|---|---|
| **depth cap: 3** | an honest but runaway chain, `A→B→C→D` | no cycle exists; nothing repeats |
| **cycle detection** | `A→B→A` | depth 2 — under any cap, so the cap would only decide how much it costs first |

A design with only a cap treats a two-node infinite loop as legal until it has paid three levels
of fan-out for it. A design with only cycle detection lets a genuinely deep chain multiply
fan-out at every level. Neither subsumes the other, and the sabotage tests prove it: unbound the
cap and only the `DEPTH` cases go red; disable the cycle check and only the `CYCLE` cases do.

**A dispatch to this plugin's own agents is fan-out, not delegation**, and is not counted —
otherwise a three-candidate build would look like a three-deep chain and trip the breaker on
ordinary work. The comparison is against the **dispatching source**, not the run's owner: using
the owner left `arbeitsplan → compass → arbeitsplan` classified as fan-out, skipping the cycle
check on exactly the shape it exists for. That hole was found by the calibration, not by reading.

## A worked chain

```
d1  depth 0   arbeitsplan -> compass:compass-explore-branches   in_progress
d2  depth 1   compass     -> andon:andon-verify                 completed
d3  depth 2   andon       -> matrize:matrize-decode             completed
d4  depth 3   matrize     -> lehre:lehre-gauge                  DENIED — over the cap of 3
```

and a cycle, denied two levels earlier than the cap would have:

```
d1  depth 0   arbeitsplan -> compass:compass-solve              completed
d2  depth 1   compass     -> arbeitsplan:arbeitsplan-run        DENIED — arbeitsplan already
                                                                 appears in its own ancestor chain
```

Inspect either with:

```bash
python3 plugins/arbeitsplan/scripts/delegation.py show --ledger analysis/arbeitsplan/<runId>/delegation.jsonl
```
