#!/usr/bin/env python3
"""Shared path resolution and flag defaults for the nacharbeit scripts.

Every nacharbeit CLI needs the same four roots, and every one of them used to
derive them with `ROOT = HERE.parent.parent` -- which resolves to the repo when
the script lives in `tools/prompt-review/` and to `plugins/nacharbeit` once it
lives inside the plugin. One place computes them; the CLIs only add flags.

    plugin_root()   the plugin directory (parent of scripts/)
    repo_root()     the working directory the scripts are run from, or --repo-root
    rubric_path()   <plugin>/references/rubric.md unless --rubric overrides it
    state_dir()     <repo>/analysis/nacharbeit unless --state-dir overrides it

Usage: imported, never run. `python3 nacharbeit_common.py` prints the resolved
defaults for the current directory so a puzzled operator can see them.
Exit: 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
DEFAULT_STATE_DIR = Path("analysis/nacharbeit")
DEFAULT_PLUGINS_ROOT = Path("plugins")
DEFAULT_FIXTURES_ROOT = Path("test/plugins/fixtures/nacharbeit")
DEFAULT_DOCS_ROOT = Path("docs")
DEFAULT_REPORT_OUT = Path("docs/prompt-quality-findings.md")
DEFAULT_KNOWN_ANSWERS = Path("docs/prompt-index.md")
DEFAULT_MARKETPLACE = Path(".claude-plugin/marketplace.json")
DEFAULT_PROMPT_INDEX_SCRIPT = Path("tools/prompt-index/build_prompt_index.py")
DEFAULT_CONTRACT_DIFF = Path("tools/plugin-serializer/contract_diff.py")
DEFAULT_WRITE_ROOTS = ("plugins/", "tools/")
DEFAULT_ARTIFACT_COPIES = {
    "references/parallel-safe-research-protocol.md": "tools/symbol-indexer/parallel-safe-research-protocol.md",
}
DEFAULT_SKIP_LINT = ("M-DUP-CONTENT", "P-MARKETPLACE-MEMBER")
DEFAULT_REPO_NAME = "this plugin set"
DEFAULT_REPO_NOTES = ""

# werkstoff itself carries two notes the review must repeat verbatim; any other repo
# passes its own with --repo-notes or none at all.
WERKSTOFF_REPO_NOTES = (
    "Report once, as a nit, that codebase-consistency ships commands rather than skills "
    "(rubric F6); do not repeat it elsewhere."
)


def plugin_root() -> Path:
    return PLUGIN_ROOT


def repo_root(override: Path | None = None) -> Path:
    return (override or Path.cwd()).resolve()


def rubric_path(override: Path | None = None) -> Path:
    return (override or (PLUGIN_ROOT / "references" / "rubric.md")).resolve()


def state_dir(override: Path | None = None, root: Path | None = None) -> Path:
    if override is not None:
        return override if override.is_absolute() else repo_root(root) / override
    return repo_root(root) / DEFAULT_STATE_DIR


def is_werkstoff(root: Path | None = None) -> bool:
    """True when the working directory is the werkstoff workshop itself, which is the
    only repo whose defaults (VitePress report, F6 note, artifact copies) should apply."""
    r = repo_root(root)
    return (r / ".rrt.toml").is_file() and (r / "plugins" / "nacharbeit" / ".claude-plugin" / "plugin.json").is_file()


def rel(p: Path, root: Path | None = None) -> str:
    """Repo-relative POSIX path when p is under the repo, else the path unchanged."""
    r = repo_root(root)
    q = p if p.is_absolute() else (r / p)
    try:
        return q.resolve().relative_to(r).as_posix()
    except ValueError:
        return p.as_posix()


def main() -> int:
    print(f"plugin_root  {plugin_root()}")
    print(f"repo_root    {repo_root()}")
    print(f"rubric       {rubric_path()}")
    print(f"state_dir    {state_dir()}")
    print(f"werkstoff    {is_werkstoff()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
