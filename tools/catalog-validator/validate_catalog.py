#!/usr/bin/env python3
"""Validate docs/catalog/**/*.md recipes against werkstoff's real capability surface.

PR #44 added a per-recipe prompt catalog under docs/catalog/<category>/*.md, each
with frontmatter (`task`, `category`, `summary`, `external`, `beats`, `grounding`)
listing an ordered sequence of skill/agent "beats". Its own description called out
what it deliberately left out: a validator that fails CI when a recipe names a
skill docs/.vitepress/data/surface.json doesn't contain. This is that validator.

What it checks, per recipe file:
    1. The six required frontmatter keys are present and non-empty (`external` is
       allowed to be an empty list -- docs/catalog/index.md documents that as the
       "werkstoff-only" convention, not a defect).
    2. `category` matches the name of the directory the file lives in.
    3. `category` is one of the category directories actually present under
       docs/catalog/ (derived live from the filesystem at run time, never from a
       hardcoded list -- a stale list is exactly the drift this tool exists to
       prevent elsewhere, so it must not reintroduce the same failure mode here).
    4. Every beat has non-empty `skill` and `why` (`prompt` is optional; its
       absence is never a failure).
    5. The rendered body contains both `<RecipeHeader />` and `<RecipeBeats />`.
       These are global Vue components (registered in docs/.vitepress/theme/index.js)
       that render the page's <h1>/summary and its Beats section from the very
       frontmatter above. They live in the markdown body rather than a layout slot
       because no VitePress slot lands inside <main>: `doc-after` renders below the
       prev/next footer (which is how 37 recipes shipped with their Beats under the
       navigation), and `doc-footer-before` renders inside a <footer> that is a
       contentinfo landmark. A recipe that omits a component renders NOTHING where
       its content should be -- no error, no warning, just a page missing its whole
       point -- so it is checked here rather than left to review.
    6. Every beat's `skill` id, when its `plugin:` namespace matches one of
       werkstoff's own 9 plugins, must resolve to a real skill or agent id in
       surface.json. A namespace that does not match any werkstoff plugin (e.g.
       `superpowers:*`, `pr-review-toolkit:*`) is counted as "external,
       unchecked" rather than failed or silently ignored -- this tool has no
       ground truth for it, but a typo'd external namespace should still show up
       as suspicious in the summary line.
    6. `openingPrompt`, `dos`, and `donts` are all OPTIONAL frontmatter keys --
       their absence is never a failure, exactly like `prompt` on a beat. When
       present: `openingPrompt` must be a non-empty string; `dos` and `donts`
       must each be a non-empty list of non-empty strings.

Files with no YAML frontmatter at all, or with frontmatter that shares none of the
recipe's required keys, are skipped -- that's genuinely not a recipe. Files with
frontmatter that has some recipe-shaped keys but is missing required ones (like a
missing `category`) are treated as mis-authored recipes and validated as such,
generating failure reports for missing keys.

Frontmatter parsing uses PyYAML. Unlike tools/surface-index/build_surface_index.py's
flat SKILL.md/agent frontmatter (scalars and simple string lists only), a recipe's
`beats` field is a list of mappings nested under a top-level key -- a shape a
hand-rolled line-based parser cannot handle without effectively reimplementing a
YAML parser. PyYAML is already a hard dependency of this job (plugin-checks.yml
installs it via `pip install pyyaml` before any Python check runs), so this tool
requires it rather than duplicating build_surface_index.py's optional fallback for
a substantially more complex grammar. The frontmatter *block extraction* -- finding
the text between the first two `---` lines -- is still done line by line, never a
regex spanning the whole file, matching this repo's stated discipline (see
CLAUDE.md's defect table: a dotall-style pattern across a whole file is exactly the
shape of bug this repo has been burned by before).

House style, matched from build_surface_index.py: collect every failure across
every file rather than stopping at the first one, and raise a named exception
class instead of returning a partial/empty result on anything that must fail
loudly.

Usage:
    python3 tools/catalog-validator/validate_catalog.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeGuard

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML installed
    yaml = None

REPO = Path(__file__).resolve().parents[2]
CATALOG_DIR = REPO / "docs" / "catalog"
SURFACE_PATH = REPO / "docs" / ".vitepress" / "data" / "surface.json"

REQUIRED_STRING_KEYS = ("task", "category", "summary", "grounding")
REQUIRED_LIST_KEYS = ("external", "beats")
REQUIRED_KEYS = REQUIRED_STRING_KEYS + REQUIRED_LIST_KEYS

#: Global Vue components every recipe body must mount. Substring checks, not a
#: regex: these are fixed literals, and a regex over markdown containing angle
#: brackets and slashes is precisely the shape this repo's CLAUDE.md documents as
#: matching nothing while reporting success.
REQUIRED_BODY_COMPONENTS = ("<RecipeHeader />", "<RecipeBeats />")


class CatalogValidatorError(RuntimeError):
    """Raised for anything that must fail loudly rather than silently under-report."""


@dataclass
class Surface:
    """The subset of surface.json this tool needs: known ids and plugin names."""

    known_ids: set[str]
    known_plugins: set[str]


@dataclass
class ValidationReport:
    failures: list[str] = field(default_factory=list)
    files_checked: int = 0
    external_unchecked: int = 0

    @property
    def ok(self) -> bool:
        return not self.failures


# --------------------------------------------------------------------------
# Surface loading
# --------------------------------------------------------------------------


def load_surface(surface_path: Path) -> Surface:
    if not surface_path.is_file():
        raise CatalogValidatorError(
            f"{surface_path}: not found -- run "
            "python3 tools/surface-index/build_surface_index.py first"
        )
    try:
        data = json.loads(surface_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogValidatorError(f"{surface_path}: invalid JSON: {exc}") from exc

    plugins = data.get("plugins")
    skill_ids = data.get("skillIds")
    agent_ids = data.get("agentIds")
    if not isinstance(plugins, list):
        raise CatalogValidatorError(f"{surface_path}: expected a 'plugins' list")
    if not isinstance(skill_ids, list) or not isinstance(agent_ids, list):
        raise CatalogValidatorError(
            f"{surface_path}: expected 'skillIds' and 'agentIds' lists"
        )

    known_plugins = {p["name"] for p in plugins if isinstance(p, dict) and "name" in p}
    known_ids = {str(i) for i in skill_ids} | {str(i) for i in agent_ids}
    return Surface(known_ids=known_ids, known_plugins=known_plugins)


# --------------------------------------------------------------------------
# Category discovery
# --------------------------------------------------------------------------


def discover_recognized_categories(catalog_dir: Path) -> set[str]:
    """Recognized categories = direct subdirectories of docs/catalog/ that
    contain at least one .md file, derived live every run. Never hardcoded --
    a hardcoded list here would be exactly the kind of documentation-drifts-
    from-reality bug this whole catalog validator exists to catch elsewhere.
    """
    if not catalog_dir.is_dir():
        raise CatalogValidatorError(f"no catalog directory found at {catalog_dir}")
    return {
        child.name
        for child in catalog_dir.iterdir()
        if child.is_dir() and any(child.glob("*.md"))
    }


# --------------------------------------------------------------------------
# Frontmatter parsing
# --------------------------------------------------------------------------


def extract_frontmatter_block(path: Path) -> str | None:
    """Return the raw text between the first two '---' lines, or None if the
    file has no opening '---' at all (docs/catalog/index.md and
    docs/catalog/_UNRESOLVED.md by convention -- not recipes).

    Line-based scan, never a regex spanning the whole file -- see module
    docstring.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise CatalogValidatorError(f"{path}: unterminated frontmatter (no closing '---')")

    return "\n".join(lines[1:end])


