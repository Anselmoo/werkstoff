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
       headings a reader could get lost in. The two length arms are gated on
       whether the page carries the long-page treatment they prescribe --
       that remedy is applied at runtime, in the DOM, so a source-only check
       could never see it land and the pages stayed red forever. The
       thresholds are untouched; see check_c4_outline() for what can still
       fail, and treatment_wiring_gaps() for the mechanism every verdict
       rests on.
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
    return set(re.findall(r"app\.component\('([A-Za-z0-9]+)'",
                          js_code(DOCS / ".vitepress" / "theme" / "index.js")))


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
# The long-page treatment, modelled from the theme that implements it
# ---------------------------------------------------------------------------
#
# C4's two reading-load arms name a RUNTIME remedy. Everything below is what
# lets the check see whether that remedy actually reaches a given page, instead
# of failing a page forever for a defect its own prescribed fix cannot touch.

THEME = DOCS / ".vitepress" / "theme"
PROSE_PREDICATE_JS = THEME / "composables" / "useProsePage.js"
BREATHERS_JS = THEME / "composables" / "useBreathers.js"
DOC_END_VUE = THEME / "components" / "DocEnd.vue"
THEME_INDEX_JS = THEME / "index.js"


def js_code(path: Path) -> str:
    """A JS/Vue source with its comments removed.

    Every wiring assertion below greps source for a construct. Grepping the raw
    file greps the PROSE TOO, and these files are heavily commented with the
    exact identifiers being asserted -- so a guard would go on passing after the
    code it guards was deleted, satisfied by the comment that describes it.
    Measured, not theorised: deleting theme/index.js's route-change hook left
    C4 green, because the comment above it still said `onAfterRouteChange`.
    That is CLAUDE.md's "code that looks correct and silently does nothing",
    committed by this audit against itself.
    """
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


def breather_params() -> tuple[int, int]:
    """`RUN_MIN` and `EVERY`, read live from useBreathers.js.

    Not copied into this file. They are the knob the design brief calls
    measured-not-guessed, and a Python copy of them would drift from the
    JavaScript that actually inserts the marks without anything noticing --
    which is the whole class of defect C4 was rewritten to stop pretending it
    could see. Missing or unparseable is an audit-cannot-run error, never a
    default: a defaulted threshold is exactly the "policy by accident" this
    check refuses elsewhere.
    """
    if not BREATHERS_JS.is_file():
        raise DocsAuditError(f"{BREATHERS_JS.relative_to(REPO)} is missing -- the breather half of "
                             "the long-page treatment cannot be modelled")
    source = js_code(BREATHERS_JS)
    values = {}
    for name in ("RUN_MIN", "EVERY"):
        match = re.search(rf"^export const {name} = (\d+)$", source, re.M)
        if match is None:
            raise DocsAuditError(f"{BREATHERS_JS.relative_to(REPO)}: cannot read `export const "
                                 f"{name} = <int>` -- C4 cannot model breather placement without it")
        values[name] = int(match.group(1))
    return values["RUN_MIN"], values["EVERY"]


def outline_max_level() -> int:
    """The deepest heading level the right-hand rail renders, from config.mjs's
    `outline: [min, max]`. Part of the long-page treatment: an outline that
    stops at h2 gives a long page no resumption structure however many h3s it
    has.
    """
    source = CONFIG.read_text(encoding="utf-8")
    match = re.search(r"^\s*outline: \[(\d+), (\d+)\],$", source, re.M)
    if match is None:
        raise DocsAuditError(f"{CONFIG.relative_to(REPO)}: cannot read `outline: [min, max]`")
    return int(match.group(2))


# Block openers, checked in this order. Order matters: a line can satisfy more
# than one pattern, and the first match wins the way markdown-it resolves it.
_FENCE = re.compile(r"^(```+|~~~+)")
_CONTAINER_OPEN = re.compile(r"^:::+\s*\S")
_CONTAINER_CLOSE = re.compile(r"^:::+\s*$")
_HEADING = re.compile(r"^(#{1,6}) ")
_THEMATIC_BREAK = re.compile(r"^(---+|\*\*\*+|___+)$")
_LIST_ITEM = re.compile(r"^([-*+] |\d+[.)] )")


