#!/usr/bin/env python3
"""Known-answer cases for `lehre_cli.py status --require-validated`, the lehre-pin gate.

    python3 plugins/lehre/scripts/test_lehre_cli.py

`lehre-pin` says "never pin an unvalidated unit". Until this gate existed that was a sentence:
`status` returned exit 0 whatever the unit states were, so a skill told to "confirm the unit is
validated" had nothing executable to stop on. This asserts the halt is real, by exit code AND by
the reason printed, because a gate that fails for the wrong reason gets "fixed" by silencing
the wrong thing.

Then it SABOTAGES the gate two ways in a throwaway copy and asserts the unvalidated unit now
slips through. A gate whose sabotaged copy still passes these cases proves nothing about the gate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
FAILURES: list[str] = []
RAN: list[str] = []


def ruleset(mode: str, units: list[dict]) -> dict:
    return {"version": 1, "provenance": "lehre", "mode": mode, "intent": "x",
            "units": units, "rules": []}


UNITS = [{"id": "a", "paths": ["src/a/*"], "depends_on": []},
         {"id": "b", "paths": ["src/b/*"], "depends_on": ["a"]}]


def build_repo(data: dict, closed: tuple[str, ...] = ()) -> Path:
    root = Path(tempfile.mkdtemp(prefix="lehre-cli-"))
    (root / ".lehre").mkdir()
    (root / ".lehre" / "ruleset.json").write_text(json.dumps(data), encoding="utf-8")
    for unit in closed:
        marker = root / ".lehre" / "units" / f"{unit}.done"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("closed by lehre-validate\n", encoding="utf-8")
    return root


def run(cli: Path, root: Path, *args: str) -> tuple[int, str]:
    out = subprocess.run([sys.executable, "-B", str(cli), "--root", str(root), "status", *args],
                         capture_output=True, text=True, check=False)
    return out.returncode, out.stdout + out.stderr


def case(name: str, data: dict, args: tuple[str, ...], want_code: int, want_text: str,
         closed: tuple[str, ...] = (), cli: Path | None = None) -> None:
    root = build_repo(data, closed)
    try:
        code, text = run(cli or SCRIPTS / "lehre_cli.py", root, *args)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    RAN.append(name)
    if code != want_code or want_text not in text:
        FAILURES.append(name)
        print(f"FAIL  {name}\n      want exit {want_code} containing {want_text!r}\n"
              f"      got  exit {code}: {text.strip()[-300:]!r}")
    else:
        print(f"ok    {name}")


GREEN = ruleset("greenfield", UNITS)
GATE = ("--require-validated",)

case("nothing validated -> halt, names both units", GREEN, GATE, 1, "not validated: a, b")
case("only a validated, all required -> halt, names b", GREEN, GATE, 1, "not validated: b",
     closed=("a",))
case("only a validated, --unit a -> pass", GREEN, (*GATE, "--unit", "a"), 0, "validated: a",
     closed=("a",))
case("--unit b with b unvalidated -> halt", GREEN, (*GATE, "--unit", "b"), 1, "not validated: b",
     closed=("a",))
case("everything validated -> pass", GREEN, GATE, 0, "gate: ok", closed=("a", "b"))
case("unknown --unit -> exit 2, never a pass", GREEN, (*GATE, "--unit", "zz"), 2, "no unit 'zz'")
case("--unit alone is refused, not silently ignored", GREEN, ("--unit", "a"), 2,
     "silently ignored", closed=("a",))
case("greenfield with zero units -> halt (decompose never ran)",
     ruleset("greenfield", []), GATE, 1, "lehre-decompose has not run")
case("brownfield with zero units -> pass, and says what it cannot check",
     ruleset("brownfield", []), GATE, 0, "no done-marker to check")
case("plain status still exits 0 with nothing validated (unchanged behaviour)",
     GREEN, (), 0, "mode=greenfield")


def sabotaged(edit_from: str, edit_to: str) -> Path:
    """A throwaway copy of the scripts with one edit, refusing an inert one."""
    box = Path(tempfile.mkdtemp(prefix="lehre-cli-sabotage-"))
    for name in ("lehre_cli.py", "lehre_core.py", "run_record.py"):
        shutil.copy(SCRIPTS / name, box / name)
    cli = box / "lehre_cli.py"
    before = cli.read_text(encoding="utf-8")
    after = before.replace(edit_from, edit_to, 1)
    if after == before:
        raise AssertionError(f"sabotage {edit_from!r} changed nothing -- it is inert")
    cli.write_text(after, encoding="utf-8")
    return cli


# The unvalidated unit MUST now slip through, or the cases above were not testing the gate.
blind_pending = sabotaged("    if pending:\n", "    if False:\n")
case("SABOTAGE pending check blinded -> unvalidated units slip through",
     GREEN, GATE, 0, "gate: ok", cli=blind_pending)
blind_mode = sabotaged('        if mode == "brownfield":', '        if True:')
case("SABOTAGE mode ignored -> greenfield-with-no-units slips through",
     ruleset("greenfield", []), GATE, 0, "no done-marker to check", cli=blind_mode)
for cli in (blind_pending, blind_mode):
    shutil.rmtree(cli.parent, ignore_errors=True)

if FAILURES:
    print(f"\n{len(FAILURES)} case(s) failed -- fix the GATE before trusting it")
    sys.exit(1)
print(f"\nlehre_cli gate: instrument verified against {len(RAN)} known answers")
