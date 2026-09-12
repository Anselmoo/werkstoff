#!/usr/bin/env python3
"""Calibration for nacharbeit_lint.py — the instrument asserts itself.

Four checks, in the order CLAUDE.md's "verify the instrument" rule demands:

1. positive  — fabricated plugins (plus a fabricated docs tree) with one planted
               defect per mechanical rule; every rule must fire, on the planted file.
2. negative  — a fabricated clean plugin, in its own repo tree, produces zero findings
               (the false-positive floor).
3. sabotage  — blank each rule in turn and rerun the positive check; the check MUST go
               red for that rule. A rule the fixture cannot make fail is not load-bearing.
4. sync      — the rubric's mechanical tables and nacharbeit_lint.META are the same id
               set with the same severities.

Usage: test_nacharbeit_lint.py            (exit 0 green, 1 red)
Exit: 0 green; 1 any check red.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINT = HERE / "nacharbeit_lint.py"
RUBRIC = HERE.parent / "references" / "rubric.md"

spec = importlib.util.spec_from_file_location("nacharbeit_lint", LINT)
assert spec is not None and spec.loader is not None
lp = importlib.util.module_from_spec(spec)
sys.modules["nacharbeit_lint"] = lp  # dataclasses need the module registered before exec (py3.14)
spec.loader.exec_module(lp)

FM = "---\nname: {name}\ndescription: {desc}\n{extra}---\n"
GOOD_DESC = "Audits one thing precisely and reports it. Use when the user asks to audit that thing."
GOOD_BODY = "\n# Title\n\nTo run the audit, read the target and report findings.\n\nSee [ref](references/guide.md) for the schema.\n"
DENY_JSON = '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}'


def w(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def wb(root: Path, rel: str, data: bytes) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def jpeg(width: int, height: int = 900) -> bytes:
    """A minimal JPEG whose SOF0 marker carries the given size (what jpeg_size reads)."""
    return b"\xff\xd8" + b"\xff\xc0" + b"\x00\x11" + b"\x08" + struct.pack(">HH", height, width) + b"\x03" + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01" + b"\xff\xd9"


def skill(root: Path, plugin: str, name: str, desc: str = GOOD_DESC, body: str = GOOD_BODY, extra: str = "", fm_override: str | None = None) -> None:
    fm = fm_override if fm_override is not None else FM.format(name=name, desc=desc, extra=extra)
    w(root, f"{plugin}/skills/{name}/SKILL.md", fm + body)
    w(root, f"{plugin}/skills/{name}/references/guide.md", "# Guide\n\nschema: {a: 1}\n")


def agent(root: Path, plugin: str, name: str, desc: str = GOOD_DESC, body: str = "\nYou are an auditor. Report findings; never modify any file.\n", extra: str = "tools: Read, Grep, Glob\n") -> None:
    w(root, f"{plugin}/agents/{name}.md", FM.format(name=name, desc=desc, extra=extra) + body)


def viewer_html(plugin: str, *, conformant: bool) -> str:
    if conformant:
        return f"""<!doctype html>
<html><head>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>{plugin} — widget report</title>
<style>
<!--__DESIGN_TOKENS__-->
.header {{ height: var(--header-h); }}
</style>
</head><body>
<h1>{plugin} — widget report</h1>
<p class="verdict">Every widget passed.</p>
<div class="legend">green = passed, red = failed (also marked with an icon)</div>
<script>
const data = window.__DATA__;
if (!data) {{ document.querySelector('.verdict').textContent = 'No data — re-run build_{plugin}_html.py to regenerate.'; }}
else {{ document.querySelector('.verdict').textContent = data.verdict; }}
</script>
</body></html>
"""
    return """<!doctype html>
