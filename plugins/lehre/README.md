# lehre

**Researches a code style, pattern and architecture doctrine — then denies the write
that would violate it.**

A *Lehre* is a go/no-go gauge: a fixture a part either passes through or is rejected by.
It also means doctrine. This plugin is both halves.

## Why this exists

Loose process discipline produces antipatterns because nothing holds a generation loop
to an architecture. `obra/superpowers` ships 14 skills and one `SessionStart` hook, so
every rule it carries sits on the top row of the enforcement ladder this repository
measured over ~40 runs:

| layer | how often the guard actually runs |
|---|---|
| prose in a `SKILL.md` | baseline |
| a fenced `python3 ...` command in a skill | 1 run in 3 |
| a guard inside a Workflow script | workflow dispatched 1 run in 14 |
| **`PreToolUse` hook, `type: "command"`** | **blocks, first attempt** |

lehre puts the rules that must hold on the bottom row. A blocking rule is not advice
a model may skip under load; the write is refused, with the rule's own rationale in the
denial message.

## What it is not

- Not a post-hoc auditor of documented conventions — that is `self-assess`.
- Not a deriver of canon from undocumented variants — that is `codebase-consistency`.
- Not a sequencing gate for cross-plugin beats — that is `takt`, which gates *whether a
  step ran*. lehre gates *what the code may look like*, and enforces its own unit order
  internally, so it needs neither.

lehre owns the write-time layer none of them occupy, plus the detection and remediation
lifecycle around it. It writes `LEHRE_BRIEF.md`, never `MODERNIZATION_BRIEF.md`, and
refuses to read any artifact whose `provenance` is not `lehre` — this repo's
`docs/orchestration/references/routing.md` records a real, unguarded filename clash
between two other pipelines, and this is the guard that clash should have had.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install lehre@werkstoff
```

lehre is inert until a repository declares a doctrine, so installing it changes nothing
until `.lehre/ruleset.json` exists.

## Two entry modes

**Greenfield — a blank page.** No files yet. `lehre-decompose` turns stated intent into
build units, the seams between them, and a dependency order that is *enforced*: a write
into a later unit is refused until the earlier one passes `lehre-validate`.

**Brownfield — an existing tree.** `lehre-codify` researches the doctrine against real
repository evidence, and `lehre-gauge` sweeps for what already violates it.

```
                     ┌─ greenfield ─ lehre-decompose ─┐
lehre-preflight ─────┤                                ├─> lehre-codify ─> .lehre/ruleset.json
                     └─ brownfield ───────────────────┘
                                                                 │
   lehre-gauge ──> lehre-brief ──> lehre-conform ──> lehre-validate ──> lehre-pin
    evaluate        suggest         implement          validate           test
                    (approval)          ^              (closes the unit)
                                        │
                            lehre_guard.py PreToolUse hook
