# Gates: drop-in reviewers for the gates that already exist

superpowers already fires a review gate after every task and again over the whole
branch. That gate is a template dispatch, not a fixed reviewer identity — so almost
anything diff-shaped can be substituted into it, or added alongside it, without
touching either plugin's own files. This reference lists what actually drops in for
free, what needs one more input to work, and what should never be routed there at all.

## What the gate actually is

`requesting-code-review`'s "How to Request" step dispatches a `general-purpose`
subagent and fills the template at `code-reviewer.md` with four placeholders:
`{DESCRIPTION}`, `{PLAN_OR_REQUIREMENTS}`, `{BASE_SHA}`, `{HEAD_SHA}`. The filled
template tells that subagent to run `git diff --stat BASE_SHA..HEAD_SHA` and
`git diff BASE_SHA..HEAD_SHA`, review only that range, and never spawn a second
reviewer of its own — the section is literally titled "You Do Not Dispatch
Subagents". `subagent-driven-development` is what actually fires this: it calls the
gate after every task, plus one more pass over the whole branch before it is
considered done.

Because the placeholders are a template's inputs, not a reviewer's identity,
nothing about the mechanism requires the dispatched subagent to be the generic
reviewer prompt. The same `BASE_SHA`/`HEAD_SHA` range, `general-purpose` dispatch,
and no-further-delegation rule apply equally to a prompt that asks for
`confab-assertion-audit`, a named `pr-review-toolkit` agent, or `andon-verify`
instead. Swapping the target changes one dispatch call in the session; it edits no
file in either `superpowers` or the plugin supplying the reviewer.

## Reviewers that drop in with no setup

Each of these takes exactly what a diff already supplies — changed files and, where
relevant, their test files — and needs nothing else read or computed first.

|Reviewer|What it catches|What it needs|
|---|---|---|
|`confab-assertion-audit`|Whether the tests just written would actually catch a plausible mutation (off-by-one, boundary flip, condition negation) to the target source|Target source files + their test files — exactly the two halves of a diff that touched both|
|`confab-contract-drift`|Drift between type hints, signatures, docstrings, or API/OpenAPI/GraphQL schemas and how the code actually calls or handles them, "after a refactor" per its own description|Contract source files (typed source, schema files); no test files required|
|`pr-review-toolkit` `code-reviewer`|CLAUDE.md compliance, style violations, bugs, code quality|"Also the agent needs to know which files to focus on for the review" — defaults to `git diff` of unstaged work if not told otherwise|
|`pr-review-toolkit` `comment-analyzer`|Comment accuracy against the code, comment rot, misleading or outdated comments|The changed files carrying the comments|
|`pr-review-toolkit` `pr-test-analyzer`|Behavioral test coverage gaps, not line-coverage percentage|The diff and its test files|
|`pr-review-toolkit` `silent-failure-hunter`|Silent failures, inadequate error handling, inappropriate fallback behavior|The diff's changed catch blocks and error paths|
|`pr-review-toolkit` `type-design-analyzer`|Encapsulation, invariant expression, usefulness, and enforcement of new or changed types, rated 1-10 per axis|The diff's type definitions|

None of the six `pr-review-toolkit` agents declares a `tools:` key in its frontmatter
— each inherits the full tool set rather than being scoped down — and none of them
fetches a pull request on its own; all six read whatever files the dispatch prompt
names. That is what makes them diff-shaped rather than PR-shaped, and why they
substitute cleanly for the `code-reviewer.md` template's own read of
`BASE_SHA..HEAD_SHA`.

## Reviewers that need one more input

`andon-verify` is not frictionless the way the reviewers above are. It routes among
seven evidence-grounded strategies — adversarial tribunal, oracle-gap numerical V&V,
a falsifiability rubric, agentic-reliability dispatch, a structural graph tier check,
property/invariant proof, or verify-the-verifier — by first classifying signals read
from "the wire's contract". A dispatch that hands it only a diff and no stated
contract has nothing to route against; the skill's own text warns against defaulting
to the tribunal strategy as a guess rather than routing through the classifier every
time. The honest asymmetry: every reviewer in the table above works from the diff
alone, and this one does not — the gate prompt must state the contract being proved,
not just the commit range.

