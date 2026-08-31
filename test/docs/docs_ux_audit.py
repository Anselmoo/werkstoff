#!/usr/bin/env python3
"""Audit the published docs site for UX defects no existing gate can see.

Why this exists
---------------
docs/ is already gated four ways: validate_catalog.py (recipe frontmatter and
skill-id resolution), config.mjs's buildCatalogSidebar() (category-vs-directory,
non-empty task, non-zero total), VitePress's `ignoreDeadLinks: false` (internal
links resolve), and regenerate-plus-`git diff --exit-code` (generated artifacts
match their source).

Every one of those checks REFERENTIAL INTEGRITY: does this identifier resolve?
A mutation run over docs/ (22 mutants: boundary flips, condition negations, index
shifts) found the consequence -- 17 of 20 non-equivalent mutants survived the full
battery, including a homepage that miscounts the catalog by 12 recipes and a
recipe whose beats were reordered into the opposite of its own stated thesis.

Nothing grades a CLAIM: a sentence that asserts a count, an ordering, a category
set, or a rule. This tool grades claims, plus the reading-load properties that
decide whether a reader can navigate 50k words at all.

What it checks:
    1. C1 -- counts claimed in prose (recipe/prompt/category totals) match reality
    2. C2 -- the category set agrees across CATEGORY_ORDER, CATEGORY_LABELS, and
       docs/catalog/index.md's own prose
    3. C3 -- no published page is unreachable from nav or sidebar (orphans)
    4. C4 -- outline shape and reading load stay navigable, graded ONLY on the
       16 genuine prose pages (see is_component_rendered()): a flat run of
       same-level headings the outline can't collapse, a page too long to
       read in one sitting, and the longest stretch of prose between two
       headings a reader could get lost in
    5. C5 -- do/don't guidance coverage across pairings and recipes
    6. C6 -- every recipe body says something its frontmatter doesn't, so a
       reader arriving from search has something to orient on

House style, matched from tools/catalog-validator/validate_catalog.py: collect
every failure across every check rather than stopping at the first, raise a named
exception for anything that must fail loudly, and derive ground truth from the
filesystem at run time, never from a hardcoded list.

Usage:
    python3 test/docs/docs_ux_audit.py            # all checks
    python3 test/docs/docs_ux_audit.py --list     # show check ids and exit
    python3 test/docs/docs_ux_audit.py --only C1  # run one check
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
CATALOG = DOCS / "catalog"
CONFIG = DOCS / ".vitepress" / "config.mjs"
CATEGORIES = DOCS / ".vitepress" / "data" / "catalog.categories.mjs"
PAIRINGS = DOCS / "orchestration" / "references" / "pairings.md"

# Spelled-out counts appear in prose ("Twenty-five development tasks"). Only the
# range the docs actually use is mapped; an unmapped word is reported as
# unparseable rather than silently skipped.
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "twenty-five": 25, "thirty": 30, "thirty-seven": 37,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "seventy-six": 76,
    "eighty": 80, "ninety": 90, "ninety-eight": 98, "one hundred": 100,
}


class DocsAuditError(RuntimeError):
    """Raised when the audit cannot run at all -- never used for a finding."""


@dataclass
class Report:
    findings: list[str] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)

    def fail(self, check: str, message: str) -> None:
        self.findings.append(f"[{check}] {message}")

    @property
    def ok(self) -> bool:
        return not self.findings


# ---------------------------------------------------------------------------
# Ground truth, derived live
# ---------------------------------------------------------------------------


def load_recipes() -> list[tuple[Path, dict]]:
    """Every recipe under docs/catalog/<category>/*.md with parsed frontmatter."""
    if yaml is None:
        raise DocsAuditError("PyYAML is required -- pip install pyyaml")
    recipes = []
    for path in sorted(CATALOG.glob("*/*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            continue
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            raise DocsAuditError(f"{path}: unterminated frontmatter")
        data = yaml.safe_load("\n".join(lines[1:end]))
        if isinstance(data, dict) and "beats" in data:
            recipes.append((path, data))
    if not recipes:
        raise DocsAuditError(f"no recipes found under {CATALOG} -- audit would vacuously pass")
    return recipes