def extract_body(path: Path) -> str:
    """Everything after the closing '---' of the frontmatter block.

    Line-based, mirroring extract_frontmatter_block: a file with no frontmatter
    is all body, which is the correct reading for a non-recipe page.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return "\n".join(lines)
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :])
    return ""


def strip_non_rendering(body: str) -> str:
    """Return only the lines of a markdown body that render as live markup.

    Why this exists: the component check below is a substring search, and a
    recipe that merely *documents* the pattern would satisfy a naive search
    while rendering none of the component's output. That is a check reporting
    a pass it did not earn -- the failure class this validator exists to
    prevent -- so the tool must not commit it itself.

    Four non-rendering contexts are removed, each verified by a probe that
    false-passed before it was handled:

        ```lang fences and ~~~ fences      a documented example
        <!-- ... --> HTML comments         a commented-out mount
        four-space indented code blocks    an indented example
        `inline code spans`                a prose mention

    Indentation is handled by dropping any line indented four or more spaces
    rather than by modelling markdown's indented-code rules, which need list
    context to get right. That is deliberately strict: every real recipe mounts
    its components at column zero, and the two error directions are not
    symmetric. A false FAIL is loud, names the file, and takes seconds to fix;
    a false PASS ships a page silently missing its entire content.

    Line-based throughout, never a regex spanning the file (see module
    docstring). Fences match on the opening run length so a ```` block
    containing ``` is not closed early -- this repo's own prompt fences are
    four backticks for exactly that reason.
    """
    out: list[str] = []
    fence_char = ""
    fence_len = 0
    in_comment = False

    for raw in body.split("\n"):
        line = raw

        # HTML comments first: a comment may wrap a fence, and a fence opened
        # inside a comment is not a fence at all.
        if in_comment:
            closer = line.find("-->")
            if closer == -1:
                continue
            line = line[closer + 3 :]
            in_comment = False
        while True:
            opener = line.find("<!--")
            if opener == -1:
                break
            closer = line.find("-->", opener + 4)
            if closer == -1:
                line = line[:opener]
                in_comment = True
                break
            line = line[:opener] + line[closer + 3 :]

        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        run_char = stripped[:1]
        if indent <= 3 and run_char in ("`", "~"):
            run = len(stripped) - len(stripped.lstrip(run_char))
            if run >= 3:
                if not fence_char:
                    fence_char, fence_len = run_char, run
                    continue
                if run_char == fence_char and run >= fence_len and not stripped[run:].strip():
                    fence_char, fence_len = "", 0
                    continue
        if fence_char:
            continue  # inside a fenced block
        if indent >= 4:
            continue  # indented code block, not rendered markup
        out.append(_strip_inline_code(line))
    return "\n".join(out)


def _strip_inline_code(line: str) -> str:
    """Remove `...` inline code spans from one line.

    Split on backticks and keep the even-indexed pieces: an unclosed span
    leaves a trailing odd piece, which is dropped, so a half-written span
    cannot smuggle a component mention through either.
    """
    if "`" not in line:
        return line
    parts = line.split("`")
    return "".join(parts[i] for i in range(0, len(parts), 2))


def validate_body(body: str) -> list[str]:
    """Check the markdown body mounts both recipe components, as live markup."""
    rendered = strip_non_rendering(body)
    failures: list[str] = []
    for component in REQUIRED_BODY_COMPONENTS:
        if component not in rendered:
            failures.append(
                f"body does not mount {component} as rendered markup -- the page would "
                f"render without the content that component produces, silently and with "
                f"no error (a mention inside a code fence, HTML comment, indented code block "
                f"or inline code span does not count)"
            )
    return failures


def try_parse_frontmatter(path: Path) -> dict | None:
    """Parse a recipe candidate's frontmatter. Returns None when the file has
    no frontmatter block at all -- the caller treats that as "not a recipe,
    skip". Raises CatalogValidatorError for a frontmatter block that exists
    but fails to parse -- that IS a real file that needs fixing, not a file
    to quietly skip.
    """
    block = extract_frontmatter_block(path)
    if block is None:
        return None
    if not block.strip():
        raise CatalogValidatorError(f"{path}: frontmatter block is empty")
    if yaml is None:
        raise CatalogValidatorError(
            f"{path}: PyYAML is required to parse recipe frontmatter "
            "(beats is a nested list-of-mappings shape a hand-rolled parser "
            "cannot handle safely) -- install it with `pip install pyyaml`"
        )
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise CatalogValidatorError(f"{path}: frontmatter failed to parse as YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogValidatorError(f"{path}: frontmatter did not parse to a mapping")
    return data


# --------------------------------------------------------------------------
# Per-recipe validation
# --------------------------------------------------------------------------


def _is_nonempty_str(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip())


def validate_required_keys(frontmatter: dict) -> list[str]:
    failures = []
    for key in REQUIRED_KEYS:
        if key not in frontmatter:
            failures.append(f"missing required key '{key}'")
            continue
        value = frontmatter[key]
        if key in REQUIRED_STRING_KEYS:
            if not _is_nonempty_str(value):
                failures.append(f"required key '{key}' is empty")
        elif key == "external":
            if not isinstance(value, list):
                failures.append("'external' must be a list (may be empty)")
        elif key == "beats":
            if not isinstance(value, list) or not value:
                failures.append("'beats' must be a non-empty list")
    return failures


def validate_category(frontmatter: dict, directory_name: str, recognized_categories: set[str]) -> list[str]:
    category = frontmatter.get("category")
    if not _is_nonempty_str(category):
        # Already reported by validate_required_keys; nothing further to check.
        return []

    failures = []
    if category != directory_name:
        failures.append(
            f"category '{category}' does not match its containing directory '{directory_name}'"
        )
    if category not in recognized_categories:
        failures.append(
            f"category '{category}' is not a recognized category "
            f"(recognized: {sorted(recognized_categories)})"
        )
    return failures


def validate_beats(frontmatter: dict, surface: Surface) -> tuple[list[str], int]:
    beats = frontmatter.get("beats")
    if not isinstance(beats, list):
        # Already reported by validate_required_keys.
        return [], 0

    failures = []
    external_unchecked = 0
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            failures.append(f"beats[{index}] is not a mapping")
            continue

        skill = beat.get("skill")
        why = beat.get("why")
        if not _is_nonempty_str(skill):
            failures.append(f"beats[{index}] missing or empty 'skill'")
        if not _is_nonempty_str(why):
            failures.append(f"beats[{index}] missing or empty 'why'")
        # `prompt` is optional -- its absence is never a failure, deliberately
        # not checked here at all.

        if not _is_nonempty_str(skill):
            continue

        if ":" not in skill:
            failures.append(f"beats[{index}] skill '{skill}' is not in 'plugin:skill' form")
            continue

        namespace = skill.split(":", 1)[0]
        if namespace in surface.known_plugins:
            if skill not in surface.known_ids:
                failures.append(
                    f"beats[{index}] skill '{skill}' not found among "
                    f"'{namespace}' plugin's skills/agents in surface.json"
                )
        else:
            external_unchecked += 1

    return failures, external_unchecked


def _is_nonempty_str_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_nonempty_str(item) for item in value)


def validate_optional_reader_affordances(frontmatter: dict) -> list[str]:
    """`openingPrompt`, `dos`, and `donts` are all OPTIONAL -- a recipe missing
    any or all of them is not a failure, exactly like a beat's `prompt`. This
    only fires when one of the three keys is actually present and malformed.
    """
    failures = []

    if "openingPrompt" in frontmatter:
        opening_prompt = frontmatter["openingPrompt"]
        if not _is_nonempty_str(opening_prompt):
            failures.append("'openingPrompt' must be a non-empty string when present")

    for key in ("dos", "donts"):
        if key not in frontmatter:
            continue
        value = frontmatter[key]
        if not _is_nonempty_str_list(value):
            failures.append(f"'{key}' must be a non-empty list of non-empty strings when present")

    return failures


def validate_recipe(
    frontmatter: dict, directory_name: str, surface: Surface, recognized_categories: set[str]
) -> tuple[list[str], int]:
    failures: list[str] = []
    failures.extend(validate_required_keys(frontmatter))
    failures.extend(validate_category(frontmatter, directory_name, recognized_categories))
    beat_failures, external_unchecked = validate_beats(frontmatter, surface)
    failures.extend(beat_failures)
    failures.extend(validate_optional_reader_affordances(frontmatter))
    return failures, external_unchecked


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------


def validate_catalog(catalog_dir: Path, surface_path: Path) -> ValidationReport:
    surface = load_surface(surface_path)
    recognized_categories = discover_recognized_categories(catalog_dir)

    report = ValidationReport()
    for path in sorted(catalog_dir.glob("**/*.md")):
        try:
            frontmatter = try_parse_frontmatter(path)
        except CatalogValidatorError as exc:
            report.files_checked += 1
            report.failures.append(f"{path}: {exc}")
            continue

        if frontmatter is None:
            continue  # no frontmatter at all -- not a recipe (e.g. index.md)
        if not any(key in frontmatter for key in REQUIRED_KEYS):
            continue  # frontmatter present but shares none of the recipe's
            # required keys -- genuinely not a recipe, not a mis-authored one

        report.files_checked += 1
        directory_name = path.parent.name
        failures, external_unchecked = validate_recipe(
            frontmatter, directory_name, surface, recognized_categories
        )
        failures.extend(validate_body(extract_body(path)))
        report.external_unchecked += external_unchecked
        for reason in failures:
            report.failures.append(f"{path}: {reason}")

    return report


def render_report(report: ValidationReport, catalog_dir: Path, repo: Path) -> str:
    lines = []
    for failure in report.failures:
        try:
            failure_path, _, reason = failure.partition(": ")
            rel = Path(failure_path).resolve().relative_to(repo)
            failure = f"{rel}: {reason}"
        except (ValueError, OSError):
            pass
        lines.append(failure)
    lines.append(
        f"checked {report.files_checked} recipe(s) under {catalog_dir.relative_to(repo) if catalog_dir.is_relative_to(repo) else catalog_dir}: "
        f"{len(report.failures)} failure(s), {report.external_unchecked} external-unchecked beat(s)"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-dir",
        type=Path,
        default=CATALOG_DIR,
        help=f"directory of recipe markdown files (default: {CATALOG_DIR.relative_to(REPO)})",
    )
    parser.add_argument(
        "--surface",
        type=Path,
        default=SURFACE_PATH,
        help=f"path to surface.json (default: {SURFACE_PATH.relative_to(REPO)})",
    )
    args = parser.parse_args(argv)

    try:
        report = validate_catalog(args.catalog_dir, args.surface)
    except CatalogValidatorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = render_report(report, args.catalog_dir, REPO)
    if report.ok:
        print(output)
        return 0
    print(output, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