def markdown_blocks(body: str) -> list[tuple[str, str]]:
    """Split a markdown body into the TOP-LEVEL block elements it renders as,
    in order, as (tag, source-text) pairs.

    This exists because useBreathers.js counts `root.children` -- the top-level
    DOM element sequence -- and nothing about a markdown source file tells you
    that sequence directly. Two consequences drive every rule below, and both
    are the difference between a model and a guess:

      * a bulleted list is ONE <ul> however many items it has. The 1,010-word
        tail of andon-behavior-contract.md is a <p> and a <ul>: two blocks, not
        nine, so no breather can land in it whatever the threshold is.
      * a `::: details` container is ONE <details>, and the paragraphs inside it
        are NOT top-level children. Six of them separate the paragraphs of
        plugin-benchmark-plan.md's longest stretch.

    Verified rather than assumed: the tag sequence this returns was diffed
    against the live client DOM of all 16 prose pages, read out of a real
    browser after hydration. See the C4 wiring notes for what that check found.
    """
    lines = body.split("\n")
    blocks: list[tuple[str, str]] = []
    i, n = 0, len(lines)

    def emit(tag: str, start: int, stop: int) -> None:
        blocks.append((tag, "\n".join(lines[start:stop])))

    while i < n:
        raw = lines[i]
        line = raw.strip()
        if not line:
            i += 1
            continue

        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            j = i + 1
            while j < n and not lines[j].strip().startswith(marker):
                j += 1
            emit("CODE", i, min(j + 1, n))
            i = j + 1
            continue

        if line.startswith(":::"):
            depth, j = 0, i
            while j < n:
                inner = lines[j].strip()
                if _CONTAINER_OPEN.match(inner):
                    depth += 1
                elif _CONTAINER_CLOSE.match(inner):
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            emit("CONTAINER", i, min(j + 1, n))
            i = j + 1
            continue

        heading = _HEADING.match(line)
        if heading:
            emit(f"H{len(heading.group(1))}", i, i + 1)
            i += 1
            continue

        if _THEMATIC_BREAK.match(line):
            emit("HR", i, i + 1)
            i += 1
            continue

        if line.startswith(">"):
            j = i
            while j < n and lines[j].strip():
                j += 1
            emit("BLOCKQUOTE", i, j)
            i = j
            continue

        if line.startswith("|"):
            j = i
            while j < n and lines[j].strip().startswith("|"):
                j += 1
            emit("TABLE", i, j)
            i = j
            continue

        if _LIST_ITEM.match(line):
            tag = "UL" if line[0] in "-*+" else "OL"
            j = i
            while j < n:
                if lines[j].strip():
                    j += 1
                    continue
                # A blank line ends the list only if what follows is neither an
                # indented continuation nor another item: markdown-it keeps both
                # inside the same (loose) list, and so must this.
                k = j + 1
                while k < n and not lines[k].strip():
                    k += 1
                if k < n and (lines[k].startswith((" ", "\t")) or _LIST_ITEM.match(lines[k])):
                    j = k
                    continue
                break
            emit(tag, i, j)
            i = j
            continue

        if line.startswith("<"):
            j = i
            while j < n and lines[j].strip():
                j += 1
            emit("HTML", i, j)
            i = j
            continue

        # Paragraph: runs to the next blank line or the next block opener.
        j = i
        while j < n and lines[j].strip():
            nxt = lines[j].strip()
            if j > i and (
                _HEADING.match(nxt)
                or _FENCE.match(nxt)
                or nxt.startswith((":::", "|", ">"))
                or _LIST_ITEM.match(nxt)
                or _THEMATIC_BREAK.match(nxt)
            ):
                break
            j += 1
        emit("P", i, max(j, i + 1))
        i = max(j, i + 1)

    return blocks


# The tags useBreathers.js counts as an unbroken text block. Kept in step with
# that file's own TEXT_TAGS by the wiring assertion below rather than by hope.
BREATHER_TEXT_TAGS = {"P", "UL", "OL"}


