#!/usr/bin/env python3
"""Regenerate a plugin from its behavior spec via the official create-plugin path.

Runs in a FRESH `claude --print` process on purpose. The whole value of
serializing to behavior JSON is that the builder never sees legacy's prose — and
a session that has been reading legacy source is itself the anchor. So this is
not a convenience wrapper; the process boundary is the experiment.

Two things are deliberately NOT passed in:
  * the legacy plugin directory — that would restore the anchoring
  * the capability inventory — the gate compares against it afterwards, and
    feeding it in would let the builder satisfy the gate structurally without
    the behavior spec having earned it

`/plugin-dev:create-plugin` normally interviews the user (it lists
AskUserQuestion in allowed-tools and says to wait for answers). Headless, there
is nobody to answer — which is fine, because the behavior spec already answers
its discovery questions. The prompt says so explicitly rather than leaving the
model to stall or invent.

The enforcement requirements are stated here AND checked by gate 2 afterwards.
Stating them alone would repeat the exact failure this rebuild exists to fix: a
rule written in prose that the model must re-read and choose to honor.

Usage:
    generate_plugin.py analysis/rebuild/andon.behavior.json -o plugins/andon
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MODEL = "opus"

REQUIREMENTS = """
NON-NEGOTIABLE IMPLEMENTATION REQUIREMENTS

These are checked mechanically after you finish. A plugin that states them in
markdown but does not implement them in executable code FAILS and is rebuilt.

