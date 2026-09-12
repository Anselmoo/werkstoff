#!/usr/bin/env python3
"""Derive gradient tokens from named colour roles — as native DTCG, with their anti-rule.

Two contexts that look like one, and must not be merged
-------------------------------------------------------
**UI surfaces.** A gradient is a token. DTCG has a native `gradient` type (an array of
`{color, position}` stops), so nothing needs inventing and every formatter can read it.

**Illustration.** Flat zones, no gradients — tone comes from halftone and from overlap
where two colours cross. That is not this file's opinion; it is the rule the surrounding
material already states, twice, in as many words.

These only look contradictory if you forget which surface you are on, so the emitted
system NAMES the mode and carries the anti-rule beside the token rather than quietly
reconciling the two.

Derivation, not decoration
--------------------------
A gradient here is built from roles that already exist — `ink -> paper`, `action ->
action-deep` — so it inherits their provenance and their contrast record. A gradient
invented from nothing is an opinionated default, and is labelled as one.

Two stops by default. A third stop is a decision someone has to defend: it usually means
two gradients wearing one name, and it is where a "brand gradient" starts drifting from
anything the palette can justify.

Usage:
    gradients.py --demo        derive from a small role set and print the tokens
    gradients.py --selftest
Exit: 0 ok, 1 selftest failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contrast as contrastlib  # noqa: E402

EXT = "com.werkstoff.matrize"

ANTI_RULE = (
    "Never in an illustration zone — there, tone comes from flat colour and from the "
    "overlap where two zones cross, not from a blend."
)


def stops(pairs: list[tuple[str, float]]) -> list[dict]:
    """DTCG gradient stops. Colours are REFERENCES, so a role change reaches the gradient."""
    return [{"color": f"{{color.{role}}}", "position": pos} for role, pos in pairs]


def gradient_token(name: str, pairs: list[tuple[str, float]], *, purpose: str,
                   mode: str = "any", derived_from: list[str] | None = None,
                   opinionated: bool = False) -> dict:
    if len(pairs) > 2:
        purpose += (" Three or more stops: state why, or split it — a third stop is "
                    "usually two gradients sharing one name.")
    ext = {
        "role": f"gradient-{name}",
        "mode": mode,
        "purpose": purpose,
        "rule": f"Use {name} only on a UI surface, in {mode} mode.",
        "antiRule": ANTI_RULE,
        "derivedFrom": derived_from or [role for role, _ in pairs],
        "card": f"CARD-GRAD-{name}",
        "edge": {"from": f"CARD-GRAD-{name}", "grade": "A"},
        "reliability": "A",
        "rights": "R1",
    }
    if opinionated:
        ext["opinionatedDefault"] = True
        ext["purpose"] = purpose + " NOT derived from a reference — an opinionated default."
    return {
        "$type": "gradient",
        "$value": stops(pairs),
        "$description": purpose,
        "$extensions": {EXT: ext},
    }


def derive(roles: dict[str, str]) -> dict:
    """Build the gradients a role set can actually support. Silence beats invention."""
    out: dict = {}
    if "ink" in roles and "paper" in roles:
        out["veil"] = gradient_token(
            "veil", [("paper", 0.0), ("ink", 1.0)],
            purpose="Legibility scrim behind text over imagery, so the contrast record "
                    "for ink-on-paper still holds where an image sits underneath.",
        )
    if "action" in roles and "action-deep" in roles:
        out["action"] = gradient_token(
            "action", [("action", 0.0), ("action-deep", 1.0)],
            purpose="Depth on the one dominant action surface. Both stops are the same "
                    "hue, so the single-dominant-action rule is not quietly broken by "
                    "introducing a second one.",
        )
    return out


def report(roles: dict[str, str]) -> list[str]:
    """What the roles could NOT support. An absent gradient is a finding, not a gap."""
    notes: list[str] = []
    if "action" in roles and "action-deep" not in roles:
        notes.append(
            "action has no deeper step, so no action gradient was derived. Adding one "
            "means adding a colour — a decision, not a formatting step."
        )
    if not roles:
        notes.append("no roles supplied; nothing to derive from.")
    return notes


def check_stops(roles: dict[str, str], name: str, token: dict) -> list[str]:
    """A gradient whose ends are indistinguishable is a flat fill with extra bytes."""
    resolved = []
    for stop in token["$value"]:
        role = stop["color"].strip("{}").split(".", 1)[-1]
        if role not in roles:
            return [f"{name}: stop references role {role!r}, which is not defined"]
        resolved.append(roles[role])
    ratio = contrastlib.ratio(resolved[0], resolved[-1])
    if ratio < 1.1:
        return [f"{name}: endpoints differ by {ratio:.2f}:1 — that is a flat fill, not a gradient"]
    return []


DEMO_ROLES = {
    "ink": "#1a1a1a",
    "paper": "#f4f2f0",
    "action": "#FA2E1A",
    "action-deep": "#a81f10",
}


def selftest() -> int:
    checks: list[tuple[str, bool]] = []
    g = derive(DEMO_ROLES)

    checks.append(("derives from roles that exist", set(g) == {"veil", "action"}))
    checks.append(("stops are REFERENCES, not literals",
                   g["veil"]["$value"][0]["color"] == "{color.paper}"))
    checks.append(("native DTCG gradient type", g["veil"]["$type"] == "gradient"))
    checks.append(("every gradient carries its anti-rule",
                   all("antiRule" in t["$extensions"][EXT] for t in g.values())))
    checks.append(("the anti-rule names the illustration exception",
                   "illustration zone" in g["veil"]["$extensions"][EXT]["antiRule"]))
    checks.append(("carries a written edge, per I8",
                   all("edge" in t["$extensions"][EXT] for t in g.values())))
    checks.append(("records what it was derived from",
                   g["action"]["$extensions"][EXT]["derivedFrom"] == ["action", "action-deep"]))

    # Silence beats invention.
    thin = derive({"action": "#FA2E1A"})
    checks.append(("no action-deep -> no action gradient invented", "action" not in thin))
    checks.append(("and the absence is REPORTED, not swallowed",
                   any("no deeper step" in n for n in report({"action": "#FA2E1A"}))))

    # A flat fill wearing a gradient's name must be caught.
    flat = gradient_token("flat", [("paper", 0.0), ("paper", 1.0)], purpose="x")
    checks.append(("indistinguishable endpoints are caught",
                   bool(check_stops(DEMO_ROLES, "flat", flat))))
    checks.append(("a real gradient passes that check",
                   not check_stops(DEMO_ROLES, "veil", g["veil"])))
    checks.append(("a dangling role reference is caught",
                   bool(check_stops({"paper": "#fff"}, "veil", g["veil"]))))

    # Three stops must be challenged, not silently accepted.
    three = gradient_token("tri", [("ink", 0.0), ("action", 0.5), ("paper", 1.0)], purpose="x")
    checks.append(("a third stop is challenged in the purpose",
                   "two gradients sharing one name" in three["$description"]))

    # An opinionated default must say so.
    op = gradient_token("brand", [("ink", 0.0), ("paper", 1.0)], purpose="Looks good.",
                        opinionated=True)
    checks.append(("an opinionated default is labelled",
                   op["$extensions"][EXT].get("opinionatedDefault") is True
                   and "NOT derived" in op["$extensions"][EXT]["purpose"]))

    for label, ok in checks:
        print(f"  {label:<52} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.demo:
        print(json.dumps({"gradient": derive(DEMO_ROLES)}, indent=2, ensure_ascii=False))
        for n in report(DEMO_ROLES):
            print(f"  FINDING: {n}", file=sys.stderr)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