<html><head><title>Bad Report</title>
<script src="https://cdn.example.com/d3.min.js"></script>
<style>.header { height: 61px; }</style>
</head><body>
<h1>Report</h1>
<div id="out"></div>
<script>
const name = window.__DATA__ && window.__DATA__.name;
document.getElementById('out').innerHTML = '<b>' + name + '</b>';
</script>
</body></html>
"""


def build_positive(root: Path) -> dict[str, str]:
    """Return {rule_id: repo-relative file expected to carry it}."""
    P = "plugins/bad"
    exp: dict[str, str] = {}
    # ---- M
    w(root, f"{P}/skills/no-fm/SKILL.md", "# no frontmatter\nbody\n")
    exp["M-FM-PARSE"] = f"{P}/skills/no-fm/SKILL.md"
    skill(root, P, "long-desc", desc="'" + ("Checks scaffolds. Use when asked. " * 40) + "<example>x</example>'")
    exp["M-DESC-LEN"] = exp["M-DESC-XML"] = f"{P}/skills/long-desc/SKILL.md"
    skill(root, P, "first-person", desc="I can help you audit things when you ask.")
    exp["M-DESC-PERSON"] = f"{P}/skills/first-person/SKILL.md"
    skill(root, P, "vague", desc="Helps with documents.")
    exp["M-DESC-VAGUE"] = f"{P}/skills/vague/SKILL.md"
    skill(root, P, "whenonly", desc='This skill should be used when the user asks to "audit"')
    exp["M-DESC-WHENONLY"] = f"{P}/skills/whenonly/SKILL.md"
    skill(root, P, "named-wrong", fm_override=FM.format(name="Named_Wrong", desc=GOOD_DESC, extra=""))
    exp["M-NAME-FORMAT"] = f"{P}/skills/named-wrong/SKILL.md"
    skill(root, P, "too-long", body="\n# T\n" + "line\n" * 520)
    exp["M-BODY-LINES"] = f"{P}/skills/too-long/SKILL.md"
    skill(root, P, "refs", body=GOOD_BODY + "Also [deep](references/deep.md) and [other](references/other.md).\n")
    w(root, f"{P}/skills/refs/references/deep.md", "# Deep\n\nSee [other](other.md).\n" + "x\n" * 120)
    w(root, f"{P}/skills/refs/references/other.md", "# Other\n\nfine\n")
    exp["M-REF-TOC"] = exp["M-REF-DEPTH"] = f"{P}/skills/refs/references/deep.md"
    skill(root, P, "unwired")
    w(root, f"{P}/skills/unwired/references/orphan.md", "# Orphan\n")
    exp["M-REF-UNWIRED"] = f"{P}/skills/unwired/SKILL.md"
    skill(root, P, "broken-link", body=GOOD_BODY + "Run [it](scripts/missing.py).\n")
    exp["M-LINK-BROKEN"] = f"{P}/skills/broken-link/SKILL.md"
    w(root, f"{P}/references/proto.md", "# Protocol\n\nidentical\n")
    w(root, "plugins/bad2/references/proto.md", "# Protocol\n\nidentical\n")
    exp["M-DUP-CONTENT"] = f"{P}/references/proto.md"
    skill(root, P, "you-voice", body="\n# T\n\nYou should read the file first.\n")
    exp["M-SKILL-VOICE"] = f"{P}/skills/you-voice/SKILL.md"
    agent(root, P, "me-voice", body="\nI will audit the code and I will report.\n")
    exp["M-AGENT-VOICE"] = f"{P}/agents/me-voice.md"
    agent(root, P, "bad-model", extra="tools: Read\nmodel: gpt-5\n")
    exp["M-AGENT-MODEL"] = f"{P}/agents/bad-model.md"
    agent(root, P, "list-tools", extra="tools:\n  - Read\n  - Grep\n")
    exp["M-AGENT-TOOLS-SHAPE"] = f"{P}/agents/list-tools.md"
    agent(root, P, "edits-no-edit", body="\nYou are a remediator. Apply the fix at the cited line, then stop.\n", extra="tools: Read, Grep\n")
    exp["M-AGENT-TOOLS-VERBS"] = f"{P}/agents/edits-no-edit.md"
    skill(root, P, "versioned", extra="version: 0.1.0\n")
    exp["M-VERSION-FIELD"] = f"{P}/skills/versioned/SKILL.md"
    w(root, f"{P}/commands/cmd.md", "---\ndescription: " + "A very long command description that keeps going. " * 5 + "\n---\n\nScan `$1` now.\n")
    exp["M-CMD-ARGHINT"] = exp["M-CMD-DESC-LEN"] = f"{P}/commands/cmd.md"
    skill(root, P, "dated", body="\n# T\n\nBefore August 2025 use the old API.\n")
    exp["M-TIME-SENSITIVE"] = f"{P}/skills/dated/SKILL.md"
    skill(root, P, "winpath", body="\n# T\n\nRun scripts\\helper.py first.\n")
    exp["M-WIN-PATHS"] = f"{P}/skills/winpath/SKILL.md"
    skill(root, P, "wild-bash", extra="allowed-tools: Read, Bash(*)\n")
    exp["M-BASH-WILDCARD"] = f"{P}/skills/wild-bash/SKILL.md"
    skill(root, P, "leaky", body="\n# T\n\nexport KEY=sk-abcdefghijklmnopqrstuvwxyz0123\n")
    exp["M-SECRETS"] = f"{P}/skills/leaky/SKILL.md"

    # ---- H: hooks.json with three entries, two declared scripts
    w(root, f"{P}/hooks/hooks.json", json.dumps({
        "hooks": {"PreToolUse": [
            {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/bad_guard.py\""}]},
            {"matcher": "Edit|Wrte", "hooks": [{"type": "prompt", "prompt": "decide whether to allow", "timeout": 15}]},
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /home/me/guard.py", "timeout": 15},
                                           {"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/missing.py\"", "timeout": 15},
                                           {"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/other_guard.py\"", "timeout": 15}]},
        ]}}, indent=1))
    for rid in ("H-TYPE-COMMAND", "H-CMD-PLUGIN-ROOT", "H-SCRIPT-EXISTS", "H-TIMEOUT", "H-MATCHER-KNOWN", "H-MATCHER-MULTIEDIT", "H-INERT-STATED"):
        exp[rid] = f"{P}/hooks/hooks.json"
    w(root, "plugins/bad2/hooks/hooks.json", json.dumps({"description": "inert always", "PreToolUse": []}))
    exp["H-JSON-PARSE"] = "plugins/bad2/hooks/hooks.json"
    w(root, f"{P}/hooks/bad_guard.py", '''#!/usr/bin/env python3
"""Usage: bad_guard.py  Exit: 0 allow."""
import json
import sys


def main() -> int:
    event = json.load(sys.stdin)
    path = event.get("tool_input", {}).get("file_path")
    if path and path.endswith(".secret"):
        print(json.dumps({"systemMessage": "no"}))
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
''')
    for rid in ("H-DENY-SHAPE", "H-EXIT-2", "H-ESCAPE-HATCH", "H-FAIL-CLOSED", "H-MULTI-PATH", "H-TEST-EXISTS"):
        exp[rid] = f"{P}/hooks/bad_guard.py"
    w(root, f"{P}/hooks/other_guard.py", '''#!/usr/bin/env python3
"""Usage: other_guard.py  Exit: 0 allow, 2 deny."""
import json
import os
import sys


def deny(reason):
    print(json.dumps(''' + DENY_JSON + '''))
    sys.exit(2)


def main():
    if os.environ.get("BAD_DISABLE_GUARD") == "1":
        sys.exit(0)
    try:
        event = json.load(sys.stdin)
        cmd = event.get("tool_input", {}).get("command", "")
        if "rm -rf" in cmd:
            deny("destructive command; set BAD_DISABLE_GUARD=1 to bypass")
    except Exception as exc:
        deny(f"could not evaluate ({exc}); set BAD_DISABLE_GUARD=1 to bypass")
    sys.exit(0)


if __name__ == "__main__":
    main()
''')
    w(root, f"{P}/hooks/test_other_guard.py", "#!/usr/bin/env python3\nif __name__ == '__main__':\n    pass\n")

    # ---- S
    w(root, f"{P}/scripts/broken.py", "#!/usr/bin/env python3\n\"\"\"Usage: broken.py\"\"\"\ndef f(:\n    pass\n")
    exp["S-PY-COMPILE"] = f"{P}/scripts/broken.py"
    w(root, f"{P}/scripts/bad.js", "function (\n")
    exp["S-JS-SYNTAX"] = f"{P}/scripts/bad.js"
    w(root, f"{P}/scripts/noshebang.py", '''import re
import subprocess
import sys


def main():
    target = sys.argv[1]
    try:
        subprocess.run("ls " + target, shell=True)
    except Exception:
        pass
    return bool(re.search(r"\\b!" + "==\\b", target))


if __name__ == "__main__":
    main()
''')
    bad_py = (root / P / "scripts" / "noshebang.py")
    bad_py.write_text(bad_py.read_text(encoding="utf-8").replace('r"\\b!" + "==\\b"', 'r"\\b!' + '==\\b"'), encoding="utf-8")
    for rid in ("S-SHEBANG", "S-DOCSTRING-USAGE", "S-ARGPARSE", "S-SILENT-REGEX", "S-EXCEPT-SWALLOW", "S-SHELL-TRUE", "S-REFERENCED"):
        exp[rid] = f"{P}/scripts/noshebang.py"

    # ---- A: a non-conformant viewer with an 800-px screenshot; README cites no demo data
    w(root, f"{P}/assets/bad-viewer.html", viewer_html("bad", conformant=False))
    wb(root, f"{P}/assets/bad-viewer-screenshot.jpg", jpeg(800))
    for rid in ("A-R1-VERDICT", "A-R4-LEGEND", "A-S1-HEIGHT", "A-S2-HEAD", "A-C1-SCREENSHOT", "A-C2-DEMO-DATA",
                "A-S3-INNERHTML", "A-S4-FAIL-VISIBLE", "A-NO-CDN", "A-TOKENS-PRESENT", "A-BUILDER-EXISTS"):
        exp[rid] = f"{P}/assets/bad-viewer.html"
    w(root, "plugins/bad2/assets/other-viewer.html", viewer_html("bad2", conformant=False))

    # A-VIEWER-REQUIRED fires on an ABSENCE, so it needs a plugin with no viewer
    # at all. `bad` and `bad2` both have one -- they exist to plant the rules
    # that grade a viewer's CONTENT -- so a third fixture plugin carries this
    # one. Minimal on purpose: a manifest is all the rule keys on.
    w(root, "plugins/bad3/.claude-plugin/plugin.json",
      json.dumps({"name": "bad3", "version": "0.1.0", "description": "Has no viewer.",
                  "author": {"name": "Anselm Hahn", "email": "x@y.z"},
                  "keywords": ["x"], "license": "MIT"}))
    w(root, "plugins/bad3/README.md", "# bad3\n\n**No viewer.**\n")
    exp["A-VIEWER-REQUIRED"] = "plugins/bad3/.claude-plugin/plugin.json"

    # ---- P
    w(root, f"{P}/.claude-plugin/plugin.json", json.dumps({"name": "wrongname", "version": "1.0", "description": "Audits widgets.", "author": {"name": "bad contributors"}}))
    for rid in ("P-MANIFEST-NAME-DIR", "P-MANIFEST-SEMVER", "P-AUTHOR-PRESENT", "P-MARKETPLACE-MEMBER", "P-MANIFEST-KEYWORDS", "P-MANIFEST-LICENSE", "P-SKILL-DIR-HAS-FILE", "P-REF-REACHABLE"):
        exp[rid] = f"{P}/.claude-plugin/plugin.json"
    exp["P-MANIFEST-PARSE"] = "plugins/bad2/.claude-plugin/plugin.json"
    w(root, ".claude-plugin/marketplace.json", json.dumps({"name": "test", "plugins": [{"name": "bad", "description": "Something else entirely.", "author": {"name": "bad contributors"}, "source": "./plugins/bad"}]}))
    (root / P / "skills" / "empty").mkdir(parents=True, exist_ok=True)
    w(root, f"{P}/README.md", "# Bad Plugin\n\nSome prose.\n\n## Example Prompts\n\n##### Do the thing\n\nno fence here\n\n![bad](assets/bad-viewer-screenshot.jpg)\n")
    for rid in ("P-README-H1", "P-README-THESIS", "P-README-WHY-NOT", "P-README-INSTALL", "P-README-PROMPTS-BLOCK", "P-README-PROMPT-TRIPLE", "P-README-VERIFY", "P-README-ESCAPE-HATCH", "A-C4-ALT"):
        exp[rid] = f"{P}/README.md"
    w(root, "plugins/bad2/README.md", "# bad2\n\n**Thesis.**\n")
    exp["P-README-SCREENSHOT"] = "plugins/bad2/README.md"
    w(root, f"{P}/CHANGELOG.md", "# Changelog\n\n## [0.1.0]\n- first\n")
    exp["P-CHANGELOG-UNRELEASED"] = f"{P}/CHANGELOG.md"

    # ---- D: a docs tree that forgot the plugin everywhere
    w(root, "docs/index.md", "---\ntagline: Nine plugins that each catch one failure mode.\n---\n\n# Nine plugins, one job each\n")
    w(root, "docs/plugins/index.md", "# Nine plugins, one job each\n")
    w(root, "docs/.vitepress/config.mjs", "export default { themeConfig: { sidebar: [{ text: 'Plugins', items: [{ text: 'other', link: '/plugins/other' }] }] } }\n")
    w(root, "docs/.vitepress/theme/components/PluginGrid.vue", "<script setup>\nconst plugins = [{ name: 'other', url: '/plugins/other', summary: 'x' }]\n</script>\n")
    w(root, "docs/plugins/references/bad-ref.md", "---\ntitle: bad ref\n---\n\n<!--@include: ../../../plugins/bad/references/proto.md-->\n")
    w(root, "docs/orchestration/README.md", "# Orchestration\n\nother is a leaf.\n")
    w(root, "docs/orchestration/references/hazards.md", "# Hazards\n\n<code>other</code> registers a hook.\n")
    w(root, "docs/catalog/quality/recipe.md", "---\ntask: x\nbeats:\n  - skill: \"bad:nonexistent\"\n    why: y\n---\n")
    w(root, "docs/prompt-index.md", "# Prompt index\n\n## other\n")
    w(root, "docs/.vitepress/data/surface.json", json.dumps({"plugins": [{"name": "other", "version": "0.1.0"}]}))
    w(root, "README.md", "# repo\n\n## Plugins\n\n- other\n")
    w(root, "CLAUDE.md", "# repo\n\n## Layout\n\n`plugins/<name>/` — nine plugins: `other`.\n\n## Other\n")
    for rid in ("D-DOCS-STUB", "D-SIDEBAR-ENTRY", "D-SIDEBAR-REFS", "D-GRID-ENTRY", "D-COUNT-PROSE", "D-ROOT-README", "D-CLAUDE-MD-LAYOUT", "D-ORCH-TABLES", "D-HAZARDS-CARD", "D-CATALOG-VALID", "D-GENERATED-FRESH"):
        exp[rid] = "docs/plugins/bad.md"

    assert set(exp) == set(lp.RULES), f"fixture does not plant every rule: {set(lp.RULES) ^ set(exp)}"
    return exp


def build_clean(root: Path) -> None:
    P = "plugins/clean"
    skill(root, P, "audit-widgets", body=GOOD_BODY + "\n## Steps\n\n1. Read.\n2. Report.\n")
    agent(root, P, "widget-auditor")
    w(root, f"{P}/commands/scan.md", "---\ndescription: Scan widgets in an area\nargument-hint: <area>\n---\n\nScan `$1`.\n")
    w(root, f"{P}/hooks/hooks.json", json.dumps({
        "description": "clean: denies a write to a .secret file. Inert until .clean/ exists.",
        "hooks": {"PreToolUse": [{"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/clean_guard.py\"", "timeout": 15}]}]},
    }, indent=1))
    w(root, f"{P}/hooks/clean_guard.py", '''#!/usr/bin/env python3
"""PreToolUse guard for clean.