##### Prove a handoff, not just review a diff

````prompt
"before merging, run andon-verify over the range BASE_SHA..HEAD_SHA. The contract
to prove: every (file, kind) pair self-assess-idiom-fix rewrote must exactly match
the modernization pattern its finding cited, and touch no line the finding did not
name."
````

> Supplies the contract `andon-verify` needs up front, mirroring the handoff
> `self-assess-idiom-fix` already declares to `andon:andon-verify` rather than
> self-verifying its own remediation.

## Routing the gate by what the diff touched

`pr-review-toolkit`'s own README states this routing directly, under "Best
Practices — When to Use Each Agent": `silent-failure-hunter` "if changed error
handling", `comment-analyzer` "if added/modified comments", `type-design-analyzer`
"if added/modified types". Extended with the werkstoff leaves this reference already
covers, the same shape holds for six touch-categories:

|Diff touched|Dispatch|
|---|---|
|Anything (always)|A general reviewer — the superpowers gate's default `code-reviewer.md` template, or `pr-review-toolkit`'s `code-reviewer`|
|Tests|`pr-test-analyzer` and `confab-assertion-audit`|
|Error handling (catch blocks, fallbacks)|`silent-failure-hunter`|
|Types or signatures|`type-design-analyzer` and `confab-contract-drift`|
|Comments or docs|`comment-analyzer`|
|Dependency manifest (`package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`)|`confab-dependency-audit`|

## Gate prompts

##### Always: the general pass

````prompt
"dispatch a general-purpose subagent filling code-reviewer.md with BASE_SHA and
HEAD_SHA for this task's range, per requesting-code-review"
````

> The default gate `subagent-driven-development` already fires after every task.

##### Tests changed

````prompt
"run pr-test-analyzer and confab-assertion-audit over the diff between BASE_SHA and
HEAD_SHA — I want to know both whether coverage is adequate and whether the
assertions would catch a plausible mutation to the source they test"
````

> Two reviewers dispatched in one response, in parallel, per
> `dispatching-parallel-agents`'s primitive.

##### Error handling changed

````prompt
"run silent-failure-hunter over the catch blocks and fallback paths touched between
BASE_SHA and HEAD_SHA"
````

> Catches suppressed errors and inadequate logging before they reach main.

##### Types or signatures changed

````prompt
"run type-design-analyzer and confab-contract-drift over the type and signature
changes between BASE_SHA and HEAD_SHA"
````

> Pairs a design-quality read with a mechanical check that docstrings and
> call-sites still agree with the declared contract.

##### Comments or docs changed

````prompt
"run comment-analyzer over the doc and comment changes between BASE_SHA and
HEAD_SHA"
````

> Flags comments that no longer describe the code they sit next to.

##### Manifest changed

````prompt
"run confab-dependency-audit over this repo's manifest after the dependency
changes in this diff"
````

> Checks each declared package against its public registry rather than trusting
> the name looks right.

##### Before merge: prove the contract, not just review the diff

````prompt
"before merging, run andon-verify over BASE_SHA..HEAD_SHA against this contract:
[state the wire and the pass/fail condition explicitly]"
````

> `andon-verify` needs the contract named in the prompt — it does not infer one
> from the diff the way the reviewers above do.

## What not to put in a gate

Two categories do not belong in this dispatch slot, for different reasons.

**Orchestrators.** `andon-loop`, `confab-cycle`, and `self-assess-autopilot` are
fixed sequences that read artifacts their own earlier steps wrote and persist state
(a ledger, a convergence pass count, an approval-gated brief). Dispatched into a
single-diff review slot they either refuse for lack of their expected artifacts or
run far more machinery than one gate needs. They own a whole task; they do not fill
one beat in someone else's.

**Pipeline-internal agents.** `code-modernization`'s `scaffolder` and
`uplift-migrator` write into `modernized/<system>/` against an already-approved
architecture and have no standalone reviewing role. `claude-security` is the
sharpest case: its skill sets `disable-model-invocation: true`, so a model can never
propose dispatching it on its own initiative — a human has to invoke it directly —
and five of its seven agents state in their own definitions that they are not for
direct invocation. None of `claude-security`'s agents belong in this gate's
dispatch slot; the plugin's own command is the only sanctioned entry point.
