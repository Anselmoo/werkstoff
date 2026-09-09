#!/usr/bin/env python3
"""Phase 0 of a nacharbeit review: every mechanically checkable rule.

Implements the mechanical rows of references/rubric.md -- `M-*` (prompt-bearing
files), `H-*` (hooks), `S-*` (scripts), `A-*` (report viewers), `P-*` (manifest,
README, CHANGELOG) and `D-*` (repo-level developer docs) -- against one or more
plugin directories. No model in the loop. Model finders downstream are told these
ids are out of scope, so anything a script can decide must be decided here.

Every rule is one entry in RULES so test_nacharbeit_lint.py can blank a rule and
prove the fixture goes red -- a rule that cannot fail is not a rule (CLAUDE.md,
"verify the instrument before trusting its verdict").

Findings share the finder schema: {file, line, quote, rule_id, angle, severity, claim,
suggested_fix, fix_tier}. `fix_tier` is "haiku" for every mechanical rule except
P-MARKETPLACE-MEMBER, whose fix lives outside the plugin (tier "human").

A rule that cannot run in this environment (no `node`, no viewer checker) is
listed under `skipped` with a reason and printed as a WARN -- never silently
passed. Output is written atomically (tmp + rename) so a crashed run never leaves
a half-written lint.json that a later stage reads as fresh.

Usage:
  nacharbeit_lint.py plugins/*                                  # text summary
  nacharbeit_lint.py plugins/* --format json                    # findings JSON
  nacharbeit_lint.py plugins/* --out analysis/nacharbeit/lint.json
  nacharbeit_lint.py plugins/nacharbeit --docs-root docs --marketplace .claude-plugin/marketplace.json
Exit: 0 on a completed scan (findings are data, not failure); 2 on bad arguments.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("pyyaml is required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

HERE = Path(__file__).resolve().parent
RUBRIC = HERE.parent / "references" / "rubric.md"

# Environment-dependent inputs. main() fills these from flags; the calibration test
# sets them directly. A None here means the rules that need it report `skipped`.
OPTIONS: dict = {
    "marketplace": None,        # Path to marketplace.json, or None
    "readme_markers": None,     # True/False: require the rrt example-prompts marker pair
    "viewer_checker": HERE / "check_viewer_conformance.py",
    "docs_root": None,          # Path to the docs site root, or None
    "node": shutil.which("node"),
}
SKIPPED: list[dict] = []

# severity + angle per rule, mirrored from the rubric tables. test_nacharbeit_lint.py
# asserts that this dict and the rubric's mechanical rows are the same set.
META: dict[str, tuple[str, str]] = {
    # ---- M: prompt-bearing files
    "M-FM-PARSE": ("blocker", "procedure"),
    "M-DESC-LEN": ("major", "procedure"),
    "M-DESC-XML": ("major", "procedure"),
    "M-DESC-PERSON": ("minor", "procedure"),
    "M-DESC-VAGUE": ("major", "meaning"),
    "M-DESC-WHENONLY": ("minor", "procedure"),
    "M-NAME-FORMAT": ("major", "procedure"),
    "M-BODY-LINES": ("minor", "procedure"),
    "M-REF-TOC": ("minor", "procedure"),
    "M-REF-DEPTH": ("minor", "procedure"),
    "M-REF-UNWIRED": ("minor", "procedure"),
    "M-LINK-BROKEN": ("major", "step-logic"),
    "M-DUP-CONTENT": ("minor", "other"),
    "M-SKILL-VOICE": ("nit", "clarity"),
    "M-AGENT-VOICE": ("nit", "clarity"),
    "M-AGENT-MODEL": ("major", "procedure"),
    "M-AGENT-TOOLS-SHAPE": ("minor", "procedure"),
    "M-AGENT-TOOLS-VERBS": ("major", "procedure"),
    "M-VERSION-FIELD": ("nit", "other"),
    "M-CMD-ARGHINT": ("minor", "procedure"),
    "M-CMD-DESC-LEN": ("nit", "procedure"),
    "M-TIME-SENSITIVE": ("minor", "other"),
    "M-WIN-PATHS": ("nit", "other"),
    "M-BASH-WILDCARD": ("minor", "procedure"),
    "M-SECRETS": ("blocker", "other"),
    # ---- H: hooks
    "H-JSON-PARSE": ("blocker", "contract"),
    "H-TYPE-COMMAND": ("major", "procedure"),
    "H-CMD-PLUGIN-ROOT": ("major", "contract"),
    "H-SCRIPT-EXISTS": ("blocker", "contract"),
    "H-TIMEOUT": ("minor", "procedure"),
    "H-MATCHER-KNOWN": ("minor", "contract"),
    "H-MATCHER-MULTIEDIT": ("nit", "contract"),
    "H-INERT-STATED": ("nit", "meaning"),
    "H-DENY-SHAPE": ("major", "contract"),
    "H-EXIT-2": ("major", "contract"),
    "H-ESCAPE-HATCH": ("minor", "procedure"),
    "H-FAIL-CLOSED": ("minor", "step-logic"),
    "H-MULTI-PATH": ("minor", "step-logic"),
    "H-TEST-EXISTS": ("minor", "other"),
    # ---- S: scripts
    "S-PY-COMPILE": ("blocker", "other"),
    "S-JS-SYNTAX": ("blocker", "other"),
    "S-SHEBANG": ("nit", "procedure"),
    "S-DOCSTRING-USAGE": ("minor", "procedure"),
    "S-ARGPARSE": ("minor", "procedure"),
    "S-SILENT-REGEX": ("major", "step-logic"),
    "S-EXCEPT-SWALLOW": ("major", "step-logic"),
    "S-SHELL-TRUE": ("minor", "other"),
    "S-REFERENCED": ("minor", "procedure"),
    # ---- A: assets and viewers
    "A-R1-VERDICT": ("major", "meaning"),
    "A-R4-LEGEND": ("major", "clarity"),
    "A-S1-HEIGHT": ("minor", "procedure"),
    "A-S2-HEAD": ("major", "contract"),
    "A-C1-SCREENSHOT": ("minor", "contract"),
    "A-C2-DEMO-DATA": ("minor", "contract"),
    "A-S3-INNERHTML": ("major", "other"),
    "A-S4-FAIL-VISIBLE": ("minor", "step-logic"),
    "A-NO-CDN": ("major", "contract"),
    "A-TOKENS-PRESENT": ("minor", "contract"),
    "A-BUILDER-EXISTS": ("minor", "contract"),
    "A-C4-ALT": ("nit", "clarity"),
    # ---- P: manifest, README, CHANGELOG
    "P-MANIFEST-PARSE": ("blocker", "contract"),
    "P-MANIFEST-NAME-DIR": ("major", "contract"),
    "P-MANIFEST-SEMVER": ("major", "contract"),
    "P-AUTHOR-PRESENT": ("major", "contract"),
    "P-MARKETPLACE-MEMBER": ("major", "contract"),
    "P-MANIFEST-KEYWORDS": ("nit", "procedure"),
    "P-MANIFEST-LICENSE": ("nit", "procedure"),
    "P-README-H1": ("minor", "meaning"),
    "P-README-THESIS": ("nit", "meaning"),
    "P-README-WHY-NOT": ("minor", "cannibalization"),
    "P-README-INSTALL": ("minor", "procedure"),
    "P-README-PROMPTS-BLOCK": ("minor", "procedure"),
    "P-README-PROMPT-TRIPLE": ("minor", "procedure"),
    "P-README-VERIFY": ("nit", "procedure"),
    "P-README-ESCAPE-HATCH": ("minor", "procedure"),
    "P-README-SCREENSHOT": ("minor", "contract"),
    "P-CHANGELOG-UNRELEASED": ("minor", "other"),
    "P-SKILL-DIR-HAS-FILE": ("major", "contract"),
    "P-REF-REACHABLE": ("minor", "procedure"),
    # ---- D: repo-level developer docs
    "D-DOCS-STUB": ("major", "contract"),
    "D-SIDEBAR-ENTRY": ("major", "contract"),
    "D-SIDEBAR-REFS": ("minor", "contract"),
    "D-GRID-ENTRY": ("minor", "contract"),
    "D-COUNT-PROSE": ("minor", "meaning"),
    "D-ROOT-README": ("minor", "contract"),
    "D-CLAUDE-MD-LAYOUT": ("minor", "contract"),
    "D-ORCH-TABLES": ("minor", "cannibalization"),
    "D-HAZARDS-CARD": ("minor", "contract"),
    "D-CATALOG-VALID": ("major", "contract"),
    "D-GENERATED-FRESH": ("major", "contract"),
}
FAMILIES = ("M", "H", "S", "A", "P", "D")

KNOWN_TOOLS = {
    "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep", "Bash", "LS",
    "WebFetch", "WebSearch", "Agent", "Task", "TodoWrite", "Skill", "AskUserQuestion",
    "KillShell", "BashOutput", "NotebookRead", "SlashCommand", "Workflow",
}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
EDIT_MATCHER_TOOLS = {"Write", "Edit", "MultiEdit"}
MODEL_ALIASES = {"inherit", "sonnet", "opus", "haiku", "fable"}
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}
PLACEHOLDER_AUTHORS = re.compile(r"^(your name|todo|author|name|.+ contributors|.+ plugin)$", re.I)
RRT_START = "<!-- rrt:auto:start:example-prompts-intro -->"
RRT_END = "<!-- rrt:auto:end:example-prompts-intro -->"

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
RE_FIRST_PERSON_DESC = re.compile(r"\bI (can|will|am|help|'ll)\b|\bI'm\b|\byou can use (this|it)\b", re.I)
RE_VAGUE_DESC = re.compile(r"^\s*(helps? with|processes data|does stuff|handles (things|stuff|files)|provides .{0,30}guidance)\b", re.I)
RE_WHENONLY = re.compile(r"^\s*This skill should be used (when|after|before|as|by|during|once|if)\b", re.I)
RE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RE_XML_TAG = re.compile(r"<[A-Za-z][A-Za-z0-9_-]*(\s[^>]*)?>")
RE_SKILL_VOICE = re.compile(r"\bYou (should|need to|must|can|will)\b")
RE_AGENT_VOICE = re.compile(r"\bI (will|am going to|'ll)\b")
RE_BODY_WRITES = re.compile(
    r"\b(apply|make|write|commit|perform) (the |a |an |each |this |that |one |exactly one )?(fix|edit|change|rewrite|patch)(es|s)?\b"
    r"|\bedit(s|ing)? (the |each |that )?(file|files|source)\b|\bmodif(y|ies) (the |each )?(file|files|source)\b|\bwrite(s)? (to|the) (file|disk|ledger)\b",
    re.I,
)
RE_READONLY_CLAIM = re.compile(
    r"\bread[- ]only\b(?![ -](inspection|command|check|shell|lookup|registry|access|mode for|for ))"
    r"|\bnever (edits?|writes?|modif(y|ies)) (a |any |the )?(file|source|artifact)"
    r"|\bdoes not (edit|write|modify) (a |any |the )?(file|source|artifact)", re.I)
RE_ARGS = re.compile(r"\$ARGUMENTS\b|\$[1-9]\b")
RE_TIME = re.compile(
    rf"\b(before|after|until|as of|since|prior to) ((({MONTHS})( \d{{1,2}})?,? )|(Q[1-4] ))?20\d\d\b", re.I
)
RE_WIN_PATH = re.compile(r"\b[A-Za-z]:\\[\w\\]+|\b(scripts|references|assets|docs|skills|agents)\\\w+")
RE_SECRET = re.compile(
    r"\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})\b"
    r"|password\s*[:=]\s*['\"][^'\"*]{6,}['\"]"
)
RE_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
RE_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
RE_PLUGIN_ROOT = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
RE_TOC_HEADING = re.compile(r"^#{1,3}\s*(contents|table of contents|in this (file|document|reference))\b", re.I | re.M)
RE_ESCAPE_VAR = re.compile(r"\b([A-Z][A-Z0-9_]*_DISABLE_GUARD)\b")
RE_EXIT_2 = re.compile(r"sys\.exit\(\s*2\s*\)|\bexit\(\s*2\s*\)|process\.exit\(\s*2\s*\)|\bexit 2\b")
RE_WIDE_DOT_WINDOW = re.compile(r"\[\^\.\]\{0,([5-9][0-9]|[0-9]{3,})\}")
RE_INNERHTML = re.compile(r"\.(innerHTML|outerHTML)\s*=|\binsertAdjacentHTML\s*\(")
RE_FAIL_VISIBLE = re.compile(r"re-?run|regenerate", re.I)
RE_CDN = re.compile(r"<(script|link)\b[^>]*\b(src|href)\s*=\s*[\"']https?://", re.I)
RE_SEMVER = re.compile(r"^\d+\.\d+\.\d+")
RE_STYLE = re.compile(r"<style\b.*?</style>", re.DOTALL | re.IGNORECASE)
RE_SCRIPT = re.compile(r"<script\b.*?</script>", re.DOTALL | re.IGNORECASE)
RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
RE_HTML_COMMENT = re.compile(r"<!--(?!__).*?-->", re.DOTALL)
RE_LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")
RE_CATALOG_BEAT = re.compile(r"^\s*-\s*skill:\s*[\"']?([a-z0-9-]+):([a-z0-9-]+)[\"']?", re.M)
PROMPT_KINDS = {"skill", "agent", "command", "reference", "doc", "workflow"}
SCRIPT_SUFFIXES = {".py", ".sh", ".js"}


@dataclass
class Unit:
    kind: str            # skill | agent | command | reference | doc | workflow | hooks | hookscript | script | viewer | manifest | readme | changelog | docs
    plugin: str
    path: Path           # repo-relative
    text: str
    plugin_dir: Path = Path(".")
    fm: dict | None = None
    fm_error: str | None = None
    body: str = ""
    body_line0: int = 1  # 1-based line number of the first body line
    lines: list[str] = field(default_factory=list)
    exists: bool = True
    extra: dict = field(default_factory=dict)


def _finding(unit: Unit, rule: str, claim: str, fix: str, *, line: int | None = None, quote: str = "", tier: str = "haiku") -> dict:
    sev, angle = META[rule]
    q = (quote or "").strip()
    if not q and unit.fm and isinstance(unit.fm.get("description"), str):
        q = unit.fm["description"]
    q = q[:160]
    return {
        "file": unit.path.as_posix(), "plugin": unit.plugin, "line": line, "quote": q, "rule_id": rule, "angle": angle,
        "severity": sev, "claim": claim, "suggested_fix": fix, "fix_tier": tier,
    }


def _skip(rule: str, reason: str) -> None:
    if not any(s["rule_id"] == rule and s["reason"] == reason for s in SKIPPED):
        SKIPPED.append({"rule_id": rule, "reason": reason})
        print(f"WARN {rule} skipped: {reason}", file=sys.stderr)


def _line_of(unit: Unit, needle: str, start_line: int = 1) -> int | None:
    for i, ln in enumerate(unit.lines, start=1):
        if i >= start_line and needle in ln:
            return i
    return None


def _first_match(unit: Unit, rx: re.Pattern, body_only: bool = True) -> tuple[int, str] | None:
    offset = unit.body_line0 if body_only else 1
    src = unit.body if body_only else unit.text
    for i, ln in enumerate(src.splitlines(), start=offset):
        if rx.search(ln):
            return i, ln
    return None


def _count_matches(unit: Unit, rx: re.Pattern) -> int:
    return sum(1 for ln in unit.body.splitlines() if rx.search(ln))


def _read(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:  # unreadable = loud, never "nothing found"
        print(f"WARN cannot read {p}: {e}", file=sys.stderr)
        return None


def parse_frontmatter(unit: Unit) -> None:
    text = unit.text
    if not text.startswith("---"):
        unit.fm_error = "no frontmatter at line 1"
        unit.body = text
        return
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        unit.fm_error = "frontmatter never closed"
        unit.body = text
        return
    raw = "\n".join(lines[1:end])
    try:
        fm = yaml.safe_load(raw)
    except Exception as e:  # noqa: BLE001
        unit.fm_error = f"YAML: {str(e).splitlines()[0][:90]}"
        unit.body = "\n".join(lines[end + 1:])
        unit.body_line0 = end + 2
        return
    unit.fm = fm if isinstance(fm, dict) else None
    if unit.fm is None:
        unit.fm_error = "frontmatter is not a mapping"
    unit.body = "\n".join(lines[end + 1:])
    unit.body_line0 = end + 2


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def _hooks_commands(text: str) -> list[dict]:
    """Every handler hooks.json declares: {event, matcher, type, command, timeout}.
    Returns [] when the JSON is unusable; H-JSON-PARSE reports that separately."""
    try:
        d = json.loads(text)
    except Exception:  # noqa: BLE001
        return []
    events = d.get("hooks") if isinstance(d, dict) else None
    if not isinstance(events, dict):
        return []
    out = []
    for event, entries in events.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for h in entry.get("hooks", []) or []:
                if isinstance(h, dict):
                    out.append({"event": event, "matcher": str(entry.get("matcher", "")), "type": h.get("type"),
                                "command": h.get("command"), "timeout": h.get("timeout")})
    return out


def _hook_script_path(plugin_dir: Path, command) -> Path | None:
    if not isinstance(command, str):
        return None
    m = RE_PLUGIN_ROOT.search(command)
    if m:
        return plugin_dir / m.group(1)
    # no ${CLAUDE_PLUGIN_ROOT}: take the first token that looks like a script path
    for tok in command.replace('"', " ").split():
        if tok.endswith((".py", ".sh", ".js")):
            return plugin_dir / tok if not tok.startswith("/") else Path(tok)
    return None


def discover(plugin_dirs: list[Path]) -> list[Unit]:
    units: list[Unit] = []
    for pd in plugin_dirs:
        plugin = pd.name

        def add(kind: str, p: Path, exists: bool = True, extra: dict | None = None) -> Unit | None:
            text = _read(p) if exists else ""
            if text is None:
                return None
            u = Unit(kind=kind, plugin=plugin, path=p, text=text, plugin_dir=pd, lines=text.splitlines(), exists=exists, extra=extra or {})
            if kind in {"skill", "agent", "command"}:
                parse_frontmatter(u)
            else:
                u.body = text
            units.append(u)
            return u

        for p in sorted(pd.glob("skills/*/SKILL.md")):
            add("skill", p)
        for p in sorted(pd.glob("agents/*.md")):
            add("agent", p)
        for p in sorted(pd.glob("commands/*.md")):
            add("command", p)
        for p in sorted(list(pd.glob("skills/*/references/**/*.md")) + list(pd.glob("references/**/*.md"))):
            add("reference", p)
        for p in sorted(pd.glob("skills/*/*.md")):
            if p.name != "SKILL.md":
                add("doc", p)
        for p in sorted(pd.glob("workflows/*.js")):
            add("workflow", p)

        # hooks: the manifest, then every script it declares (missing ones included, so
        # H-SCRIPT-EXISTS has a unit to hang on)
        hook_scripts: set[Path] = set()
        hj = pd / "hooks" / "hooks.json"
        if hj.is_file():
            hu = add("hooks", hj)
            if hu is not None:
                cmds = _hooks_commands(hu.text)
                hu.extra["commands"] = cmds
                for c in cmds:
                    sp = _hook_script_path(pd, c.get("command"))
                    if sp is None or sp in hook_scripts:
                        continue
                    hook_scripts.add(sp)
                    add("hookscript", sp, exists=sp.is_file(), extra={"matcher": c.get("matcher", ""), "declared_in": hj.as_posix()})

        # scripts: anything executable-shaped under scripts/ and hooks/, minus fixtures
        for p in sorted(list(pd.glob("scripts/**/*")) + list(pd.glob("hooks/*"))):
            if not p.is_file() or p.suffix not in SCRIPT_SUFFIXES or p in hook_scripts:
                continue
            parts = p.relative_to(pd).parts
            if any(x in {"fixtures", "testdata", "__pycache__", "node_modules"} for x in parts):
                continue
            add("script", p)

        for p in sorted(pd.glob("assets/*-viewer.html")):
            add("viewer", p)

        mf = pd / ".claude-plugin" / "plugin.json"
        add("manifest", mf, exists=mf.is_file())
        rd = pd / "README.md"
        add("readme", rd, exists=rd.is_file())
        cl = pd / "CHANGELOG.md"
        add("changelog", cl, exists=cl.is_file())

        docs_root = OPTIONS.get("docs_root")
        if docs_root is not None and Path(docs_root).is_dir():
            stub = Path(docs_root) / "plugins" / f"{plugin}.md"
            add("docs", stub, exists=stub.is_file(), extra={"docs_root": Path(docs_root)})
    return units


# ---------------------------------------------------------------------------
# M rules: prompt-bearing files. Each takes (unit, ctx) and returns findings.
# ---------------------------------------------------------------------------

def r_fm_parse(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind not in {"skill", "agent", "command"}:
        return []
    if u.fm_error:
        return [_finding(u, "M-FM-PARSE", f"frontmatter unusable: {u.fm_error}; the file loads with empty metadata and never triggers",
                         "fix the YAML so `---` is line 1 and the block parses", line=1, quote=u.lines[0] if u.lines else "")]
    desc = (u.fm or {}).get("description")
    if not isinstance(desc, str) or not desc.strip():
        return [_finding(u, "M-FM-PARSE", "frontmatter has no non-empty description", "add a description", line=1)]
    if u.kind == "agent" and not (u.fm or {}).get("name"):
        return [_finding(u, "M-FM-PARSE", "agent frontmatter has no name; the runtime treats the file as documentation", "add name:", line=1)]
    return []


def _desc(u: Unit) -> str | None:
    d = (u.fm or {}).get("description")
    return d if isinstance(d, str) else None


def r_desc_len(u: Unit, ctx: list[Unit]) -> list[dict]:
    d = _desc(u)
    if u.kind not in {"skill", "agent"} or d is None or len(d) <= 1024:
        return []
    return [_finding(u, "M-DESC-LEN", f"description is {len(d)} chars; the official cap is 1024",
                     "move examples and rationale into the body; keep what + when in ≤1024 chars", line=_line_of(u, "description:"))]


def r_desc_xml(u: Unit, ctx: list[Unit]) -> list[dict]:
    d = _desc(u)
    if u.kind not in {"skill", "agent"} or d is None:
        return []
    m = RE_XML_TAG.search(d)
    if not m:
        return []
    return [_finding(u, "M-DESC-XML", f"description contains an XML-style tag {m.group(0)!r}; descriptions cannot contain XML tags",
                     "move <example> blocks into a `## When to invoke` body section", line=_line_of(u, "description:"), quote=d[max(0, m.start() - 40): m.end() + 40])]


def r_desc_person(u: Unit, ctx: list[Unit]) -> list[dict]:
    d = _desc(u)
    if u.kind not in {"skill", "agent"} or d is None:
        return []
    m = RE_FIRST_PERSON_DESC.search(d)
    if not m:
        return []
    return [_finding(u, "M-DESC-PERSON", f"description is not third person ({m.group(0)!r})",
                     "rewrite in third person: 'Processes X… Use when…'", line=_line_of(u, "description:"), quote=d[max(0, m.start() - 40): m.end() + 40])]


def r_desc_vague(u: Unit, ctx: list[Unit]) -> list[dict]:
    d = _desc(u)
    if u.kind not in {"skill", "agent", "command"} or d is None:
        return []
    if not RE_VAGUE_DESC.search(d):
        return []
    return [_finding(u, "M-DESC-VAGUE", "description opens with a generic capability claim", "name the specific job and the trigger contexts", line=_line_of(u, "description:"))]


def r_desc_whenonly(u: Unit, ctx: list[Unit]) -> list[dict]:
    d = _desc(u)
    if u.kind != "skill" or d is None or not RE_WHENONLY.search(d):
        return []
    return [_finding(u, "M-DESC-WHENONLY", "description opens with the when-only template and never leads with what the skill does",
                     "lead with an active-verb what-clause, then 'Use when …'", line=_line_of(u, "description:"))]


def r_name_format(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind not in {"skill", "agent"} or u.fm is None:
        return []
    name = u.fm.get("name")
    if not isinstance(name, str):
        return []  # missing name is M-FM-PARSE's job (agents) or fine (skills default to dir)
    problems = []
    if len(name) > 64:
        problems.append("longer than 64 chars")
    if not RE_NAME.match(name):
        problems.append("not lowercase-hyphen")
    if "anthropic" in name or "claude" in name:
        problems.append("contains a reserved word")
    expected = u.path.parent.name if u.kind == "skill" else u.path.stem
    if name != expected:
        problems.append(f"does not match {'directory' if u.kind == 'skill' else 'file stem'} {expected!r}")
    if not problems:
        return []
    return [_finding(u, "M-NAME-FORMAT", f"name {name!r} " + "; ".join(problems), "rename to match the official name rules and the file location",
                     line=_line_of(u, "name:"), quote=f"name: {name}")]


def r_body_lines(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "skill":
        return []
    n = len(u.body.splitlines())
    if n < 500:
        return []
    return [_finding(u, "M-BODY-LINES", f"SKILL.md body is {n} lines; official guidance is under 500",
                     "move reference material into references/ and link it with when-to-read guidance", line=u.body_line0, quote=f"({n} body lines)")]


def r_ref_toc(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "reference":
        return []
    n = len(u.lines)
    if n <= 100:
        return []
    head = "\n".join(u.lines[:40])
    if RE_TOC_HEADING.search(head) or head.count("](#") >= 3:
        return []
    return [_finding(u, "M-REF-TOC", f"reference file is {n} lines with no table of contents in its first 40 lines",
                     "add a `## Contents` list so a partial read still shows the full scope", line=1, quote=u.lines[0] if u.lines else "")]


def _resolve_link(u: Unit, target: str) -> Path | None:
    t = target.split("#", 1)[0].strip()
    if not t or t.startswith(("http://", "https://", "mailto:", "#")):
        return None
    plugin_dir = u.plugin_dir
    if "${CLAUDE_PLUGIN_ROOT}" in t:
        p = plugin_dir / t.replace("${CLAUDE_PLUGIN_ROOT}/", "").replace("${CLAUDE_PLUGIN_ROOT}", "")
    elif "$" in t or "<" in t or "*" in t or t.startswith("/"):
        return None  # templated, or absolute on the user's machine: out of scope
    else:
        p = u.path.parent / t
    norm = Path(os.path.normpath(p))
    pnorm = Path(os.path.normpath(plugin_dir))
    if pnorm not in norm.parents and norm != pnorm:
        return None  # escapes the plugin (runtime scratch paths like ../analysis/...)
    if "analysis" in norm.parts:
        return None  # generated at run time, never checked in
    return p


def r_ref_depth(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "reference":
        return []
    out = []
    for i, ln in enumerate(u.lines, start=1):
        for m in RE_MD_LINK.finditer(ln):
            p = _resolve_link(u, m.group(1))
            if p is None or p.suffix != ".md" or p.name == "SKILL.md":
                continue
            if "references" in p.parts and p.exists():
                out.append(_finding(u, "M-REF-DEPTH", f"reference links to another reference ({m.group(1)}); references must stay one level deep from SKILL.md",
                                    "link this file from SKILL.md instead and drop the nested link", line=i, quote=ln))
                return out
    return out


def r_ref_unwired(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "skill":
        return []
    refs_dir = u.path.parent / "references"
    if not refs_dir.is_dir():
        return []
    out = []
    for p in sorted(refs_dir.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(u.path.parent).as_posix()
        if p.name in u.text or rel in u.text:
            continue
        out.append(_finding(u, "M-REF-UNWIRED", f"references/{p.relative_to(refs_dir).as_posix()} is never named in SKILL.md, so nothing tells the model when to load it",
                            "add a Resources bullet naming the file and when to read it", line=None, quote=rel))
    return out


def r_link_broken(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind not in PROMPT_KINDS or u.kind == "workflow":
        return []
    out = []
    for i, ln in enumerate(u.lines, start=1):
        targets = [m.group(1) for m in RE_MD_LINK.finditer(ln)]
        targets += ["${CLAUDE_PLUGIN_ROOT}/" + m.group(1) for m in RE_PLUGIN_ROOT.finditer(ln)]
        for t in targets:
            p = _resolve_link(u, t)
            if p is None:
                continue
            if not p.exists():
                out.append(_finding(u, "M-LINK-BROKEN", f"link target {t!r} does not exist", "fix the path or delete the link", line=i, quote=ln))
    return out


def r_dup_content(u: Unit, ctx: list[Unit]) -> list[dict]:
    # one finding per duplicate group, attached to the group's first member
    if u.kind not in PROMPT_KINDS or u.kind == "workflow" or not u.text.strip():
        return []
    h = hashlib.sha256(u.text.encode()).hexdigest()
    same = [v for v in ctx if v.kind in PROMPT_KINDS and v.kind != "workflow" and v.text == u.text]
    if len(same) < 2 or same[0] is not u:
        return []
    others = ", ".join(v.path.as_posix() for v in same[1:])
    return [_finding(u, "M-DUP-CONTENT", f"byte-identical to {len(same) - 1} other file(s): {others}",
                     "keep one copy in a shared location and link it; a fact lives in one place", line=1, quote=f"sha256 {h[:12]} × {len(same)}")]


def r_skill_voice(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "skill":
        return []
    m = _first_match(u, RE_SKILL_VOICE)
    if not m:
        return []
    n = _count_matches(u, RE_SKILL_VOICE)
    return [_finding(u, "M-SKILL-VOICE", f"body addresses the reader in second person on {n} line(s)", "rewrite in imperative/infinitive form", line=m[0], quote=m[1])]


def r_agent_voice(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "agent":
        return []
    hits = []
    in_fence = False
    for i, ln in enumerate(u.body.splitlines(), start=u.body_line0):
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or re.match(r"\s*(user|assistant|human):", ln, re.I) or "<example>" in ln:
            continue
        if RE_AGENT_VOICE.search(ln):
            hits.append((i, ln))
    if not hits:
        return []
    return [_finding(u, "M-AGENT-VOICE", f"agent body speaks in first person on {len(hits)} line(s)", "write the system prompt in second person ('You …')", line=hits[0][0], quote=hits[0][1])]


def r_agent_model(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "agent" or u.fm is None or "model" not in u.fm:
        return []
    m = str(u.fm["model"])
    if m in MODEL_ALIASES or re.match(r"^claude-[a-z0-9.-]+$", m):
        return []
    return [_finding(u, "M-AGENT-MODEL", f"model {m!r} is not a documented alias or full model id", "use inherit|sonnet|opus|haiku|fable or a full id", line=_line_of(u, "model:"), quote=f"model: {m}")]


def _tools_tokens(fm: dict) -> list[str] | None:
    t = fm.get("tools")
    if t is None:
        return None
    if isinstance(t, list):
        return [str(x).strip() for x in t]
    return [x.strip() for x in str(t).split(",") if x.strip()]


def r_agent_tools_shape(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "agent" or u.fm is None or "tools" not in u.fm:
        return []
    t = u.fm["tools"]
    line = _line_of(u, "tools:")
    if isinstance(t, list):
        return [_finding(u, "M-AGENT-TOOLS-SHAPE", "tools is a YAML list; the canonical form is a comma-separated string", "write `tools: Read, Grep, Glob`", line=line, quote=f"tools: {t}")]
    bad = []
    for tok in _tools_tokens(u.fm) or []:
        base = tok.split("(", 1)[0]
        if tok == "*" or not (base in KNOWN_TOOLS or base.startswith("mcp__")):
            bad.append(tok)
    if not bad:
        return []
    return [_finding(u, "M-AGENT-TOOLS-SHAPE", f"unknown tool token(s) {bad}; the agent may fail to launch or silently lose tools", "use documented tool names", line=line, quote=f"tools: {t}")]


def r_agent_tools_verbs(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "agent" or u.fm is None:
        return []
    toks = _tools_tokens(u.fm)
    if toks is None:
        return []  # inherits everything; least-privilege is a Q-PROC-TOOLS-ROLE judgement
    has_write = bool(set(toks) & WRITE_TOOLS)
    wm = _first_match(u, RE_BODY_WRITES)
    rm = _first_match(u, RE_READONLY_CLAIM)
    out = []
    if wm and not has_write and not rm:
        out.append(_finding(u, "M-AGENT-TOOLS-VERBS", "body instructs the agent to edit or write files but tools grants neither Edit nor Write",
                            "grant Edit/Write or rewrite the body as propose-only", line=wm[0], quote=wm[1]))
    if rm and has_write:
        out.append(_finding(u, "M-AGENT-TOOLS-VERBS", "body claims the agent is read-only but tools grants Edit/Write",
                            "drop Edit/Write from tools or remove the read-only claim", line=rm[0], quote=rm[1]))
    return out


def r_version_field(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind not in {"skill", "agent"} or u.fm is None or "version" not in u.fm:
        return []
    return [_finding(u, "M-VERSION-FIELD", "frontmatter carries version:, which no runtime reads and nothing maintains", "delete the key", line=_line_of(u, "version:"), quote=f"version: {u.fm['version']}")]


def r_cmd_arghint(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "command" or u.fm is None:
        return []
    m = _first_match(u, RE_ARGS)
    if not m or u.fm.get("argument-hint"):
        return []
    return [_finding(u, "M-CMD-ARGHINT", "body uses positional arguments but frontmatter has no argument-hint", "add `argument-hint: <what> [optional]`", line=m[0], quote=m[1])]


def r_cmd_desc_len(u: Unit, ctx: list[Unit]) -> list[dict]:
    d = _desc(u)
    if u.kind != "command" or d is None or len(d) <= 150:
        return []
    return [_finding(u, "M-CMD-DESC-LEN", f"command description is {len(d)} chars; it renders in /help", "cut to one clause", line=_line_of(u, "description:"))]


def r_time_sensitive(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind not in PROMPT_KINDS:
        return []
    m = _first_match(u, RE_TIME)
    if not m:
        return []
    return [_finding(u, "M-TIME-SENSITIVE", "body contains a dated instruction that will silently become wrong", "state the current method; move legacy into an 'Old patterns' section", line=m[0], quote=m[1])]


def r_win_paths(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind not in PROMPT_KINDS or u.kind == "workflow":
        return []
    m = _first_match(u, RE_WIN_PATH)
    if not m:
        return []
    return [_finding(u, "M-WIN-PATHS", "Windows-style path", "use forward slashes", line=m[0], quote=m[1])]


def r_bash_wildcard(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind not in {"skill", "command"} or u.fm is None:
        return []
    at = u.fm.get("allowed-tools")
    if at is None:
        return []
    toks = [str(x).strip() for x in at] if isinstance(at, list) else [x.strip() for x in str(at).split(",")]
    bad = [t for t in toks if t in {"*", "Bash", "Bash(*)", "Bash(*:*)"}]
    if not bad:
        return []
    return [_finding(u, "M-BASH-WILDCARD", f"allowed-tools grants unscoped shell access {bad}", "scope it: `Bash(git:*)`", line=_line_of(u, "allowed-tools"), quote=f"allowed-tools: {at}")]


def r_secrets(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind not in PROMPT_KINDS:
        return []
    m = _first_match(u, RE_SECRET, body_only=False)
    if not m:
        return []
    return [_finding(u, "M-SECRETS", "credential-shaped literal", "remove it; use a masked placeholder", line=m[0], quote=re.sub(r"(?<=.{4}).", "*", m[1].strip())[:80])]


# ---------------------------------------------------------------------------
# H rules: hooks/hooks.json and the scripts it declares
# ---------------------------------------------------------------------------

def _hook_json(u: Unit):
    try:
        return json.loads(u.text)
    except Exception:  # noqa: BLE001
        return None


def r_h_json_parse(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hooks":
        return []
    d = _hook_json(u)
    if not isinstance(d, dict):
        return [_finding(u, "H-JSON-PARSE", "hooks.json is not a JSON object; the runtime registers nothing", "make it `{\"hooks\": {\"PreToolUse\": [...]}}`", line=1, quote=(u.lines[0] if u.lines else "")[:120])]
    events = d.get("hooks")
    if not isinstance(events, dict) or not events:
        return [_finding(u, "H-JSON-PARSE", "hooks.json has no `hooks` object mapping an event to handlers, so it registers zero events", "add `\"hooks\": {\"PreToolUse\": [{\"matcher\": ..., \"hooks\": [...]}]}`", line=1, quote="hooks")]
    for ev, entries in events.items():
        if not isinstance(entries, list) or not all(isinstance(e, dict) and isinstance(e.get("hooks"), list) for e in entries):
            return [_finding(u, "H-JSON-PARSE", f"event {ev!r} is not a list of {{matcher, hooks[]}} entries", "wrap each handler set in `{\"matcher\": ..., \"hooks\": [...]}`", line=_line_of(u, ev), quote=ev)]
    return []


def r_h_type_command(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hooks":
        return []
    out = []
    for c in u.extra.get("commands", []):
        if c.get("type") != "command":
            out.append(_finding(u, "H-TYPE-COMMAND", f"a {c['event']} handler is type {c.get('type')!r}; only type \"command\" enforces without asking a model to decide",
                                "make it `\"type\": \"command\"` with a script that exits 2 to deny", line=_line_of(u, '"type"'), quote=f"type: {c.get('type')}"))
    return out


def r_h_cmd_plugin_root(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hooks":
        return []
    out = []
    for c in u.extra.get("commands", []):
        cmd = c.get("command")
        if not isinstance(cmd, str):
            continue
        if "${CLAUDE_PLUGIN_ROOT}" not in cmd or re.search(r"(^|\s|\")/(home|Users|root|opt|tmp|var)/", cmd):
            out.append(_finding(u, "H-CMD-PLUGIN-ROOT", "hook command does not locate its script through ${CLAUDE_PLUGIN_ROOT} (or hard-codes an absolute path), so it breaks wherever the plugin is installed",
                                "write `python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/<script>.py\"`", line=_line_of(u, '"command"'), quote=cmd[:120]))
    return out


def r_h_script_exists(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hooks":
        return []
    out = []
    for c in u.extra.get("commands", []):
        sp = _hook_script_path(u.plugin_dir, c.get("command"))
        if sp is None:
            continue
        if not sp.is_file():
            out.append(_finding(u, "H-SCRIPT-EXISTS", f"declared hook script {sp.as_posix()} does not exist: a declaration without an implementation",
                                "add the script or fix the command path", line=_line_of(u, '"command"'), quote=str(c.get("command"))[:120]))
    return out


def r_h_timeout(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hooks":
        return []
    out = []
    for c in u.extra.get("commands", []):
        if c.get("type") == "command" and not isinstance(c.get("timeout"), int):
            out.append(_finding(u, "H-TIMEOUT", f"the {c['event']} command handler sets no integer `timeout`", "add `\"timeout\": 15`", line=_line_of(u, '"command"'), quote=str(c.get("command"))[:120]))
            break
    return out


def r_h_matcher_known(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hooks":
        return []
    out = []
    seen = set()
    for c in u.extra.get("commands", []):
        m = c.get("matcher", "")
        if m in seen or m in {"", "*", ".*"}:
            continue
        seen.add(m)
        toks = [t.strip() for t in m.split("|") if t.strip()]
        bad = [t for t in toks if not (t in KNOWN_TOOLS or t.startswith("mcp__"))]
        if bad:
            out.append(_finding(u, "H-MATCHER-KNOWN", f"matcher names unknown tool(s) {bad}; a matcher that matches nothing is a hook that never runs", "use documented tool names joined by |", line=_line_of(u, m), quote=m))
    return out


def r_h_matcher_multiedit(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hooks":
        return []
    for c in u.extra.get("commands", []):
        m = c.get("matcher", "")
        toks = {t.strip() for t in m.split("|")}
        if toks & {"Edit", "Write"} and "MultiEdit" not in toks:
            return [_finding(u, "H-MATCHER-MULTIEDIT", "matcher gates Edit/Write but not MultiEdit, so a multi-file edit bypasses the guard", "add MultiEdit to the matcher", line=_line_of(u, m), quote=m)]
    return []


def r_h_inert_stated(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hooks":
        return []
    d = _hook_json(u)
    desc = d.get("description") if isinstance(d, dict) else None
    if isinstance(desc, str) and "inert" in desc.lower():
        return []
    return [_finding(u, "H-INERT-STATED", "hooks.json description does not state when the hook is inert; a reader cannot tell whether it will fire on their repo", "add a description ending 'Inert until <marker> exists.'", line=1, quote=(desc or "")[:120])]


def _is_edit_gating(u: Unit) -> bool:
    toks = {t.strip() for t in str(u.extra.get("matcher", "")).split("|")}
    return bool(toks & EDIT_MATCHER_TOOLS)


def r_h_deny_shape(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hookscript" or not u.exists:
        return []
    t = u.text
    if "permissionDecision" in t and "hookEventName" not in t:
        return [_finding(u, "H-DENY-SHAPE", "the deny JSON carries permissionDecision but no hookEventName; the runtime discards the decision and the hook silently allows",
                         "emit {\"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", \"permissionDecision\": \"deny\", \"permissionDecisionReason\": ...}}", line=_line_of(u, "permissionDecision"), quote="permissionDecision")]
    if "systemMessage" in t and "permissionDecisionReason" not in t:
        return [_finding(u, "H-DENY-SHAPE", "the script uses systemMessage instead of permissionDecisionReason; the runtime ignores the deny",
                         "replace systemMessage with hookSpecificOutput.permissionDecisionReason", line=_line_of(u, "systemMessage"), quote="systemMessage")]
    if "permissionDecision" not in t and "systemMessage" not in t:
        return [_finding(u, "H-DENY-SHAPE", "the script never emits a deny decision JSON; exit 2 alone is not a decision the runtime keeps",
                         "print the hookSpecificOutput JSON on stdout before exiting 2", line=1, quote=(u.lines[0] if u.lines else "")[:120])]
    return []


def r_h_exit_2(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hookscript" or not u.exists:
        return []
    if RE_EXIT_2.search(u.text) or re.search(r"^\s*return 2\b", u.text, re.M) or re.search(r"(DENY|BLOCK)\w*\s*=\s*2\b", u.text):
        return []
    return [_finding(u, "H-EXIT-2", "the script never exits with code 2, so no deny it prints is honoured", "exit 2 after printing the deny JSON and the reason on stderr", line=1, quote=(u.lines[0] if u.lines else "")[:120])]


def r_h_escape_hatch(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hookscript" or not u.exists:
        return []
    names = set(RE_ESCAPE_VAR.findall(u.text))
    if not names:
        return [_finding(u, "H-ESCAPE-HATCH", "no <NAME>_DISABLE_GUARD escape hatch; a wrong denial can only be bypassed by editing the plugin", "read one env var and name it in every deny reason", line=1, quote=(u.lines[0] if u.lines else "")[:120])]
    for n in names:
        if len(re.findall(rf"\b{re.escape(n)}\b", u.text)) >= 2:
            return []
    return [_finding(u, "H-ESCAPE-HATCH", f"escape hatch {sorted(names)[0]} is read but never named in a deny reason, so a blocked caller does not learn it exists", "include the variable name in the deny message", line=_line_of(u, sorted(names)[0]), quote=sorted(names)[0])]


def _py_tree(u: Unit) -> ast.AST | None:
    if u.path.suffix != ".py":
        return None
    cached = u.extra.get("_tree")
    if cached is not None:
        return cached if cached is not False else None
    try:
        tree = ast.parse(u.text)
    except SyntaxError:
        u.extra["_tree"] = False
        return None
    u.extra["_tree"] = tree
    return tree


def _calls_named(node: ast.AST, names: set[str]) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id in names:
                return True
            if isinstance(f, ast.Attribute) and f.attr in names:
                return True
    return False


def _exits_zero(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "exit" and n.args:
            a = n.args[0]
            if isinstance(a, ast.Constant) and a.value == 0:
                return True
    return False


def r_h_fail_closed(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hookscript" or not u.exists or u.path.suffix != ".py":
        return []
    tree = _py_tree(u)
    if tree is None:
        return []  # S-PY-COMPILE reports the parse failure
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)
                and (n.type is None or (isinstance(n.type, ast.Name) and n.type.id in {"Exception", "BaseException"}))]
    if not handlers:
        return [_finding(u, "H-FAIL-CLOSED", "no broad except handler: an unexpected error propagates as exit 1, which the runtime treats as a non-blocking error and allows the call",
                         "wrap the evaluation in try/except Exception and deny with the escape hatch named", line=1, quote=(u.lines[0] if u.lines else "")[:120])]
    last = max(handlers, key=lambda h: h.lineno)
    body = ast.Module(body=last.body, type_ignores=[])
    if _calls_named(body, {"deny"}) and not (_calls_named(body, {"allow"}) or _exits_zero(body)):
        return []
    return [_finding(u, "H-FAIL-CLOSED", f"the broad except handler at line {last.lineno} allows (or exits 0) on an internal error; a guard that fails open on its own bug is not a guard",
                     "call deny(...) in that handler, naming the escape hatch", line=last.lineno, quote=u.lines[last.lineno - 1] if last.lineno <= len(u.lines) else "")]


def r_h_multi_path(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hookscript" or not u.exists or not _is_edit_gating(u):
        return []
    missing = [k for k in ("edits", "file_paths") if not re.search(rf"[\"']{k}[\"']", u.text)]
    if not missing:
        return []
    return [_finding(u, "H-MULTI-PATH", f"an edit-gating script reads only file_path; a MultiEdit payload carrying its paths in {missing} yields no target and bypasses the gate",
                     "collect file_path, edits[].file_path and file_paths, and deny when the set is empty", line=_line_of(u, "file_path"), quote="file_path")]


def r_h_test_exists(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "hookscript" or not u.exists:
        return []
    stem = u.path.stem
    candidates = [u.path.parent / f"test_{stem}.py"] + list(u.plugin_dir.glob(f"**/test_{stem}.py"))
    if any(c.is_file() for c in candidates):
        return []
    return [_finding(u, "H-TEST-EXISTS", f"no test_{stem}.py beside the hook script; 'the hook exists' and 'the hook denies' are different claims",
                     f"add hooks/test_{stem}.py that feeds a violating stdin payload and asserts exit 2 plus hookEventName", line=1, quote=stem)]


# ---------------------------------------------------------------------------
# S rules: scripts under scripts/ and hooks/
# ---------------------------------------------------------------------------

def _is_script(u: Unit) -> bool:
    return u.kind in {"script", "hookscript"} and u.exists


def _is_entry_point(u: Unit) -> bool:
    if u.path.suffix == ".sh":
        return True
    return u.path.suffix == ".py" and "__main__" in u.text


def r_s_py_compile(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _is_script(u) or u.path.suffix != ".py":
        return []
    try:
        ast.parse(u.text)
    except SyntaxError as e:
        return [_finding(u, "S-PY-COMPILE", f"does not parse: {e.msg} (line {e.lineno})", "fix the syntax error", line=e.lineno, quote=(u.lines[e.lineno - 1] if e.lineno and e.lineno <= len(u.lines) else "")[:120])]
    return []


_NODE_CACHE: dict[tuple[str, str], tuple[int, str]] = {}


def r_s_js_syntax(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not ((_is_script(u) and u.path.suffix == ".js") or u.kind == "workflow"):
        return []
    node = OPTIONS.get("node")
    if not node:
        _skip("S-JS-SYNTAX", "node is not on PATH")
        return []
    k = (u.path.as_posix(), hashlib.sha256(u.text.encode()).hexdigest())
    if k not in _NODE_CACHE:
        try:
            r = subprocess.run([node, "--check", str(u.path)], capture_output=True, text=True, timeout=60)
            _NODE_CACHE[k] = (r.returncode, (r.stderr or "").strip())
        except (OSError, subprocess.TimeoutExpired) as e:
            _NODE_CACHE[k] = (1, f"{type(e).__name__}: {e}")
    rc, err = _NODE_CACHE[k]
    if rc == 0:
        return []
    first = next((ln for ln in err.splitlines() if ln.strip() and not ln.startswith(("(node:", "Node.js"))), err)
    m = re.search(r":(\d+)$", first.split("\n")[0])
    return [_finding(u, "S-JS-SYNTAX", f"node --check fails: {first[:140]}", "fix the JavaScript syntax", line=int(m.group(1)) if m else None, quote=first[:120])]


def r_s_shebang(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _is_script(u) or not _is_entry_point(u):
        return []
    first = u.lines[0] if u.lines else ""
    if first.startswith("#!") and re.search(r"python3|bash|\bsh\b", first):
        return []
    return [_finding(u, "S-SHEBANG", "entry-point script has no interpreter shebang", "start with `#!/usr/bin/env python3` (or bash)", line=1, quote=first[:120])]


def r_s_docstring_usage(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _is_script(u) or u.path.suffix != ".py" or not _is_entry_point(u) or u.path.stem.startswith("test_"):
        return []
    tree = _py_tree(u)
    if tree is None:
        return []
    doc = ast.get_docstring(tree) or ""
    if re.search(r"\busage\b", doc, re.I) or re.search(r"^\s*(import argparse|from argparse import)", u.text, re.M):
        return []
    return [_finding(u, "S-DOCSTRING-USAGE", "entry-point script has neither a module docstring stating its usage nor an argparse --help, so a caller cannot tell how to run it",
                     "add a `Usage:` line to the module docstring (and `Exit:` codes)", line=1, quote=(u.lines[0] if u.lines else "")[:120])]


def r_s_argparse(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _is_script(u) or u.path.suffix != ".py":
        return []
    if "sys.argv" not in u.text or re.search(r"^\s*(import argparse|from argparse import)", u.text, re.M):
        return []
    return [_finding(u, "S-ARGPARSE", "script reads sys.argv by hand, so it has no --help and silently mis-parses unexpected arguments", "parse arguments with argparse", line=_line_of(u, "sys.argv"), quote="sys.argv")]


def r_s_silent_regex(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not (_is_script(u) or u.kind == "workflow"):
        return []
    checks = [(r"\b!==", "`\\b!==` (no word character is adjacent to '!', so it never matches)"), (r"\b===", "`\\b===` (never matches)")]
    if u.path.suffix == ".sh":
        checks.append((r"[^\n]", "`[^\\n]` in a POSIX bracket expression (means 'not backslash, not n')"))
    uses_regex = re.compile(r"\bre\.\w+\(|RegExp\(|\.(test|match|matchAll|replace|search)\(|\b(grep|egrep|awk|sed)\b")
    for i, ln in enumerate(u.lines, start=1):
        if not uses_regex.search(ln):
            continue
        for needle, why in checks:
            if needle in ln:
                return [_finding(u, "S-SILENT-REGEX", f"regex form that fails silently: {why}", "rewrite the pattern; see test/plugins/lint-oracles.sh", line=i, quote=ln.strip()[:120])]
        if RE_WIDE_DOT_WINDOW.search(ln):
            return [_finding(u, "S-SILENT-REGEX", "regex form that fails silently: `[^.]{0,N}` with N ≥ 50 cannot span a dotted file name or module path", "narrow the window or drop the dot exclusion", line=i, quote=ln.strip()[:120])]
    return []


def r_s_except_swallow(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _is_script(u) or u.path.suffix != ".py":
        return []
    tree = _py_tree(u)
    if tree is None:
        return []
    for n in ast.walk(tree):
        if isinstance(n, ast.ExceptHandler) and len(n.body) == 1 and isinstance(n.body[0], ast.Pass):
            if n.type is None or (isinstance(n.type, ast.Name) and n.type.id in {"Exception", "BaseException"}):
                return [_finding(u, "S-EXCEPT-SWALLOW", f"`except: pass` at line {n.lineno} swallows every error, so a failure looks like 'nothing found'", "catch the specific exception and report or re-raise", line=n.lineno, quote=u.lines[n.lineno - 1].strip()[:120])]
    return []


def r_s_shell_true(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _is_script(u) or u.path.suffix != ".py":
        return []
    tree = _py_tree(u)
    if tree is None:
        return []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in n.keywords):
            return [_finding(u, "S-SHELL-TRUE", "subprocess call with shell=True; arguments are interpolated into a shell", "pass an argument list without shell=True", line=n.lineno, quote=u.lines[n.lineno - 1].strip()[:120])]
    return []


def r_s_referenced(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _is_script(u):
        return []
    stem = u.path.stem
    if stem.startswith("test_") or stem.endswith("_test") or stem in {"__init__", "conftest"} or "/lib/" in u.path.as_posix():
        return []
    name = u.path.name
    for v in ctx:
        if v is u or v.plugin != u.plugin:
            continue
        if name in v.text:
            return []
        if v.kind in {"script", "hookscript"} and re.search(rf"^\s*(from|import)\s+[\w.]*\b{re.escape(stem)}\b", v.text, re.M):
            return []
    return [_finding(u, "S-REFERENCED", f"{name} is named by no skill, agent, command, README, hook or sibling script in the plugin, so nothing says when to run it",
                     "reference it from the SKILL.md or README that needs it, stating whether to run or read it", line=1, quote=name)]


# ---------------------------------------------------------------------------
# A rules: report viewers. R1/R4/S1/S2/C1/C2 delegate to the vendored CI checker.
# ---------------------------------------------------------------------------

_VIEWER_MOD = None


def _viewer_checker():
    global _VIEWER_MOD
    if _VIEWER_MOD is not None:
        return _VIEWER_MOD if _VIEWER_MOD is not False else None
    p = OPTIONS.get("viewer_checker")
    if not p or not Path(p).is_file():
        _VIEWER_MOD = False
        return None
    spec = importlib.util.spec_from_file_location("check_viewer_conformance", str(p))
    if spec is None or spec.loader is None:
        _VIEWER_MOD = False
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_viewer_conformance"] = mod
    spec.loader.exec_module(mod)
    _VIEWER_MOD = mod
    return mod


def _viewer_codes(u: Unit) -> dict[str, list[str]] | None:
    """{code: [messages]} from the CI checker, cached on the unit."""
    if "_codes" in u.extra:
        return u.extra["_codes"]
    mod = _viewer_checker()
    if mod is None:
        u.extra["_codes"] = None
        return None
    try:
        errs = mod.check(u.plugin, str(u.path), plugin_dir=str(u.plugin_dir))
    except Exception as e:  # noqa: BLE001 -- an unreadable screenshot is a C1 defect, not a crash
        errs = [f"{u.path.as_posix()}: C1 -- {type(e).__name__}: {e}"]
    codes: dict[str, list[str]] = {}
    for line in errs:
        m = re.search(r": (R1|R4|S1|S2|C1|C2) -- (.*)$", line)
        if m:
            codes.setdefault(m.group(1), []).append(m.group(2))
    u.extra["_codes"] = codes
    return codes


def _delegated(u: Unit, rule: str, code: str, fix: str) -> list[dict]:
    if u.kind != "viewer":
        return []
    codes = _viewer_codes(u)
    if codes is None:
        _skip(rule, "viewer checker not available (--viewer-checker)")
        return []
    msgs = codes.get(code)
    if not msgs:
        return []
    return [_finding(u, rule, f"{code}: " + "; ".join(msgs), fix, line=None, quote=msgs[0][:120])]


def r_a_r1(u, ctx): return _delegated(u, "A-R1-VERDICT", "R1", "add a static element with class=\"verdict\" that states the finding in words")
def r_a_r4(u, ctx): return _delegated(u, "A-R4-LEGEND", "R4", "add a static legend or note element visible without interaction")
def r_a_s1(u, ctx): return _delegated(u, "A-S1-HEIGHT", "S1", "replace the bare 61px with var(--header-h)")
def r_a_s2(u, ctx): return _delegated(u, "A-S2-HEAD", "S2", "give the head the CSP meta, the canonical tokens marker, and a matching static <title>/<h1>")
def r_a_c1(u, ctx): return _delegated(u, "A-C1-SCREENSHOT", "C1", "commit a 1600-px-wide <viewer>-screenshot.jpg rendered from the demo data")
def r_a_c2(u, ctx): return _delegated(u, "A-C2-DEMO-DATA", "C2", "cite the committed demo data under scripts/fixtures/ or scripts/testdata/ from the README")


def _script_blocks(u: Unit) -> str:
    return " ".join(RE_SCRIPT.findall(u.text))


def _strip_comments(text: str) -> str:
    return RE_LINE_COMMENT.sub(" ", RE_HTML_COMMENT.sub(" ", RE_BLOCK_COMMENT.sub(" ", text)))


def _constant_literal_follows(src: str) -> bool:
    """True when the text after an assignment is one quoted literal with no `${`
    interpolation and no concatenation -- a constant message, not data."""
    rest = src.lstrip()
    if not rest or rest[0] not in "'\"`":
        return False
    q = rest[0]
    i = 1
    while i < len(rest):
        if rest[i] == "\\":
            i += 2
            continue
        if rest[i] == q:
            break
        i += 1
    lit, after = rest[1:i], rest[i + 1:].lstrip()
    return "${" not in lit and (not after or after[0] in ";}\n")


def r_a_s3_innerhtml(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "viewer":
        return []
    scripts = _strip_comments(_script_blocks(u))
    for m in RE_INNERHTML.finditer(scripts):
        if m.group(0).rstrip().endswith("=") and _constant_literal_follows(scripts[m.end():m.end() + 400]):
            continue
        return [_finding(u, "A-S3-INNERHTML", f"template renders data through {m.group(0).strip()} — the second XSS barrier is missing", "render every string through textContent", line=_line_of(u, m.group(0).split("=")[0].strip().lstrip(".")), quote=m.group(0)[:120])]
    return []


def r_a_s4_fail_visible(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "viewer":
        return []
    if RE_FAIL_VISIBLE.search(_script_blocks(u)):
        return []
    return [_finding(u, "A-S4-FAIL-VISIBLE", "no visible-failure branch: the script never tells the reader to re-run or regenerate when its input is missing or unparseable", "render a 're-run <builder> to regenerate' message on missing or bad input", line=None, quote=u.path.name)]


def r_a_no_cdn(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "viewer":
        return []
    m = _first_match(u, RE_CDN, body_only=False)
    if not m:
        return []
    return [_finding(u, "A-NO-CDN", "loads a script or stylesheet from the network; the viewer must be self-contained under default-src 'none'", "inline the asset (see tools/d3-subset)", line=m[0], quote=m[1].strip()[:120])]


def r_a_tokens_present(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "viewer" or (u.plugin_dir / "assets" / "tokens.css").is_file():
        return []
    return [_finding(u, "A-TOKENS-PRESENT", "plugin ships a viewer but no assets/tokens.css; the builder cannot inject the design tokens", "vendor tools/design-tokens/tokens.css via .rrt.toml artifact_targets", line=None, quote="assets/tokens.css")]


def r_a_builder_exists(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "viewer":
        return []
    for v in ctx:
        if v.plugin == u.plugin and v.kind == "script" and v.path.suffix == ".py" and (u.path.name in v.text or "__DESIGN_TOKENS__" in v.text):
            return []
    return [_finding(u, "A-BUILDER-EXISTS", f"no scripts/*.py names {u.path.name} or injects the design-tokens marker; the viewer has no builder", "add scripts/build_<report>_html.py that reads the template by name", line=None, quote=u.path.name)]


def r_a_c4_alt(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "viewer":
        return []
    shot = u.path.name[:-len(".html")] + "-screenshot.jpg"
    readme = next((v for v in ctx if v.plugin == u.plugin and v.kind == "readme"), None)
    if readme is None:
        return []
    for i, ln in enumerate(readme.lines, start=1):
        for m in RE_MD_IMAGE.finditer(ln):
            if shot in m.group(2):
                alt = m.group(1).strip()
                if len(alt) >= 10 and alt.lower() != u.plugin:
                    return []
                return [_finding(readme, "A-C4-ALT", f"screenshot alt text {alt!r} does not describe the image", "describe what the picture shows, not the feature", line=i, quote=ln.strip()[:120])]
    return []


# ---------------------------------------------------------------------------
# P rules: manifest, README, CHANGELOG
# ---------------------------------------------------------------------------

def _manifest(u: Unit):
    if "_mf" in u.extra:
        return u.extra["_mf"]
    try:
        d = json.loads(u.text) if u.exists else None
    except Exception:  # noqa: BLE001
        d = None
    u.extra["_mf"] = d if isinstance(d, dict) else None
    return u.extra["_mf"]


def r_p_manifest_parse(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    if not u.exists:
        return [_finding(u, "P-MANIFEST-PARSE", ".claude-plugin/plugin.json is missing; the directory is not a plugin", "add the manifest with name, version, description, author", line=None, quote="plugin.json")]
    d = _manifest(u)
    if d is None:
        return [_finding(u, "P-MANIFEST-PARSE", "plugin.json is not a JSON object", "fix the JSON", line=1, quote=(u.lines[0] if u.lines else "")[:120])]
    missing = [k for k in ("name", "version", "description") if not (isinstance(d.get(k), str) and d[k].strip())]
    if missing:
        return [_finding(u, "P-MANIFEST-PARSE", f"plugin.json lacks non-empty {missing}", "fill the required keys", line=1, quote=", ".join(missing))]
    return []


def r_p_manifest_name_dir(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    d = _manifest(u)
    if d is None or not isinstance(d.get("name"), str):
        return []
    if d["name"] == u.plugin:
        return []
    return [_finding(u, "P-MANIFEST-NAME-DIR", f"manifest name {d['name']!r} differs from the directory {u.plugin!r}", "make them equal", line=_line_of(u, '"name"'), quote=f"name: {d['name']}")]


def r_p_manifest_semver(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    d = _manifest(u)
    if d is None or not isinstance(d.get("version"), str) or RE_SEMVER.match(d["version"]):
        return []
    return [_finding(u, "P-MANIFEST-SEMVER", f"version {d['version']!r} is not x.y.z, which the release tooling cannot bump", "use semantic versioning", line=_line_of(u, '"version"'), quote=f"version: {d['version']}")]


def r_p_author_present(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    d = _manifest(u)
    if d is None:
        return []
    a = d.get("author")
    name = a.get("name") if isinstance(a, dict) else (a if isinstance(a, str) else None)
    if not isinstance(name, str) or not name.strip() or PLACEHOLDER_AUTHORS.match(name.strip()):
        return [_finding(u, "P-AUTHOR-PRESENT", f"author.name is missing or a placeholder ({name!r})", "name a real author", line=_line_of(u, '"author"'), quote=str(name))]
    return []


def r_p_marketplace_member(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    mp = OPTIONS.get("marketplace")
    if not mp:
        return []
    mp = Path(mp)
    if not mp.is_file():
        _skip("P-MARKETPLACE-MEMBER", f"marketplace file not found: {mp}")
        return []
    d = _manifest(u)
    if d is None:
        return []
    try:
        entries = json.loads(mp.read_text(encoding="utf-8")).get("plugins", [])
    except Exception as e:  # noqa: BLE001
        return [_finding(u, "P-MARKETPLACE-MEMBER", f"marketplace.json unreadable: {e}", "fix marketplace.json", tier="human")]
    entry = next((e for e in entries if isinstance(e, dict) and e.get("name") == u.plugin), None)
    if entry is None:
        return [_finding(u, "P-MARKETPLACE-MEMBER", f"{u.plugin} has no entry in {mp.as_posix()}; it cannot be installed from the marketplace", "add the marketplace entry", tier="human", quote=u.plugin)]
    problems = []
    ma = (entry.get("author") or {}).get("name") if isinstance(entry.get("author"), dict) else None
    pa = (d.get("author") or {}).get("name") if isinstance(d.get("author"), dict) else None
    if ma != pa:
        problems.append(f"author.name {pa!r} vs marketplace {ma!r}")
    if entry.get("description") != d.get("description"):
        problems.append("description differs from the marketplace copy (run `rrt fields`)")
    src = str(entry.get("source", ""))
    if not src.rstrip("/").endswith(f"/{u.plugin}"):
        problems.append(f"source {src!r} does not point at ./plugins/{u.plugin}")
    if not problems:
        return []
    return [_finding(u, "P-MARKETPLACE-MEMBER", "; ".join(problems), "sync the marketplace entry with plugin.json", tier="human", quote=u.plugin)]


def r_p_manifest_keywords(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    d = _manifest(u)
    if d is None or (isinstance(d.get("keywords"), list) and d["keywords"]):
        return []
    return [_finding(u, "P-MANIFEST-KEYWORDS", "no keywords list; marketplace search cannot find the plugin by topic", "add 3–6 keywords", line=1, quote="keywords")]


def r_p_manifest_license(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    d = _manifest(u)
    if d is None or isinstance(d.get("license"), str) and d["license"].strip():
        return []
    return [_finding(u, "P-MANIFEST-LICENSE", "no license field", "add `\"license\": \"MIT\"` (or the license the plugin carries)", line=1, quote="license")]


def _readme(u: Unit) -> bool:
    return u.kind == "readme"


def _headings(u: Unit) -> list[tuple[int, str]]:
    out = []
    in_fence = False
    for i, ln in enumerate(u.lines, start=1):
        if ln.startswith("```") or ln.startswith("````"):
            in_fence = not in_fence
            continue
        if not in_fence and ln.startswith("#"):
            out.append((i, ln.strip()))
    return out


def r_p_readme_h1(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u):
        return []
    if not u.exists:
        return [_finding(u, "P-README-H1", "README.md is missing", f"add README.md opening with `# {u.plugin}`", quote="README.md")]
    hs = _headings(u)
    if hs and hs[0][1] == f"# {u.plugin}":
        return []
    return [_finding(u, "P-README-H1", f"README's first heading is {hs[0][1] if hs else 'absent'!r}, not `# {u.plugin}`", f"open with `# {u.plugin}`", line=hs[0][0] if hs else 1, quote=(hs[0][1] if hs else "")[:120])]


def r_p_readme_thesis(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u) or not u.exists:
        return []
    hs = _headings(u)
    if not hs:
        return []
    i = hs[0][0]
    nxt = next((ln for ln in u.lines[i:] if ln.strip()), "")
    if nxt.startswith("**"):
        return []
    return [_finding(u, "P-README-THESIS", "no bold one-line thesis directly under the H1", "state what the plugin does in one bold sentence under the title", line=i + 1, quote=nxt[:120])]


def r_p_readme_why_not(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u) or not u.exists:
        return []
    heads = {h for _, h in _headings(u)}
    missing = [h for h in ("## Why this exists", "## What it is not") if h not in heads]
    if not missing:
        return []
    return [_finding(u, "P-README-WHY-NOT", f"README lacks {missing}; a reader cannot tell the problem it owns from the siblings it defers to", "add both sections, naming the sibling plugins with adjacent jobs", line=None, quote=", ".join(missing))]


def r_p_readme_install(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u) or not u.exists:
        return []
    has_heading = any(h.startswith("## Install") for _, h in _headings(u))
    has_cmd = f"plugin install {u.plugin}@" in u.text or re.search(rf"--plugin-dir\s+\S*{re.escape(u.plugin)}", u.text)
    if has_heading and has_cmd:
        return []
    return [_finding(u, "P-README-INSTALL", f"no `## Install` section with `/plugin install {u.plugin}@<marketplace>` (or a --plugin-dir line)", "add the install block", line=None, quote="## Install")]


def r_p_readme_prompts_block(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u) or not u.exists or not OPTIONS.get("readme_markers"):
        return []
    if RRT_START in u.text and RRT_END in u.text:
        return []
    return [_finding(u, "P-README-PROMPTS-BLOCK", "the rrt example-prompts-intro marker pair is missing, so `rrt docs inject` cannot keep the shared frame identical", f"add {RRT_START} … {RRT_END} around the Example Prompts heading", line=None, quote=RRT_START)]


def prompt_triples(u: Unit) -> tuple[int, list[str]]:
    """(labels found, problems) mirroring tools/prompt-index/build_prompt_index.py's line scan."""
    lines = u.lines
    in_section, i, labels, problems = False, 0, 0, []
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("## Example Prompts"):
            in_section = True
            i += 1
            continue
        if in_section and ln.startswith("## "):
            break
        if in_section and ln.startswith("##### "):
            labels += 1
            label = ln[6:].strip()
            j = i + 1
            while j < len(lines) and not lines[j].startswith("````") and not lines[j].startswith("##### ") and not lines[j].startswith("## "):
                j += 1
            if j >= len(lines) or not lines[j].startswith("````"):
                problems.append(f"{label!r} (line {i + 1}) has no ````prompt fence")
                i = j
                continue
            if not lines[j].startswith("````prompt"):
                problems.append(f"{label!r} (line {i + 1}) fence is not ````prompt")
            j += 1
            while j < len(lines) and not lines[j].startswith("````"):
                j += 1
            j += 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            i = j
            continue
        i += 1
    return labels, problems


