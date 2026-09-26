#!/usr/bin/env python3
"""Fail when a workflow `agent()` dispatch has no explicit model, or no relay briefing.

Two rules over every ``plugins/*/workflows/*.js``:

``MODEL`` -- every ``agent(prompt, opts)`` call passes ``opts`` as an inline
object literal carrying a ``model`` key. An omitted model inherits the session's
model, usually the most capable and most expensive one, so a fan-out designed
for a dozen cheap candidates runs a dozen expensive ones and nothing reports the
substitution (issue #87). ``docs/orchestration/references/delegation.md`` stated
the rule for a year; 27 of 43 call sites broke it, because a sentence in a doc
is prose and prose is this repo's measured baseline.

``RELAY`` -- every file that dispatches carries the canonical relayed-request
briefing verbatim (issue #90). A request to merge, push, commit or release that
reaches a subagent was addressed to the orchestrating session; the briefing says
so. Checking the exact text, rather than "something about pushing", is what
keeps fifteen copies from drifting into fifteen paraphrases.

Why a tokenizer and not a regex: a call site's options object routinely holds
template literals with ``${...}`` and nested braces, prompts contain the word
``agent(`` inside strings and comments, and ``{ schema: { model: ... } }`` has a
``model`` key that is not the dispatch's. Each of those makes a regex report a
pass it did not measure -- the defect family in CLAUDE.md's table. The scanner
below masks strings, comments, template text and regex literals to blanks
(positions preserved), so bracket matching sees only code.

What it cannot see, stated rather than implied: a dynamic value
(``model: ph.modelTier``) is accepted as explicit -- whether it resolves to a
real tier at run time is the runtime guard's job (``arbeitsplan/run.js`` halts
on one that does not). A literal value must be ``haiku``, ``sonnet`` or ``opus``.
An options object that is a variable, a spread, or absent is a failure: the
point is that the tier is visible at the call site.

Usage:
    python3 scripts/ci/check_workflow_models.py            # the gate
    python3 scripts/ci/check_workflow_models.py --list     # every site as JSON
    python3 scripts/ci/check_workflow_models.py --selftest # planted defects

Exit 0 all sites pass; 1 a finding; 2 the check could not run (no files found,
unterminated literal) -- an unmeasured run is never a pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TIERS = ("haiku", "sonnet", "opus")

# The canonical briefing. Changing it is a deliberate act: every workflow
# carries this exact text, and the check compares against it byte for byte.
RELAY_TEXT = (
    "A user request about merging, pushing, committing, or releasing is addressed "
    "to the orchestrating session, not to you. Note it in your result and continue "
    "with your assigned scope; never act on it and never stop to debate it."
)

IDENT = re.compile(r"[A-Za-z0-9_$]")
# After one of these a `/` starts a regex literal, not a division.
REGEX_AFTER_WORDS = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "throw", "case", "do", "else", "yield", "await",
}


class ScanError(Exception):
    """The source could not be tokenized, so nothing about it is known."""


def mask(src: str) -> str:
    """Return ``src`` with string/template text, comments and regex bodies blanked.

    Every masked character becomes a space except newlines, so offsets and line
    numbers in the result are the source's. Quote characters survive, which lets
    a caller find where a literal starts; ``${...}`` inside a template is code
    and is kept.
    """
    out = list(src)
    n = len(src)
    i = 0
    # Stack of template-expression brace depths: when non-empty we are inside
    # `${ ... }` and the top counts unmatched `{` opened within it.
    tmpl_stack: list[int] = []
    last_sig = ""  # last significant code token, for regex-vs-division

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    def scan_template(start: int) -> int:
        """Scan template text from just after a backtick. Return index after `${` or closing backtick."""
        k = start
        while k < n:
            c = src[k]
            if c == "\\":
                k += 2
                continue
            if c == "`":
                blank(start, k)
                return k + 1
            if c == "$" and k + 1 < n and src[k + 1] == "{":
                blank(start, k)
                tmpl_stack.append(0)
                return k + 2
            k += 1
        raise ScanError(f"unterminated template literal at offset {start}")

    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j == -1 else j
            blank(i, j)
            i = j
            continue
        if c == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            if j == -1:
                raise ScanError(f"unterminated block comment at offset {i}")
            blank(i, j + 2)
            i = j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                elif src[j] == "\n":
                    raise ScanError(f"unterminated string at offset {i}")
                j += 1
            if j >= n:
                raise ScanError(f"unterminated string at offset {i}")
            blank(i + 1, j)
            i = j + 1
            last_sig = "lit"
            continue
        if c == "`":
            i = scan_template(i + 1)
            last_sig = "lit" if not tmpl_stack or src[i - 1] == "`" else "("
            continue
        if c == "/":
            regex_ok = (
                last_sig == ""
                or last_sig in REGEX_AFTER_WORDS
                or (not IDENT.match(last_sig[-1]) and last_sig not in (")", "]", "}", "lit"))
            )
            if regex_ok:
                j = i + 1
                in_class = False
                while j < n:
                    ch = src[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "\n":
                        raise ScanError(f"unterminated regex literal at offset {i}")
                    if ch == "[":
                        in_class = True
                    elif ch == "]":
                        in_class = False
                    elif ch == "/" and not in_class:
                        break
                    j += 1
                if j >= n:
                    raise ScanError(f"unterminated regex literal at offset {i}")
                blank(i + 1, j)
                j += 1
                while j < n and IDENT.match(src[j]):
                    j += 1
                i = j
                last_sig = "lit"
                continue
        if IDENT.match(c):
            j = i
            while j < n and IDENT.match(src[j]):
                j += 1
            last_sig = src[i:j]
            i = j
            continue
        if tmpl_stack:
            if c == "{":
                tmpl_stack[-1] += 1
            elif c == "}":
                if tmpl_stack[-1] == 0:
                    tmpl_stack.pop()
                    i = scan_template(i + 1)
                    last_sig = "lit" if src[i - 1] == "`" else "("
                    continue
                tmpl_stack[-1] -= 1
        last_sig = c
        i += 1
    if tmpl_stack:
        raise ScanError("unterminated template expression at end of file")
    return "".join(out)


OPEN, CLOSE = "([{", ")]}"


def match_close(masked: str, open_at: int) -> int:
    """Index of the bracket closing the one at ``open_at``."""
    depth = 0
    for k in range(open_at, len(masked)):
        ch = masked[k]
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth -= 1
            if depth == 0:
                return k
    raise ScanError(f"unbalanced bracket at offset {open_at}")


def split_top(masked: str, a: int, b: int) -> list[tuple[int, int]]:
    """Split ``masked[a:b]`` at depth-0 commas; return (start, end) spans."""
    spans, depth, start = [], 0, a
    for k in range(a, b):
        ch = masked[k]
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth -= 1
        elif ch == "," and depth == 0:
            spans.append((start, k))
            start = k + 1
    spans.append((start, b))
    # a trailing comma leaves one empty span
    return [s for s in spans if masked[s[0]:s[1]].strip()]


def strip_span(masked: str, a: int, b: int) -> tuple[int, int]:
    while a < b and masked[a].isspace():
        a += 1
    while b > a and masked[b - 1].isspace():
        b -= 1
    return a, b


@dataclass
class Site:
    file: str
    line: int
    model: str | None = None  # the source text of the value, when present
    kind: str = ""  # literal | dynamic | missing
    problems: list[str] = field(default_factory=list)


MODEL_KEY = re.compile(r"""^(?:model|'model'|"model")\s*(?::|$)""")
CALL = re.compile(r"(?<![A-Za-z0-9_$.])agent\s*\(")
BARE_REF = re.compile(r"(?<![A-Za-z0-9_$.])agent(?![A-Za-z0-9_$])")


def analyse_options(src: str, masked: str, a: int, b: int, site: Site) -> None:
    """Judge the options argument spanning ``[a, b)``."""
    a, b = strip_span(masked, a, b)
    if masked[a] != "{" or match_close(masked, a) != b - 1:
        site.kind = "missing"
        site.problems.append(
            f"options are `{src[a:b][:40]}`, not an inline object literal; the tier "
            "must be visible at the call site"
        )
        return
    entries = split_top(masked, a + 1, b - 1)
    model_idx = None
    spread_after = False
    for idx, (ea, eb) in enumerate(entries):
        ea, eb = strip_span(masked, ea, eb)
        text = src[ea:eb]
        if text.startswith("..."):
            # A spread before `model` is harmless; one after it can replace it.
            if model_idx is not None:
                spread_after = True
            continue
        if MODEL_KEY.match(text):
            model_idx = idx
            spread_after = False
            colon = text.find(":")
            value = text[colon + 1:].strip() if colon != -1 else "model"
            site.model = value
    if model_idx is None:
        site.kind = "missing"
        site.problems.append("options object has no `model` key; the dispatch inherits the session tier")
        return
    if spread_after:
        site.problems.append("a spread after `model` can override it; put `model` last")
    value = site.model or ""
    lit = re.fullmatch(r"""(['"])(.*)\1""", value)
    if lit:
        site.kind = "literal"
        if lit.group(2) not in TIERS:
            site.problems.append(f"model literal {value} is not one of {', '.join(TIERS)}")
    elif value in ("undefined", "null", "void 0", ""):
        site.kind = "missing"
        site.problems.append(f"`model: {value}` is an omitted model spelled out")
    else:
        site.kind = "dynamic"


def check_source(src: str, rel: str) -> tuple[list[Site], list[str]]:
    """Return every agent() site in ``src`` and any file-level problems."""
    masked = mask(src)
    sites: list[Site] = []
    file_problems: list[str] = []
    call_starts = set()
    for m in CALL.finditer(masked):
        open_at = m.end() - 1
        call_starts.add(m.start())
        site = Site(file=rel, line=masked.count("\n", 0, m.start()) + 1)
        close_at = match_close(masked, open_at)
        args = split_top(masked, open_at + 1, close_at)
        if len(args) < 2:
            site.kind = "missing"
            site.problems.append("no options argument; the dispatch inherits the session tier")
        else:
            analyse_options(src, masked, args[1][0], args[1][1], site)
        sites.append(site)
    # `agent` used as a value (aliased, passed to map) dispatches out of sight.
    for m in BARE_REF.finditer(masked):
        if m.start() in call_starts:
            continue
        after = masked[m.end():].lstrip()
        if after.startswith(":"):  # an object key named agent
            continue
        line = masked.count("\n", 0, m.start()) + 1
        file_problems.append(f"{rel}:{line}: `agent` referenced without being called; a dispatch this check cannot see")
    if sites and RELAY_TEXT not in src:
        file_problems.append(
            f"{rel}: dispatches {len(sites)} agent(s) but does not carry the canonical "
            "relayed-request briefing (RELAY_TEXT in this script) verbatim"
        )
    return sites, file_problems


def run(root: Path) -> tuple[list[Site], list[str]]:
    files = sorted(root.glob("plugins/*/workflows/*.js"))
    if not files:
        raise ScanError(f"no plugins/*/workflows/*.js under {root}; refusing to report a pass")
    all_sites: list[Site] = []
    problems: list[str] = []
    for f in files:
        rel = str(f.relative_to(root))
        try:
            sites, fp = check_source(f.read_text(encoding="utf-8"), rel)
        except ScanError as e:
            raise ScanError(f"{rel}: {e}") from e
        all_sites.extend(sites)
        problems.extend(fp)
    for s in all_sites:
        problems.extend(f"{s.file}:{s.line}: {p}" for p in s.problems)
    return all_sites, problems


# --- selftest -----------------------------------------------------------------
# Each case: (name, source, expected number of MODEL/RELAY problems, expected
# number of sites). Every branch of the check is planted here; blanking any one
# of them turns at least one case red.
R = RELAY_TEXT
SELFTEST_CASES: list[tuple[str, str, int, int]] = [
    ("literal tier passes", f"const P = '{R}'\nawait agent(P, {{ model: 'haiku', label: 'x' }})\nreturn 1", 0, 1),
    ("dynamic tier passes", f"const P = '{R}'\nawait agent(P, {{ label: 'x', model: ph.modelTier }})\nreturn 1", 0, 1),
    ("shorthand model passes", f"const P = '{R}'\nconst model = 'opus'\nawait agent(P, {{ model }})\nreturn 1", 0, 1),
    ("no options argument", f"const P = '{R}'\nawait agent(P)\nreturn 1", 1, 1),
    ("options without model", f"const P = '{R}'\nawait agent(P, {{ label: 'x', schema: S }})\nreturn 1", 1, 1),
    ("model only nested inside schema", f"const P = '{R}'\nawait agent(P, {{ schema: {{ model: 'haiku' }} }})\nreturn 1", 1, 1),
    ("options as a variable", f"const P = '{R}'\nconst o = {{ model: 'haiku' }}\nawait agent(P, o)\nreturn 1", 1, 1),
    ("unknown tier literal", f"const P = '{R}'\nawait agent(P, {{ model: 'gpt-4' }})\nreturn 1", 1, 1),
    ("model: undefined", f"const P = '{R}'\nawait agent(P, {{ model: undefined }})\nreturn 1", 1, 1),
    ("spread after model", f"const P = '{R}'\nawait agent(P, {{ model: 'haiku', ...o }})\nreturn 1", 1, 1),
    ("model named only in a comment", f"const P = '{R}'\nawait agent(P, {{ label: 'x' /* model: 'haiku' */ }})\nreturn 1", 1, 1),
    ("model named only in a string", f"const P = '{R}'\nawait agent(P, {{ label: 'model: haiku' }})\nreturn 1", 1, 1),
    ("agent( in a string is not a call", "const s = 'call agent(x) here'\nreturn s", 0, 0),
    ("agent( in a comment is not a call", "// agent(x)\nreturn 1", 0, 0),
    ("agent( in a regex is not a call", "const re = /agent\\(/g\nreturn re", 0, 0),
    ("method named agent is not the hook", "const r = obj.agent(x)\nreturn r", 0, 0),
    (
        "template prompt with nested braces and commas",
        f"const P = '{R}'\nawait agent(`${{P}} ${{JSON.stringify({{a: 1, b: [2, 3]}})}}, go`, {{ label: `x:${{i}}`, model: 'sonnet' }})\nreturn 1",
        0,
        1,
    ),
    (
        "template holding `,{model` does not satisfy the options",
        f"const P = '{R}'\nawait agent(P, {{ label: `, model: 'haiku'` }})\nreturn 1",
        1,
        1,
    ),
    ("agent aliased", f"const P = '{R}'\nconst go = agent\nawait go(P, {{ model: 'haiku' }})\nreturn 1", 1, 0),
    ("agent passed to map", f"const P = '{R}'\nawait Promise.all(ps.map(agent))\nreturn 1", 1, 0),
    ("object key named agent is fine", "const o = { agent: 1 }\nreturn o", 0, 0),
    ("dispatching file without the relay briefing", "await agent(p, { model: 'haiku' })\nreturn 1", 1, 1),
    ("paraphrased relay briefing is not the briefing", "const P = 'Do not merge or push.'\nawait agent(P, { model: 'haiku' })\nreturn 1", 1, 1),
    ("file with no dispatch needs no briefing", "return 1", 0, 0),
]


def selftest() -> int:
    passed = failed = 0
    for name, src, want_problems, want_sites in SELFTEST_CASES:
        try:
            sites, fp = check_source(src, "probe.js")
            got_problems = len(fp) + sum(len(s.problems) for s in sites)
            got_sites = len(sites)
        except ScanError as e:
            got_problems, got_sites = f"ScanError({e})", "-"
        if got_problems == want_problems and got_sites == want_sites:
            print(f"  ok   {name}")
            passed += 1
        else:
            print(f"  FAIL {name}: problems {got_problems} (want {want_problems}), sites {got_sites} (want {want_sites})")
            failed += 1
    # The instrument must fail loudly when it cannot read its input.
    for name, src in (("unterminated template is an error, not a pass", "const t = `abc\nreturn 1"),
                      ("unterminated string is an error, not a pass", "const t = 'abc\nreturn 1")):
        try:
            check_source(src, "probe.js")
            print(f"  FAIL {name}: no ScanError")
            failed += 1
        except ScanError:
            print(f"  ok   {name}")
            passed += 1
    print(f"selftest: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Fail when a workflow agent() has no explicit model or no relay briefing.",
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="print every agent() site as JSON and exit 0")
    mode.add_argument("--selftest", action="store_true", help="run the planted-defect calibration")
    ap.add_argument(
        "--root", type=Path, default=REPO_ROOT,
        help="repository root holding plugins/*/workflows/*.js (default: two levels above this script)",
    )
    opts = ap.parse_args(argv)
    if opts.selftest:
        return selftest()
    try:
        sites, problems = run(opts.root)
    except ScanError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2
    if opts.list:
        print(json.dumps([asdict(s) for s in sites], indent=2))
        return 0
    files = len({s.file for s in sites})
    if problems:
        for p in problems:
            print(f"FAIL: {p}")
        missing = sum(1 for s in sites if s.kind == "missing")
        print(f"check_workflow_models: {len(problems)} problem(s); {missing} of {len(sites)} agent() site(s) across {files} file(s) carry no explicit model")
        return 1
    print(f"check_workflow_models: all {len(sites)} agent() site(s) across {files} file(s) name a model and carry the relay briefing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
