#!/usr/bin/env python3
"""Classify each of a plugin's MUST-rules as enforced in code, stated in prose, or absent.

WHY THIS EXISTS
---------------
The andon pilot spent hours running `claude --print` and scoring transcripts by
regex to answer "are this plugin's stop rules real guards?". That instrument is
expensive (3-4 min per data point), noisy, and was contaminated three separate
ways. A static read answers the same question in about a second, exactly, and
deterministically — because whether a rule is enforced in code is a property of
the source, not of a sampled run.

WHAT COUNTS AS ENFORCEMENT
--------------------------
Counting `throw` is NOT enough, and this is the whole subtlety. Both andon and
confab throw. Every one of andon's four throws
(`workflows/andon-cycle-scan.js:24-36`) validates a *workflow argument* —
repoPath traversal, stageFiles entries. Useful hygiene; not a stop rule.

Confab enforces the SAME rule andon only writes down. Its reopen limit is
control flow (rebuilt from confab-cycle-scan.js into plugins/confab/scripts/lib/ledger.py
during plugin rebuild):

    plugins/confab/scripts/lib/ledger.py:90   record["status"] = "escalated" if record["reopenCount"] > max_reopens else "open"
    plugins/confab/scripts/lib/ledger.py:56   raise CycleBoundExceededError(...)

Andon's identical rule ("the same wire reopens three times -> escalate") greps
to zero hits across its workflows. So the discriminating question is:

    does a conditional TEST THE RULE'S OWN STATE and CHANGE WHAT HAPPENS?

Three classifications per rule:

  code    a conditional whose test mentions the rule's state, whose body
          diverts control (throw/raise/return/break/continue/exit), OR a loop
          bounded by the rule's state
  prose   the rule appears only in markdown — a sentence the model must
          re-read and choose to honor
  absent  neither

Argument validation is reported separately as `arg_guards`, never credited to a
rule. A plugin can have many and still enforce nothing.

LIMITS — read these before trusting a verdict
---------------------------------------------
This is a lexical analyser, not a semantic one. It can be fooled by a
conditional that mentions a rule's state without enforcing it, and it cannot
see enforcement expressed through a helper whose name shares no term with the
rule. Treat `code` as "there is a control-flow guard worth reading at this
line", and read the cited line. The cited file:line is the point, not the label.

Usage:
    audit_enforcement.py --rules rules/andon.json <plugin-dir> [<plugin-dir> ...]
    audit_enforcement.py --rules rules/andon.json --format json <dir>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

CODE_EXT = {".js", ".mjs", ".cjs", ".ts", ".py", ".sh", ".bash"}
DOC_EXT = {".md"}

# Vendored/shared files that are byte-identical across plugins and implement
# none of any plugin's own rules. Without this the auditor "finds" enforcement
# in the symbol indexer: it reported andon's wire-proof rule as CODE at
# scripts/build_symbol_index.py:501, which is the RRT-managed copy every plugin
# carries. A shared file cannot be evidence about the plugin that contains it.
VENDORED = {"build_symbol_index.py", "test_build_symbol_index.py", "migrate-query-symbol.js"}

# A conditional or loop header. Captures the test expression.
COND = re.compile(r"^\s*(?:\}\s*)?(?:if|else if|elif|while|for)\s*\(?(?P<test>[^{:]{0,200})", re.MULTILINE)
# A loop header at all...
LOOP = re.compile(r"^\s*(?:\}\s*)?(for|while)\b")
# ...but only a BOUNDED loop is a guard. `for (const f of stageFiles)` merely
# iterates; counting it credited andon with two guards that were really an
# enclosing loop around an argument throw and a for..of whose window happened
# to contain a `return`. A bound needs a comparison against a limit.
BOUNDED = re.compile(r"[<>]=?|\b(range|slice)\s*\(")
# Control-flow divergence inside a guard body.
DIVERT = re.compile(r"\b(throw|raise|return|break|continue|process\.exit|sys\.exit|exit\s+\d)\b")
# An argument-validation throw: tests the SHAPE of an input rather than a state.
# NOTE the split: `\b` asserts a word boundary, so `\b!==\b` can never match —
# there is no word character adjacent to `!`. Keeping the punctuation operators
# outside the \b group is load-bearing; with them inside, `if (x !== null)`
# escaped the arg-guard filter and got credited as rule enforcement.
ARG_SHAPE = re.compile(r"\b(typeof|Array\.isArray|Number\.isFinite|instanceof|isinstance)\b|!==|===|!=|\bis None\b|\bis not None\b")
# Names that indicate the value came from workflow args rather than loop state.
ARG_SOURCE = re.compile(r"\bARGS\b|\bargs\.|\bArgs\b")


@dataclass
class Hit:
    file: str
    line: int
    text: str


@dataclass
class RuleVerdict:
    rule_id: str
    section: str
    verdict: str  # code | prose | absent
    code_sites: list[Hit] = field(default_factory=list)
    prose_sites: list[Hit] = field(default_factory=list)


def iter_files(root: Path, exts: set[str]) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not (p.is_file() and p.suffix in exts):
            continue
        if "test-fixtures" in p.parts or "node_modules" in p.parts or p.name in VENDORED:
            continue
        out.append(p)
    return out


def find_code_guards(root: Path, state_terms: list[str], exclude: set[tuple[str, int]]) -> list[Hit]:
    """Conditionals/loops that test the rule's state AND divert control.

    `exclude` carries the argument-validation sites. A site can look like both —
    `if (!wireClaim && !Array.isArray(stageFiles)) throw` tests an ARG whose
    name merely contains the rule's term "wire". Crediting that as enforcement
    of the andon rule is precisely the error this subtraction prevents, and it
    is the error the first version of this tool made.
    """
    terms = [t.lower() for t in state_terms]
    hits: list[Hit] = []
    for p in iter_files(root, CODE_EXT):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            m = COND.match(line)
            if not m:
                continue
            test = m.group("test").lower()
            if not any(t in test for t in terms):
                continue
            # Divergence may be on this line (one-liners, `for` bounds) or in the
            # next few lines of the block.
            if (str(p), i + 1) in exclude:
                continue
            window = "\n".join(lines[i:i + 4])
            is_loop = LOOP.match(line) is not None
            if is_loop and not BOUNDED.search(test):
                continue  # plain iteration, not a guard
            if is_loop or DIVERT.search(window):
                hits.append(Hit(str(p), i + 1, line.strip()[:160]))
    return hits


def find_arg_guards(root: Path) -> list[Hit]:
    """Throws that validate an input's shape — hygiene, never rule enforcement."""
    hits: list[Hit] = []
    for p in iter_files(root, CODE_EXT):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            m = COND.match(line)
            if not m:
                continue
            test = m.group("test")
            window = "\n".join(lines[i:i + 4])
            if DIVERT.search(window) and (ARG_SHAPE.search(test) or ARG_SOURCE.search(test)):
                hits.append(Hit(str(p), i + 1, line.strip()[:160]))
    return hits