def longest_text_run(body: str) -> int:
    """Longest run of consecutive top-level text blocks -- the quantity
    useBreathers.js thresholds on. A page whose longest run is below RUN_MIN
    receives no breather anywhere, however long the page is.
    """
    longest = run = 0
    for tag, _ in markdown_blocks(body):
        if tag in BREATHER_TEXT_TAGS:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def treatment_wiring_gaps() -> list[str]:
    """Is the long-page treatment actually wired, at all, for any page?

    This is the anti-vacuity half of C4's reading-load arms. The terminal node
    renders on EVERY prose page, so "does this page have a terminal node" is a
    per-page property that can no longer fail once the mark ships -- asserting
    it would be theatre. What can fail is the mechanism: a deleted component, a
    predicate that stopped agreeing with this file's, a route hook that was
    never registered so the marks vanish from the second page onward. Every
    long page's verdict depends on these, so a break here turns every long page
    red again rather than silently passing them all.
    """
    gaps: list[str] = []

    if not DOC_END_VUE.is_file():
        gaps.append(f"{DOC_END_VUE.relative_to(REPO)} is missing -- nothing emits the terminal node")
    else:
        doc_end = js_code(DOC_END_VUE)
        if "wk-doc-end" not in doc_end:
            gaps.append(f"{DOC_END_VUE.relative_to(REPO)} does not emit class `wk-doc-end`, which "
                        "is the class werkstoff.css styles")
        if 'aria-hidden="true"' not in doc_end:
            gaps.append(f"{DOC_END_VUE.relative_to(REPO)} does not set aria-hidden -- the mark "
                        "would be announced as content")

    if not PROSE_PREDICATE_JS.is_file():
        gaps.append(f"{PROSE_PREDICATE_JS.relative_to(REPO)} is missing -- the marks have no "
                    "prose-page scope, so the terminal node lands mid-page on every recipe")
    else:
        predicate = js_code(PROSE_PREDICATE_JS)
        # The runtime predicate must gate on the same signals is_component_rendered()
        # does. These three are named here because this file's own predicate names
        # them; the fourth signal is cross-checked live below.
        for key in ("layout", "beats", "pairings"):
            if not re.search(rf"\bfm\.{key}\b", predicate):
                gaps.append(f"{PROSE_PREDICATE_JS.relative_to(REPO)}: isProsePage() does not gate "
                            f"on `{key}`, so it disagrees with this file's is_component_rendered()")
        # The fourth signal: a globally registered component invoked in a page
        # BODY. Read live from enhanceApp() so registering a new component and
        # forgetting to list it fails here instead of silently mis-scoping both
        # marks on that component's page (docs/catalog/index.md is exactly this
        # case -- prose frontmatter, `<CatalogGrid />` body).
        listed = set(re.findall(r"'([A-Za-z0-9]+)'",
                                re.search(r"COMPONENT_TAGS = \[([^\]]*)\]", predicate).group(1)
                                if re.search(r"COMPONENT_TAGS = \[([^\]]*)\]", predicate) else ""))
        missing = registered_components() - listed
        if missing:
            gaps.append(f"{PROSE_PREDICATE_JS.relative_to(REPO)}: COMPONENT_TAGS is missing "
                        f"{sorted(missing)}, which theme/index.js registers globally -- a page "
                        "whose body invokes one would be graded as prose here and marked as "
                        "prose there, both wrongly")

    if not BREATHERS_JS.is_file():
        gaps.append(f"{BREATHERS_JS.relative_to(REPO)} is missing -- nothing inserts breathers")
    else:
        breathers = js_code(BREATHERS_JS)
        if "wk-breather" not in breathers:
            gaps.append(f"{BREATHERS_JS.relative_to(REPO)} does not emit class `wk-breather`")
        for attr in ('aria-hidden', 'role'):
            if f"'{attr}'" not in breathers:
                gaps.append(f"{BREATHERS_JS.relative_to(REPO)} does not set {attr} -- a breather "
                            "must carry nothing a screen reader announces")
        declared = set(re.findall(r"'(P|UL|OL|[A-Z]+)'",
                                  re.search(r"TEXT_TAGS = new Set\(\[([^\]]*)\]\)", breathers).group(1)
                                  if re.search(r"TEXT_TAGS = new Set\(\[([^\]]*)\]\)", breathers) else ""))
        if declared != BREATHER_TEXT_TAGS:
            gaps.append(f"{BREATHERS_JS.relative_to(REPO)}: TEXT_TAGS is {sorted(declared)} but "
                        f"this file models {sorted(BREATHER_TEXT_TAGS)} -- longest_text_run() "
                        "would count a different thing than the code that inserts the marks")

    if not THEME_INDEX_JS.is_file():
        gaps.append(f"{THEME_INDEX_JS.relative_to(REPO)} is missing")
    else:
        index_js = js_code(THEME_INDEX_JS)
        # Every pattern here is CALL-SHAPED on purpose. Matching a bare
        # identifier matches the `import { onMounted, applyBreathers } from ...`
        # line at the top of the file, so deleting the call while leaving the
        # import -- which is what actually happens when someone rips a hook out
        # -- would leave the guard green. Measured: an identifier-only version
        # of both hook assertions passed with the hooks deleted.
        if not re.search(r"h\(DocEnd\)", index_js):
            gaps.append(f"{THEME_INDEX_JS.relative_to(REPO)}: DocEnd is imported but never "
                        "rendered -- nothing puts the terminal node on the page")
        elif not re.search(r"'doc-footer-before':\s*\(\)\s*=>\s*h\(DocEnd\)", index_js):
            gaps.append(f"{THEME_INDEX_JS.relative_to(REPO)}: DocEnd is rendered, but not from the "
                        "`doc-footer-before` slot -- `doc-after` renders below the whole "
                        "VPDocFooter, which would put the terminal node under 'Edit this page' "
                        "and prev/next, marking the end of the page furniture rather than the "
                        "end of the document")
        # RecipeBeats must NOT be slot-rendered. It is a markdown-body component
        # (theme/index.js explains why: no slot lands inside <main>). Putting it
        # back in a slot would render every recipe's Beats TWICE -- once from the
        # body, once from the slot -- and the page would still look plausible.
        if re.search(r"'doc-[a-z-]+':[^\n]*h\(RecipeBeats\)", index_js):
            gaps.append(f"{THEME_INDEX_JS.relative_to(REPO)}: RecipeBeats is rendered from a layout "
                        "slot as well as the markdown body -- every recipe would emit its Beats "
                        "twice")
        if not re.search(r"applyBreathers\(", index_js):
            gaps.append(f"{THEME_INDEX_JS.relative_to(REPO)}: applyBreathers is imported but "
                        "never called")
        else:
            if not re.search(r"onMounted\(\s*\w", index_js):
                gaps.append(f"{THEME_INDEX_JS.relative_to(REPO)}: breathers are not applied on "
                            "mount, so the first page a reader loads gets none")
            if not re.search(r"watch\(\(\) => route\.path", index_js) and \
               not re.search(r"onAfterRouteChange\s*=", index_js):
                gaps.append(f"{THEME_INDEX_JS.relative_to(REPO)}: breathers are not re-applied on "
                            "route change. VitePress is an SPA -- a mount-only version silently "
                            "does nothing from the second page onward")

    if outline_max_level() < 3:
        gaps.append(f"{CONFIG.relative_to(REPO)}: `outline` stops at h{outline_max_level()}, so a "
                    "long page's h3s never reach the right-hand rail")

    return gaps


