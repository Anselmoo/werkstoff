# Python CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`argparse` (stdlib) in the entry point. The core module **imports no CLI
framework and never touches `sys.argv`**.

## Project layout (Pillar 2: core separation)
```
<app>/
  pyproject.toml
  src/<app>/__init__.py
  src/<app>/core.py    # pure logic, zero argparse/sys.argv
  src/<app>/cli.py     # thin entry: parse -> core -> format -> exit
  tests/test_help_snapshot.py
  cli-scaffold.manifest.json
```
`core_files: ["src/<app>/core.py"]`, `entry_file: "src/<app>/cli.py"`.

## Help & completions (Pillar 1)
argparse renders `--help` (Usage, positional Arguments, Options). `argcomplete`
provides bash/zsh completion.

## NO_COLOR (Pillar 3)
Gate ANSI on `os.environ.get("NO_COLOR")` being falsy.

## Exit codes (Pillar 3)
`sys.exit(...)` mapped to the frozen contract; argparse exits the usage code on
parse error. Wrap the core call and map caught exceptions to the runtime code.

## --json / --no-input (Pillar 5)
`--json` serializes with the stdlib `json` module. `--no-input` disables prompts;
missing required input then exits the usage code. Use `sys.stdin.isatty()` to
fail fast when non-interactive.

## stdout / stderr (Pillar 5)
Results via `print(...)`; diagnostics via `print(..., file=sys.stderr)`.

## Distribution (Pillar 4)
**PyPI**: `pyproject.toml` with a `[project.scripts]` console entry point,
built with `python -m build`, uploaded with `twine`.

## Snapshot testing (Pillar 3)
`pytest` + `syrupy`: capture `--help` output and assert against the stored snapshot.

## Worked example (sketch)
```python
# core.py — no argparse
def greet(name: str) -> str:
    if not name:
        raise ValueError("name required")
    return f"Hello, {name}"
```
```python
# cli.py — thin
import argparse, json, os, sys
from .core import greet
def main(argv=None):
    p = argparse.ArgumentParser(prog="<app>")
    p.add_argument("name", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("-n", "--no-input", action="store_true")
    args = p.parse_args(argv)                      # parse error -> exit 2
    _no_color = os.environ.get("NO_COLOR")
    if args.name is None and (args.no_input or not sys.stdin.isatty()):
        print("error: name required", file=sys.stderr); return 2
    try:
        msg = greet(args.name or "")
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr); return 1
    print(json.dumps({"message": msg}) if args.json else msg)
    return 0
if __name__ == "__main__":
    sys.exit(main())
```