def find_prose(root: Path, prose_terms: list[str]) -> list[Hit]:
    terms = [t.lower() for t in prose_terms]
    hits: list[Hit] = []
    for p in iter_files(root, DOC_EXT):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            low = line.lower()
            if any(t in low for t in terms):
                hits.append(Hit(str(p), i + 1, line.strip()[:160]))
    return hits


# An obligation the plugin places on the model, in its own instructions. Scoped
# to skills/ and agents/ — README and CHANGELOG describe the plugin to a human
# and are not instructions anything executes.
OBLIGATION = re.compile(
    r"\b(MUST NOT|MUST|NEVER|SHALL NOT|shall not|must not|must never|never |refuse|refuses|"
    r"do not |don't |may not |cannot |is forbidden|is prohibited|halt|stop )",
)


def profile(plugin_dir: Path) -> dict:
    """Generic enforcement profile — no rule inventory needed.

    Answers "how much of this plugin's own discipline is executable?" by
    counting the obligations it states against the control-flow guards it
    actually has. Comparable across plugins with entirely different rules,
    which a single plugin's rule inventory is not.
    """
    arg_hits = find_arg_guards(plugin_dir)
    arg_sites = {(h.file, h.line) for h in arg_hits}

    # Every control-flow guard, regardless of subject, minus argument validation.
    guards: list[Hit] = []
    code_lines = 0
    for p in iter_files(plugin_dir, CODE_EXT):
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        code_lines += len(lines)
        for i, line in enumerate(lines):
            if (str(p), i + 1) in arg_sites:
                continue
            m = COND.match(line)
            if not m:
                continue
            if LOOP.match(line) and not BOUNDED.search(m.group("test")):
                continue  # plain iteration, not a guard
            if DIVERT.search("\n".join(lines[i:i + 4])):
                guards.append(Hit(str(p), i + 1, line.strip()[:120]))

    obligations = 0
    doc_lines = 0
    for p in iter_files(plugin_dir, DOC_EXT):
        parts = p.parts
        if not ("skills" in parts or "agents" in parts):
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        doc_lines += len(lines)
        obligations += sum(1 for ln in lines if OBLIGATION.search(ln))

    return {
        "code_files": len(iter_files(plugin_dir, CODE_EXT)),
        "code_lines": code_lines,
        "instruction_lines": doc_lines,
        "obligations_stated": obligations,
        "control_flow_guards": len(guards),
        "arg_guards": len(arg_hits),
        "guards_per_obligation": round(len(guards) / obligations, 3) if obligations else None,
        "guard_sites": [f"{h.file}:{h.line}" for h in guards[:8]],
    }


