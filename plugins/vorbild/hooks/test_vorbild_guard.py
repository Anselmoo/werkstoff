#!/usr/bin/env python3
"""Calibration for vorbild_guard.py — it must DENY and it must ALLOW.

A guard that denies everything is as broken as one that denies nothing, and only the
first kind gets noticed. Every rule below is asserted in both directions, and the
negative cases are the ones that matter: this guard's whole design claim is that it
polices two paths inside one directory and nothing else.

Run: python3 plugins/vorbild/hooks/test_vorbild_guard.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "vorbild_guard.py"

DENY = 2
ALLOW = 0


def run(cwd: Path, file_path: str, env: dict[str, str] | None = None) -> tuple[int, str]:
    event = json.dumps(
        {"cwd": str(cwd), "tool_name": "Edit", "tool_input": {"file_path": file_path}}
    )
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=event,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **(env or {})},
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def run_input(cwd: Path, tool_input: dict, tool: str = "MultiEdit") -> tuple[int, str]:
    event = json.dumps({"cwd": str(cwd), "tool_name": tool, "tool_input": tool_input})
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=event,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def design_repo(tmp: Path, *, choice: dict | None = None, root: str = ".design") -> Path:
    (tmp / root / "references" / "hig").mkdir(parents=True, exist_ok=True)
    (tmp / root / "references" / "hig" / "type.css").write_text(":root{}\n")
    (tmp / root / "system").mkdir(parents=True, exist_ok=True)
    (tmp / root / "out").mkdir(parents=True, exist_ok=True)
    if choice is not None:
        (tmp / root / "system" / "spread-choice.json").write_text(json.dumps(choice))
    return tmp


CASES: list[tuple[str, int, str]] = []


def case(name: str, expected: int, got: int, blob: str, needle: str = "") -> None:
    ok = got == expected and (not needle or needle in blob)
    CASES.append((name, expected, "PASS" if ok else f"FAIL (exit {got})"))
    if not ok:
        print(f"  !! {name}: expected exit {expected}, got {got}")
        if needle and needle not in blob:
            print(f"     reason did not mention {needle!r}")
        print(f"     output: {blob[:300]}")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw).resolve()

        # --- inertness: no design root at all -------------------------------
        plain = tmp / "plain"
        (plain / "src").mkdir(parents=True)
        code, out = run(plain, "src/api.py")
        case("inert: no design root, unrelated edit allowed", ALLOW, code, out)
        code, out = run(plain, "references/anything.css")
        case("inert: 'references/' outside a design root allowed", ALLOW, code, out)

        # --- rule 1: references are read-only -------------------------------
        r1 = design_repo(tmp / "r1")
        code, out = run(r1, ".design/references/hig/type.css")
        case("rule1: edit inside references/ denied", DENY, code, out, "read-only")
        code, out = run(r1, str(r1 / ".design/references/hig/type.css"))
        case("rule1: absolute path into references/ denied", DENY, code, out, "read-only")
        code, out = run(r1, ".design/system/DECODE.md")
        case("rule1: writing a Design Card allowed", ALLOW, code, out)
        code, out = run(r1, "src/api.py")
        case("rule1: edit elsewhere in the repo allowed", ALLOW, code, out)
        code, out = run(r1, ".design/references/hig/type.css", {"VORBILD_DISABLE_GUARD": "1"})
        case("rule1: escape hatch releases the deny", ALLOW, code, out)

        # --- MultiEdit payload shapes: the silent-bypass class ---------------
        # A guard whose matcher lists MultiEdit but which only reads `file_path` finds
        # no target on these payloads and allows them. That is the defect shape this
        # repo keeps hitting: correct-looking code that quietly does nothing.
        code, out = run_input(r1, {"edits": [{"file_path": ".design/references/hig/type.css"}]})
        case("multiedit: edits[].file_path into references/ denied", DENY, code, out, "read-only")
        code, out = run_input(r1, {"file_paths": ["src/ok.py", ".design/references/hig/type.css"]})
        case("multiedit: one guarded path among many still denies", DENY, code, out, "read-only")
        code, out = run_input(r1, {"edits": [{"file_path": "src/a.py"}, {"file_path": "src/b.py"}]})
        case("multiedit: all-unrelated payload allowed", ALLOW, code, out)
        code, out = run_input(r1, {"edits": []})
        case("multiedit: empty payload allowed", ALLOW, code, out)

        # --- rule 2: forced choice gates tokens.json and out/ ----------------
        open_choice = design_repo(tmp / "r2open", choice={"id": "spread-01", "chosen": ""})
        code, out = run(open_choice, ".design/system/tokens.json")
        case("rule2: tokens.json denied while choice open", DENY, code, out, "spread-01")
        code, out = run(open_choice, ".design/out/sketchbook.html")
        case("rule2: out/ denied while choice open", DENY, code, out, "spread-01")
        code, out = run(open_choice, ".design/system/LEXIKON.md")
        case("rule2: other system/ files still allowed", ALLOW, code, out)

        answered = design_repo(tmp / "r2done", choice={"id": "spread-01", "chosen": "b"})
        code, out = run(answered, ".design/system/tokens.json")
        case("rule2: tokens.json allowed once chosen", ALLOW, code, out)
        code, out = run(answered, ".design/out/sketchbook.html")
        case("rule2: out/ allowed once chosen", ALLOW, code, out)

        no_record = design_repo(tmp / "r2none")
        code, out = run(no_record, ".design/system/tokens.json")
        case("rule2: no spread record at all -> not a gate", ALLOW, code, out)

        corrupt = design_repo(tmp / "r2bad")
        (corrupt / ".design/system/spread-choice.json").write_text("{not json")
        code, out = run(corrupt, ".design/system/tokens.json")
        case("rule2: unparseable record denies (not 'no decision made')", DENY, code, out)

        # --- settings: configurable root, enforcement off -------------------
        custom = tmp / "custom"
        design_repo(custom, root="docs/design")
        (custom / ".claude").mkdir(parents=True, exist_ok=True)
        (custom / ".claude/vorbild.local.md").write_text("---\nroot: docs/design\n---\n")
        code, out = run(custom, "docs/design/references/hig/type.css")
        case("settings: configured root is honoured", DENY, code, out, "read-only")
        code, out = run(custom, ".design/references/hig/type.css")
        case("settings: default root not policed once overridden", ALLOW, code, out)

        off = design_repo(tmp / "off")
        (off / ".claude").mkdir(parents=True, exist_ok=True)
        (off / ".claude/vorbild.local.md").write_text("---\nenforcement: off\n---\n")
        code, out = run(off, ".design/references/hig/type.css")
        case("settings: enforcement off releases the deny", ALLOW, code, out)

    width = max(len(n) for n, _, _ in CASES)
    for name, _, verdict in CASES:
        print(f"  {name.ljust(width)}  {verdict}")
    failed = [c for c in CASES if not c[2].startswith("PASS")]
    print(f"\n{len(CASES)} case(s), {len(failed)} failure(s)")
    if failed:
        print("RED")
        return 1
    print("GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