Usage: fed a PreToolUse JSON event on stdin by the runtime.
Exit: 0 allow; 2 deny (with the hookSpecificOutput JSON on stdout).
"""
import json
import os
import sys


def deny(reason):
    print(json.dumps(''' + DENY_JSON + '''))
    sys.stderr.write(reason + "\\n")
    sys.exit(2)


def targets(tool_input):
    found = []
    single = tool_input.get("file_path")
    if isinstance(single, str):
        found.append(single)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        found += [e.get("file_path") for e in edits if isinstance(e, dict)]
    plural = tool_input.get("file_paths")
    if isinstance(plural, list):
        found += [p for p in plural if isinstance(p, str)]
    return [f for f in found if f]


def main():
    if os.environ.get("CLEAN_DISABLE_GUARD") == "1":
        sys.exit(0)
    try:
        event = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    cwd = event.get("cwd") or os.getcwd()
    if not os.path.isdir(os.path.join(cwd, ".clean")):
        sys.exit(0)
    try:
        paths = targets(event.get("tool_input") or {})
        if not paths:
            deny("no determinable path; set CLEAN_DISABLE_GUARD=1 to bypass")
        for p in paths:
            if p.endswith(".secret"):
                deny("writes to .secret files are refused; set CLEAN_DISABLE_GUARD=1 to bypass")
    except SystemExit:
        raise
    except Exception as exc:
        deny(f"guard could not evaluate ({exc}); set CLEAN_DISABLE_GUARD=1 to bypass")
    sys.exit(0)


if __name__ == "__main__":
    main()
''')
    w(root, f"{P}/hooks/test_clean_guard.py", "#!/usr/bin/env python3\n\"\"\"Usage: test_clean_guard.py  Exit: 0 green.\"\"\"\nimport sys\n\nif __name__ == '__main__':\n    sys.exit(0)\n")
    w(root, f"{P}/scripts/build_clean_html.py", '''#!/usr/bin/env python3
"""Render clean-viewer.html from a report.

