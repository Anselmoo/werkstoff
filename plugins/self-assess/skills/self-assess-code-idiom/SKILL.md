---
name: self-assess-code-idiom
description: This skill should be used when the user asks to "find modernization opportunities", "check for deprecated idioms", "find code smells", or as part of self-assess-autopilot's CHECK phase. Judges idioms against the actual language version declared in the repo's manifest, never a fixed list, and categorizes each finding as modernization or smell.
---

# self-assess-code-idiom

Find deprecated idioms the repo's own declared language version obsoletes, plus generic code
smells.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-code-idiom
```

## Step 1: Detect the actual version per language -- never assume one

Rule: judge idioms against the version the manifest actually declares, not a fixed list or
training-data assumption:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py detect-language-version --repo <repo_root> --language python
```

Run once per detected language (reuse `detect-languages` from preflight/stage-map for the
list). A `null` result means the manifest declares no version constraint -- in that case, only
flag idioms deprecated in EVERY version the language has ever shipped, never a version-specific
one, since there is nothing to judge against.

## Step 2: Find findings, categorized

Dispatch `idiom-auditor` with the detected version per language and (if present)
`.claude/house-rules.md` for repo-specific style context. Every finding MUST carry
`category` in `{"modernization", "smell"}`:

- `modernization`: a deprecated language/library idiom the detected version actually
  obsoletes (e.g. `Optional[X]` when the manifest declares Python >=3.10 supports `X | None`).
  Never flag an idiom the declared version does NOT obsolete.
- `smell`: a generic quality issue (broad `except`, magic numbers, long functions, deep
  nesting, missing types in an otherwise-typed module) that requires design judgment, not a
  mechanical rewrite.

Findings ambiguous enough that a mechanical fix could be wrong (e.g. the "modern" idiom would
change behavior in this codebase's edge case) MUST carry a `severityNote` -- this is the flag
`self-assess-idiom-fix` uses later to skip auto-applying them.

## Step 3: Verify

Unless `skip_verification` is set, confirm each finding by re-reading the cited code and
re-checking it against the detected version -- never trust the first pass.

## Step 4: Validate and write

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind code_idiom_summary --file <path-or-inline-json>
```

The validator rejects any finding whose `category` is outside `{modernization, smell}`.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename CODE_IDIOM.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename code_idiom_summary.json
```

## Read-only constraint

Never use Write/Edit outside the resolved output paths, and never apply a finding here --
`self-assess-idiom-fix` is the only skill authorized to act on `code_idiom_summary.json`.
