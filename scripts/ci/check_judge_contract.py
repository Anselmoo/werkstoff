#!/usr/bin/env python3
"""Fail when a vendored copy of the judge verdict contract drifts from its canonical source.

The contract (verdict@2, docs/plugin-authoring/references/judge-contract.md) has three
canonical files under ``tools/judge-contract/``, each vendored byte for byte:

    verdict.inline.js   the block between ``// judge-contract:start verdict@2`` and
                        ``// judge-contract:end``, pasted into a Workflow script
                        (workflows have no imports, so a copy is the only way in)
    judge_contract.py   copied into a plugin's ``scripts/`` for script-side decide()
    judge-contract.md   copied into a plugin's ``references/`` and cited by a SKILL

Rules, over ``plugins/*/workflows/*.js`` and the vendored copies:

    JC-UNTERMINATED      a start marker with no end after it, or an end with no start
    JC-MULTIPLE          more than one start marker in one file
    JC-DRIFT             a block that is not byte-identical to the canonical block
                         (indentation, CRLF, a different ``verdict@N`` -- all drift)
    JC-REQUIRED          a workflow on REQUIRED_WORKFLOWS carries no block: a judge
                         workflow cannot drop out of the contract by deleting its marker
    JC-UNVENDORED-USE    a workflow names decideVerdict / spotCheck /
                         JUDGE_VERDICT_SCHEMA but carries no block -- a hand-written
                         look-alike, or a paste that lost its markers
    JC-SHADOW            outside the vendored block, with strings, comments, regex bodies
                         and template text masked, a use of decideVerdict, spotCheck or
                         JUDGE_VERDICT_SCHEMA that is not a plain use of the block's own
                         binding. The marker and the bytes stay intact while the call
                         resolves to a look-alike, so the rule is stated on every occurrence
                         rather than on a list of rebinding forms:
                           - decideVerdict / spotCheck: every occurrence must be a CALL (the
                             next non-space character is "("), or an object-literal key
                             (``{ spotCheck: spotCheck(...) }``, a name directly after "{" or ","
                             and before ":" inside braces). A property of another object
                             (``obj.spotCheck(...)``, preceded by "." but not "...") is not the
                             binding and is skipped. A bare name -- a parameter, a destructuring
                             target, a for-of target, a catch binding, an assignment target, a
                             shorthand, an alias, an equality test -- is not a call and fails,
                             as does any name directly after function / class / const / let / var.
                           - JUDGE_VERDICT_SCHEMA: every occurrence must be a plain READ: the next
                             significant character is one of , ) } ] ; : or end of file, or the
                             line ends and the next line does not continue the expression. It
                             also fails after a declaration keyword, or inside a parameter list
                             (a "(...)" followed by "=>", or by "{" unless the word before the
                             "(" is if / while / for / switch / with / await in STATEMENT
                             position) or a destructuring pattern (a "{...}" or "[...]" followed
                             by "=", of or in). Those words are legal method names, so
                             ``{ if(JUDGE_VERDICT_SCHEMA) { ... } }`` and
                             ``class A { for(JUDGE_VERDICT_SCHEMA) { ... } }`` declare a method
                             whose parameter is the schema. The word is a statement head only
                             when the character before it is not "," "." or "*", no get / set /
                             static / async precedes it, and its innermost enclosing bracket is
                             absent (top level) or a "{" that is a block: the text before that
                             "{" is classified, and it is a class body or object literal when it
                             follows ``class ...``, "=", "(", ",", "[", ":" (other than
                             ``case x:`` / ``default:``), an operator, or one of return / typeof /
                             in / of / new / yield / await / throw / void / delete / case /
                             extends / instanceof / default / export. Anything else (")", "=>",
                             ";", "{", "}", else / try / finally / do / static, a bare name) is a
                             block. A labelled block (``lbl: { if (x) { ... } }``) reads as an
                             object literal and fails closed.
    JC-ESCAPE            outside the vendored block, a ``\\u`` left in the masked text. Strings,
                         comments, regex bodies and template text are blanked, so a backslash-u
                         that survives is an identifier escape (``const \\u0064ecideVerdict``,
                         ``function g(spot\\u{43}heck)``) that rebinds a contract name without
                         the name ever appearing. Not allowed in a judge workflow; a ``\\u``
                         inside a string, comment, regex or template is fine.
                         NOT covered by JC-SHADOW / JC-ESCAPE: a rebinding through eval / with /
                         globalThis, mutating the schema through a call argument
                         (``Object.assign(JUDGE_VERDICT_SCHEMA, x)``) or through an alias taken by
                         a plain read, and an optional call (``spotCheck?.()``, which fails closed
                         here). A schema read inside a call whose ")" is followed by a "{" on any
                         later line (Allman style) is read as a parameter list and fails closed.
    JC-PY-DRIFT          a vendored judge_contract.py differs from the canonical
    JC-MD-DRIFT          a vendored references/judge-contract.md differs from the canonical

Every copy on VENDORED_PY and VENDORED_MD must exist: an absent one exits 2, never SKIP,
because a copy that is not there cannot be compared and an unmeasured run is not a pass.
A ``may_be_absent`` flag stays on VENDORED_PY for a copy that is being vendored; it prints
SKIP on every run and is never counted as a pass of that rule. No entry uses it today.

Usage:
    python3 scripts/ci/check_judge_contract.py [--root DIR]
    python3 scripts/ci/check_judge_contract.py --selftest

Exit 0 every copy matches; 1 a finding; 2 the check could not run (a canonical file
missing or malformed, no workflows found, a REQUIRED or non-optional file missing, an
unreadable file) -- an unmeasured run is never a pass. STDLIB ONLY. Python >= 3.11.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

MIN_PYTHON = (3, 11)
REPO_ROOT = Path(__file__).resolve().parents[2]
START = "// judge-contract:start verdict@2"
START_PREFIX = "// judge-contract:start"
END = "// judge-contract:end"
CANON_JS = "tools/judge-contract/verdict.inline.js"
CANON_PY = "tools/judge-contract/judge_contract.py"
CANON_MD = "tools/judge-contract/judge-contract.md"
WORKFLOW_GLOB = "plugins/*/workflows/*.js"
# Workflows that judge items and therefore MUST carry the block. Add, never remove
# without removing the judge too.
REQUIRED_WORKFLOWS = (
    "plugins/passung/workflows/canonize.js",
    "plugins/passung/workflows/verify.js",
)
# (path, may_be_absent). Any other judge_contract.py under plugins/*/scripts/ is
# found by glob and held to the same rule. May_be_absent is False for every entry: the
# befund copy landed, and a copy that can vanish unreported is not a gate.
VENDORED_PY = (("plugins/befund/scripts/lib/judge_contract.py", False),)
# Required references/ copies. Absence exits 2; a difference is JC-MD-DRIFT. Any other
# references/judge-contract.md is found by MD_GLOB and held to the same byte rule (the
# glob also reaches the required ones; the existence check is what VENDORED_MD adds).
VENDORED_MD = (
    "plugins/befund/references/judge-contract.md",
    "plugins/passung/references/judge-contract.md",
)
PY_GLOB = "plugins/*/scripts/**/judge_contract.py"
MD_GLOB = "plugins/*/references/judge-contract.md"
USES = re.compile(r"\b(?:decideVerdict|spotCheck|JUDGE_VERDICT_SCHEMA)\b")
# The three names the block defines. A rebinding of one outside the block shadows it.
CONTRACT_NAMES = ("decideVerdict", "spotCheck", "JUDGE_VERDICT_SCHEMA")


class CannotRun(Exception):
    pass


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    message: str


def read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CannotRun(f"cannot read {path}: {exc}") from exc


def markers(data: bytes) -> tuple[list[int], list[int], list[bytes]]:
    """Line indexes of start and end markers (matched on the stripped line), and the lines."""
    lines = data.splitlines(keepends=True)
    starts, ends = [], []
    for i, raw in enumerate(lines):
        s = raw.decode("utf-8", errors="replace").strip()
        if s.startswith(START_PREFIX):
            starts.append(i)
        elif s == END:
            ends.append(i)
    return starts, ends, lines


def canonical_block(root: Path) -> bytes:
    path = root / CANON_JS
    if not path.is_file():
        raise CannotRun(f"canonical block {CANON_JS} not found under {root}")
    starts, ends, lines = markers(read_bytes(path))
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        raise CannotRun(f"{CANON_JS} must hold exactly one {START!r} ... {END!r} block")
    if lines[starts[0]].rstrip(b"\r\n") != START.encode():
        raise CannotRun(f"{CANON_JS}'s start marker is not exactly {START!r}")
    return b"".join(lines[starts[0]: ends[0] + 1])


def first_diff_line(a: bytes, b: bytes) -> int:
    la, lb = a.splitlines(keepends=True), b.splitlines(keepends=True)
    for i, (x, y) in enumerate(zip(la, lb, strict=False)):
        if x != y:
            return i + 1
    return min(len(la), len(lb)) + 1


_NAME_RE = re.compile(r"(?<![\w$])(?:decideVerdict|spotCheck|JUDGE_VERDICT_SCHEMA)(?![\w$])")
_SCHEMA = "JUDGE_VERDICT_SCHEMA"
# A declaration keyword directly before the name makes it a binding, call-shaped or not.
_DECL_BEFORE = re.compile(r"(?:\b(?:class|const|let|var)\s+|\bfunction\s*\*?\s*)$")
# "(...) {" after one of these is a statement head, not a parameter list -- but only in
# statement position: as a method name (``{ if(x) {} }``) it is a parameter list.
_CONTROL_HEADS = frozenset({"if", "while", "for", "switch", "with", "await"})
# A "{" after one of these opens an object literal / class body, not a block.
_VALUE_WORDS = frozenset({"return", "typeof", "in", "of", "new", "yield", "await", "throw", "void", "delete",
                          "case", "extends", "instanceof", "default", "export"})
_CLASS_HEAD = re.compile(r"\bclass\b[^;{}]*$")
_CASE_LABEL = re.compile(r"(?:\bcase\b[^:;{}]*|\bdefault)\s*:$")
_MODIFIER_BEFORE = re.compile(r"(?<![\w$])(?:get|set|static|async)\s+$")
# A next line starting with one of these continues the expression the name ends.
_CONTINUES = re.compile(r"[=.(\[+\-*/%&|^<>?]|(?:in|of|instanceof)(?![\w$])")
_PAIRS = {")": "(", "]": "[", "}": "{"}


def _next_sig(text: str, i: int) -> int:
    """Index of the first non-whitespace character at or after ``i``; ``len(text)`` if none."""
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    return i


def _spans(text: str) -> list[tuple[int, int]]:
    """(open, close) index pairs of every bracket group; an unclosed one runs to the end."""
    stack: list[int] = []
    out: list[tuple[int, int]] = []
    for i, c in enumerate(text):
        if c in "([{":
            stack.append(i)
        elif c in _PAIRS and stack and text[stack[-1]] == _PAIRS[c]:
            out.append((stack.pop(), i))
    out += [(o, len(text)) for o in stack]
    return out


def _opens_member_body(before: str) -> bool:
    """Does a "{" preceded by ``before`` open a class body / object literal (not a block)?

    Unclassifiable text fails closed: a "{" is a block only when the text before it
    says so.
    """
    before = before.rstrip()
    if not before:
        return False
    if _CLASS_HEAD.search(before[-400:]):
        return True
    last = before[-1]
    if before.endswith("=>") or last in ")};{":
        return False
    if last == ":":
        return not _CASE_LABEL.search(before[-400:])
    if last.isalnum() or last in "_$":
        m = re.search(r"([\w$]+)$", before)
        return bool(m) and m.group(1) in _VALUE_WORDS
    return True


def _statement_position(text: str, spans: list[tuple[int, int]], kw: int) -> bool:
    """Is the word at ``kw`` a statement head rather than a shorthand-method name?"""
    if text[:kw].rstrip()[-1:] in (",", ".", "*") or _MODIFIER_BEFORE.search(text[max(0, kw - 20):kw]):
        return False
    inner = [sp for sp in spans if sp[0] < kw < sp[1]]
    if not inner:
        return True
    o = min(inner, key=lambda sp: sp[1] - sp[0])[0]
    return text[o] == "{" and not _opens_member_body(text[:o])


def _binding_group(text: str, spans: list[tuple[int, int]], open_i: int, close_i: int) -> str | None:
    """Why the bracket group is a binding position (parameters / pattern), or None."""
    rest = text[_next_sig(text, close_i + 1):]
    if text[open_i] == "(":
        if rest.startswith("=>"):
            return "an arrow parameter list"
        if rest.startswith("{"):
            base = max(0, open_i - 40)
            m = re.search(r"([\w$]+)\s*$", text[base:open_i])
            if not m or m.group(1) not in _CONTROL_HEADS or not _statement_position(text, spans, base + m.start(1)):
                return "a function, method or catch parameter list"
        return None
    if re.match(r"=(?![=>])", rest):
        return "a destructuring assignment or declaration pattern"
    if re.match(r"(?:of|in)(?![\w$])", rest):
        return "a for-of / for-in binding pattern"
    return None


def _is_object_key(text: str, spans: list[tuple[int, int]], start: int, nxt: int) -> bool:
    """``{ name: value }`` / ``, name: value`` directly inside braces: a property name, no reference."""
    if text[nxt:nxt + 1] != ":" or text[:start].rstrip()[-1:] not in ("{", ","):
        return False
    inner = [sp for sp in spans if sp[0] < start < sp[1]]
    return bool(inner) and text[min(inner, key=lambda sp: sp[1] - sp[0])[0]] == "{"


def _violation(text: str, spans: list[tuple[int, int]], name: str, start: int, end: int) -> str | None:
    """Why this occurrence of ``name`` is not a plain use of the block's binding, or None."""
    before = text[:start].rstrip()
    if before.endswith(".") and not before.endswith("..."):
        return None  # a property of some other object, not the binding
    if _DECL_BEFORE.search(text[max(0, start - 60):start]):
        return "declared"
    nxt = _next_sig(text, end)
    ch = text[nxt] if nxt < len(text) else ""
    if name != _SCHEMA:
        if ch == "(" or _is_object_key(text, spans, start, nxt):
            return None
        return "used as something other than a call"
    plain = ch == "" or ch in ",)}];:"
    if not plain and "\n" in text[end:nxt]:
        plain = not _CONTINUES.match(text, nxt)
    if not plain:
        return "used as something other than a plain read"
    for open_i, close_i in sorted(spans, key=lambda s: s[1] - s[0]):
        if open_i < start < close_i:
            why = _binding_group(text, spans, open_i, close_i)
            if why:
                return f"read inside {why}"
    return None