1. ENFORCEMENT IN CODE, NOT PROSE.
   Every rule in the spec's "rules" array whose "must" says MUST NOT / MUST
   refuse / MUST halt / MUST stop has to be enforced by executable code that can
   actually refuse — a conditional that tests the rule's own state and then
   throws, raises, returns early, breaks, or exits non-zero. A sentence in a
   SKILL.md telling the model to stop is NOT enforcement: it is a rule the model
   must re-read and choose to honor, and it is measurably unreliable.
   Put these guards in a workflow script (workflows/*.js) or a stdlib helper
   script (scripts/*.py) that the skill invokes.

2. NUMERIC BOUNDS ARE CONSTANTS IN CODE.
   Every threshold, retry/repeat limit, depth bound or "at most N" in the spec
   becomes a named constant plus a conditional that enforces it. Not a sentence.

3. PERSISTED STATE IS VALIDATED ON READ AND WRITE.
   If the plugin reads or writes any artifact (a ledger, a report, a state
   file), ship a validator that rejects a record missing a field that gates a
   decision. Never infer, default, or repair a missing gating value — reject it
   and surface it. A value nobody supplied must never enter the artifact.

4. FIELDS THAT GATE A DECISION ARE FIRST-CLASS KEYS.
   Anything a later decision branches on lives in structured frontmatter or
   JSON, never in a prose sentence inside a body paragraph.

5. WRITE SCOPE IS ENFORCED BEFORE DISPATCH, IN CODE.
   Reject path traversal, absolute paths, and targets outside the plugin's
   declared output directory — with a check that throws, before any write.

6. A RULE THAT MUST HOLD REGARDLESS OF MODEL COOPERATION GOES IN A HOOK.
   This is measured, not theoretical. Across ~40 runs, every in-plugin layer
   degrades the same way, because entering it is a sentence the model chooses
   to follow:

       rule as prose in a SKILL.md            baseline
       rule as code that raises               19 rules enforced, 1 case in 5 moved
       guard behind a fenced `python3` block  invoked 1 run in 3
       guard inside the Workflow script       workflow dispatched 1 run in 14
       PreToolUse hook                        blocked on the first attempt

   So for any rule whose "must" says MUST NOT / refuse / halt / stop, ship a
   `hooks/hooks.json` declaring a PreToolUse hook plus the script it runs:

     - `"type": "command"`, NEVER `"type": "prompt"` — a prompt hook asks a
       model to decide, which is the model-mediated path this replaces.
     - The deny path must emit BOTH: exit code 2 with the reason on stderr,
       AND stdout JSON of exactly
       {"hookSpecificOutput":{"hookEventName":"PreToolUse",
        "permissionDecision":"deny","permissionDecisionReason":"<why>"}}
       Omitting `hookEventName` or using `systemMessage` instead of
       `permissionDecisionReason` makes the runtime SILENTLY IGNORE the deny —
       the hook runs, decides correctly, and the edit proceeds anyway.
     - The hook MUST be inert unless this repo actually uses the plugin: check
       for the plugin's own state/artifact directory first and exit 0 allowing
       when absent, or it will police every unrelated repository.
     - Fail CLOSED on internal error, and name an explicit escape hatch in the
       message. Beware helpers that swallow errors: `pathlib.Path.glob()`
       silently returns nothing on PermissionError, which turns an unreadable
       state directory into "nothing to enforce".

DESIGN FREELY OTHERWISE. The spec states obligations, not implementations. You
are not porting anything; there is no existing code to preserve or match.
"""

PROMPT = """/plugin-dev:create-plugin

Build a complete Claude Code plugin that satisfies the behavioral specification
below. Write it into the current working directory.

This is a NON-INTERACTIVE run. Do not ask clarifying questions and do not wait
for answers — there is nobody to answer them. The specification already answers
create-plugin's discovery questions: what the plugin is for, when each skill
triggers, what each component must guarantee. Where the spec is genuinely silent
on a detail, choose a sensible default and note it in the plugin's README under
"Design decisions".

There is no existing implementation to look at, port, or match. Design from the
obligations.

@@REQUIREMENTS@@

BEHAVIORAL SPECIFICATION
@@SPEC@@

FRONTMATTER MUST PARSE AS YAML
Every skills/<id>/SKILL.md and agents/<id>.md begins with `---` frontmatter.
If it fails to parse, the file still loads — with EMPTY metadata, no
description and no tools — so the skill or agent silently never triggers. It
looks fine on disk and does nothing. This has already happened once: three
agents were written with a bare multi-line `description:` containing raw
`<example>` blocks and unescaped quotes.

  - `description:` must be either a single-line double-quoted scalar, or a
    YAML block scalar introduced with `>-` whose continuation lines are all
    indented. Never start a continuation line at column 0.
  - Inside a bare (unquoted) scalar, never use `<`, `>`, `:` followed by a
    space, `#`, or an unescaped `"`.
  - QUOTE ANY VALUE CONTAINING BRACKETS. `[` opens a YAML flow sequence, so
    CLI-usage notation collides with it: `argument-hint: [path] [--flag]` is
    two flow sequences side by side and is INVALID YAML. This is the single
    most common break observed — it silently killed 8 of 8 skills in one
    generated plugin. Write `argument-hint: "[path] [--flag]"` instead.
    The same applies to any value with `{`, `}`, `,`, `&`, `*`, `|` or a
    leading `%` or `@`.
  - Put long trigger examples in the BODY, below the closing `---`, not in the
    frontmatter.
  - Before you finish, re-read each frontmatter block and confirm it is valid
    YAML.

Produce the full plugin: .claude-plugin/plugin.json, skills/, agents/,
workflows/ and/or scripts/ as needed, and a README.md. Every skill and agent in
the spec must exist, and every rule in the spec must be implemented — a rule
with no implementation is a silently dropped requirement. If the spec is large,
work through the rules list systematically rather than summarising it. When
finished, list the files you created.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Regenerate a plugin from its behavior spec.")
    ap.add_argument("behavior_json", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--transcript", type=Path)
    args = ap.parse_args(argv)

    if not args.behavior_json.is_file():
        print(f"ERROR: no such spec: {args.behavior_json}", file=sys.stderr)
        return 2
    spec = args.behavior_json.read_text()
    doc = json.loads(spec)
    prompt = PROMPT.replace("@@REQUIREMENTS@@", REQUIREMENTS).replace("@@SPEC@@", spec)

    work = Path(tempfile.mkdtemp(prefix="regen-"))
    print(f"generating {doc.get('plugin')} with {args.model} in {work}", file=sys.stderr)
    print(f"  spec: {len(doc.get('skills', []))} skills, {len(doc.get('agents', []))} agents, "
          f"{len(doc.get('rules', []))} rules", file=sys.stderr)

    # plugin-dev must stay ENABLED here — it is the generator. The clean box is
    # for testing the result, not for building it.
    cmd = ["claude", "--print", "--model", args.model,
           "--permission-mode", "bypassPermissions", prompt]
    try:
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True,
                           timeout=args.timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print(f"ERROR: generation timed out after {args.timeout}s; work kept at {work}", file=sys.stderr)
        return 1

    out = r.stdout.strip()
    if args.transcript:
        args.transcript.parent.mkdir(parents=True, exist_ok=True)
        args.transcript.write_text(out + ("\n\n--- stderr ---\n" + r.stderr if r.stderr else ""))
    if not out or re.search(r"hit your (session|usage) limit|not logged in", out, re.I):
        print(f"ERROR: generation did not run — {out[:150] or r.stderr[:150]}", file=sys.stderr)
        return 1

    produced = work / ".claude-plugin/plugin.json"
    if not produced.is_file():
        # Some runs nest the plugin one level down under its own name.
        nested = list(work.glob("*/.claude-plugin/plugin.json"))
        if nested:
            work = nested[0].parent.parent
        else:
            print(f"ERROR: no plugin.json produced; work kept at {work}", file=sys.stderr)
            print(out[-600:], file=sys.stderr)
            return 1

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(work, args.out)
    n = sum(1 for _ in args.out.rglob("*") if _.is_file())
    print(f"wrote {args.out} ({n} files)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
