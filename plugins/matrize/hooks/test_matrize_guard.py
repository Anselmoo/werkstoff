#!/usr/bin/env python3
"""Calibration for matrize_guard.py — it must DENY and it must ALLOW.

A guard that denies everything is as broken as one that denies nothing, and only the
first kind gets noticed. Every rule below is asserted in both directions, and the
negative cases are the ones that matter: this guard's whole design claim is that it
polices two paths inside one directory and nothing else.

Run: python3 plugins/matrize/hooks/test_matrize_guard.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "matrize_guard.py"

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


def run_env(cwd: Path, tool_input: dict, env: dict) -> tuple[int, str]:
    event = json.dumps({"cwd": str(cwd), "tool_name": "Write", "tool_input": tool_input})
    proc = subprocess.run([sys.executable, str(GUARD)], input=event, capture_output=True,
                          text=True, env={"PATH": "/usr/bin:/bin", **env})
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
        code, out = run(r1, ".design/references/hig/type.css", {"MATRIZE_DISABLE_GUARD": "1"})
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

        # --- rule 4: the vocabulary decides what may be a token ---------------
        # The guard's scope claim is that it polices ONE file. Every case below is
        # paired with the same bad document written somewhere else, which must pass.
        def tok(vocab: dict | None, **over) -> str:
            ext = {
                "role": "dominant-action", "card": "CARD-007",
                "reliability": "A", "rights": "R1",
                "edge": {"from": "CARD-007", "grade": "A"},
                "contrast": {"ratio": 3.84, "passesAA": False, "passesAALarge": True,
                             "mode": "light"},
            }
            if vocab is not None:
                ext["vocab"] = vocab
            ext.update(over)
            return json.dumps({"color": {"action": {
                "$type": "color",
                "$value": {"colorSpace": "srgb", "components": [0.98, 0.18, 0.10],
                           "hex": "#FA2E1A"},
                "$extensions": {"com.werkstoff.matrize": ext}}}})

        GOOD = tok({"term": "Action / interactive", "dimension": "color-system",
                    "kind": "token"})
        NO_VOCAB = tok(None)
        PROPERTY_TERM = tok({"term": "Stacking context", "dimension": "grid-and-spacing"})
        NO_MODE = tok({"term": "Action / interactive", "dimension": "color-system"},
                      contrast={"ratio": 3.84, "passesAA": False, "passesAALarge": True})

        r4 = design_repo(tmp / "r4", choice={"id": "spread-01", "chosen": "b"})
        (r4 / ".design/system/tokens.json").write_text(GOOD)

        code, out = run_input(r4, {"file_path": ".design/system/tokens.json",
                                   "content": GOOD}, "Write")
        case("rule4: a conforming tokens.json is allowed", ALLOW, code, out)
        code, out = run_input(r4, {"file_path": ".design/system/tokens.json",
                                   "content": NO_VOCAB}, "Write")
        case("rule4: a token naming no concept is denied", DENY, code, out,
             "V-VOCAB-MISSING")
        code, out = run_input(r4, {"file_path": ".design/system/tokens.json",
                                   "content": PROPERTY_TERM}, "Write")
        case("rule4: a `property` term stored as a value is denied", DENY, code, out,
             "V-VOCAB-NOT-A-TOKEN")
        code, out = run_input(r4, {"file_path": ".design/system/tokens.json",
                                   "content": NO_MODE}, "Write")
        case("rule4: a contrast record with no appearance mode is denied", DENY, code,
             out, "V-CONTRAST-NO-MODE")

        # Scope, both directions. The same bad document elsewhere must pass.
        code, out = run_input(r4, {"file_path": ".design/out/tokens.json",
                                   "content": NO_VOCAB}, "Write")
        case("rule4: scope -- the same document in out/ is allowed", ALLOW, code, out)
        code, out = run_input(r4, {"file_path": ".design/system/draft.json",
                                   "content": NO_VOCAB}, "Write")
        case("rule4: scope -- another system/ json is allowed", ALLOW, code, out)
        code, out = run_input(r4, {"file_path": "package.json", "content": NO_VOCAB},
                              "Write")
        case("rule4: scope -- a repo json outside the root is allowed", ALLOW, code, out)

        # An Edit carries a fragment. Applied to the file it produces a whole document;
        # if the result is not JSON the guard must ALLOW rather than guess.
        code, out = run_input(r4, {"file_path": ".design/system/tokens.json",
                                   "old_string": '"kind": "token"',
                                   "new_string": '"kind": "rule"'}, "Edit")
        case("rule4: an Edit that breaks the schema is denied", DENY, code, out,
             "V-VOCAB-KIND-MISMATCH")
        code, out = run_input(r4, {"file_path": ".design/system/tokens.json",
                                   "old_string": '{"color"', "new_string": "not json at all"},
                              "Edit")
        case("rule4: an Edit whose result is not JSON is allowed, not guessed at",
             ALLOW, code, out)
        code, out = run_input(r4, {"file_path": ".design/system/tokens.json",
                                   "old_string": "text that is not in the file",
                                   "new_string": "x"}, "Edit")
        case("rule4: an Edit that cannot be applied is allowed", ALLOW, code, out)
        code, out = run_input(r4, {"edits": [
            {"file_path": ".design/system/tokens.json",
             "old_string": '"dimension": "color-system"',
             "new_string": '"dimension": "grid-and-spacing"'}]})
        case("rule4: a MultiEdit payload is validated too", DENY, code, out,
             "V-VOCAB-UNKNOWN")
        code, out = run_env(r4, {"file_path": ".design/system/tokens.json",
                                 "content": NO_VOCAB}, {"MATRIZE_DISABLE_GUARD": "1"})
        case("rule4: escape hatch releases the deny", ALLOW, code, out)

        # --- rule 3: colour is never the only channel, on a DECLARED surface ---
        BARE = ("<style>.sw-1{background:#5b7fa6}.sw-2{background:#7a9e6b}"
                ".sw-3{background:#c98f4a}</style>\n" + "\n" * 40 +
                "<td class=\"sw-1\"></td><td class=\"sw-2\"></td><td class=\"sw-3\"></td>")
        LABELLED = ("<style>.sw-1{background:#5b7fa6}.sw-2{background:#7a9e6b}"
                    ".sw-3{background:#c98f4a}</style>\n" + "\n" * 40 +
                    "<li><span class=\"sw-1\"></span><span>alpha</span></li>"
                    "<li><span class=\"sw-2\"></span><span>beta</span></li>"
                    "<li><span class=\"sw-3\"></span><span>gamma</span></li>")

        r3 = design_repo(tmp / "r3")
        (r3 / ".claude").mkdir(parents=True, exist_ok=True)
        (r3 / ".claude/matrize.local.md").write_text(
            "---\nsurfaces: docs/**/*.html\n---\n")
        (r3 / "docs").mkdir(parents=True, exist_ok=True)

        code, out = run_input(r3, {"file_path": "docs/chart.html", "content": BARE}, "Write")
        case("rule3: colour-only on a declared surface denied", DENY, code, out,
             "colour alone")
        code, out = run_input(r3, {"file_path": "docs/chart.html", "content": LABELLED}, "Write")
        case("rule3: the same swatches WITH labels allowed", ALLOW, code, out)
        code, out = run_input(r3, {"file_path": "src/chart.html", "content": BARE}, "Write")
        case("rule3: same content OUTSIDE a declared surface allowed", ALLOW, code, out)

        # Undeclared project: the rule does not exist at all.
        r3b = design_repo(tmp / "r3b")
        code, out = run_input(r3b, {"file_path": "docs/chart.html", "content": BARE}, "Write")
        case("rule3: inert when no surfaces are declared", ALLOW, code, out)

        # Undecidable content is allowed, which is NOT the same as failing closed.
        code, out = run_input(r3, {"file_path": "docs/chart.html",
                                   "content": "<p>ordinary prose, no categories</p>"}, "Write")
        case("rule3: content with no categorical encoding allowed", ALLOW, code, out)
        code, out = run_input(r3, {"file_path": "docs/chart.html",
                                   "new_string": "<td class=\"sw-1\"></td>"}, "Edit")
        case("rule3: an Edit fragment with no palette is not guessed at", ALLOW, code, out)

        # A self-contained palette-index IS decidable in a fragment.
        PAL = ("const P = ['#5b7fa6','#7a9e6b','#c98f4a'];\n"
               "var c = P[h % P.length];\nnode.setAttribute('fill', c);")
        code, out = run_input(r3, {"file_path": "docs/chart.html", "new_string": PAL}, "Edit")
        case("rule3: a hashed palette in an Edit fragment is denied", DENY, code, out,
             "colour alone")

        code, out = run_input(r3, {"file_path": "docs/chart.html", "content": BARE},
                              "Write")
        case("rule3: escape hatch still releases it", ALLOW,
             *run_env(r3, {"file_path": "docs/chart.html", "content": BARE},
                      {"MATRIZE_DISABLE_GUARD": "1"}))

        # --- settings: configurable root, enforcement off -------------------
        custom = tmp / "custom"
        design_repo(custom, root="docs/design")
        (custom / ".claude").mkdir(parents=True, exist_ok=True)
        (custom / ".claude/matrize.local.md").write_text("---\nroot: docs/design\n---\n")
        code, out = run(custom, "docs/design/references/hig/type.css")
        case("settings: configured root is honoured", DENY, code, out, "read-only")
        code, out = run(custom, ".design/references/hig/type.css")
        case("settings: default root not policed once overridden", ALLOW, code, out)

        off = design_repo(tmp / "off")
        (off / ".claude").mkdir(parents=True, exist_ok=True)
        (off / ".claude/matrize.local.md").write_text("---\nenforcement: off\n---\n")
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
