#!/usr/bin/env python3
"""Phase 0 of the prompt-quality review: every mechanically checkable rule.

Implements the `M-*` rows of docs/plugin-authoring/references/prompt-quality-rubric.md
against skills, agents, commands, references, and workflow scripts under one or more
plugin directories. No model in the loop. Model finders downstream are told these ids
are out of scope, so anything regex can decide must be decided here.

Every rule is one entry in RULES so test-lint-prompts.py can blank a rule and prove the
fixture goes red — a rule that cannot fail is not a rule (CLAUDE.md, "verify the
instrument before trusting its verdict").

Findings share the finder schema: {file, line, quote, rule_id, angle, severity, claim,
suggested_fix, fix_tier}. `fix_tier` is always "haiku": a mechanical finding has a
mechanical fix.

Output is written atomically (tmp + rename) so a crashed run never leaves a half-written
lint.json that a later stage reads as fresh.

Usage:
  lint_prompts.py plugins/*                         # text summary to stdout
  lint_prompts.py plugins/* --format json           # findings JSON to stdout
  lint_prompts.py plugins/* --out analysis/prompt-review/lint.json
Exit: 0 on a completed scan (findings are data, not failure); 2 on bad arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("pyyaml is required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

RUBRIC = Path("docs/plugin-authoring/references/prompt-quality-rubric.md")

# severity + angle per rule, mirrored from the rubric table. test-lint-prompts.py asserts
# that this dict and the rubric's M-* rows are the same set.
META: dict[str, tuple[str, str]] = {
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
}

KNOWN_TOOLS = {
    "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep", "Bash", "LS",
    "WebFetch", "WebSearch", "Agent", "Task", "TodoWrite", "Skill", "AskUserQuestion",
    "KillShell", "BashOutput", "NotebookRead", "SlashCommand", "Workflow",
}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
MODEL_ALIASES = {"inherit", "sonnet", "opus", "haiku", "fable"}

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
RE_PLUGIN_ROOT = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
RE_TOC_HEADING = re.compile(r"^#{1,3}\s*(contents|table of contents|in this (file|document|reference))\b", re.I | re.M)


@dataclass
class Unit:
    kind: str            # skill | agent | command | reference | doc | workflow
    plugin: str
    path: Path           # repo-relative
    text: str
    fm: dict | None = None
    fm_error: str | None = None
    body: str = ""
    body_line0: int = 1  # 1-based line number of the first body line
    lines: list[str] = field(default_factory=list)


def _finding(unit: Unit, rule: str, claim: str, fix: str, *, line: int | None = None, quote: str = "") -> dict:
    sev, angle = META[rule]
    q = (quote or "").strip()
    if not q and unit.fm and isinstance(unit.fm.get("description"), str):
        q = unit.fm["description"]
    q = q[:160]
    return {
        "file": str(unit.path), "line": line, "quote": q, "rule_id": rule, "angle": angle,
        "severity": sev, "claim": claim, "suggested_fix": fix, "fix_tier": "haiku",
    }


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


def discover(plugin_dirs: list[Path]) -> list[Unit]:
    units: list[Unit] = []
    for pd in plugin_dirs:
        plugin = pd.name
        def add(kind: str, p: Path) -> None:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError as e:  # unreadable = loud, never "nothing found"
                print(f"WARN cannot read {p}: {e}", file=sys.stderr)
                return
            u = Unit(kind=kind, plugin=plugin, path=p, text=text, lines=text.splitlines())
            if kind in {"skill", "agent", "command"}:
                parse_frontmatter(u)
            else:
                u.body = text
            units.append(u)
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
    return units


# ---------------------------------------------------------------------------
# rules: each takes (unit, ctx) and returns a list of findings. ctx = all units.
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
    plugin_dir = Path(*u.path.parts[:2]) if len(u.path.parts) >= 2 else u.path.parent
    if "${CLAUDE_PLUGIN_ROOT}" in t:
        p = plugin_dir / t.replace("${CLAUDE_PLUGIN_ROOT}/", "").replace("${CLAUDE_PLUGIN_ROOT}", "")
    elif "$" in t or "<" in t or "*" in t or t.startswith("/"):
        return None  # templated, or absolute on the user's machine: out of scope
    else:
        p = u.path.parent / t
    norm = Path(os.path.normpath(p))
    if plugin_dir not in norm.parents and norm != plugin_dir:
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
        rel = str(p.relative_to(u.path.parent))
        if p.name in u.text or rel in u.text:
            continue
        out.append(_finding(u, "M-REF-UNWIRED", f"references/{p.relative_to(refs_dir)} is never named in SKILL.md, so nothing tells the model when to load it",
                            "add a Resources bullet naming the file and when to read it", line=None, quote=rel))
    return out


def r_link_broken(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind == "workflow":
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
    if u.kind == "workflow" or not u.text.strip():
        return []
    h = hashlib.sha256(u.text.encode()).hexdigest()
    same = [v for v in ctx if v.kind != "workflow" and v.text == u.text]
    if len(same) < 2 or same[0] is not u:
        return []
    others = ", ".join(str(v.path) for v in same[1:])
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
    m = _first_match(u, RE_TIME)
    if not m:
        return []
    return [_finding(u, "M-TIME-SENSITIVE", "body contains a dated instruction that will silently become wrong", "state the current method; move legacy into an 'Old patterns' section", line=m[0], quote=m[1])]


def r_win_paths(u: Unit, ctx: list[Unit]) -> list[dict]:
    if u.kind == "workflow":
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
    m = _first_match(u, RE_SECRET, body_only=False)
    if not m:
        return []
    return [_finding(u, "M-SECRETS", "credential-shaped literal", "remove it; use a masked placeholder", line=m[0], quote=re.sub(r"(?<=.{4}).", "*", m[1].strip())[:80])]


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
}
assert set(RULES) == set(META), "RULES and META drifted"


def lint(plugin_dirs: list[Path]) -> dict:
    units = discover(plugin_dirs)
    findings: list[dict] = []
    for u in units:
        for rid, fn in RULES.items():
            findings.extend(fn(u, units))
    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f["rule_id"]] = by_rule.get(f["rule_id"], 0) + 1
    return {
        "units": {k: sum(1 for u in units if u.kind == k) for k in ("skill", "agent", "command", "reference", "doc", "workflow")},
        "files_scanned": len(units),
        "by_rule": dict(sorted(by_rule.items())),
        "findings": findings,
    }


def rubric_hash() -> str | None:
    if not RUBRIC.is_file():
        return None
    return hashlib.sha256(RUBRIC.read_bytes()).hexdigest()


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mechanical prompt-quality lint (rubric M-* rules).")
    ap.add_argument("plugin_dirs", nargs="+", type=Path)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--out", type=Path, help="write JSON here atomically (tmp + rename)")
    a = ap.parse_args(argv)
    for d in a.plugin_dirs:
        if not d.is_dir():
            print(f"ERROR: not a directory: {d}", file=sys.stderr)
            return 2
    result = lint(a.plugin_dirs)
    result["rubricHash"] = rubric_hash()
    text = json.dumps(result, indent=2) + "\n"
    if a.out:
        write_atomic(a.out, text)
        print(f"wrote {a.out}: {len(result['findings'])} finding(s) over {result['files_scanned']} files", file=sys.stderr)
    if a.format == "json" and not a.out:
        print(text, end="")
    elif a.format == "text":
        print(f"{result['files_scanned']} files: " + ", ".join(f"{k}={v}" for k, v in result["units"].items()))
        for rid, n in result["by_rule"].items():
            print(f"  {n:4d}  {rid}")
        for f in result["findings"]:
            loc = f"{f['file']}" + (f":{f['line']}" if f["line"] else "")
            print(f"- [{f['severity']}] {f['rule_id']}  {loc}\n    {f['claim']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
