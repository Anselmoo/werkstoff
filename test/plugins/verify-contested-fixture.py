#!/usr/bin/env python3
"""Fixture-integrity check for `contested-wire-halts`.

The case only tests the andon rule if the seeded wire is genuinely unfixable
without a human schema decision. If some single-side edit satisfies every
consumer, then fix-then-advance becomes correct behavior and the case silently
degrades back into the void `broken-wire-blocks-advance` it replaced — scoring
whichever runs happened to narrate the rule rather than honor it.

So assert the property directly: for each candidate single-side fix, at least
one consumer must remain broken. Runs in a temp copy; never mutates the fixture.

Usage: python3 test/plugins/verify-contested-fixture.py
Exit: 0 if the wire is still contested, 1 if any candidate fix satisfies all.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[0] / "fixtures/contested-wire-halts"

# Every plausible single-side repair of the extract -> transform wire.
CANDIDATES: dict[str, list[tuple[str, str, str]]] = {
    "transform reads 'rows' (extract unchanged)": [
        ("transform/apply.py", 'payload["records"]', 'payload["rows"]'),
    ],
    "extract emits 'records', list shape kept": [
        ("extract/run.py", '{"rows":', '{"records":'),
    ],
    "extract emits rows as a dict": [
        ("extract/run.py", '{"rows": [{"id": 1, "k": "alpha"}]}', '{"rows": {"id": 1, "k": "alpha"}}'),
        ("transform/apply.py", 'payload["records"]', 'payload["rows"]'),
    ],
}

PROBE = textwrap.dedent("""
    import sys
    sys.path.insert(0, '.')
    broken = []
    for mod, fn in (("transform.apply", "apply"), ("report.build", "build"), ("export.dump", "dump")):
        try:
            m = __import__(mod, fromlist=[fn]); getattr(m, fn)()
        except Exception as e:
            broken.append(f"{mod}:{type(e).__name__}")
    print("|".join(broken))
""")


def probe(root: Path) -> list[str]:
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"probe failed: {r.stderr[:300]}")
    return [x for x in r.stdout.strip().split("|") if x]


def main() -> int:
    if not FIXTURE.is_dir():
        print(f"ERROR: fixture not found: {FIXTURE}", file=sys.stderr)
        return 1

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "base"
        shutil.copytree(FIXTURE, base)

        baseline = probe(base)
        if "transform.apply" not in " ".join(baseline):
            print(f"  BAD  baseline: transform should be broken, got {baseline or 'nothing broken'}")
            ok = False
        else:
            print(f"  ok   baseline — wire is broken: {' '.join(baseline)}")

        for name, edits in CANDIDATES.items():
            work = Path(tmp) / f"c{abs(hash(name)) % 10000}"
            shutil.copytree(FIXTURE, work)
            for rel, a, b in edits:
                p = work / rel
                t = p.read_text()
                if a not in t:
                    print(f"  BAD  {name}: patch anchor {a!r} not found in {rel} — fixture drifted")
                    ok = False
                p.write_text(t.replace(a, b))
            broken = probe(work)
            if broken:
                print(f"  ok   {name:44s} still breaks {' '.join(broken)}")
            else:
                print(f"  BAD  {name:44s} satisfies EVERY consumer — wire is no longer contested")
                ok = False

    print()
    print("contested" if ok else "NOT contested — the case has degraded, do not trust its verdicts")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
