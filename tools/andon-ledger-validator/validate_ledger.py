#!/usr/bin/env python3
"""Validate an andon ledger's persisted records against their own schema.

Motivation is empirical, not theoretical. Against the real ledger from
spectrafit-core (66 gap records, 35 evidence records, commit 55e2c4f^):

  * `blast radius`   — 0/66 in frontmatter, 65/66 in a body prose bullet, 1/66 absent
  * `verdict`        — 0/35 in frontmatter, 35/35 in a body prose bullet
  * `non-overridable`— 0/35 in frontmatter, 35/35 in a body prose bullet
  * `on constraint`  — 0/66 in frontmatter, 66/66 in a body prose bullet
  * `resource:`      — used in 35/35 evidence records, unused in 66/66 gap records
  * silent truncation— 22/66 descriptions and 12/66 titles severed mid-word

Every field that gates a downstream decision (the authorization ceiling, the
andon rule) exists only as free text inside a markdown bullet. That is worse
than a missing field: a missing field announces itself when something looks
for it, whereas prose looks present to a human reviewer and is invisible to
code. This validator makes both conditions loud.

Deliberately NOT a format change. The ledger stays human-readable markdown
with YAML-ish frontmatter; JSON would have prevented none of the defects above
(same overloaded string, same prose bullet, same truncation, just in braces).
The missing thing is validation, which is orthogonal to serialization.

Deliberately NOT a repair tool. It never fills in, infers, or normalizes a
missing gating value — inventing a value a human never supplied is the exact
failure this exists to catch. It reports; a human fixes.

Stdlib only, so it stays self-contained inside a plugin bundle.

Usage:
    validate_ledger.py <ledger-dir> [--mode read|write] [--format text|json]

Exit codes: 0 clean (or read-mode with only migration findings), 1 findings
that block, 2 the ledger directory is unusable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = "1.0"

# Ordered enum for the authorization ceiling (behavior contract §3 cond. 2).
BLAST_RADIUS = ("local+reversible", "hard-to-reverse", "shared-state-visible")
VERDICTS = ("green", "red", "amber", "unknown")

# Fields that gate a downstream decision, per record type. `body_label` is the
# markdown bullet the legacy writer actually emits, which is how a record ends
# up parseable-by-eye but not by code.
GATING = {
    "gap": [
        ("blast_radius", "Blast radius", BLAST_RADIUS),
        ("on_constraint", "On constraint", None),
    ],
    "evidence": [
        ("verdict", "Verdict", VERDICTS),
        ("non_overridable", "Non-overridable", None),
    ],
}

# One record must represent exactly one gap (behavior contract §9.3). A title
# that counts its own findings is the signature of a record holding several.
MULTI_GAP = re.compile(
    r"\b\d+\s+(contradiction|gap|issue|mismatch|error|drift|defect|problem|violation)s\b",
    re.IGNORECASE,
)
# A machine-written field that stops mid-word carries no terminal punctuation
# and no closing bracket — the writer hit a length cap and severed the claim.
TRUNCATED_MIN = 100


@dataclass
class Finding:
    record: str
    code: str
    severity: str  # "block" | "migrate" | "warn"
    detail: str


def parse_record(text: str) -> tuple[dict[str, str], str]:
    """Split a record into (frontmatter mapping, body).

    A deliberately small parser: these records are machine-written with a
    fixed `key: value` shape, and depending on PyYAML would cost the
    self-contained-bundle property for no gain.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    front: dict[str, str] = {}
    for line in parts[1].splitlines():
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$', line)
        if m:
            front[m.group(1).replace("-", "_").lower()] = m.group(2).strip().strip('"')
    return front, parts[2]


