#!/usr/bin/env python3
"""Generate docs/prompt-index.md from every plugin README's Example Prompts section.

The per-plugin prompts are authored in each `plugins/<name>/README.md`, which is
where they belong -- a reader installing one plugin should find its prompts in
its own README. This script collects them onto one page so a reader browsing the
docs site can see the whole surface at once, WITHOUT that page becoming a second
hand-maintained copy that drifts the moment a README gains a prompt.

The output is a tracked artifact: `.rrt.toml` registers it as an artifact_target,
so `rrt artifacts --check --strict` fails if the generated page no longer matches
the READMEs it came from. Regenerate with `rrt artifacts --regenerate`, or by
running this script directly.

Parsing is line-based on purpose. The prompt idiom is:

    ##### <label>

    ````prompt
    "<the prompt text>"
    ````

    > <annotation naming the skill it triggers>

A regex spanning that whole shape would be exactly the kind of pattern this
repository has repeatedly been burned by -- one that matches nothing and reports
success. A line scanner either finds a block or it does not, and this script
fails loudly when a README's section yields zero prompts.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGINS = REPO / "plugins"
OUTPUT = REPO / "docs" / "prompt-index.md"

SECTION_HEADING = "## Example Prompts"
PROMPT_LABEL = "##### "
FENCE = "````"


def parse_readme(path: Path) -> list[dict]:
    """Return every prompt block in this README's Example Prompts section."""
    lines = path.read_text(encoding="utf-8").splitlines()
    prompts: list[dict] = []

    in_section = False
    index = 0
    while index < len(lines):
        line = lines[index]

        if line.startswith(SECTION_HEADING):
            in_section = True
            index += 1
            continue

        # Any other H2 closes the section. H3-H6 stay inside it.
        if in_section and line.startswith("## ") and not line.startswith(SECTION_HEADING):
            break

        if in_section and line.startswith(PROMPT_LABEL):
            label = line[len(PROMPT_LABEL):].strip()
            body: list[str] = []
            note: list[str] = []
            cursor = index + 1

            # Walk to the opening fence, stopping if the next prompt starts first.
            while cursor < len(lines) and not lines[cursor].startswith(FENCE):
                if lines[cursor].startswith(PROMPT_LABEL) or lines[cursor].startswith("## "):
                    break
                cursor += 1

            if cursor < len(lines) and lines[cursor].startswith(FENCE):
                cursor += 1
                while cursor < len(lines) and not lines[cursor].startswith(FENCE):
                    body.append(lines[cursor])
                    cursor += 1
                cursor += 1  # step past the closing fence

                # Collect the blockquote annotation that follows, if any.
                while cursor < len(lines) and not lines[cursor].strip():
                    cursor += 1
                while cursor < len(lines) and lines[cursor].startswith(">"):
                    note.append(lines[cursor].lstrip(">").strip())
                    cursor += 1

            if body:
                prompts.append({"label": label, "body": body, "note": " ".join(note).strip()})
            index = cursor
            continue

        index += 1

    return prompts


def main() -> int:
    plugin_dirs = sorted(d for d in PLUGINS.iterdir() if (d / "README.md").is_file())
    if not plugin_dirs:
        print("error: no plugin READMEs found", file=sys.stderr)
        return 1

    collected: list[tuple[str, list[dict]]] = []
    empty: list[str] = []
    for plugin_dir in plugin_dirs:
        prompts = parse_readme(plugin_dir / "README.md")
        if not prompts:
            empty.append(plugin_dir.name)
        collected.append((plugin_dir.name, prompts))

    if empty:
        # A plugin README with an Example Prompts heading but no parsed prompt means
        # the idiom changed and this script is now silently under-reporting.
        print(f"error: no prompts parsed for: {', '.join(empty)}", file=sys.stderr)
        return 1

    total = sum(len(p) for _, p in collected)
    out: list[str] = []
    out.append("# Prompt index by plugin")
    out.append("")
    out.append(
        f"Every example prompt shipped by the {len(collected)} plugin READMEs, {total} in"
    )
    out.append(
        "total, collected on one page. This is the plugin-indexed view; for the task-indexed"
    )
    out.append("view — which skill fires at which moment of a piece of work — see the")
    out.append("[prompt catalog](/catalog/).")
    out.append("")
    out.append("This page is generated from the plugin READMEs by")
    out.append("`tools/prompt-index/build_prompt_index.py` and tracked as an artifact, so it")
    out.append("cannot drift from them. Edit the prompts in their own README, never here.")
    out.append("")

    for name, prompts in collected:
        out.append(f"## {name}")
        out.append("")
        out.append(f"[`plugins/{name}/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/{name}/README.md) — {len(prompts)} prompts.")
        out.append("")
        for prompt in prompts:
            # h3, not the h5 the source READMEs use. PROMPT_LABEL above is the
            # PARSER's pattern for reading those READMEs and is deliberately
            # unchanged; this is the emitted level. At h5 the right-hand outline
            # showed only the nine plugin names, so 98 prompts were unnavigable and
            # the page was nine consecutive h2s with nothing between them -- which
            # is what test/docs/docs_ux_audit.py's C4 flags once a ninth plugin
            # exists (it did, from lehre onward, and had been red on main since).
            out.append(f"### {prompt['label']}")
            out.append("")
            out.append(FENCE + "prompt")
            out.extend(prompt["body"])
            out.append(FENCE)
            out.append("")
            if prompt["note"]:
                out.append(f"> {prompt['note']}")
                out.append("")

    OUTPUT.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO)}: {total} prompts across {len(collected)} plugins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