def r_p_readme_prompt_triple(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u) or not u.exists or "## Example Prompts" not in u.text:
        return []
    labels, problems = prompt_triples(u)
    if labels == 0:
        return [_finding(u, "P-README-PROMPT-TRIPLE", "Example Prompts section has no `#####` prompt; the prompt index will fail on this README", "add at least one `#####` label + ````prompt fence + `>` note", line=_line_of(u, "## Example Prompts"), quote="## Example Prompts")]
    if not problems:
        return []
    return [_finding(u, "P-README-PROMPT-TRIPLE", "prompt block is not the label / ````prompt fence / `>` note triple the index scrapes: " + "; ".join(problems[:3]), "fix each block to the triple shape", line=_line_of(u, "## Example Prompts"), quote=problems[0][:120])]


def r_p_readme_verify(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u) or not u.exists:
        return []
    if any(re.match(r"^## (Verifying|Testing|Tests)\b", h) for _, h in _headings(u)):
        return []
    return [_finding(u, "P-README-VERIFY", "no `## Verifying …` or `## Testing` section: a contributor cannot tell how to prove a change to this plugin", "add the section with the commands that verify a change", line=None, quote="## Verifying")]


def _plugin_escape_vars(ctx: list[Unit], plugin: str) -> set[str]:
    out: set[str] = set()
    for v in ctx:
        if v.plugin == plugin and v.kind == "hookscript" and v.exists:
            out |= set(RE_ESCAPE_VAR.findall(v.text))
    return out