def body_value(body: str, label: str) -> str | None:
    """Read a gating value out of a markdown body bullet, e.g. `- Verdict: green`.

    Used ONLY to tell "in the wrong place" apart from "absent" — never to
    supply the value to a caller as if it were validly declared.
    """
    m = re.search(rf'^\s*[-*]\s*{re.escape(label)}\s*:\s*(.+?)\s*$', body, re.MULTILINE)
    if m:
        return m.group(1).rstrip(".")
    m = re.search(rf'{re.escape(label)}\s*:\s*([^.\n]+)', body, re.IGNORECASE)
    return m.group(1).strip() if m else None


def check_record(text: str, rel: str) -> list[Finding]:
    front, body = parse_record(text)
    out: list[Finding] = []
    rtype = front.get("type", "")
    if rtype not in GATING:
        return [Finding(rel, "unknown-type", "warn", f"type={rtype!r} has no schema")]

    for key, label, enum in GATING[rtype]:
        declared = front.get(key)
        if declared is not None and declared != "":
            if enum and declared not in enum:
                out.append(Finding(rel, f"{key}-invalid", "block",
                                   f"{key}={declared!r} is not one of {list(enum)}"))
            continue
        found = body_value(body, label)
        if found is None:
            # Nothing to gate on, anywhere. The authorization ceiling has no
            # input; the loop must not proceed on this record.
            out.append(Finding(rel, f"{key}-absent", "block",
                               f"required gating field {key!r} is absent from "
                               f"frontmatter and body — nothing may infer it"))
        else:
            # Present, but only a human can see it. Recoverable by moving it;
            # never by this tool guessing that the prose meant what it says.
            out.append(Finding(rel, f"{key}-in-prose", "migrate",
                               f"{key!r} exists only as body prose "
                               f"({label}: {found!r}); no code path can read it"))

    title, desc = front.get("title", ""), front.get("description", "")
    if rtype == "gap" and MULTI_GAP.search(title):
        out.append(Finding(rel, "multi-gap-record", "block",
                           f"title counts several findings ({title[:60]!r}); one record "
                           f"must hold exactly one gap or per-gap status is undecidable"))
    for name, val in (("title", title), ("description", desc)):
        if len(val) >= TRUNCATED_MIN and not val.rstrip().endswith((".", ")", "]", "`", "!", "?")):
            out.append(Finding(rel, f"{name}-truncated", "warn",
                               f"{name} appears severed mid-word: ...{val[-40:]!r}"))
    if rtype == "evidence" and not front.get("resource"):
        out.append(Finding(rel, "resource-unused", "warn",
                           "schema declares `resource:` but it is empty"))
    return out


def validate(ledger: Path) -> list[Finding]:
    findings: list[Finding] = []
    for sub in ("gaps", "evidence"):
        d = ledger / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            findings.extend(check_record(p.read_text(encoding="utf-8"),
                                         str(p.relative_to(ledger))))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("ledger", type=Path)
    ap.add_argument("--mode", choices=("read", "write"), default="write",
                    help="write: any block OR migrate finding fails (new records must be "
                         "well-formed). read: only block findings fail, so a legacy ledger "
                         "stays loudly reportable instead of unusable.")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args(argv)

    if not args.ledger.is_dir():
        print(f"ERROR: not a directory: {args.ledger}", file=sys.stderr)
        return 2

    findings = validate(args.ledger)
    fatal = {"block"} if args.mode == "read" else {"block", "migrate"}
    blocking = [f for f in findings if f.severity in fatal]

    if args.format == "json":
        print(json.dumps({"schema_version": SCHEMA_VERSION, "mode": args.mode,
                          "findings": [asdict(f) for f in findings],
                          "blocking": len(blocking)}, indent=2))
    else:
        by_sev: dict[str, list[Finding]] = {}
        for f in findings:
            by_sev.setdefault(f.severity, []).append(f)
        for sev in ("block", "migrate", "warn"):
            group = by_sev.get(sev, [])
            if not group:
                continue
            print(f"\n{sev.upper()} ({len(group)})")
            for f in group:
                print(f"  {f.record}: [{f.code}] {f.detail}")
        print(f"\n{len(findings)} findings, {len(blocking)} blocking in --mode {args.mode}")

    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