Usage: build_clean_html.py <report.json> [--out clean-report.html]
Exit: 0 written; 1 unreadable input.
"""
import argparse
import sys

MARKER = "<!--__DESIGN_TOKENS__-->"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.parse_args()
    return 0


if __name__ == "__main__":
    sys.exit(main())
''')
    w(root, f"{P}/assets/clean-viewer.html", viewer_html("clean", conformant=True))
    w(root, f"{P}/assets/tokens.css", ":root { --header-h: 61px; }\n")
    wb(root, f"{P}/assets/clean-viewer-screenshot.jpg", jpeg(1600))
    w(root, f"{P}/scripts/fixtures/sample.json", "{}\n")
    w(root, f"{P}/.claude-plugin/plugin.json", json.dumps({"name": "clean", "version": "0.1.0", "description": "Audits widgets and reports every failing one.", "author": {"name": "Test Author", "email": "t@example.org"}, "keywords": ["widgets"], "license": "MIT"}))
    w(root, ".claude-plugin/marketplace.json", json.dumps({"name": "test", "plugins": [{"name": "clean", "description": "Audits widgets and reports every failing one.", "author": {"name": "Test Author", "email": "t@example.org"}, "source": "./plugins/clean"}]}))
    w(root, f"{P}/README.md", f"""# clean