def r_p_readme_escape_hatch(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u) or not u.exists:
        return []
    names = _plugin_escape_vars(ctx, u.plugin)
    if not names or any(n in u.text for n in names):
        return []
    return [_finding(u, "P-README-ESCAPE-HATCH", f"the hook's escape hatch {sorted(names)[0]} is not documented in the README", "add an `## Escape hatch` section naming it", line=None, quote=sorted(names)[0])]


def r_p_readme_screenshot(u: Unit, ctx: list[Unit]) -> list[dict]:
    if not _readme(u) or not u.exists:
        return []
    viewers = [v for v in ctx if v.plugin == u.plugin and v.kind == "viewer"]
    if not viewers:
        return []
    for v in viewers:
        shot = v.path.name[:-len(".html")] + "-screenshot.jpg"
        if shot not in u.text:
            return [_finding(u, "P-README-SCREENSHOT", f"README never embeds {shot}; the report the plugin produces is invisible to a reader deciding whether to install it", "embed the screenshot with a runnable demo command", line=None, quote=shot)]
    return []


def r_p_changelog_unreleased(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "changelog":
        return []
    if u.exists and "## [Unreleased]" in u.text:
        return []
    return [_finding(u, "P-CHANGELOG-UNRELEASED", "CHANGELOG.md is missing or has no `## [Unreleased]` section; the release tooling slices nothing", "add a Keep-a-Changelog file with an Unreleased section", line=None, quote="## [Unreleased]")]


def r_p_skill_dir_has_file(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    out = []
    for d in sorted(p for p in (u.plugin_dir / "skills").glob("*") if p.is_dir()) if (u.plugin_dir / "skills").is_dir() else []:
        if not (d / "SKILL.md").is_file():
            out.append(_finding(u, "P-SKILL-DIR-HAS-FILE", f"skills/{d.name}/ has no SKILL.md; the runtime silently ignores the directory", "add SKILL.md or delete the directory", line=None, quote=f"skills/{d.name}"))
    return out


def r_p_ref_reachable(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind != "manifest":
        return []
    refs = sorted((u.plugin_dir / "references").glob("*.md")) if (u.plugin_dir / "references").is_dir() else []
    if not refs:
        return []
    hay = "\n".join(v.text for v in ctx if v.plugin == u.plugin and v.kind in {"skill", "agent", "command", "readme"})
    out = []
    for r in refs:
        if r.name not in hay:
            out.append(_finding(u, "P-REF-REACHABLE", f"references/{r.name} is named by no skill, agent, command or the README", "link it from the component that needs it, with when-to-read guidance", line=None, quote=f"references/{r.name}"))
    return out


# ---------------------------------------------------------------------------
# D rules: repo-level developer docs (only with --docs-root)
# ---------------------------------------------------------------------------

def _docs(u: Unit) -> Path | None:
    return u.extra.get("docs_root") if u.kind == "docs" else None


def _repo_file(u: Unit, rel_path: str) -> str | None:
    p = Path(rel_path)
    return _read(p) if p.is_file() else None


def r_d_docs_stub(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    if u.exists and "@include" in u.text and f"plugins/{u.plugin}/README.md" in u.text:
        return []
    return [_finding(u, "D-DOCS-STUB", f"{u.path.as_posix()} is missing or does not @include plugins/{u.plugin}/README.md; the docs site has no page for the plugin", "add the 5-line include stub", quote=u.path.as_posix())]


def _config(u: Unit) -> str | None:
    return _repo_file(u, str(_docs(u) / ".vitepress" / "config.mjs"))


def r_d_sidebar_entry(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    cfg = _config(u)
    if cfg is None:
        _skip("D-SIDEBAR-ENTRY", "docs/.vitepress/config.mjs not found")
        return []
    if f"'/plugins/{u.plugin}'" in cfg or f'"/plugins/{u.plugin}"' in cfg:
        return []
    return [_finding(u, "D-SIDEBAR-ENTRY", f"config.mjs has no sidebar link to /plugins/{u.plugin}", "add the entry to the Plugins sidebar group, alphabetically", quote=f"/plugins/{u.plugin}")]


def r_d_sidebar_refs(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    cfg = _config(u)
    if cfg is None:
        return []
    out = []
    refdir = _docs(u) / "plugins" / "references"
    for stub in sorted(refdir.glob("*.md")) if refdir.is_dir() else []:
        t = _read(stub) or ""
        if f"plugins/{u.plugin}/references/" not in t:
            continue
        if f"/plugins/references/{stub.stem}'" in cfg or f'/plugins/references/{stub.stem}"' in cfg:
            continue
        out.append(_finding(u, "D-SIDEBAR-REFS", f"docs stub {stub.as_posix()} exists but config.mjs never links /plugins/references/{stub.stem}", "nest it under the plugin's sidebar item", quote=stub.stem))
    return out


def r_d_grid_entry(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    grid = _repo_file(u, str(_docs(u) / ".vitepress" / "theme" / "components" / "PluginGrid.vue"))
    if grid is None:
        return []
    if re.search(rf"name:\s*['\"]{re.escape(u.plugin)}['\"]", grid):
        return []
    return [_finding(u, "D-GRID-ENTRY", "PluginGrid.vue (hand-kept) has no card for the plugin", "append {name, url, summary}", quote=u.plugin)]


def _count_prose_targets(docs_root: Path) -> list[str]:
    return [str(docs_root / "index.md"), str(docs_root / "plugins" / "index.md"), "CLAUDE.md"]


def r_d_count_prose(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    firsts = [v for v in ctx if v.kind == "docs"]
    if not firsts or firsts[0] is not u:
        return []  # repo-level fact: report once, on the first docs unit
    plugins_root = u.plugin_dir.parent
    count = len(list(plugins_root.glob("*/.claude-plugin/plugin.json")))
    out = []
    for f in _count_prose_targets(_docs(u)):
        t = _repo_file(u, f)
        if t is None:
            continue
        rx = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\s+plugins?\b", re.I)
        for line, ln in enumerate(t.splitlines(), start=1):
            # headline lines only: a heading, a tagline, or the Layout summary -- prose
            # like "five plugins register a hook" counts something else
            if not (ln.startswith("#") or ln.lstrip().startswith("tagline:") or "plugins:" in ln):
                continue
            m = rx.search(ln)
            if m and NUMBER_WORDS[m.group(1).lower()] != count:
                out.append(_finding(u, "D-COUNT-PROSE", f"{f}:{line} says {m.group(0)!r} but {count} plugins are on disk", "update the count word", line=line, quote=ln.strip()[:120]))
                break
    return out


def r_d_root_readme(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    t = _repo_file(u, "README.md")
    if t is None:
        return []
    if f"plugins/{u.plugin}/README.md" in t and t.count(f"`{u.plugin}`") >= 1:
        return []
    return [_finding(u, "D-ROOT-README", f"root README.md has no `## Plugins` bullet linking plugins/{u.plugin}/README.md (and naming `{u.plugin}` in the install list)", "add the bullet and the install-list name", quote=u.plugin)]


def r_d_claude_md_layout(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    t = _repo_file(u, "CLAUDE.md")
    if t is None:
        return []
    m = re.search(r"^## Layout\n(.*?)(?=^## |\Z)", t, re.M | re.S)
    section = m.group(1) if m else ""
    if f"`{u.plugin}`" in section:
        return []
    return [_finding(u, "D-CLAUDE-MD-LAYOUT", f"CLAUDE.md's `## Layout` list does not name `{u.plugin}`", "add it to the plugin list and bump the count", quote=u.plugin)]


def r_d_orch_tables(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    t = _repo_file(u, str(_docs(u) / "orchestration" / "README.md"))
    if t is None:
        return []
    if u.plugin in t:
        return []
    return [_finding(u, "D-ORCH-TABLES", "docs/orchestration/README.md never mentions the plugin, so its skills are neither classified as orchestrators nor as leaves", "add its orchestrators to the table and name its leaves", quote=u.plugin)]


def r_d_hazards_card(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    if not any(v.plugin == u.plugin and v.kind == "hooks" for v in ctx):
        return []
    t = _repo_file(u, str(_docs(u) / "orchestration" / "references" / "hazards.md"))
    if t is None or f"<code>{u.plugin}</code>" in t or f"`{u.plugin}`" in t:
        return []
    return [_finding(u, "D-HAZARDS-CARD", "the plugin registers a PreToolUse hook but hazards.md has no card for it; a reader cannot see what will fire on their repo", "add a hazard card: matcher, inert condition, escape hatch", quote=u.plugin)]


def r_d_catalog_valid(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    cat = _docs(u) / "catalog"
    if not cat.is_dir():
        return []
    ids = {p.name for p in (u.plugin_dir / "skills").glob("*") if p.is_dir()} | {p.stem for p in (u.plugin_dir / "agents").glob("*.md")} | {p.stem for p in (u.plugin_dir / "commands").glob("*.md")}
    out = []
    for recipe in sorted(cat.rglob("*.md")):
        t = _read(recipe) or ""
        for m in RE_CATALOG_BEAT.finditer(t):
            if m.group(1) == u.plugin and m.group(2) not in ids:
                out.append(_finding(u, "D-CATALOG-VALID", f"{recipe.as_posix()} names {u.plugin}:{m.group(2)}, which is not a skill, agent or command of the plugin", "fix the beat id", quote=f"{u.plugin}:{m.group(2)}"))
    return out


def r_d_generated_fresh(u: Unit, ctx: list[Unit]) -> list[dict]:
    if _docs(u) is None:
        return []
    out = []
    idx = _repo_file(u, str(_docs(u) / "prompt-index.md"))
    if idx is not None and f"## {u.plugin}\n" not in idx + "\n":
        out.append(_finding(u, "D-GENERATED-FRESH", "docs/prompt-index.md has no section for the plugin; regenerate it", "run tools/prompt-index/build_prompt_index.py", quote=f"## {u.plugin}"))
    surf = _repo_file(u, str(_docs(u) / ".vitepress" / "data" / "surface.json"))
    mf = next((v for v in ctx if v.plugin == u.plugin and v.kind == "manifest"), None)
    version = (_manifest(mf) or {}).get("version") if mf else None
    if surf is not None:
        try:
            entry = next((p for p in json.loads(surf).get("plugins", []) if p.get("name") == u.plugin), None)
        except Exception:  # noqa: BLE001
            entry = None
        if entry is None or (version and entry.get("version") != version):
            out.append(_finding(u, "D-GENERATED-FRESH", "docs/.vitepress/data/surface.json is missing the plugin or carries a stale version; regenerate it", "run tools/surface-index/build_surface_index.py", quote=f"surface.json {u.plugin}"))
    return out


RULES = {
    "M-FM-PARSE": r_fm_parse,
    "M-DESC-LEN": r_desc_len,
    "M-DESC-XML": r_desc_xml,
    "M-DESC-PERSON": r_desc_person,
    "M-DESC-VAGUE": r_desc_vague,
    "M-DESC-WHENONLY": r_desc_whenonly,
    "M-NAME-FORMAT": r_name_format,
    "M-BODY-LINES": r_body_lines,
    "M-REF-TOC": r_ref_toc,
    "M-REF-DEPTH": r_ref_depth,
    "M-REF-UNWIRED": r_ref_unwired,
    "M-LINK-BROKEN": r_link_broken,
    "M-DUP-CONTENT": r_dup_content,
    "M-SKILL-VOICE": r_skill_voice,
    "M-AGENT-VOICE": r_agent_voice,
    "M-AGENT-MODEL": r_agent_model,
    "M-AGENT-TOOLS-SHAPE": r_agent_tools_shape,
    "M-AGENT-TOOLS-VERBS": r_agent_tools_verbs,
    "M-VERSION-FIELD": r_version_field,
    "M-CMD-ARGHINT": r_cmd_arghint,
    "M-CMD-DESC-LEN": r_cmd_desc_len,
    "M-TIME-SENSITIVE": r_time_sensitive,
    "M-WIN-PATHS": r_win_paths,
    "M-BASH-WILDCARD": r_bash_wildcard,
    "M-SECRETS": r_secrets,
    "H-JSON-PARSE": r_h_json_parse,
    "H-TYPE-COMMAND": r_h_type_command,
    "H-CMD-PLUGIN-ROOT": r_h_cmd_plugin_root,
    "H-SCRIPT-EXISTS": r_h_script_exists,
    "H-TIMEOUT": r_h_timeout,
    "H-MATCHER-KNOWN": r_h_matcher_known,
    "H-MATCHER-MULTIEDIT": r_h_matcher_multiedit,
    "H-INERT-STATED": r_h_inert_stated,
    "H-DENY-SHAPE": r_h_deny_shape,
    "H-EXIT-2": r_h_exit_2,
    "H-ESCAPE-HATCH": r_h_escape_hatch,
    "H-FAIL-CLOSED": r_h_fail_closed,
    "H-MULTI-PATH": r_h_multi_path,
    "H-TEST-EXISTS": r_h_test_exists,
    "S-PY-COMPILE": r_s_py_compile,
    "S-JS-SYNTAX": r_s_js_syntax,
    "S-SHEBANG": r_s_shebang,
    "S-DOCSTRING-USAGE": r_s_docstring_usage,
    "S-ARGPARSE": r_s_argparse,
    "S-SILENT-REGEX": r_s_silent_regex,
    "S-EXCEPT-SWALLOW": r_s_except_swallow,
    "S-SHELL-TRUE": r_s_shell_true,
    "S-REFERENCED": r_s_referenced,
    "A-R1-VERDICT": r_a_r1,
    "A-R4-LEGEND": r_a_r4,
    "A-S1-HEIGHT": r_a_s1,
    "A-S2-HEAD": r_a_s2,
    "A-C1-SCREENSHOT": r_a_c1,
    "A-C2-DEMO-DATA": r_a_c2,
    "A-S3-INNERHTML": r_a_s3_innerhtml,
    "A-S4-FAIL-VISIBLE": r_a_s4_fail_visible,
    "A-NO-CDN": r_a_no_cdn,
    "A-TOKENS-PRESENT": r_a_tokens_present,
    "A-BUILDER-EXISTS": r_a_builder_exists,
    "A-C4-ALT": r_a_c4_alt,
    "P-MANIFEST-PARSE": r_p_manifest_parse,
    "P-MANIFEST-NAME-DIR": r_p_manifest_name_dir,
    "P-MANIFEST-SEMVER": r_p_manifest_semver,
    "P-AUTHOR-PRESENT": r_p_author_present,
    "P-MARKETPLACE-MEMBER": r_p_marketplace_member,
    "P-MANIFEST-KEYWORDS": r_p_manifest_keywords,
    "P-MANIFEST-LICENSE": r_p_manifest_license,
    "P-README-H1": r_p_readme_h1,
    "P-README-THESIS": r_p_readme_thesis,
    "P-README-WHY-NOT": r_p_readme_why_not,
    "P-README-INSTALL": r_p_readme_install,
    "P-README-PROMPTS-BLOCK": r_p_readme_prompts_block,
    "P-README-PROMPT-TRIPLE": r_p_readme_prompt_triple,
    "P-README-VERIFY": r_p_readme_verify,
    "P-README-ESCAPE-HATCH": r_p_readme_escape_hatch,
    "P-README-SCREENSHOT": r_p_readme_screenshot,
    "P-CHANGELOG-UNRELEASED": r_p_changelog_unreleased,
    "P-SKILL-DIR-HAS-FILE": r_p_skill_dir_has_file,
    "P-REF-REACHABLE": r_p_ref_reachable,
    "D-DOCS-STUB": r_d_docs_stub,
    "D-SIDEBAR-ENTRY": r_d_sidebar_entry,
    "D-SIDEBAR-REFS": r_d_sidebar_refs,
    "D-GRID-ENTRY": r_d_grid_entry,
    "D-COUNT-PROSE": r_d_count_prose,
    "D-ROOT-README": r_d_root_readme,
    "D-CLAUDE-MD-LAYOUT": r_d_claude_md_layout,
    "D-ORCH-TABLES": r_d_orch_tables,
    "D-HAZARDS-CARD": r_d_hazards_card,
    "D-CATALOG-VALID": r_d_catalog_valid,
    "D-GENERATED-FRESH": r_d_generated_fresh,
}
assert set(RULES) == set(META), "RULES and META drifted"
KINDS = ("skill", "agent", "command", "reference", "doc", "workflow", "hooks", "hookscript", "script", "viewer", "manifest", "readme", "changelog", "docs")


def lint(plugin_dirs: list[Path]) -> dict:
    SKIPPED.clear()
    units = discover(plugin_dirs)
    findings: list[dict] = []
    for u in units:
        for rid, fn in RULES.items():
            findings.extend(fn(u, units))
    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f["rule_id"]] = by_rule.get(f["rule_id"], 0) + 1
    return {
        "units": {k: sum(1 for u in units if u.kind == k) for k in KINDS},
        "files_scanned": len(units),
        "by_rule": dict(sorted(by_rule.items())),
        "skipped": list(SKIPPED),
        "findings": findings,
    }


def rubric_hash(rubric: Path | None = None) -> str | None:
    r = rubric or RUBRIC
    if not r.is_file():
        return None
    return hashlib.sha256(r.read_bytes()).hexdigest()


def rubric_ids(rubric: Path | None = None) -> tuple[list[str], list[str]]:
    """(mechanical ids, judgement ids) scraped from the rubric's tables."""
    r = rubric or RUBRIC
    text = r.read_text(encoding="utf-8") if r.is_file() else ""
    ids = re.findall(r"^\| `([A-Z]+-[A-Z0-9-]+)` \|", text, re.M)
    mech = [i for i in ids if i.split("-", 1)[0] in FAMILIES]
    judge = [i for i in ids if i not in mech]
    return mech, judge


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def configure(*, marketplace: Path | None, readme_markers: bool | None, viewer_checker: Path | None, docs_root: Path | None) -> None:
    """Fill OPTIONS from resolved flags. readme_markers=None means 'on when .rrt.toml exists'."""
    OPTIONS["marketplace"] = marketplace if marketplace and Path(marketplace).is_file() else None
    OPTIONS["readme_markers"] = readme_markers if readme_markers is not None else Path(".rrt.toml").is_file()
    OPTIONS["viewer_checker"] = viewer_checker
    OPTIONS["docs_root"] = docs_root if docs_root and Path(docs_root).is_dir() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mechanical nacharbeit lint (rubric M/H/S/A/P/D rules).")
    ap.add_argument("plugin_dirs", nargs="+", type=Path)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--out", type=Path, help="write JSON here atomically (tmp + rename)")
    ap.add_argument("--rubric", type=Path, default=RUBRIC)
    ap.add_argument("--marketplace", type=Path, default=Path(".claude-plugin/marketplace.json"), help="marketplace.json to check membership against (skipped when absent)")
    ap.add_argument("--readme-markers", dest="readme_markers", action="store_true", default=None, help="require the rrt example-prompts marker pair")
    ap.add_argument("--no-readme-markers", dest="readme_markers", action="store_false")
    ap.add_argument("--viewer-checker", type=Path, default=HERE / "check_viewer_conformance.py")
    ap.add_argument("--docs-root", type=Path, default=None, help="docs site root for the D-* rules (default: off)")
    a = ap.parse_args(argv)
    for d in a.plugin_dirs:
        if not d.is_dir():
            print(f"ERROR: not a directory: {d}", file=sys.stderr)
            return 2
    configure(marketplace=a.marketplace, readme_markers=a.readme_markers, viewer_checker=a.viewer_checker, docs_root=a.docs_root)
    result = lint(a.plugin_dirs)
    result["rubricHash"] = rubric_hash(a.rubric)
    text = json.dumps(result, indent=2) + "\n"
    if a.out:
        write_atomic(a.out, text)
        print(f"wrote {a.out}: {len(result['findings'])} finding(s) over {result['files_scanned']} files", file=sys.stderr)
    if a.format == "json" and not a.out:
        print(text, end="")
    elif a.format == "text":
        print(f"{result['files_scanned']} files: " + ", ".join(f"{k}={v}" for k, v in result["units"].items() if v))
        for rid, n in result["by_rule"].items():
            print(f"  {n:4d}  {rid}")
        for f in result["findings"]:
            loc = f"{f['file']}" + (f":{f['line']}" if f["line"] else "")
            print(f"- [{f['severity']}] {f['rule_id']}  {loc}\n    {f['claim']}")
        for s in result["skipped"]:
            print(f"  SKIPPED {s['rule_id']}: {s['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