def shadow_findings(rel: str, data: bytes, block_lines: tuple[int, int]) -> list[Finding]:
    """JC-SHADOW: occurrences of the contract's names outside lines ``block_lines`` (0-based, inclusive)."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        from check_workflow_models import ScanError, mask
    except ImportError as exc:
        raise CannotRun(f"cannot import mask() from scripts/ci/check_workflow_models.py: {exc}") from exc
    try:
        masked = mask(data.decode("utf-8", errors="replace"))
    except ScanError as exc:
        raise CannotRun(f"{rel} could not be tokenized, so JC-SHADOW was not measured: {exc}") from exc
    rows = masked.split("\n")
    a, b = block_lines
    for i in range(a, min(b, len(rows) - 1) + 1):
        rows[i] = ""
    text = "\n".join(rows)
    spans = _spans(text)
    hits: set[tuple[int, str, str]] = set()
    for m in _NAME_RE.finditer(text):
        why = _violation(text, spans, m.group(0), m.start(), m.end())
        if why:
            hits.add((text.count("\n", 0, m.start()) + 1, m.group(0), why))
    out = [Finding("JC-SHADOW", rel, f"line {line}: {name} is {why} outside the vendored block")
           for line, name, why in sorted(hits)]
    # Strings, comments, regex bodies and template text are blank, so a backslash-u
    # left in the text is an identifier escape: it can spell a contract name
    # without the name appearing, so it is refused wherever it sits.
    escapes = sorted({text.count("\n", 0, m.start()) + 1 for m in re.finditer(r"\\u", text)})
    out += [Finding("JC-ESCAPE", rel, f"line {line}: identifier escapes are not allowed in a judge workflow")
            for line in escapes]
    return out


def check_workflow(rel: str, data: bytes, canon: bytes, required: bool) -> list[Finding]:
    starts, ends, lines = markers(data)
    out = []
    if len(starts) > 1:
        out.append(Finding("JC-MULTIPLE", rel, f"{len(starts)} start markers; vendor the block once"))
    if starts and not any(e > starts[0] for e in ends):
        out.append(Finding("JC-UNTERMINATED", rel, f"start marker on line {starts[0] + 1} has no {END!r} after it"))
    if ends and (not starts or ends[0] < starts[0]):
        out.append(Finding("JC-UNTERMINATED", rel, f"{END!r} on line {ends[0] + 1} has no start marker before it"))
    if out:
        return out
    if not starts:
        if required:
            out.append(Finding("JC-REQUIRED", rel, "a judge workflow on REQUIRED_WORKFLOWS carries no judge-contract block"))
        elif USES.search(data.decode("utf-8", errors="replace")):
            out.append(Finding("JC-UNVENDORED-USE", rel,
                               "names decideVerdict/spotCheck/JUDGE_VERDICT_SCHEMA without the vendored block"))
        return out
    end = next(e for e in ends if e > starts[0])
    block = b"".join(lines[starts[0]: end + 1])
    if block != canon:
        n = starts[0] + first_diff_line(block, canon)
        out.append(Finding("JC-DRIFT", rel, f"block differs from {CANON_JS} (first difference at line {n}); re-vendor it verbatim"))
    out += shadow_findings(rel, data, (starts[0], end))
    return out


def check(root: Path) -> tuple[list[Finding], list[str]]:
    canon = canonical_block(root)
    findings: list[Finding] = []
    skips: list[str] = []
    workflows = sorted(root.glob(WORKFLOW_GLOB))
    if not workflows:
        raise CannotRun(f"no {WORKFLOW_GLOB} found under {root}; nothing was measured")
    for req in REQUIRED_WORKFLOWS:
        if not (root / req).is_file():
            raise CannotRun(f"REQUIRED workflow {req} does not exist; update REQUIRED_WORKFLOWS deliberately if it moved")
    for wf in workflows:
        rel = wf.relative_to(root).as_posix()
        findings += check_workflow(rel, read_bytes(wf), canon, rel in REQUIRED_WORKFLOWS)

    canon_py_path = root / CANON_PY
    canon_md_path = root / CANON_MD
    for p in (canon_py_path, canon_md_path):
        if not p.is_file():
            raise CannotRun(f"canonical file {p.relative_to(root).as_posix()} not found")
    canon_py, canon_md = read_bytes(canon_py_path), read_bytes(canon_md_path)

    py_copies = {p.relative_to(root).as_posix() for p in root.glob(PY_GLOB)}
    for rel, may_be_absent in VENDORED_PY:
        if rel in py_copies:
            continue
        if may_be_absent:
            skips.append(f"SKIP JC-PY-DRIFT {rel}: not vendored yet (listed may_be_absent); this rule did not run for it")
        else:
            raise CannotRun(f"vendored copy {rel} does not exist")
    for rel in sorted(py_copies):
        if read_bytes(root / rel) != canon_py:
            findings.append(Finding("JC-PY-DRIFT", rel, f"differs from {CANON_PY}; copy it again, never edit the copy"))
    for rel in VENDORED_MD:
        if not (root / rel).is_file():
            raise CannotRun(f"vendored copy {rel} does not exist; copy {CANON_MD} there")
    md_copies = {p.relative_to(root).as_posix() for p in root.glob(MD_GLOB)}
    for rel in sorted(md_copies):
        if read_bytes(root / rel) != canon_md:
            findings.append(Finding("JC-MD-DRIFT", rel, f"differs from {CANON_MD}; copy it again, never edit the copy"))
    return findings, skips


# --- selftest -----------------------------------------------------------------

def _tree(src: Path, dst: Path, canon_block: str, files: dict[str, str | None]) -> None:
    for rel in (CANON_JS, CANON_PY, CANON_MD):
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, dst / rel)
    good_wf = f"phase('x')\n{canon_block}const v = decideVerdict(null, R, {{ item: 'a' }})\nreturn spotCheck([v])\n"
    base: dict[str, str | None] = {req: good_wf for req in REQUIRED_WORKFLOWS}
    base["plugins/other/workflows/plain.js"] = "phase('x')\nreturn 1\n"
    for rel_py, _optional in VENDORED_PY:
        base[rel_py] = (src / CANON_PY).read_text(encoding="utf-8")
    for rel_md in VENDORED_MD:
        base[rel_md] = (src / CANON_MD).read_text(encoding="utf-8")
    base.update(files)
    for rel, text in base.items():
        if text is None:
            (dst / rel).unlink(missing_ok=True)
            continue
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))


def selftest() -> int:
    try:
        block = canonical_block(REPO_ROOT).decode("utf-8")
        canon_py = (REPO_ROOT / CANON_PY).read_text(encoding="utf-8")
        canon_md = (REPO_ROOT / CANON_MD).read_text(encoding="utf-8")
    except (CannotRun, OSError) as exc:
        print(f"ERROR: selftest needs the canonical files: {exc}", file=sys.stderr)
        return 2
    req0, req1 = REQUIRED_WORKFLOWS
    wf = f"phase('x')\n{block}return 1\n"
    drifted = block.replace("outcome = 'fail'", "outcome = 'pass'", 1)
    lines = block.splitlines(keepends=True)
    no_end = "".join(lines[:-1])
    other = "plugins/other/workflows/judge.js"
    # (name, files overriding the clean tree (None deletes), expected rule ids, expected exit)
    cases: list[tuple[str, dict, set[str], int]] = [
        ("clean tree", {}, set(), 0),
        ("an optional block also vendored cleanly", {other: wf}, set(), 0),
        ("one changed byte in the block", {req0: f"phase('x')\n{drifted}return 1\n"}, {"JC-DRIFT"}, 1),
        ("the block indented", {req0: "phase('x')\n" + "".join("  " + ln for ln in lines) + "return 1\n"}, {"JC-DRIFT"}, 1),
        ("the block with CRLF line ends", {req0: "phase('x')\n" + block.replace("\n", "\r\n") + "return 1\n"}, {"JC-DRIFT"}, 1),
        # A copy still on the previous contract is drift: verdict@2 is a superset, but a
        # verdict@1 block cannot read an undecidable criterion, so it must be re-vendored.
        ("a copy still on verdict@1", {req0: wf.replace(START, START_PREFIX + " verdict@1")}, {"JC-DRIFT"}, 1),
        ("start marker without end", {req0: f"phase('x')\n{no_end}return 1\n"}, {"JC-UNTERMINATED"}, 1),
        ("end marker without start", {other: f"phase('x')\n{END}\nreturn 1\n"}, {"JC-UNTERMINATED"}, 1),
        ("two blocks", {req0: f"phase('x')\n{block}{block}return 1\n"}, {"JC-MULTIPLE"}, 1),
        ("a required workflow without the block", {req1: "phase('x')\nreturn 1\n"}, {"JC-REQUIRED"}, 1),
        ("a hand-written decideVerdict", {other: "function decideVerdict(r) { return r }\nreturn decideVerdict(1)\n"},
         {"JC-UNVENDORED-USE"}, 1),
        ("a drifted python copy", {VENDORED_PY[0][0]: canon_py + "# edited\n"}, {"JC-PY-DRIFT"}, 1),
        ("a second, drifted python copy", {"plugins/other/scripts/judge_contract.py": canon_py.replace("0.7", "0.6", 1)},
         {"JC-PY-DRIFT"}, 1),
        ("a drifted markdown copy", {"plugins/other/references/judge-contract.md": canon_md + "\nedited\n"}, {"JC-MD-DRIFT"}, 1),
        ("an identical markdown copy", {"plugins/other/references/judge-contract.md": canon_md}, set(), 0),
    ]
    # JC-SHADOW: one planted rebinding per form, appended after the clean block.
    shadows = (
        ("function declaration", "function decideVerdict(r) { return r }\n"),
        ("generator function declaration", "function* spotCheck(v) { yield v }\n"),
        ("const declaration", "const spotCheck = (v) => v\n"),
        ("let declaration", "let JUDGE_VERDICT_SCHEMA = {}\n"),
        ("var declaration", "var decideVerdict = null\n"),
        ("uninitialised let declaration", "let spotCheck\n"),
        ("loop binding", "for (const decideVerdict of [1]) { f(decideVerdict) }\n"),
        ("class declaration", "class spotCheck {}\n"),
        ("destructuring declaration", "const { decideVerdict } = require_it\n"),
        ("array destructuring declaration", "const [spotCheck] = fns\n"),
        ("plain reassignment", "spotCheck = () => []\n"),
        ("compound reassignment", "JUDGE_VERDICT_SCHEMA ||= {}\n"),
        ("arrow parameter", "const f = decideVerdict => 1\n"),
        ("arrow parameter list", "const f = (a, spotCheck) => 1\n"),
        ("function parameter", "function g(x, JUDGE_VERDICT_SCHEMA) { return x }\n"),
        ("catch binding", "try { f() } catch (decideVerdict) { g() }\n"),
        ("template expression rebinding", "const t = `${(() => { var spotCheck = 1; return 1 })()}`\n"),
        # (a) destructuring assignment (no declaration keyword, so the old forms missed it)
        ("array destructuring assignment", ";[spotCheck] = [() => []]\n"),
        ("object destructuring assignment", ";({ decideVerdict } = evil)\n"),
        ("destructuring assignment of the schema", ";({ JUDGE_VERDICT_SCHEMA } = evil)\n"),
        ("renamed destructuring assignment", ";({ a: JUDGE_VERDICT_SCHEMA } = evil)\n"),
        # (b) destructuring declaration with defaults
        ("destructuring declaration with a default", "const { x = 1, decideVerdict } = evil\n"),
        ("destructuring declaration, schema last", "const { a = f(), JUDGE_VERDICT_SCHEMA } = evil\n"),
        # (c) for-of / for-in rebinding
        ("for-of rebinding", "for (decideVerdict of [() => 1]) { g() }\n"),
        ("for-in rebinding", "for (spotCheck in o) { g() }\n"),
        ("for-of schema rebinding", "for (JUDGE_VERDICT_SCHEMA of [{}]) { g() }\n"),
        ("for-of destructuring rebinding", "for ({ JUDGE_VERDICT_SCHEMA } of [o]) { g() }\n"),
        # (d) method / class-method parameters
        ("object method parameter", "const o = { run(decideVerdict) { return 1 } }\n"),
        ("class method parameter", "class K { run(spotCheck) { return 1 } }\n"),
        ("method parameter, schema", "const o = { run(a, JUDGE_VERDICT_SCHEMA) { return 1 } }\n"),
        ("async arrow parameter", "const f = async (spotCheck) => 1\n"),
        # (e) arrow parameters after a call default
        ("arrow parameter after a call default", "const f = (a = g(), decideVerdict) => 1\n"),
        ("arrow parameter after a call default, schema", "const f = (a = g(), JUDGE_VERDICT_SCHEMA) => 1\n"),
        ("rest parameter", "const f = (...spotCheck) => 1\n"),
        ("destructured parameter", "const f = ({ decideVerdict }) => 1\n"),
        # other non-call uses
        ("an alias", "const f = decideVerdict\n"),
        ("passed as a value", "run(spotCheck)\n"),
        ("compared", "const same = decideVerdict === spotCheck\n"),
        ("schema compound assignment", "JUDGE_VERDICT_SCHEMA += 1\n"),
        ("schema member assignment", "JUDGE_VERDICT_SCHEMA.required = []\n"),
        ("schema element assignment", "JUDGE_VERDICT_SCHEMA['required'] = []\n"),
        ("schema assignment on the next line", "JUDGE_VERDICT_SCHEMA\n  = {}\n"),
        ("schema declared without a value", "let JUDGE_VERDICT_SCHEMA\n"),
        # control-head words are legal method names: not a statement head in member position
        ("object-literal method named if", "const o = { if(JUDGE_VERDICT_SCHEMA) { return 1 } }\n"),
        ("class method named for", "class A { for(JUDGE_VERDICT_SCHEMA) { return 1 } }\n"),
        ("class method named while, after another method", "class B { m() {} while(JUDGE_VERDICT_SCHEMA) { } }\n"),
        ("static class method named switch", "class C { static switch(JUDGE_VERDICT_SCHEMA) { } }\n"),
        ("async object method named with", "const o = { async with(JUDGE_VERDICT_SCHEMA) { } }\n"),
        ("generator object method named if", "const o = { *if(JUDGE_VERDICT_SCHEMA) { } }\n"),
        ("object method named for, after a property", "const o = { a: 1, for(JUDGE_VERDICT_SCHEMA) { } }\n"),
        ("method named if on an exported object", "export default { if(JUDGE_VERDICT_SCHEMA) { } }\n"),
        ("method named if on a class with a call in its head", "class D extends mixin(B) { if(JUDGE_VERDICT_SCHEMA) { } }\n"),
        ("method named if on a returned object", "function r() { return { if(JUDGE_VERDICT_SCHEMA) { } } }\n"),
    )
    for form, snippet in shadows:
        cases.append((f"shadowed by a {form}", {req0: f"phase('x')\n{block}{snippet}return 1\n"}, {"JC-SHADOW"}, 1))
    # JC-ESCAPE: an identifier spelled with a unicode escape rebinds a contract name unseen.
    escapes = (
        ("decideVerdict declaration", "const \\u0064ecideVerdict = (r) => r\n"),
        ("spotCheck var", "var spot\\u0043heck = null\n"),
        ("schema let", "let JUDGE_VERDICT_\\u0053CHEMA = {}\n"),
        ("braced parameter", "function g(spot\\u{43}heck) { return 1 }\n"),
    )
    for form, snippet in escapes:
        cases.append((f"an identifier escape: {form}", {req0: f"phase('x')\n{block}{snippet}return 1\n"}, {"JC-ESCAPE"}, 1))
    cases += [
        ("a shadow placed above the block", {req0: f"function spotCheck() {{}}\n{block}return 1\n"}, {"JC-SHADOW"}, 1),
        ("a shadow in a non-required file that also carries the block", {other: f"{block}const spotCheck = 1\n"},
         {"JC-SHADOW"}, 1),
        ("the names only used, compared, keyed and mentioned",
         {req0: f"phase('x')\n{block}"
                "const v = decideVerdict(null, R, { item: 'a' })\n"
                "const same = other.decideVerdict === other.decideVerdict && other.spotCheck == other.spotCheck\n"
                "const out = { spotCheck: spotCheck([v], 3), schema: JUDGE_VERDICT_SCHEMA }\n"
                "const spotChecks = [spotCheck([v])]\n"
                "obj.spotCheck = 1\n"
                "// function decideVerdict() {} const spotCheck = 1\n"
                "const s = 'const spotCheck = 1; function decideVerdict() {}'\n"
                "const t = `let JUDGE_VERDICT_SCHEMA = ${spotCheck([v])}`\n"
                "return spotChecks.map((w) => decideVerdict(w, R, { item: w.item }))\n"}, set(), 0),
        ("clean uses: calls, schema value, a call on another object, a key, a multi-line schema value",
         {req0: f"phase('x')\n{block}"
                "const v = decideVerdict(null, R, { item: 'a' })\n"
                "const o = { decideVerdict: decideVerdict(v, R, { item: 'b' }), spotCheck: spotCheck([v]) }\n"
                "const r = await agent('p', { schema: JUDGE_VERDICT_SCHEMA })\n"
                "const r2 = await agent('p', {\n  label: 'l',\n  schema: JUDGE_VERDICT_SCHEMA\n})\n"
                "const w = other.decideVerdict(1) + this.spotCheck(2) + a?.spotCheck(3)\n"
                "for (const x of [JUDGE_VERDICT_SCHEMA]) { f(x) }\n"
                "if (spotCheck([v]).length) { g() }\n"
                "const ks = Object.keys(JUDGE_VERDICT_SCHEMA)\n"
                "const t = flag ? JUDGE_VERDICT_SCHEMA : null\n"
                "return o\n"}, set(), 0),
        ("a unicode escape only inside a string, comment, regex and template",
         {req0: f"phase('x')\n{block}"
                "const s = 'caf\\u00e9 \\u0064ecideVerdict'\n"
                "// \\u0064ecideVerdict\n"
                "const re = /\\u0041+/u\n"
                "const t = `\\u0041 ${s}`\n"
                "return decideVerdict(null, R, { item: 'a' })\n"}, set(), 0),
        ("control statements in statement position, nested in blocks and bodies",
         {req0: f"phase('x')\n{block}"
                "function f(x) {\n  if (JUDGE_VERDICT_SCHEMA) { g() }\n  else if (x) { h() }\n"
                "  for (const a of [JUDGE_VERDICT_SCHEMA]) { g(a) }\n"
                "  while (JUDGE_VERDICT_SCHEMA) { break }\n"
                "  switch (JUDGE_VERDICT_SCHEMA) {\n    case 1: { if (JUDGE_VERDICT_SCHEMA) { g() } break }\n"
                "    default: { for (const b of [JUDGE_VERDICT_SCHEMA]) { g(b) } }\n  }\n}\n"
                "const k = () => { if (JUDGE_VERDICT_SCHEMA) { return 1 } return 2 }\n"
                "class K { m() { if (JUDGE_VERDICT_SCHEMA) { return 1 } } static { if (JUDGE_VERDICT_SCHEMA) { g() } } }\n"
                "const o = { m() { for (const c of [JUDGE_VERDICT_SCHEMA]) { g(c) } } }\n"
                "try { g() } finally { if (JUDGE_VERDICT_SCHEMA) { g() } }\n"
                "{ if (JUDGE_VERDICT_SCHEMA) { g() } }\n"
                "if (JUDGE_VERDICT_SCHEMA) {\n  g()\n}\n"
                "return 1\n"}, set(), 0),
        ("a required markdown copy drifted", {VENDORED_MD[0]: canon_md + "\nedited\n"}, {"JC-MD-DRIFT"}, 1),
        ("the other required markdown copy drifted", {VENDORED_MD[1]: canon_md.replace("verdict@2", "verdict@1", 1)},
         {"JC-MD-DRIFT"}, 1),
        ("both required markdown copies identical", {VENDORED_MD[0]: canon_md, VENDORED_MD[1]: canon_md}, set(), 0),
    ]
    failed = 0
    for name, files, expected, want_exit in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(REPO_ROOT, root, block, {**{req: wf for req in REQUIRED_WORKFLOWS}, **files})
            try:
                findings, skips = check(root)
                got_exit = 1 if findings else 0
                got = {f.rule for f in findings}
            except CannotRun:
                got_exit, got, skips = 2, set(), []
            ok = got == expected and got_exit == want_exit
            ok = ok and not skips
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}: expected {sorted(expected)} exit {want_exit}, got {sorted(got)} exit {got_exit}")
    # Each cannot-run case names the branch it expects, by message: with REQUIRED
    # non-empty, "no workflows" also means "required missing", and a bare exit-2
    # check could not tell the two branches apart.
    cannot_run = (
        ("no workflows at all", {**{req: None for req in REQUIRED_WORKFLOWS}, "plugins/other/workflows/plain.js": None},
         "nothing was measured"),
        ("a required workflow deleted", {req0: None}, "REQUIRED workflow"),
        ("the canonical markdown deleted", {CANON_MD: None}, "canonical file"),
        ("the required python copy absent", {VENDORED_PY[0][0]: None}, f"vendored copy {VENDORED_PY[0][0]}"),
        ("a required markdown copy absent", {VENDORED_MD[0]: None}, f"vendored copy {VENDORED_MD[0]}"),
        ("the other required markdown copy absent", {VENDORED_MD[1]: None}, f"vendored copy {VENDORED_MD[1]}"),
    )
    for name, files, says in cannot_run:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(REPO_ROOT, root, block, {**{req: wf for req in REQUIRED_WORKFLOWS}, **files})
            try:
                check(root)
                ok, msg = False, "no error"
            except CannotRun as exc:
                ok, msg = says in str(exc), str(exc)
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}: expected exit 2 saying {says!r}, got {msg[:70]!r}")
    print(f"check_judge_contract selftest: {len(cases) + len(cannot_run)} cases, {failed} failed")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"ERROR: needs Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(description=(__doc__ or "judge-contract sync check").splitlines()[0])
    p.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this checkout)")
    p.add_argument("--selftest", action="store_true", help="run the planted-defect cases")
    a = p.parse_args(argv)
    if a.selftest:
        return selftest()
    try:
        findings, skips = check(a.root.resolve())
    except CannotRun as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for s in skips:
        print(s)
    for f in findings:
        print(f"FAIL {f.rule} {f.path}: {f.message}")
    print(f"judge-contract: {len(findings)} finding(s), {len(skips)} skipped")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