**Audits widgets and reports every failing one.**

## Why this exists

Widgets fail silently.

## What it is not

- Not a widget builder — that is `other`.

## Install

```
/plugin install clean@test
```

{lp.RRT_START}
## Example Prompts

Say any of these.
{lp.RRT_END}

##### Audit the widgets

````prompt
"audit the widgets in this repo"
````

> Routes to `audit-widgets`.

## Report

![The widget report rendered from the sample data, every row green](assets/clean-viewer-screenshot.jpg)

Rebuild it from the committed demo data: `python3 scripts/build_clean_html.py scripts/fixtures/sample.json`.

## Verifying a change to this plugin

```bash
python3 plugins/clean/hooks/test_clean_guard.py
```

## Escape hatch

`CLEAN_DISABLE_GUARD=1` bypasses the guard for one session.
""")
    w(root, f"{P}/CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n\n### Added\n- everything\n")
    # docs tree that knows about the plugin
    w(root, "docs/index.md", "---\ntagline: One plugin that catches one failure mode.\n---\n\n# One plugin, one job\n")
    w(root, "docs/plugins/index.md", "# One plugin, one job\n")
    w(root, "docs/plugins/clean.md", "---\ntitle: clean\n---\n\n<!--@include: ../../plugins/clean/README.md-->\n")
    w(root, "docs/.vitepress/config.mjs", "export default { themeConfig: { sidebar: [{ text: 'Plugins', items: [{ text: 'clean', link: '/plugins/clean' }] }] } }\n")
    w(root, "docs/.vitepress/theme/components/PluginGrid.vue", "<script setup>\nconst plugins = [{ name: 'clean', url: '/plugins/clean', summary: 'Audits widgets.' }]\n</script>\n")
    w(root, "docs/orchestration/README.md", "# Orchestration\n\n`clean`'s audit-widgets is a leaf.\n")
    w(root, "docs/orchestration/references/hazards.md", "# Hazards\n\n<code>clean</code> registers a hook; inert until .clean/ exists.\n")
    w(root, "docs/prompt-index.md", "# Prompt index\n\n## clean\n")
    w(root, "docs/.vitepress/data/surface.json", json.dumps({"plugins": [{"name": "clean", "version": "0.1.0"}]}))
    w(root, "README.md", "# repo\n\n## Plugins\n\n- **[`clean`](plugins/clean/README.md)** — audits widgets.\n\nSwap `clean` for any plugin name.\n")
    w(root, "CLAUDE.md", "# repo\n\n## Layout\n\n`plugins/<name>/` — one plugin: `clean`.\n\n## Other\n")


def run(root: Path, plugins: list[str]) -> list[dict]:
    cwd = os.getcwd()
    os.chdir(root)
    try:
        lp.configure(marketplace=Path(".claude-plugin/marketplace.json"), readme_markers=True,
                     viewer_checker=HERE / "check_viewer_conformance.py", docs_root=Path("docs"))
        return lp.lint([Path(p) for p in plugins])["findings"]
    finally:
        os.chdir(cwd)


def main() -> int:
    red = 0
    if not shutil.which("node"):
        print("RED  environment: node is not on PATH, so S-JS-SYNTAX cannot be calibrated")
        return 1
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        exp = build_positive(root)

        # 1. positive
        findings = run(root, ["plugins/bad", "plugins/bad2", "plugins/bad3"])
        for rid, f in exp.items():
            hits = [x for x in findings if x["rule_id"] == rid and x["file"] == f]
            if not hits:
                print(f"RED  positive: {rid} did not fire on {f}")
                red += 1
        print(f"     positive: {len(exp)} rules checked, {len(findings)} findings")

        # 3. sabotage — each rule must be load-bearing
        saved = dict(lp.RULES)
        for rid in saved:
            lp.RULES[rid] = lambda _u, _ctx: []
            after = run(root, ["plugins/bad", "plugins/bad2", "plugins/bad3"])
            lp.RULES[rid] = saved[rid]
            if any(x["rule_id"] == rid for x in after):
                print(f"RED  sabotage: blanking {rid} did not remove its findings — the check is not load-bearing")
                red += 1
        print(f"     sabotage: {len(saved)} rules blanked, each went red")

    # 2. negative — its own tree, so the docs-level rules see a repo that knows the plugin
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_clean(root)
        clean = run(root, ["plugins/clean"])
        if clean:
            for x in clean:
                print(f"RED  negative: clean plugin produced {x['rule_id']} on {x['file']}: {x['claim']}")
            red += len(clean)
        else:
            print("     negative: clean plugin silent")

    # 4. rubric ↔ META sync
    text = RUBRIC.read_text(encoding="utf-8")
    rubric_ids = set(re.findall(r"^\| `((?:M|H|S|A|P|D)-[A-Z0-9-]+)` \|", text, re.M))
    if rubric_ids != set(lp.META):
        print(f"RED  sync: rubric mechanical ids {sorted(rubric_ids ^ set(lp.META))} differ from lint META")
        red += 1
    else:
        print(f"     sync: rubric and lint agree on {len(rubric_ids)} mechanical ids")
    for rid, (sev, _) in lp.META.items():
        m = re.search(rf"^\| `{re.escape(rid)}` \|.*?\| (blocker|major|minor|nit) \|", text, re.M)
        if m and m.group(1) != sev:
            print(f"RED  sync: {rid} severity is {sev} in lint but {m.group(1)} in rubric")
            red += 1

    print("GREEN" if not red else f"RED ({red})")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
