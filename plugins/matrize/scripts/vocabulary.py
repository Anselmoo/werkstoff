#!/usr/bin/env python3
"""Compile references/vocabulary/*.md into a term registry the checks can enforce.

Why a compiler
--------------
The six vocabulary files are the plugin's domain layer, and until now they reached it only
as prose inside four SKILL.md files. This repository has measured what prose in a SKILL.md
is worth as enforcement: it is the baseline row, beneath "a fenced command, 1 run in 3".
So the most load-bearing content in the plugin was the least enforced content in it.

This turns 223 dimension terms and 31 asset classes into a registry, and
`validate_tokens.py` and the PreToolUse guard turn the registry into a refusal.

Parsed at runtime, never compiled to a committed JSON
-----------------------------------------------------
One source, so there is no second copy to drift. Six small files cost nothing to reparse.

Headers are found by the separator row, NEVER by the first cell
----------------------------------------------------------------
Writing this the obvious way first -- whitelist first cells (`Term`, `Class`, `Kind`,
`Origin`, ...) and treat any matching row as a header -- silently mis-parses `motion.md`.
Its Principles table contains an ordinary data row beginning

    | Origin | Motion emanates from what triggered it. A menu opens from its button, ...

and the naive detector re-latches there mid-table, attributing the rows that follow to a
table that does not exist. No error, plausible counts. `selftest` plants exactly that row
against exactly that parser, and fails if the sabotage is not caught.

Terms are addressed by dimension, because homonyms are real
-----------------------------------------------------------
`Opacity` is `derived` in `color-system.md` (a tint produced from alpha) and `property` in
`motion.md` (the thing a fade animates). Keying the registry on the bare word made those
two collide and reported a conflict in files that have none. A term is therefore addressed
as `<dimension>/<slug>`, and a bare term that resolves to more than one dimension is
reported as ambiguous rather than resolved to whichever was parsed first.

The other failure this file exists to prevent
---------------------------------------------
A parser extracting ZERO terms makes every rule downstream pass vacuously, green all the
way. So `selftest` asserts the real per-file counts against figures measured by hand, and
`load()` refuses a file that yields nothing.

Why there is no term PROPOSER
-----------------------------
Measured against this repository's own 50 declarations, exact-name matching binds **1**.
CSS custom properties are ROLE names (`--space-1`, `--bg`); the vocabulary names CONCEPTS
(`Spacing step`, `Surface / background`). No string matcher bridges that, and one that
appeared to would be guessing. Naming the concept is interpretation, which invariant I3
keeps in a separate artefact written by a separate agent -- so `--audit` reports what is
named and what is not, and proposes nothing.

Usage:
    vocabulary.py                  # summarise the registry
    vocabulary.py --json           # machine-readable registry
    vocabulary.py --audit FILE     # which tokens name a concept, and which do not
    vocabulary.py --selftest       # the compiler asserts itself
Exit: 0 clean, 1 the registry has problems, 2 the files could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOCAB_DIR = HERE.parent / "references" / "vocabulary"
README = "README.md"

DIMENSIONS = ("color-system", "grid-and-spacing", "icon-system", "motion", "typography")
TAXONOMY = "visual-asset-taxonomy"

# Header tuples this compiler understands. A table whose header is not here is ignored --
# reported in `problems` rather than guessed at.
H_TERM = ("Term", "What it names", "Kind")
H_TERM_NOKIND = ("Term", "What it names")
H_CLASS = ("Class", "Purpose", "Established", "Origin")
H_KIND_LEGEND = ("Kind", "Meaning")
H_ORIGIN_LEGEND = ("Origin", "Meaning", "What a design system can deliver")
H_PRINCIPLE = ("Principle", "Statement")
H_NORMALISE = ("As written", "Normalises to")
H_CEILING = ("Term", "File", "max", "Quoted source bullet")
H_MANDATORY = ("Class",)

KINDS = ("token", "derived", "rule", "property")

# Declared, never matched by substring: `derived from token` CONTAINS `token`, and a
# containment test files it under exactly the wrong kind.
KIND_ALIASES = {
    "token": "token",
    "derived": "derived",
    "rule": "rule",
    "property": "property",
    "derived from token": "derived",
    "token (a text style)": "token",
}

# Compound origins are not collapsed to one atom -- that would throw away the part that
# bounds the promise. Each keeps its components; `deliverable_whole` is the only reduction,
# and it is the conservative one: only a purely `derivable` class can be delivered entire.
ORIGIN_ATOMS = ("derivable", "drawn", "captured", "shot")

SEP = re.compile(r"^:?-{2,}:?$")


def slug(text: str) -> str:
    text = text.replace("`", "").strip().lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text)).strip("-")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    if not line.lstrip().startswith("|"):
        return False
    parts = cells(line)
    return bool(parts) and all(SEP.match(p) for p in parts)


FIRST_CELLS = ("Term", "Class", "Kind", "Origin", "Principle", "As written")


def tables(text: str) -> list[tuple[tuple[str, ...], list[list[str]], int]]:
    """Every markdown table as (header, rows, 1-based header line number).

    A header is a row whose NEXT line is a separator row. Nothing about the cell contents
    is consulted, so no data row can ever be mistaken for one.
    """
    lines = text.splitlines()
    out: list[tuple[tuple[str, ...], list[list[str]], int]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.lstrip().startswith("|") or is_separator(line):
            i += 1
            continue
        if i + 1 >= len(lines) or not is_separator(lines[i + 1]):
            i += 1
            continue
        header, rows = tuple(cells(line)), []
        j = i + 2
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            if not is_separator(lines[j]):
                rows.append(cells(lines[j]))
            j += 1
        out.append((header, rows, i + 1))
        i = j
    return out


def naive_tables(text: str) -> list[tuple[tuple[str, ...], list[list[str]], int]]:
    """The WRONG parser, kept executable so the selftest can prove it is wrong.

    It decides header-ness per line from the first cell. `motion.md`'s Principles table
    carries an ordinary data row beginning `| Origin | Motion emanates from ...`, so this
    re-latches in the middle of a table, invents a boundary, and misattributes the rows
    after it. It raises nothing and its counts look plausible, which is the whole problem.
    """
    out: list[tuple[tuple[str, ...], list[list[str]], int]] = []
    header, rows, start = None, [], 0
    for n, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith("|") or is_separator(line):
            continue
        row = cells(line)
        if row[0] in FIRST_CELLS:
            if header:
                out.append((header, rows, start))
            header, rows, start = tuple(row), [], n
        elif header:
            rows.append(row)
    if header:
        out.append((header, rows, start))
    return out


class Term:
    def __init__(self, display: str, dimension: str, kind: str | None, line: int) -> None:
        self.slug = slug(display)
        self.display, self.dimension, self.kind, self.line = display, dimension, kind, line

    @property
    def key(self) -> str:
        return f"{self.dimension}/{self.slug}"

    def as_dict(self) -> dict:
        return {"slug": self.slug, "display": self.display, "dimension": self.dimension,
                "kind": self.kind, "line": self.line}


class AssetClass:
    def __init__(self, display: str, purpose: str, established: str, origin_raw: str) -> None:
        self.slug = slug(display)
        self.display, self.purpose, self.established = display, purpose, established
        self.origin_raw = origin_raw
        self.origins = {a for a in ORIGIN_ATOMS if a in origin_raw.lower()}
        # Only a bare `derivable` can be delivered entire. A compound cannot, and scanning
        # for atoms is not enough to see that: `derivable from icon + token` contains the
        # word "derivable" and depends on a DRAWN icon. "mixed" names no atom at all.
        self.deliverable_whole = origin_raw.strip().lower() == "derivable"

    def as_dict(self) -> dict:
        return {"slug": self.slug, "display": self.display, "purpose": self.purpose,
                "established": self.established, "origin": self.origin_raw,
                "origins": sorted(self.origins), "deliverableWhole": self.deliverable_whole}


class Registry:
    def __init__(self) -> None:
        self.terms: dict[str, Term] = {}               # "<dimension>/<slug>" -> Term
        self.index: dict[str, list[str]] = {}          # bare slug -> the keys holding it
        self.classes: dict[str, AssetClass] = {}
        self.ceilings: dict[str, str | None] = {}      # term KEY -> "A"|"B"|"C"|None
        self.pairs: list[tuple[str, str, str]] = []    # (slug a, slug b, the heading)
        self.cautions: list[str] = []                  # confused-pair headings that are not a pair
        self.mandatory: list[str] = []                 # slugs of mandatory asset classes
        self.legend: dict[str, str] = {}
        self.problems: list[str] = []
        self.counts: dict[str, int] = {}

    def add(self, term: Term) -> None:
        if term.key not in self.terms:
            self.terms[term.key] = term
            self.index.setdefault(term.slug, []).append(term.key)

    def lookup(self, term_slug: str, dimension: str | None = None
               ) -> tuple[Term | None, str | None]:
        """(term, reason-it-could-not-be-resolved). Ambiguity is reported, never guessed.

        `Opacity` is a real homonym -- `derived` in colour, `property` in motion -- so a
        bare term naming more than one dimension is unresolvable by construction, and
        picking whichever parsed first would be a confidently wrong kind.
        """
        if dimension:
            term = self.terms.get(f"{dimension}/{term_slug}")
            if term:
                return term, None
            if term_slug in self.index:
                return None, (f"{term_slug!r} exists, but not in dimension {dimension!r} "
                              f"(it is in {', '.join(sorted(self.dimensions_of(term_slug)))})")
            return None, f"{term_slug!r} is not a vocabulary term"
        keys = self.index.get(term_slug, [])
        if not keys:
            return None, f"{term_slug!r} is not a vocabulary term"
        if len(keys) > 1:
            return None, (f"{term_slug!r} is named by {len(keys)} dimensions "
                          f"({', '.join(sorted(self.dimensions_of(term_slug)))}); "
                          f"name the dimension")
        return self.terms[keys[0]], None

    def dimensions_of(self, term_slug: str) -> set[str]:
        return {self.terms[k].dimension for k in self.index.get(term_slug, [])}

    @property
    def homonyms(self) -> dict[str, list[str]]:
        return {s: sorted(self.dimensions_of(s))
                for s, keys in self.index.items() if len(keys) > 1}

    def as_dict(self) -> dict:
        return {
            "terms": {k: v.as_dict() for k, v in sorted(self.terms.items())},
            "homonyms": self.homonyms,
            "classes": {k: v.as_dict() for k, v in sorted(self.classes.items())},
            "ceilings": self.ceilings, "pairs": self.pairs, "cautions": self.cautions,
            "mandatory": self.mandatory, "legend": self.legend,
            "counts": self.counts, "problems": self.problems,
        }


# re.M matters: without it `^` anchors to the start of the SECTION, matches the first
# heading only, and every later pair is silently dropped -- 0 pairs from six files that
# all have them.
CONFUSED_HEADING = re.compile(r"^\*\*(.+?)\.?\*\*", re.M)
VS = re.compile(r"^(.+?)\s+vs\.?\s+(.+?)$", re.IGNORECASE)


def confused_pairs(text: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """The bolded lead-ins under `## Frequently confused pairs`.

    Not every one is a pair -- "Scrim is not an image." and "Dark mode is not inverted
    light mode." are one-sided cautions. Those are kept as cautions rather than forced into
    a pair shape, because inventing a second side would invent a term.
    """
    section = re.search(r"^## Frequently confused pairs\s*$(.*?)(?=^## |\Z)",
                        text, re.M | re.S)
    if not section:
        return [], []
    pairs: list[tuple[str, str, str]] = []
    cautions: list[str] = []
    for match in CONFUSED_HEADING.finditer(section.group(1)):
        heading = match.group(1).strip()
        parts = VS.match(heading)
        if parts:
            pairs.append((slug(parts.group(1)), slug(parts.group(2)), heading))
        else:
            cautions.append(heading)
    return pairs, cautions


def parse_dimension(reg: Registry, name: str, text: str) -> None:
    seen = 0
    for header, rows, line in tables(text):
        if header == H_TERM:
            for offset, row in enumerate(rows):
                raw_kind = row[2]
                kind = KIND_ALIASES.get(raw_kind.lower())
                if kind is None:
                    reg.problems.append(
                        f"{name}.md:{line + 2 + offset}: kind {raw_kind!r} is not in the "
                        f"declared alias map; add it to references/vocabulary/README.md "
                        f"rather than letting it fall through")
                reg.add(Term(row[0], name, kind, line + 2 + offset))
                seen += 1
        elif header == H_TERM_NOKIND:
            for offset, row in enumerate(rows):
                reg.add(Term(row[0], name, None, line + 2 + offset))
        elif header == H_CLASS:
            for row in rows:
                cls = AssetClass(row[0], row[1], row[2], row[3])
                reg.classes[cls.slug] = cls
        elif header == H_KIND_LEGEND and name == "grid-and-spacing":
            reg.legend[name] = json.dumps(
                {slug(r[0]): r[1] for r in rows}, sort_keys=True)
        elif header in (H_ORIGIN_LEGEND, H_PRINCIPLE):
            pass  # read by humans, not by the checks
        else:
            reg.problems.append(f"{name}.md:{line}: unrecognised table header {header}")
    reg.counts[name] = seen
    pairs, cautions = confused_pairs(text)
    reg.pairs.extend(pairs)
    reg.cautions.extend(cautions)


def parse_readme(reg: Registry, text: str) -> None:
    for header, rows, line in tables(text):
        if header == H_KIND_LEGEND:
            reg.legend[README] = json.dumps({slug(r[0]): r[1] for r in rows}, sort_keys=True)
        elif header == H_CEILING:
            for row in rows:
                term, filename, cap, quote = row[0], row[1], row[2], row[3]
                key = f"{filename[:-3]}/{slug(term)}"
                reg.ceilings[key] = None if cap == "none" else cap
                reg.problems.extend(_check_ceiling(term, filename, cap, quote, line))
        elif header == H_MANDATORY:
            reg.mandatory = [slug(r[0]) for r in rows]
        elif header == H_NORMALISE:
            declared = {r[0].replace("`", "").strip(): r[1].replace("`", "").strip()
                        for r in rows}
            for written, into in declared.items():
                if KIND_ALIASES.get(written) != into:
                    reg.problems.append(
                        f"README.md:{line}: the normalisation table says {written!r} -> "
                        f"{into!r}, but KIND_ALIASES says "
                        f"{KIND_ALIASES.get(written)!r}")
        else:
            reg.problems.append(f"README.md:{line}: unrecognised table header {header}")


def _check_ceiling(term: str, filename: str, cap: str, quote: str, line: int) -> list[str]:
    problems: list[str] = []
    if cap not in ("A", "B", "C", "none"):
        problems.append(f"README.md:{line}: ceiling {cap!r} for {term!r} is not A, B, C or none")
    source = VOCAB_DIR / filename
    try:
        body = source.read_text(encoding="utf-8")
    except OSError:
        problems.append(f"README.md:{line}: ceiling for {term!r} cites {filename}, "
                        f"which cannot be read")
        return problems
    if quote not in body:
        problems.append(
            f"VOCAB-CEILING-UNSOURCED: the ceiling for {term!r} quotes {quote!r}, which no "
            f"longer appears in {filename}. The bullet was reworded; re-read it and update "
            f"the ceiling deliberately rather than leaving a rule pointing at nothing.")
    return problems


def load(vocab_dir: Path = VOCAB_DIR) -> Registry:
    reg = Registry()
    # os.listdir, not Path.glob: glob swallows PermissionError and makes an unreadable
    # directory look empty, which here would mean "no terms" and a vacuous green.
    import os
    present = set(os.listdir(vocab_dir))
    for name in (*DIMENSIONS, TAXONOMY):
        filename = f"{name}.md"
        if filename not in present:
            reg.problems.append(f"{filename} is missing from {vocab_dir}")
            continue
        parse_dimension(reg, name, (vocab_dir / filename).read_text(encoding="utf-8"))
    if README in present:
        parse_readme(reg, (vocab_dir / README).read_text(encoding="utf-8"))
    else:
        reg.problems.append(f"{README} is missing; the kind legend and the grade ceilings "
                            f"live there and nothing can be enforced without them")

    # The vacuous-pass guard. A file that yields nothing is a parser regression, not an
    # empty file, and everything downstream would go green.
    for name in DIMENSIONS:
        if reg.counts.get(name, 0) == 0:
            reg.problems.append(
                f"VOCAB-EMPTY: {name}.md yielded 0 terms. A registry with no terms makes "
                f"every downstream rule pass vacuously; this is a parser failure.")
    if not reg.classes:
        reg.problems.append("VOCAB-EMPTY: the asset taxonomy yielded 0 classes")

    # F24: the legend is authored inline in one file only. Canonical copy is the README's.
    inline = reg.legend.get("grid-and-spacing")
    canonical = reg.legend.get(README)
    if inline and canonical and inline != canonical:
        reg.problems.append(
            "VOCAB-LEGEND-DRIFT: grid-and-spacing.md's inline kind legend no longer "
            "matches the canonical one in README.md")
    if canonical and set(json.loads(canonical)) != set(KINDS):
        reg.problems.append(
            f"VOCAB-LEGEND-DRIFT: README.md's legend defines {sorted(json.loads(canonical))}, "
            f"but the code's KINDS is {sorted(KINDS)}")

    for key in reg.ceilings:
        if key not in reg.terms:
            reg.problems.append(
                f"VOCAB-CEILING-UNBOUND: the ceiling for {key!r} names no term in the "
                f"registry, so it can never fire")
    for cls_slug in reg.mandatory:
        if cls_slug not in reg.classes:
            reg.problems.append(
                f"VOCAB-MANDATORY-UNBOUND: mandatory coverage names {cls_slug!r}, which is "
                f"not an asset class in the taxonomy")
    return reg


def kind_tally(reg: Registry) -> dict[str, int]:
    tally = dict.fromkeys(KINDS, 0)
    for term in reg.terms.values():
        if term.kind:
            tally[term.kind] += 1
    return tally


# Counted by hand from the six files, and the reason this compiler can be trusted at all.
EXPECTED_TERMS = {"color-system": 46, "grid-and-spacing": 38, "icon-system": 36,
                  "motion": 46, "typography": 57}
EXPECTED_CLASSES = 31


def selftest() -> int:
    checks: list[tuple[str, bool]] = []
    reg = load()

    for name, want in EXPECTED_TERMS.items():
        checks.append((f"{name}.md yields {want} terms",
                       reg.counts.get(name) == want))
    checks.append((f"the taxonomy yields {EXPECTED_CLASSES} asset classes",
                   len(reg.classes) == EXPECTED_CLASSES))
    checks.append(("223 dimension terms in total",
                   sum(reg.counts[n] for n in EXPECTED_TERMS) == 223))

    tally = kind_tally(reg)
    # Counted by hand BEFORE normalisation as token 77 / rule 65 / property 62 /
    # derived 15 plus four compound spellings; `derived from token` x3 and
    # `token (a text style)` x1 fold in, giving 78 / 65 / 62 / 18. The first draft of this
    # check asserted the pre-normalisation figures and failed -- correctly.
    checks.append(("kinds normalise to token 78 / rule 65 / property 62 / derived 18",
                   tally == {"token": 78, "rule": 65, "property": 62, "derived": 18}))
    checks.append(("every kind tallied sums back to 223 rows",
                   sum(tally.values()) == 223))

    origins = {}
    for cls in reg.classes.values():
        origins[cls.origin_raw] = origins.get(cls.origin_raw, 0) + 1
    checks.append(("asset origins tally drawn 14 / derivable 9 / captured 2",
                   (origins.get("drawn"), origins.get("derivable"),
                    origins.get("captured")) == (14, 9, 2)))
    checks.append(("a compound origin keeps its raw spelling",
                   reg.classes["icon-badge"].origin_raw == "derivable from icon + token"))
    # The atom scan alone would call this deliverable whole: the string contains
    # "derivable". It depends on a DRAWN icon, so it is not.
    checks.append(("`derivable from icon + token` is NOT deliverable whole",
                   not reg.classes["icon-badge"].deliverable_whole))
    checks.append(("only a bare `derivable` class is deliverable whole",
                   reg.classes["indicator-dot"].deliverable_whole
                   and not reg.classes["logo-wordmark"].deliverable_whole
                   and not reg.classes["avatar"].deliverable_whole))

    # The compound spellings must NOT be resolved by containment.
    checks.append(("`derived from token` normalises to derived, not token",
                   KIND_ALIASES["derived from token"] == "derived"))
    checks.append(("every alias value is a canonical kind",
                   set(KIND_ALIASES.values()) == set(KINDS)))

    # F25 -- the sabotage. The naive first-cell detector must produce DIFFERENT, wrong
    # output on motion.md. If it agrees with the strict parser, the sabotage is inert and
    # this test proves nothing.
    motion = (VOCAB_DIR / "motion.md").read_text(encoding="utf-8")
    strict_headers = [h for h, _, _ in tables(motion)]
    naive_headers = [h for h, _, _ in naive_tables(motion)]
    checks.append(("a first-cell header parser invents a table in motion.md",
                   any(h[0] == "Origin" and len(h) > 1
                       and "Motion emanates" in h[1] for h in naive_headers)))
    checks.append(("and so disagrees with the strict parser",
                   naive_headers != strict_headers))
    checks.append(("the strict parser does not invent that table",
                   not any("Motion emanates" in "".join(h) for h in strict_headers)))
    # Where the damage actually lands: the Principles table loses two thirds of its rows
    # to a header that does not exist. The Term tables are upstream of the mis-latch and
    # survive, which is exactly why a term count alone would not have caught this.
    strict_principles = [len(r) for h, r, _ in tables(motion) if h == H_PRINCIPLE]
    naive_principles = [len(r) for h, r, _ in naive_tables(motion) if h == H_PRINCIPLE]
    checks.append(("the naive parser drops rows from motion.md`s Principles table",
                   strict_principles == [6] and naive_principles == [2]))

    # Homonyms are legitimate, and must be reported rather than resolved.
    checks.append(("`Opacity` is recorded in both colour and motion",
                   reg.homonyms.get("opacity") == ["color-system", "motion"]))
    term, why = reg.lookup("opacity")
    checks.append(("a bare homonym does not resolve, and says why",
                   term is None and why is not None and "name the dimension" in why))
    term, why = reg.lookup("opacity", "motion")
    checks.append(("the same term resolves once the dimension is named",
                   term is not None and term.kind == "property"))
    term, why = reg.lookup("opacity", "typography")
    checks.append(("asking for it in the wrong dimension fails with the right ones named",
                   term is None and "color-system" in (why or "")))
    term, why = reg.lookup("no-such-concept")
    checks.append(("an unknown term resolves to nothing",
                   term is None and "not a vocabulary term" in (why or "")))

    # The vacuous-pass guard must actually fire.
    blank = Registry()
    parse_dimension(blank, "motion", "no tables here at all\n")
    checks.append(("a file yielding no terms is counted as zero, not skipped",
                   blank.counts.get("motion") == 0))

    checks.append(("the ceilings are all bound to real terms",
                   all(k in reg.terms for k in reg.ceilings) and len(reg.ceilings) == 5))
    checks.append(("`growth rule` may not be set from a reference at all",
                   "icon-system/growth-rule" in reg.ceilings
                   and reg.ceilings["icon-system/growth-rule"] is None))
    checks.append(("`baseline grid` is capped at C",
                   reg.ceilings.get("grid-and-spacing/baseline-grid") == "C"))

    # A reworded bullet must be caught, not silently pass.
    bad = _check_ceiling("Baseline grid", "grid-and-spacing.md", "C",
                         "Baseline grid — grade A, obviously", 1)
    checks.append(("a ceiling quoting a bullet that no longer exists is reported",
                   any("VOCAB-CEILING-UNSOURCED" in p for p in bad)))
    good = _check_ceiling("Baseline grid", "grid-and-spacing.md", "C",
                          "Baseline grid — grade C at best", 1)
    checks.append(("a ceiling whose bullet is intact is NOT reported", good == [])) 

    checks.append(("the kind legend in README and grid-and-spacing agree",
                   reg.legend.get(README) == reg.legend.get("grid-and-spacing")))
    checks.append(("the three mandatory classes bind to real taxonomy entries",
                   len(reg.mandatory) == 3
                   and all(s in reg.classes for s in reg.mandatory)))
    checks.append(("confused pairs are extracted, and one-sided cautions are not forced "
                   "into a pair", len(reg.pairs) >= 15 and len(reg.cautions) >= 2
                   and any("scrim" in c.lower() for c in reg.cautions)))
    EXT_KEY = "com.werkstoff.matrize"

    def tok(vocab):
        ext = {"vocab": vocab} if vocab else {}
        return {"$value": 1, "$extensions": {EXT_KEY: ext}}

    audited = audit(reg, {"a": {"named": tok({"term": "Gutter",
                                              "dimension": "grid-and-spacing"}),
                                "bare": tok(None),
                                "made-up": tok({"term": "Vibe"}),
                                "extended": tok({"term": "Vibe", "extends": "reason",
                                                 "declaredBy": "CARD-1"})}})
    checks.append(("--audit separates named, unnamed and unknown",
                   audited == (["a.extended", "a.named"], ["a.bare"], ["a.made-up"])))

    checks.append(("the registry is clean", not reg.problems))

    for label, ok in checks:
        print(f"  {label:<64} {'ok' if ok else 'FAIL'}")
    bad_count = sum(1 for _, ok in checks if not ok)
    if reg.problems:
        print("\nproblems:")
        for problem in reg.problems:
            print(f"  - {problem}")
    print(f"\n{len(checks)} check(s), {bad_count} failure(s)")
    print("RED" if bad_count else "GREEN")
    return 1 if bad_count else 0


def audit(reg: Registry, doc: dict) -> tuple[list[str], list[str], list[str]]:
    """(named, unnamed, unknown) token paths. Reports; never proposes a binding."""
    named, unnamed, unknown = [], [], []
    stack: list[tuple[str, dict]] = [("", doc)]
    while stack:
        prefix, node = stack.pop()
        for key, value in node.items():
            if key.startswith("$") or not isinstance(value, dict):
                continue
            path = f"{prefix}.{key}" if prefix else key
            if "$value" not in value:
                stack.append((path, value))
                continue
            spec = ((value.get("$extensions") or {}).get("com.werkstoff.matrize")
                    or {}).get("vocab")
            if not isinstance(spec, dict) or not spec.get("term"):
                unnamed.append(path)
                continue
            term, _ = reg.lookup(slug(spec["term"]), spec.get("dimension"))
            (named if term or spec.get("extends") else unknown).append(path)
    return sorted(named), sorted(unnamed), sorted(unknown)


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--audit", metavar="FILE", help="a tokens.json to audit")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--vocab-dir", default=str(VOCAB_DIR))
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    try:
        reg = load(Path(args.vocab_dir))
    except OSError as exc:
        print(f"vocabulary.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.audit:
        try:
            doc = json.loads(Path(args.audit).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"vocabulary.py: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        named, unnamed, unknown = audit(reg, doc)
        total = len(named) + len(unnamed) + len(unknown)
        print(f"{args.audit}: {total} token(s)")
        print(f"  {len(named)} name a vocabulary concept")
        print(f"  {len(unnamed)} name none")
        print(f"  {len(unknown)} name a concept the vocabulary does not have")
        for path in unnamed:
            print(f"    unnamed  {path}")
        for path in unknown:
            print(f"    unknown  {path}")
        return 1 if (unnamed or unknown) else 0

    if args.json:
        print(json.dumps(reg.as_dict(), indent=2, sort_keys=True))
    else:
        tally = kind_tally(reg)
        print(f"{len(reg.terms)} distinct terms across {len(DIMENSIONS)} dimensions "
              f"({sum(reg.counts.values())} rows)")
        for kind in KINDS:
            print(f"  {kind:<10} {tally[kind]}")
        print(f"{len(reg.classes)} asset classes, "
              f"{sum(1 for c in reg.classes.values() if c.deliverable_whole)} deliverable whole")
        print(f"{len(reg.ceilings)} written grade ceiling(s), "
              f"{len(reg.pairs)} confused pair(s), {len(reg.cautions)} caution(s)")
        for problem in reg.problems:
            print(f"  - {problem}", file=sys.stderr)
    return 1 if reg.problems else 0


if __name__ == "__main__":
    sys.exit(main())