def parse_number(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def published_pages() -> list[Path]:
    """Markdown pages VitePress actually builds (srcExclude honoured)."""
    excluded = {"andon-pilot-findings.md", "andon-pilot-handoff.md", "catalog/_UNRESOLVED.md"}
    pages = []
    for path in sorted(DOCS.rglob("*.md")):
        rel = path.relative_to(DOCS).as_posix()
        if rel.startswith(".vitepress/") or rel in excluded:
            continue
        pages.append(path)
    return pages


def body_words(path: Path) -> int:
    """Word count of the markdown body, excluding YAML frontmatter."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            lines = lines[end + 1:]
    return len(" ".join(lines).split())


def frontmatter_and_body(path: Path) -> tuple[dict, str]:
    """Split a page into its parsed frontmatter dict and its raw markdown body
    (frontmatter stripped). Shared by the component-page predicate and the
    reading-load metrics so both walk the same text.
    """
    if yaml is None:
        raise DocsAuditError("PyYAML is required -- pip install pyyaml")
    lines = path.read_text(encoding="utf-8").splitlines()
    fm: dict = {}
    body_lines = lines
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            fm = yaml.safe_load("\n".join(lines[1:end])) or {}
            body_lines = lines[end + 1:]
    return fm, "\n".join(body_lines)


def registered_components() -> set[str]:
    """Component tags VitePress will actually render on a page, read live from
    the theme's own enhanceApp() registrations in theme/index.js -- never
    hardcoded here, so a newly registered component cannot silently leave a
    page mis-graded (the exact drift this tool exists to catch).
    """
    source = (DOCS / ".vitepress" / "theme" / "index.js").read_text(encoding="utf-8")
    return set(re.findall(r"app\.component\('([A-Za-z0-9]+)'", source))


def is_component_rendered(path: Path) -> bool:
    """A page whose reading experience is decided by a Vue component, not by
    prose rhythm -- pairings.md and the 25+ catalog recipes carry almost all
    of their content in YAML frontmatter and render it through PairingCards.vue
    / RecipeBeats.vue, and index.md is a VitePress `layout: home` hero. Grading
    those pages' word counts or heading density as prose measures the wrong
    thing entirely (see docs/... council brief, S0c/S7.0). Derived live from
    the same signals the components themselves gate on:

      - `layout` frontmatter other than the default/'doc' (index.md -> 'home')
      - a `beats` frontmatter list (RecipeBeats.vue's own v-if guard)
      - a `pairings` frontmatter list (PairingCards.vue's data source)
      - an explicit tag for any globally-registered component in the body
        (e.g. `<CatalogGrid />` on docs/catalog/index.md, which carries none
        of the frontmatter keys above)
    """
    fm, body = frontmatter_and_body(path)
    if fm.get("layout") not in (None, "doc"):
        return True
    if fm.get("beats"):
        return True
    if fm.get("pairings"):
        return True
    return any(re.search(rf"<{tag}\b", body) for tag in registered_components())


def longest_gap_between_headings(body: str) -> int:
    """Word count of the longest unbroken stretch of prose between two `##`-
    `####` headings (or between the top/bottom of the page and the nearest
    one). Operationalises the actual user complaint -- "the breaks are not
    clear for the reader" -- as a distance a reader must travel without a
    landmark, rather than as an average frequency across the whole page. See
    S7.4 of the council brief: this is the metric the complaint is about.
    """
    segments = re.split(r"^#{2,4} .*$", body, flags=re.M)
    return max((len(seg.split()) for seg in segments), default=0)


# ---------------------------------------------------------------------------
# C1 -- claim registry: prose that asserts a number must match reality
# ---------------------------------------------------------------------------


def check_c1_counts(report: Report, recipes: list[tuple[Path, dict]]) -> None:
    """Each entry pairs a literal sentence pattern with the value that makes it
    true. Deliberately explicit, one regex per claim, anchored to a short span --
    never one clever pattern sweeping the corpus. See CLAUDE.md's defect table.
    """
    n_recipes = len(recipes)
    n_prompts = sum(1 for _, fm in recipes for b in fm.get("beats") or [] if b.get("prompt"))
    n_beats = sum(len(fm.get("beats") or []) for _, fm in recipes)
    n_categories = len({fm.get("category") for _, fm in recipes})

    claims = [
        (DOCS / "index.md", r"([A-Za-z-]+|\d+) development tasks", n_recipes, "catalog recipes"),
        (DOCS / "index.md", r"([A-Za-z-]+|\d+) copy-paste prompts", n_prompts, "beats carrying a prompt"),
        (DOCS / "orchestration" / "references" / "catalog.md",
         r"the same\s+([A-Za-z-]+|\d+) task recipes", n_recipes, "catalog recipes"),
    ]
    for path, pattern, expected, label in claims:
        if not path.is_file():
            report.fail("C1", f"{path.relative_to(REPO)}: claim source file is missing")
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(pattern, text)
        if match is None:
            report.fail("C1", f"{path.relative_to(REPO)}: no sentence matching /{pattern}/ -- "
                              "the claim was reworded or removed; update this registry")
            continue
        claimed = parse_number(match.group(1))
        if claimed is None:
            report.fail("C1", f"{path.relative_to(REPO)}: cannot parse '{match.group(1)}' as a number")
        elif claimed != expected:
            report.fail("C1", f"{path.relative_to(REPO)}: claims {claimed} {label}, actual is {expected} "
                              f"(in: \"{match.group(0)}\")")

    # Unclaimed-but-derivable totals, reported for awareness, not failure.
    report.checks_run.append(f"C1 ground truth: {n_recipes} recipes, {n_beats} beats, "
                             f"{n_prompts} prompts, {n_categories} categories")


# ---------------------------------------------------------------------------
# C2 -- the category set must agree in all three places that state it
# ---------------------------------------------------------------------------


def check_c2_categories(report: Report, recipes: list[tuple[Path, dict]]) -> None:
    on_disk = {p.parent.name for p, _ in recipes}

    source = CATEGORIES.read_text(encoding="utf-8")
    block = re.search(r"CATEGORY_ORDER = \[(.*?)\]", source, re.S)
    if block is None:
        raise DocsAuditError(f"{CATEGORIES}: could not locate CATEGORY_ORDER")
    declared = set(re.findall(r"'([^']+)'", block.group(1)))

    labels = re.search(r"CATEGORY_LABELS = \{(.*?)\n\}", source, re.S)
    labelled = set(re.findall(r"^\s*'?([a-z-]+)'?:", labels.group(1), re.M)) if labels else set()

    if declared != on_disk:
        report.fail("C2", f"CATEGORY_ORDER {sorted(declared)} != categories on disk {sorted(on_disk)}")
    if labelled and labelled != on_disk:
        report.fail("C2", f"CATEGORY_LABELS {sorted(labelled)} != categories on disk {sorted(on_disk)}")

    # The comment above CATEGORY_ORDER states a count; a stale count there is the
    # same defect class as a stale count on the homepage.
    comment = re.search(r"//\s*Fixed display order for the ([a-z-]+) recipe categories", source)
    if comment:
        claimed = parse_number(comment.group(1))
        if claimed is not None and claimed != len(on_disk):
            report.fail("C2", f"{CATEGORIES.relative_to(REPO)}: comment says "
                              f"'{comment.group(1)} recipe categories', there are {len(on_disk)}")

    # docs/catalog/index.md enumerates the categories in prose for the reader.
    prose = (CATALOG / "index.md").read_text(encoding="utf-8")
    listed = re.search(r"Filter by category — (.+?) — or by whether", prose, re.S)
    if listed is None:
        report.fail("C2", "docs/catalog/index.md: no 'Filter by category — ... — or by whether' "
                          "sentence found; update this check if it was reworded")
    else:
        named = len(re.split(r",| or ", listed.group(1).replace("\n", " ")))
        named = len([s for s in re.split(r",|\bor\b", listed.group(1).replace("\n", " ")) if s.strip()])
        if named != len(on_disk):
            report.fail("C2", f"docs/catalog/index.md prose names {named} categories, "
                              f"{len(on_disk)} exist on disk: {sorted(on_disk)}")


# ---------------------------------------------------------------------------
# C3 -- no orphan pages: everything built must be reachable from nav or sidebar
# ---------------------------------------------------------------------------


# Pages that are unreachable from nav ON PURPOSE, each with the reason on the
# record. An entry here is a decision, not a suppression: anything NOT listed
# that falls out of navigation is a defect.
INTENTIONAL_ORPHANS = {
    "orchestration/references/catalog.md":
        "redirect stub kept so external links against the pre-#44 URL still resolve",
}


def check_c3_orphans(report: Report) -> None:
    config = CONFIG.read_text(encoding="utf-8")
    linked = set(re.findall(r"link:\s*'(/[^']*)'", config))
    # The catalog sidebar section is built at run time from the filesystem, so
    # every catalog recipe counts as linked by construction.
    linked_prefixes = {"/catalog/"}

    for path in published_pages():
        rel = path.relative_to(DOCS).as_posix()
        if rel == "index.md":
            continue
        route = "/" + re.sub(r"(^|/)(README|index)\.md$", r"\1", rel).removesuffix(".md")
        route = route.rstrip("/") or "/"
        if route in linked or f"{route}/" in linked:
            continue
        if any(route.startswith(p) for p in linked_prefixes):
            continue
        if rel in INTENTIONAL_ORPHANS:
            report.checks_run.append(f"C3 intentional orphan: {rel} ({INTENTIONAL_ORPHANS[rel]})")
            continue
        report.fail("C3", f"{rel}: built and published but reachable from no nav or sidebar entry "
                          f"(expected route {route}) -- add a sidebar entry or srcExclude it")


# ---------------------------------------------------------------------------
# C4 -- outline shape: a flat run of same-level headings is an unnavigable page
# ---------------------------------------------------------------------------


# These thresholds decide what the audit calls a UX defect rather than a
# long-but-fine page. They are the one genuinely editorial judgment in this
# file, and were set by human sign-off on a design-council brief that measured
# the site's 16 genuine prose pages (see is_component_rendered() above -- the
# other 40 published pages carry their content in frontmatter, rendered by a
# Vue component, and are excluded from every threshold below). Every number
# was calibrated BEFORE this session's rhythm/measure/palette fixes landed, so
# it must not be retuned against post-fix output -- see CLAUDE.md's "Never
# retune an oracle after the thing it grades exists."

# Consecutive '##' headings with no '###' between them. Measured distribution
# across the 16 prose pages: 10, 8, 7, 6, 6, 6, 6, 6, 4, 4, 4, 4, 3, 2, 2, 0.
# 8 fails exactly craft-standards.md (10 flat h2s over 1,389 words -- the
# least navigable outline on the site) and passes prompt-index.md (8 flat
# h2s, one per plugin -- werkstoff has 8 plugins, so that flatness is the
# domain's natural cardinality, not a defect). 6 would false-positive on four
# pages that are deliberately flat lists of peer topics (routing, gates,
# delegation, hazards); 10 would fail nothing, making this arm vacuous.
MAX_FLAT_RUN = 8

# Body words (frontmatter excluded) before a page is flagged. Prose
# distribution: 8235, 6094, 3705, 2962, 1539, 1508, 1499, 1499, 1393, 1389,
# 1373, 1277, 1154, 1041, 388, 100. 6500 fails exactly
# andon-behavior-contract.md (8235) and passes plugin-benchmark-plan.md
# (6094). ~6500 words is ~30 minutes at 220wpm -- the point past which a page
# cannot be read in one sitting and resumption becomes the design problem.
# NOTE: the remedy for a failure here is NOT "split the page" -- the human
# sign-off ruled that out explicitly; see the reworded message below.
MAX_PAGE_WORDS = 6500

# Longest run of prose words between two headings (see
# longest_gap_between_headings()). REPLACES a headings-per-1000-words density
# check that was removed outright rather than kept alongside this one.
# Density measures the wrong thing: prompt-index.md has the LOWEST heading
# density on the entire site (2.7/1k) and the SHORTEST worst stretch (77
# words) of any prose page -- it is a dense index of short entries, and
# density misreads it as the worst-structured page on the site. The user's
# actual complaint ("the breaks are not clear for the reader") is a statement
# about the distance between breaks, not their average frequency, which is
# exactly what this metric measures instead. Measured worst stretches:
# andon-behavior-contract.md 1016, plugin-benchmark-plan.md 762,
# output-shape-findings.md 538, orchestration/README.md 324,
# prompt-index.md 77. At 700 the check fails exactly the two pages a reader
# would name and clears prompt-index.md by an order of magnitude. ~700 words
# is ~3 minutes of uninterrupted reading -- a defensible outer bound for a
# technical document with no landmark in sight.
MAX_WORDS_BETWEEN_HEADINGS = 700


def check_c4_outline(report: Report) -> None:
    if MAX_FLAT_RUN is None or MAX_PAGE_WORDS is None or MAX_WORDS_BETWEEN_HEADINGS is None:
        report.fail("C4", "reading-load thresholds are unset (MAX_FLAT_RUN, MAX_PAGE_WORDS, "
                          "MAX_WORDS_BETWEEN_HEADINGS) -- set them rather than defaulting, so "
                          "the policy is a decision on the record instead of an accident")
        return

    excluded = graded = 0
    for path in published_pages():
        rel = path.relative_to(DOCS).as_posix()
        if is_component_rendered(path):
            excluded += 1
            continue
        graded += 1

        words = body_words(path)
        fm, body = frontmatter_and_body(path)
        headings = re.findall(r"^(#{2,4}) ", body, re.M)
        if not headings:
            continue

        run = longest = 0
        for level in headings:
            if level == "##":
                run += 1
                longest = max(longest, run)
            else:
                run = 0
        if longest > MAX_FLAT_RUN:
            report.fail("C4", f"{rel}: {longest} consecutive '##' headings with no '###' between "
                              f"them (max {MAX_FLAT_RUN}) -- the right-hand outline renders them "
                              "as one flat list the reader cannot collapse")
        if words > MAX_PAGE_WORDS:
            report.fail("C4", f"{rel}: {words} words (~{words // 220} min read, max {MAX_PAGE_WORDS}) "
                              "-- this page must carry the full long-page treatment (breathers, "
                              "the terminal node, and an outline that reaches h3), not be split: "
                              "splitting is explicitly out of scope for this check")
        gap = longest_gap_between_headings(body)
        if gap > MAX_WORDS_BETWEEN_HEADINGS:
            report.fail("C4", f"{rel}: {gap} words in the longest stretch between headings "
                              f"(max {MAX_WORDS_BETWEEN_HEADINGS}) -- a reader who looks away in "
                              "this stretch has no landmark to resume from")

    report.checks_run.append(
        f"C4 component-page exclusion: {excluded} of {excluded + graded} published pages are "
        f"component-rendered (frontmatter-driven beats/pairings, or a home layout) and excluded "
        f"from reading-load grading; {graded} genuine prose pages graded"
    )


# ---------------------------------------------------------------------------
# C5 -- do/don't coverage: the affordance exists, but only on one page
# ---------------------------------------------------------------------------


def check_c5_dos_donts(report: Report, recipes: list[tuple[Path, dict]]) -> None:
    if yaml is None:
        raise DocsAuditError("PyYAML is required")
    text = PAIRINGS.read_text(encoding="utf-8")
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise DocsAuditError(f"{PAIRINGS}: unterminated frontmatter")
    pairings = (yaml.safe_load("\n".join(lines[1:end])) or {}).get("pairings") or []

    with_dd = sum(1 for p in pairings if p.get("dos") and p.get("donts"))
    if with_dd != len(pairings):
        report.fail("C5", f"pairings.md: {len(pairings) - with_dd} of {len(pairings)} pairings "
                          "carry no dos/donts pair")

    recipes_with_dd = sum(1 for _, fm in recipes if fm.get("dos") or fm.get("donts"))
    with_opening = sum(1 for _, fm in recipes if fm.get("openingPrompt"))

    # Derive the verdict from the numbers rather than asserting it in prose. An
    # earlier version of this note hardcoded "the affordance exists on the pairing
    # page only" -- which stopped being true the moment recipes gained dos/donts,
    # making this tool guilty of exactly the stale-claim defect it exists to catch.
    if recipes_with_dd == 0:
        verdict = ("the affordance exists on the pairing page only, not on the pages "
                   "the homepage sends readers to first")
    elif recipes_with_dd < len(recipes):
        verdict = (f"{len(recipes) - recipes_with_dd} recipe(s) still carry no do/don't "
                   "guidance while the pairing page carries it throughout")
    else:
        verdict = "every recipe and every pairing carries do/don't guidance"
    report.checks_run.append(
        f"C5 coverage: dos/donts on {with_dd}/{len(pairings)} pairings and "
        f"{recipes_with_dd}/{len(recipes)} recipes; openingPrompt on "
        f"{with_opening}/{len(recipes)} recipes -- {verdict}"
    )


# ---------------------------------------------------------------------------
# C6 -- every recipe body must say something the frontmatter does not
# ---------------------------------------------------------------------------


def check_c6_bodies(report: Report, recipes: list[tuple[Path, dict]]) -> None:
    for path, fm in recipes:
        rel = path.relative_to(DOCS).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
        body = "\n".join(lines[end + 1:]).strip()
        if not body:
            report.fail("C6", f"{rel}: empty body -- renders as bare frontmatter-driven beats "
                              "with no orientation for a reader who arrived from search")
        elif len(body.split()) < 25:
            report.fail("C6", f"{rel}: body is {len(body.split())} words -- too short to orient "
                              "a reader who landed here from search rather than the grid")


CHECKS = {
    "C1": ("counts claimed in prose match reality", check_c1_counts),
    "C2": ("the category set agrees in all places that state it", check_c2_categories),
    "C3": ("no published page is unreachable from nav or sidebar", check_c3_orphans),
    "C4": ("outline shape and reading load stay navigable", check_c4_outline),
    "C5": ("do/don't guidance coverage", check_c5_dos_donts),
    "C6": ("every recipe body orients a reader arriving from search", check_c6_bodies),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list check ids and exit")
    parser.add_argument("--only", action="append", metavar="ID", help="run only these checks")
    args = parser.parse_args(argv)

    if args.list:
        for cid, (desc, _) in CHECKS.items():
            print(f"{cid}  {desc}")
        return 0

    selected = args.only or list(CHECKS)
    unknown = [c for c in selected if c not in CHECKS]
    if unknown:
        print(f"error: unknown check(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    report = Report()
    try:
        recipes = load_recipes()
        for cid in selected:
            _, fn = CHECKS[cid]
            fn(report, recipes) if fn.__code__.co_argcount == 2 else fn(report)
    except DocsAuditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for note in report.checks_run:
        print(f"note: {note}")
    stream = sys.stdout if report.ok else sys.stderr
    for finding in report.findings:
        print(finding, file=stream)
    print(f"\n{len(selected)} check(s) run over docs/: {len(report.findings)} finding(s)", file=stream)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
