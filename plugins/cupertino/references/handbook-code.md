# Handbook dimensions — Code

Apple-engineering-craft framing: clarity, restraint, consistency —
informed by, not copied from, the HIG and Primer's design-systems
methodology applied to code instead of pixels. Unlike the design domain,
`cupertino` has no existing material for code conventions — every
dimension below is new. `cupertino-handbook-draft` reads this table to
know what to analyze in an existing codebase, or scaffold as a sensible
default for an empty one.

| Dimension id | Title |
|---|---|
| `naming-vocabulary` | Naming & vocabulary consistency |
| `error-handling` | Error-handling discipline |
| `module-boundaries` | Module boundaries & dependency direction |
| `api-surface` | Public API surface & predictability |
| `function-restraint` | Function size/complexity restraint |
| `comment-philosophy` | Comment philosophy |
| `formatting-baseline` | Formatting/lint baseline |

## `naming-vocabulary` — Naming & vocabulary consistency

**Rationale**: Craft's "the seam matters" applied to code: the same
concept should have the same name everywhere it appears, so the reader
never has to re-derive that two names mean the same thing.

**What the draft step analyzes/scaffolds**: the vocabulary already in use
for the project's core domain concepts (e.g. does "user" ever become
"account" or "customer" elsewhere for the same entity?), and the casing/
naming convention already established per language.

**Detection signal**: a new identifier introducing a synonym for an
existing domain concept already named elsewhere, or a naming-convention
mismatch (e.g. `snake_case` introduced into an otherwise `camelCase`
module).

## `error-handling` — Error-handling discipline

**Rationale**: Reduction applied to failure: a swallowed error removes
information the next reader needs, which is the opposite of restraint —
restraint means doing without decoration, never doing without visibility.

**What the draft step analyzes/scaffolds**: how the codebase currently
signals failure (exceptions, result types, error codes) and whether
catch/except blocks already log, re-raise, or handle explicitly rather
than swallowing silently.

**Detection signal**: a new empty or comment-only `catch`/`except` block,
or a new function that can fail with no way for its caller to observe
that.

## `module-boundaries` — Module boundaries & dependency direction

**Rationale**: Hierarchy's "system tokens, not local values" applied to
architecture — a dependency direction that only holds by convention, not
by structure, is a system that looks coherent until someone doesn't know
the convention.

**What the draft step analyzes/scaffolds**: the project's actual layering
(what depends on what) and any stated or observable rule about which
direction is allowed (e.g. "core never imports from adapters").

**Detection signal**: a new import that crosses a layering boundary the
handbook names as one-directional (e.g. a domain-layer file importing from
an infrastructure-layer file).

## `api-surface` — Public API surface & predictability

**Rationale**: Usability's "every action must have an immediate,
perceptible consequence" applied to APIs: a caller should be able to
predict a function's behavior from its name and signature alone.

**What the draft step analyzes/scaffolds**: the project's convention for
what counts as public vs. internal (module boundaries, `__all__`, export
lists, access modifiers) and whether public signatures already avoid
surprising side effects (a getter that mutates, a "read" function that
writes).

**Detection signal**: a new public function whose name implies a pure
read/query but that also mutates state, or a new public API added with no
corresponding entry in the project's documented API surface.

## `function-restraint` — Function size/complexity restraint

**Rationale**: Reduction applied to a single unit of code: a function that
does one thing is one the reader can hold in context at once, matching
this repo's own stated preference for "smaller, focused files" and units.

**What the draft step analyzes/scaffolds**: the rough size/complexity
already typical for functions in this codebase (not an arbitrary universal
number — calibrated to what this project's own idiomatic functions look
like), to avoid importing a generic threshold that doesn't fit the
project's actual style.

**Detection signal**: a new function significantly longer or more
deeply nested than the codebase's own established norm for its language
and layer.

## `comment-philosophy` — Comment philosophy

**Rationale**: "Why, not what" — a comment that restates what well-named
code already says is noise; a comment that explains a non-obvious
constraint, invariant, or workaround is craft.

**What the draft step analyzes/scaffolds**: whether the codebase's
existing comments (where present) tend to explain the "why" already, or
lean toward restating the "what" — this becomes the handbook's stated
target, not an imported universal rule.

**Detection signal**: a new comment that only restates the line(s) below
it in prose, adding no information a reader couldn't get from the code
itself.

## `formatting-baseline` — Formatting/lint baseline

**Rationale**: Consistency at the mechanical layer frees attention for the
decisions that actually matter — this dimension exists to name whatever
formatting/lint baseline the project has already chosen, not to invent a
new one.

**What the draft step analyzes/scaffolds**: the project's existing
formatter/linter configuration (if any) and codifies it as a named rule
in the handbook rather than leaving it implicit in a config file nobody
reads as policy. If a `self-assess`-family skill (`self-assess-lint-audit`,
`self-assess-code-idiom`) is present in the current session's Skill list,
name it as complementary here — it already enforces house-rules-level
formatting/idiom conventions in more depth than this handbook attempts;
this dimension only needs to state the baseline, not re-implement that
enforcement.

**Detection signal**: new code that doesn't match the project's own
declared formatter output (e.g. inconsistent quote style, indentation, or
import ordering relative to the rest of the codebase).