```

## What is enforced, and what is not

Stated plainly, because a rule everyone believes blocks and doesn't is worse than no
rule at all.

| | denied at write time | fails a sweep and CI |
|---|---|---|
| `blocking` + `forbid-path` / `require-location` / `python-import` / `python-construct` | **yes** | yes |
| `blocking` + `linter` | no — content is not on disk yet | yes |
| `advisory` with a machine predicate | no | reported, does not fail |
| `advisory` + `judgement` | no | reported for `violation-auditor`; **never** machine-checked |
| anything written through `Bash` rather than `Write`/`Edit` | no | yes |
| a write into a unit with unvalidated dependencies | **yes** | — |
| a write to `.lehre/units/*.done` or a weakening of `.lehre/ruleset.json` | **yes** | — |

The two gaps are deliberate and layered over, not hidden: `lehre-gauge` sweeps the tree
as it actually is, and `lehre-pin` emits a CI check that runs the same evaluator with no
agent in the loop.

## The doctrine map

One HTML report, written to `.lehre/DOCTRINE_MAP.html`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_doctrine_html.py" . \
    --template "${CLAUDE_PLUGIN_ROOT}/assets/doctrine-viewer.html" \
    --tokens "${CLAUDE_PLUGIN_ROOT}/assets/tokens.css"
```

It answers the one question this plugin exists for — *of every rule declared, how many
actually deny a write?* — and that is a **flow** question, not a categorical one. Each
rule travels `provenance -> severity -> check kind -> enforcement outcome`, so the
primary view is a Sankey with a funnel strip above it and the unit build-order graph
below.

Three choices worth stating, because each is load-bearing:

- **Ribbons are coloured by where a rule ENDS, not where it starts.** A blocking rule
  draining into amber "sweep + CI only" is the exact failure this plugin is built
  around; a source-coloured Sankey would hide it.
- **The funnel is genuinely nested.** `declared -> blocking -> denied at write time`,
  each a strict subset of the last. Hook-tier is deliberately *not* a step: it counts
  advisory rules too, so it is not a subset of blocking, and slotting it between them
  renders a "no drop" that is an artifact of two overlapping sets rather than a fact.
- **A single global scale across all four stages.** Legitimate only because every rule
  passes exactly one node per stage, so all stages sum to the same total. A per-stage
  scale would make a 2-rule band in a 2-node stage look like a 5-rule band in a 5-node
  one.

Self-contained and offline — no CDN, no network, no external font. It deliberately does
**not** vendor the marketplace's 125 KB d3 subset: that bundle ships d3-hierarchy, zoom,
selection, interpolate, ease, force and scale, but no `d3-sankey`, so the layout is
hand-written and the dependency would buy nothing. It does vendor
`tools/design-tokens/tokens.css`, because a viewer inventing its own palette would break
the one thing all eight viewers share.

Click any node in the enforcement flow to filter the rule table; ribbons are grouped by
full path tuple, so the filter is exact rather than approximate.

![Doctrine map for an 11-rule brownfield ruleset: a funnel reading 11 declared, 8 blocking (-3), 5 denied at write time (-3), and a separate amber "3 believed to block" callout for the blocking rules that never deny a write; below it a Sankey carrying every rule from provenance through severity and check kind to enforcement outcome, with the three linter-kind ribbons draining amber into "sweep + CI only"; a build-order graph showing contracts validated, adapters and writer ready, and cli blocked by both; and a rule table listing all 11 rules with severity, provenance, check kind, enforcement badge and rationale](assets/doctrine-viewer-screenshot.jpg)

That image is reproducible rather than a one-off capture — the doctrine it shows is
committed at `scripts/fixtures/sample_doctrine_ruleset.json` (11 rules chosen so all four
enforcement outcomes and all six check kinds appear, and so three blocking rules leak into
amber). To rebuild it:

```bash
mkdir -p /tmp/lehre-demo/.lehre/units
cp plugins/lehre/scripts/fixtures/sample_doctrine_ruleset.json /tmp/lehre-demo/.lehre/ruleset.json
touch /tmp/lehre-demo/.lehre/units/contracts.done   # so `contracts` renders validated, `cli` blocked
python3 plugins/lehre/scripts/build_doctrine_html.py /tmp/lehre-demo \
    --template plugins/lehre/assets/doctrine-viewer.html \
    --tokens plugins/lehre/assets/tokens.css
```

## The guard protects its own control plane

Gates on the tree are worth nothing if the agent can edit the state the gates read.
Both of these returned exit 0 before Gate 0 existed, verified by probe rather than
assumed:

```
Write .lehre/units/contracts.done             -> ALLOWED   forge the marker, skip the order gate
Write .lehre/ruleset.json  {... "rules": []}  -> ALLOWED   blank the doctrine, pass everything after
```

Neither was caught downstream, because `lehre-pin`'s CI runs the gauge against whatever
ruleset is on disk — a gutted one exits 0 and CI is green. "Only `lehre-validate` writes
the marker" was prose, which this repo measures at the *bottom* of the enforcement
ladder, guarding the file the *top* of it depends on.

Gate 0 now denies both, and the ordering is deliberate: it runs before the gates it
protects.

- **`.lehre/units/*.done`** — refused outright. That state records that a unit's rules
  and seams were *checked*, so writing it by hand asserts a check that never ran. No
  legitimate author is affected: `lehre_cli.py close` writes it through `Bash`, which
  this hook does not match.
- **`.lehre/ruleset.json`** — weakening refused, **tightening allowed**. A change is
  weaker only if a rule that currently denies writes stops denying, or a build-order
  dependency edge disappears. Adding a rule, raising a severity, extending a `forbid`
  list and editing prose all pass untouched, so `lehre-codify` never needs the bypass.
  A proposed file that will not parse counts as weakening, not as an error to pass
  through — an unusable ruleset makes the hook fail closed on every later write.

The denial message deliberately does **not** name the marker path, the unit, or the
convention. The order-gate message used to end "it writes `.lehre/units/<unit>.done`",
which told a blocked model exactly what to forge. A refusal should not double as
instructions.

## Rule provenance

Every rule names an external authority. Its `sourceMode` says what else it rests on:

- `evidence-backed` — authority **and** real `file:line` in this repo (brownfield only)
- `intent-derived` — authority **and** a span quoted from the user's stated intent
- `scaffolded-default` — authority alone, honestly labelled. **The normal case on a
  blank page**, not a degraded one

`rule-critic` independently re-derives each claim. A rule citing `file:line` in a repo
where no such file exists is refused — on greenfield that is the fabrication a
schema-satisfying researcher reaches for first.

## The check vocabulary is closed

Six kinds, and an unknown kind is a schema error rather than a silently skipped rule.
Path matching is `fnmatch`, never regex; structural matching is Python's `ast`. Three of
the six silent defects in this repository's `CLAUDE.md` are regex forms that match
nothing and raise nothing — `[^.]{0,80}` cannot span a dotted filename, `[^\n]` in a
bracket expression means "not backslash, not the letter n", `\b!==\b` never matches. A
glob cannot express any of them.

### The sixth kind exists because of a defect

`doctrine-researcher` is told to return candidates whose predicate is NONE — "is this a
process boundary", "does this handler own business logic" — and `lehre-codify` files those
as advisory. The schema then **refused to persist them**, because `check.kind` had to be one
of the five machine kinds. So the pipeline researched a rule class it could not store, and
`violation-auditor` — whose entire job is auditing that class — was dispatched by nothing,
because nothing could ever be in its input set. `confab-agentic-reliability` found it.

`judgement` is the honest home for those: advisory **by schema** (a blocking rule nothing
can evaluate is a validation error, not a footnote), required to carry the question an
auditor answers in `check.asks`, never evaluated by `evaluate_file`, and surfaced by the
gauge as `needs_judgement_pass` so `lehre-gauge` step 5 can dispatch the auditor once per
rule. It never counts toward the violation total and never fails a sweep on its own.

See [`references/ruleset-schema.md`](references/ruleset-schema.md) for the full schema.

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Start a new project so it cannot drift

````prompt
"I'm starting a CLI that ingests CSV from three vendors and writes Parquet. Set it up
properly — I don't want the usual mess where everything imports everything."
````

##### Establish and enforce a doctrine on an existing repo

````prompt
"research what rules this codebase should follow for its stack, check them against what
we actually do, and make the important ones actually enforced"
````

##### Find where the code violates its own architecture

````prompt
"where do we violate our own layering, and which of those are real"
````

##### Make the rules survive without the plugin

````prompt
"pin these rules into CI so they still hold when nobody's running Claude"
````

##### Ask what is currently blocked

````prompt
"lehre status — what can I build next?"
````

## Verifying a change to this plugin

```bash
python3 plugins/lehre/scripts/test_lehre_core.py     # evaluator + schema known answers
python3 plugins/lehre/hooks/test_lehre_guard.py      # the hook denies AND allows
python3 test/plugins/lint-frontmatter.py plugins/lehre
python3 test/plugins/verify-hooks-deny.py plugins/lehre
claude plugin validate plugins/lehre --strict
```

`test_lehre_core.py` is not optional ceremony. Its first run caught a real defect: one
import statement produced two violations, because the extractor deliberately reports
both `a.b` and `a.b.c` for `from a.b import c`. The hook still denied — just with a
doubled count feeding every report built on top of it.

### Behavioural cases

Four cases in `test/plugins/cases.tsv` exercise the model-mediated half, where prose is
what can be skipped. The hook is not among them: it is deterministic and covered by the
two scripts above.

```bash
bash test/plugins/calibrate-lehre-oracles.sh    # ALWAYS first — see below
bash test/plugins/verify-clean-box.sh
bash test/plugins/run.sh lehre-validate-fidelity
```

| case | seeded defect |
|---|---|
| `lehre-gauge-layering` | a real layering violation, plus a clean sibling that must not be reported |
| `lehre-validate-fidelity` | **zero** rule violations — the intent names three vendors and only two exist, and `get_adapter` returns `None` silently |
| `lehre-gauge-unevaluated` | a file that will not parse, which must be reported unjudged rather than clean |
| `lehre-preflight-greenfield` | no source files, and a prompt that calls the repo "this existing codebase" |

Measurement history, kept because the corrections matter more than the numbers:

- An early N=5 sweep of `lehre-validate-fidelity` scored 4/5. The one FAIL was an **oracle
  false negative** — markdown emphasis split `not` from `close`, and the alternation
  required them adjacent. The run had refused correctly. Oracle revised; the exact phrasing
  is now a fixed must-PASS case in the calibration suite.
- A later sweep scored 4/5 again. That FAIL **never executed** (`API Error: Your computer
  went to sleep`, 245 bytes). `run.sh` scores ERROR on rate-limit and login banners and on
  sub-200-byte replies, but not on that, so an interrupted run was recorded as a plugin
  failure. Worth fixing in `run.sh`; it would mis-score any plugin's sweep.
- **Both of those sweeps are void anyway**, along with the first four case results: the
  fixtures documented their own seeded defect in `README.md`, and `run.sh` strips only
  `_EXPECTED.md`. The answer key was copied into the model's working directory. Renaming to
  `_EXPECTED.md` fixed it; a post-strip check confirms `vendor_c` now survives only in
  `ruleset.json`'s `intent`, which is the input the plugin must reason from.
- **Currently verified, on clean fixtures, every transcript read rather than tallied:** all
  four cases PASS at N=1, and `lehre-validate-fidelity` is **5/5 with 0 errors** at N=5. In
  none of the five did the run invoke `close` — the anti-pattern never had to fire. All five
  reported the ruleset passing, which is the point: the fidelity gap is orthogonal to every
  rule in the doctrine, and no rule could have caught it.

That 5/5 is worth reading carefully rather than as a score. This case is not a prose-only
guard: closing a unit requires actively invoking `lehre_cli.py close`, so failing it means
running a command, not merely omitting a sentence. That is why it holds N/N where a rule
living only in a SKILL.md would not — and it is the whole argument for where this plugin
puts its gates.

`calibrate-lehre-oracles.sh` runs first because an oracle must be proven to discriminate
*before* it grades anything — never retuned after seeing a result. Its 14 assertions pair
one correct transcript per case with violations that must fail, and the one that earns
its keep is `lehre-validate-fidelity`'s anti-pattern: a run that names the `vendor_c` gap
and closes the unit anyway says all the right words and does the wrong thing. Only the
anti-pattern separates it from a correct refusal.

## Escape hatch

`LEHRE_DISABLE_GUARD=1` bypasses the guard for one session. It is deliberately visible
and deliberately total: there is no per-rule bypass, because a per-rule bypass becomes
permanent. If a rule is wrong, amend it through `lehre-codify` so the change is
recorded and reviewed.