def treatment_gaps(body: str, run_min: int) -> list[str]:
    """Which parts of the long-page treatment this particular page does NOT get.

    Empty means the page carries it in full and a length finding against it is
    not actionable. Non-empty is a real defect with a real remedy, and the
    remedy is a source change the author can make.
    """
    gaps: list[str] = []

    if not re.search(r"^### ", body, re.M):
        gaps.append("its outline never reaches h3 (the page has no `###` heading), so the "
                    "right-hand rail offers one flat list and no resumption points")

    run = longest_text_run(body)
    if run < run_min:
        gaps.append(f"no breather is inserted anywhere on it -- its longest run of consecutive "
                    f"top-level text blocks is {run}, below useBreathers.js's RUN_MIN={run_min} "
                    "(a bulleted list is one block, and a `::: details` container ends a run)")

    return gaps


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
    """Reading load, graded against the remedy this check actually prescribes.

    WHY THE TWO LENGTH ARMS ARE CONDITIONAL, and why that is a correctness fix
    rather than a softening
    ----------------------------------------------------------------------
    MAX_PAGE_WORDS and MAX_WORDS_BETWEEN_HEADINGS are measured from the
    MARKDOWN SOURCE, and the remedy both of them name -- the long-page
    treatment: breathers, the terminal node, an outline that reaches h3 -- is
    applied at RUNTIME, in the DOM. Splitting the page is ruled out by the same
    human sign-off that set the numbers. So as originally written, neither arm
    could ever observe its own prescribed fix being applied: the word count is
    identical before and after the treatment lands, and the pages stayed red
    permanently no matter what shipped. A check whose only satisfiable exit is
    a remedy it forbids is not measuring what it claims to measure.

    The thresholds are UNCHANGED. What changed is the predicate they feed: a
    long page, or a long unbroken stretch, is a defect when the page does not
    carry the long-page treatment. Carrying it is not free and not automatic --
    see treatment_gaps() for the two per-page conditions that can fail, and
    treatment_wiring_gaps() for the mechanism every page's verdict rests on.

    WHAT STILL FAILS, so this is not a vacuous pass
    ----------------------------------------------
      * an over-long page or stretch whose outline never reaches h3;
      * an over-long page with no run of consecutive text blocks long enough
        for useBreathers.js to fire on -- a page of tables, code fences or
        `::: details` containers gets no breather however long it is;
      * ANY over-long page at all, the moment the mechanism itself breaks:
        DocEnd deleted, the predicate drifting from is_component_rendered(),
        the route hook dropped so the marks vanish from the second page onward.
    The flat-run arm is deliberately NOT gated. Its remedy is a source change
    (add h3s), the treatment does not touch it, and it can still fail on its own.
    """
    if MAX_FLAT_RUN is None or MAX_PAGE_WORDS is None or MAX_WORDS_BETWEEN_HEADINGS is None:
        report.fail("C4", "reading-load thresholds are unset (MAX_FLAT_RUN, MAX_PAGE_WORDS, "
                          "MAX_WORDS_BETWEEN_HEADINGS) -- set them rather than defaulting, so "
                          "the policy is a decision on the record instead of an accident")
        return

    run_min, every = breather_params()
    wiring = treatment_wiring_gaps()
    for gap_text in wiring:
        report.fail("C4", f"the long-page treatment is not wired: {gap_text}")

    excluded = graded = treated = 0
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

        gap = longest_gap_between_headings(body)
        over_long_page = words > MAX_PAGE_WORDS
        over_long_gap = gap > MAX_WORDS_BETWEEN_HEADINGS
        if not (over_long_page or over_long_gap):
            continue

        # Only pages that are actually over a length threshold are asked
        # whether they carry the treatment. Asking a short page would be noise:
        # the treatment exists to make length survivable, and a page that is
        # not long has nothing to survive.
        missing = wiring + treatment_gaps(body, run_min)
        if not missing:
            treated += 1
            report.checks_run.append(
                f"C4 long-page treatment carried: {rel} "
                f"({words} words, longest stretch {gap}) -- outline reaches h3 and its longest "
                f"text-block run of {longest_text_run(body)} is at or over RUN_MIN={run_min}, so "
                f"useBreathers.js inserts a breather every {every}th block; the terminal node "
                "closes the page"
            )
            continue

        reasons = "; ".join(missing)
        if over_long_page:
            report.fail("C4", f"{rel}: {words} words (~{words // 220} min read, max {MAX_PAGE_WORDS}) "
                              "and the page does NOT carry the full long-page treatment "
                              "(breathers, the terminal node, and an outline that reaches h3). "
                              f"Splitting it is out of scope for this check; what is missing: {reasons}")
        if over_long_gap:
            report.fail("C4", f"{rel}: {gap} words in the longest stretch between headings "
                              f"(max {MAX_WORDS_BETWEEN_HEADINGS}) -- a reader who looks away in "
                              "this stretch has no landmark to resume from, and the page does NOT "
                              f"carry the long-page treatment that would give them one: {reasons}")

    report.checks_run.append(
        f"C4 component-page exclusion: {excluded} of {excluded + graded} published pages are "
        f"component-rendered (frontmatter-driven beats/pairings, or a home layout) and excluded "
        f"from reading-load grading; {graded} genuine prose pages graded"
    )
    report.checks_run.append(
        f"C4 long-page treatment: wired ({len(wiring)} wiring defects), carried by {treated} of "
        f"the graded pages that exceed a length threshold"
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