def audit(plugin_dir: Path, rules: dict) -> tuple[list[RuleVerdict], list[Hit]]:
    # Argument validation is computed FIRST and subtracted, so a shape check on
    # an arg whose name shares a term with a rule can never be credited as
    # enforcement of that rule.
    arg_hits = find_arg_guards(plugin_dir)
    arg_sites = {(h.file, h.line) for h in arg_hits}
    verdicts: list[RuleVerdict] = []
    for r in rules["rules"]:
        code = find_code_guards(plugin_dir, r.get("state_terms", []), arg_sites)
        prose = find_prose(plugin_dir, r.get("prose_terms", []))
        v = "code" if code else ("prose" if prose else "absent")
        verdicts.append(RuleVerdict(r["id"], str(r.get("section", "")), v, code, prose[:3]))
    return verdicts, find_arg_guards(plugin_dir)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Classify a plugin's MUST-rules as code / prose / absent.")
    ap.add_argument("plugin_dirs", nargs="+", type=Path)
    ap.add_argument("--rules", type=Path,
                    help="Rule inventory (rules/<plugin>.json). Required unless --profile.")
    ap.add_argument("--profile", action="store_true",
                    help="Generic enforcement profile — obligations stated vs guards that "
                         "enforce them. Needs no rule inventory, so it is comparable across "
                         "plugins with entirely different rules.")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--require-code", action="store_true",
                    help="Exit 1 unless EVERY rule is code-enforced. This is gate 2: "
                         "it is what makes 'enforce in code' a gate rather than advice.")
    args = ap.parse_args(argv)

    if args.profile:
        rows = {}
        for d in args.plugin_dirs:
            if not d.is_dir():
                print(f"ERROR: not a directory: {d}", file=sys.stderr)
                return 2
            rows[str(d)] = profile(d)
        if args.format == "json":
            print(json.dumps(rows, indent=2))
        else:
            print(f"{'plugin':<34}{'code':>6}{'instr':>7}{'oblig':>7}{'GUARDS':>8}{'args':>6}{'g/o':>8}")
            print(f"{'':<34}{'lines':>6}{'lines':>7}{'stated':>7}{'':>8}{'':>6}{'':>8}")
            print("-" * 76)
            for d, r in rows.items():
                go = "—" if r["guards_per_obligation"] is None else f"{r['guards_per_obligation']:.3f}"
                print(f"{d:<34}{r['code_lines']:>6}{r['instruction_lines']:>7}"
                      f"{r['obligations_stated']:>7}{r['control_flow_guards']:>8}"
                      f"{r['arg_guards']:>6}{go:>8}")
            print("\nGUARDS = conditionals that test non-argument state and divert control")
            print("        (throw/return/break/exit). This is enforcement. `args` is input")
            print("        validation — necessary hygiene, but it enforces no rule.")
        return 0

    if not args.rules:
        print("ERROR: --rules is required unless --profile is given", file=sys.stderr)
        return 2
    rules = json.loads(args.rules.read_text())
    report: dict[str, dict] = {}
    worst_ok = True

    for d in args.plugin_dirs:
        if not d.is_dir():
            print(f"ERROR: not a directory: {d}", file=sys.stderr)
            return 2
        verdicts, argg = audit(d, rules)
        report[str(d)] = {
            "rules": [
                {"id": v.rule_id, "section": v.section, "verdict": v.verdict,
                 "code_sites": [f"{h.file}:{h.line}" for h in v.code_sites],
                 "prose_sites": [f"{h.file}:{h.line}" for h in v.prose_sites]}
                for v in verdicts
            ],
            "arg_guards": [f"{h.file}:{h.line}" for h in argg],
            "totals": {k: sum(1 for v in verdicts if v.verdict == k) for k in ("code", "prose", "absent")},
        }
        if any(v.verdict != "code" for v in verdicts):
            worst_ok = False

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        for d, r in report.items():
            print(f"\n══ {d}")
            for row in r["rules"]:
                mark = {"code": "CODE ", "prose": "prose", "absent": "  -  "}[row["verdict"]]
                where = row["code_sites"][0] if row["code_sites"] else (row["prose_sites"][0] if row["prose_sites"] else "")
                print(f"   [{mark}] {row['id']:32s} {where}")
            t = r["totals"]
            print(f"   totals: code={t['code']} prose={t['prose']} absent={t['absent']}"
                  f"  |  arg-validation guards (not rule enforcement): {len(r['arg_guards'])}")

    return 0 if (worst_ok or not args.require_code) else 1


if __name__ == "__main__":
    sys.exit(main())
