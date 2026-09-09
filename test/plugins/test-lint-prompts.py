#!/usr/bin/env python3
"""Calibration for tools/prompt-review/lint_prompts.py — the instrument asserts itself.

Three checks, in the order CLAUDE.md's "verify the instrument" rule demands:

1. positive  — a fabricated plugin with one planted defect per M-* rule; every rule must
               fire at least once, on the planted file.
2. negative  — a fabricated clean plugin produces zero findings (false-positive floor).
3. sabotage  — blank each rule in turn and rerun the positive check; the check MUST go red
               for that rule. A rule the fixture cannot make fail is not load-bearing.
4. sync      — the rubric's M-* table and lint_prompts.META are the same id set.

Usage: test-lint-prompts.py            (exit 0 green, 1 red)
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LINT = ROOT / "tools/prompt-review/lint_prompts.py"
RUBRIC = ROOT / "docs/plugin-authoring/references/prompt-quality-rubric.md"

spec = importlib.util.spec_from_file_location("lint_prompts", LINT)
assert spec is not None and spec.loader is not None
lp = importlib.util.module_from_spec(spec)
sys.modules["lint_prompts"] = lp  # dataclasses need the module registered before exec (py3.14)
spec.loader.exec_module(lp)

FM = "---\nname: {name}\ndescription: {desc}\n{extra}---\n"
GOOD_DESC = "Audits one thing precisely and reports it. Use when the user asks to audit that thing."
GOOD_BODY = "\n# Title\n\nTo run the audit, read the target and report findings.\n\nSee [ref](references/guide.md) for the schema.\n"


def w(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def skill(root: Path, plugin: str, name: str, desc: str = GOOD_DESC, body: str = GOOD_BODY, extra: str = "", fm_override: str | None = None) -> None:
    fm = fm_override if fm_override is not None else FM.format(name=name, desc=desc, extra=extra)
    w(root, f"{plugin}/skills/{name}/SKILL.md", fm + body)
    w(root, f"{plugin}/skills/{name}/references/guide.md", "# Guide\n\nschema: {a: 1}\n")


def agent(root: Path, plugin: str, name: str, desc: str = GOOD_DESC, body: str = "\nYou are an auditor. Report findings; never modify any file.\n", extra: str = "tools: Read, Grep, Glob\n") -> None:
    w(root, f"{plugin}/agents/{name}.md", FM.format(name=name, desc=desc, extra=extra) + body)


def build_positive(root: Path) -> dict[str, str]:
    """Return {rule_id: repo-relative file expected to carry it}."""
    P = "plugins/bad"
    exp: dict[str, str] = {}
    # M-FM-PARSE: no frontmatter
    w(root, f"{P}/skills/no-fm/SKILL.md", "# no frontmatter\nbody\n")
    exp["M-FM-PARSE"] = f"{P}/skills/no-fm/SKILL.md"
    # M-DESC-LEN + M-DESC-XML
    skill(root, P, "long-desc", desc="'" + ("Checks scaffolds. Use when asked. " * 40) + "<example>x</example>'")
    exp["M-DESC-LEN"] = exp["M-DESC-XML"] = f"{P}/skills/long-desc/SKILL.md"
    # M-DESC-PERSON
    skill(root, P, "first-person", desc="I can help you audit things when you ask.")
    exp["M-DESC-PERSON"] = f"{P}/skills/first-person/SKILL.md"
    # M-DESC-VAGUE
    skill(root, P, "vague", desc="Helps with documents.")
    exp["M-DESC-VAGUE"] = f"{P}/skills/vague/SKILL.md"
    # M-DESC-WHENONLY
    skill(root, P, "whenonly", desc='This skill should be used when the user asks to "audit"')
    exp["M-DESC-WHENONLY"] = f"{P}/skills/whenonly/SKILL.md"
    # M-NAME-FORMAT: name mismatches dir
    skill(root, P, "named-wrong", fm_override=FM.format(name="Named_Wrong", desc=GOOD_DESC, extra=""))
    exp["M-NAME-FORMAT"] = f"{P}/skills/named-wrong/SKILL.md"
    # M-BODY-LINES
    skill(root, P, "too-long", body="\n# T\n" + "line\n" * 520)
    exp["M-BODY-LINES"] = f"{P}/skills/too-long/SKILL.md"
    # M-REF-TOC + M-REF-DEPTH: a long reference with no TOC that links to a sibling reference
    skill(root, P, "refs", body=GOOD_BODY + "Also [deep](references/deep.md) and [other](references/other.md).\n")
    w(root, f"{P}/skills/refs/references/deep.md", "# Deep\n\nSee [other](other.md).\n" + "x\n" * 120)
    w(root, f"{P}/skills/refs/references/other.md", "# Other\n\nfine\n")
    exp["M-REF-TOC"] = exp["M-REF-DEPTH"] = f"{P}/skills/refs/references/deep.md"
    # M-REF-UNWIRED: a reference nobody names
    skill(root, P, "unwired")
    w(root, f"{P}/skills/unwired/references/orphan.md", "# Orphan\n")
    exp["M-REF-UNWIRED"] = f"{P}/skills/unwired/SKILL.md"
    # M-LINK-BROKEN
    skill(root, P, "broken-link", body=GOOD_BODY + "Run [it](scripts/missing.py).\n")
    exp["M-LINK-BROKEN"] = f"{P}/skills/broken-link/SKILL.md"
    # M-DUP-CONTENT: same reference in two plugins
    w(root, f"{P}/references/proto.md", "# Protocol\n\nidentical\n")
    w(root, "plugins/bad2/references/proto.md", "# Protocol\n\nidentical\n")
    exp["M-DUP-CONTENT"] = f"{P}/references/proto.md"
    # M-SKILL-VOICE
    skill(root, P, "you-voice", body="\n# T\n\nYou should read the file first.\n")
    exp["M-SKILL-VOICE"] = f"{P}/skills/you-voice/SKILL.md"
    # M-AGENT-VOICE
    agent(root, P, "me-voice", body="\nI will audit the code and I will report.\n")
    exp["M-AGENT-VOICE"] = f"{P}/agents/me-voice.md"
    # M-AGENT-MODEL
    agent(root, P, "bad-model", extra="tools: Read\nmodel: gpt-5\n")
    exp["M-AGENT-MODEL"] = f"{P}/agents/bad-model.md"
    # M-AGENT-TOOLS-SHAPE: YAML list
    agent(root, P, "list-tools", extra="tools:\n  - Read\n  - Grep\n")
    exp["M-AGENT-TOOLS-SHAPE"] = f"{P}/agents/list-tools.md"
    # M-AGENT-TOOLS-VERBS: body edits, tools read-only
    agent(root, P, "edits-no-edit", body="\nYou are a remediator. Apply the fix at the cited line, then stop.\n", extra="tools: Read, Grep\n")
    exp["M-AGENT-TOOLS-VERBS"] = f"{P}/agents/edits-no-edit.md"
    # M-VERSION-FIELD
    skill(root, P, "versioned", extra="version: 0.1.0\n")
    exp["M-VERSION-FIELD"] = f"{P}/skills/versioned/SKILL.md"
    # M-CMD-ARGHINT + M-CMD-DESC-LEN
    w(root, f"{P}/commands/cmd.md", "---\ndescription: " + "A very long command description that keeps going. " * 5 + "\n---\n\nScan `$1` now.\n")
    exp["M-CMD-ARGHINT"] = exp["M-CMD-DESC-LEN"] = f"{P}/commands/cmd.md"
    # M-TIME-SENSITIVE
    skill(root, P, "dated", body="\n# T\n\nBefore August 2025 use the old API.\n")
    exp["M-TIME-SENSITIVE"] = f"{P}/skills/dated/SKILL.md"
    # M-WIN-PATHS
    skill(root, P, "winpath", body="\n# T\n\nRun scripts\\helper.py first.\n")
    exp["M-WIN-PATHS"] = f"{P}/skills/winpath/SKILL.md"
    # M-BASH-WILDCARD
    skill(root, P, "wild-bash", extra="allowed-tools: Read, Bash(*)\n")
    exp["M-BASH-WILDCARD"] = f"{P}/skills/wild-bash/SKILL.md"
    # M-SECRETS
    skill(root, P, "leaky", body="\n# T\n\nexport KEY=sk-abcdefghijklmnopqrstuvwxyz0123\n")
    exp["M-SECRETS"] = f"{P}/skills/leaky/SKILL.md"
    assert set(exp) == set(lp.RULES), f"fixture does not plant every rule: {set(lp.RULES) ^ set(exp)}"
    return exp


def build_clean(root: Path) -> None:
    P = "plugins/clean"
    skill(root, P, "audit-widgets", body=GOOD_BODY + "\n## Steps\n\n1. Read.\n2. Report.\n")
    agent(root, P, "widget-auditor")
    w(root, f"{P}/commands/scan.md", "---\ndescription: Scan widgets in an area\nargument-hint: <area>\n---\n\nScan `$1`.\n")


def run(root: Path, plugins: list[str]) -> list[dict]:
    import os
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return lp.lint([Path(p) for p in plugins])["findings"]
    finally:
        os.chdir(cwd)


def main() -> int:
    red = 0
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        exp = build_positive(root)
        build_clean(root)

        # 1. positive
        findings = run(root, ["plugins/bad", "plugins/bad2"])
        for rid, f in exp.items():
            hits = [x for x in findings if x["rule_id"] == rid and x["file"] == f]
            if not hits:
                print(f"RED  positive: {rid} did not fire on {f}")
                red += 1
        print(f"     positive: {len(exp)} rules checked, {len(findings)} findings")

        # 2. negative
        clean = run(root, ["plugins/clean"])
        if clean:
            for x in clean:
                print(f"RED  negative: clean plugin produced {x['rule_id']} on {x['file']}: {x['claim']}")
            red += len(clean)
        else:
            print("     negative: clean plugin silent")

        # 3. sabotage — each rule must be load-bearing
        saved = dict(lp.RULES)
        for rid in saved:
            lp.RULES[rid] = lambda _u, _ctx: []
            after = run(root, ["plugins/bad", "plugins/bad2"])
            lp.RULES[rid] = saved[rid]
            if any(x["rule_id"] == rid for x in after):
                print(f"RED  sabotage: blanking {rid} did not remove its findings — the check is not load-bearing")
                red += 1
        print(f"     sabotage: {len(saved)} rules blanked, each went red")

    # 4. rubric ↔ META sync
    rubric_ids = set(re.findall(r"^\| `(M-[A-Z-]+)` \|", RUBRIC.read_text(encoding="utf-8"), re.M))
    if rubric_ids != set(lp.META):
        print(f"RED  sync: rubric M-* ids {sorted(rubric_ids ^ set(lp.META))} differ from lint META")
        red += 1
    else:
        print(f"     sync: rubric and lint agree on {len(rubric_ids)} M-* ids")
    for rid, (sev, _) in lp.META.items():
        m = re.search(rf"^\| `{re.escape(rid)}` \|.*?\|.*?\| (blocker|major|minor|nit) \|", RUBRIC.read_text(encoding="utf-8"), re.M)
        if m and m.group(1) != sev:
            print(f"RED  sync: {rid} severity is {sev} in lint but {m.group(1)} in rubric")
            red += 1

    print("GREEN" if not red else f"RED ({red})")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
