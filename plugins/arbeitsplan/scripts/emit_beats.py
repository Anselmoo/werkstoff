#!/usr/bin/env python3
"""Compile a workflow.json's phase graph into takt beats.

usage: emit_beats.py [-h] [--write] [--out PATH] [--selftest] [spec]

Ordering between phases -- and between this plugin and compass, andon and the
rest -- belongs to takt, not to arbeitsplan's own guard. takt's charter says so:
the beats span plugins, and no single plugin honestly owns that order. This
script is the compiler for the declaration takt already knows how to enforce.

TWO THINGS THIS REFUSES TO DO, both of them consequences rather than opinions:

  * It will not overwrite a declaration it did not write. takt reads only the
    FIRST fenced json block, so there is no safe merge; replacing a hand-written
    file would silently switch off rules somebody meant. A file without this
    plugin's provenance key is reported, not replaced.
  * It will not write at all without --write. Creating .claude/takt.local.md
    makes takt LIVE and fail-closed in the repository, which is the user's
    decision to take, not this script's.

Exit: 0 clean, 1 refused, 2 the spec could not be read.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROVENANCE = "arbeitsplan"


def beats_for(spec: dict) -> list:
    """One beat per phase that depends on an earlier phase's marker.

    A phase with no `requires` gates nothing and gets no beat: takt silently
    skips a beat that gates nothing, so emitting one would put a line in the
    declaration that looks enforced and is not.
    """
    beats = []
    for ph in spec.get("phases", []):
        requires = ph.get("requires") or []
        if not requires:
            continue
        for marker in requires:
            beats.append({
                "id": f"{ph['id']}-after-{marker}",
                "tools": ["Skill", "Task", "Agent"],
                "skills": ["arbeitsplan-run", f"arbeitsplan:{ph.get('agentType', '')}".rstrip(":")],
                "require": marker,
                "reason": (
                    f"phase '{ph['id']}' consumes what phase marker '{marker}' records; "
                    f"running it first would judge candidates that do not exist yet."
                ),
            })
    for d in spec.get("delegates") or []:
        if not d.get("beat"):
            continue
        beats.append({
            "id": f"delegate-{d['plugin']}-{d['beat']}",
            "tools": ["Skill", "Task", "Agent"],
            "skills": ["arbeitsplan-run"],
            "require": d["beat"],
            "reason": (
                f"{d['plugin']}:{d['skill']} is declared as a delegate for this run, so the "
                f"swarm does not start before it has produced '{d['beat']}'."
            ),
        })
    return [b for b in beats if b["skills"]]


def load_declarations(plugins_root) -> dict:
    """Every installed plugin's .claude-plugin/beats.json, keyed by plugin name.

    It lives next to plugin.json rather than in references/ for one concrete
    reason: M-REF-UNWIRED requires every references/*.md to be named by a
    SKILL.md, and takt ships no skills -- a beats file there would be
    permanently unwireable in the one plugin that most needs one.
    """
    out = {}
    root = Path(plugins_root)
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        f = d / ".claude-plugin" / "beats.json"
        if not f.is_file():
            continue
        try:
            out[d.name] = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            raise SystemExit(f"emit_beats.py: {f} is not valid JSON: {exc}")
    return out


def evidence_path(ev: dict, plugin: str, decls: dict) -> str:
    """Where the evidence for this marker actually lives, repo-relative.

    `relativeTo: "output_dir"` is left as a documented default rather than
    resolved: the value is configurable per repository, and inventing the
    configured value here would produce a beat that gates on a path this
    repository does not use. The default is stated in `configuredIn` so a
    reader can see what was assumed.
    """
    path = ev.get("path", "")
    if ev.get("relativeTo") == "output_dir" and plugin == "self-assess":
        return f"analysis/self-assess/{path}"
    return path


def check_evidence(plugin: str, produce: dict, root: Path) -> list:
    """Is this marker evidenced by something that actually exists on disk?

    Three kinds, and the whole point is that `none` is LEGAL TO DECLARE and
    IMPOSSIBLE TO DEPEND ON. Round 2 shipped markers nothing wrote, and the
    resulting beat had no key: it denied forever, escapable only by disabling
    every other beat. Recording *why* a step cannot be evidenced keeps that
    knowledge in the repository instead of being re-derived by someone
    shipping the same broken marker again.
    """
    ev = produce.get("evidence")
    marker = produce.get("marker", "?")
    if not isinstance(ev, dict) or not ev.get("kind"):
        return [f"{plugin}:{marker} declares no evidence -- every produces entry must say how "
                f"its completion can be observed, even if the answer is 'it cannot'"]
    kind = ev["kind"]
    if kind == "none":
        if not ev.get("why"):
            return [f"{plugin}:{marker} is kind 'none' with no 'why' -- an unevidenced step must "
                    f"record why, or the next reader re-derives it the expensive way"]
        return []
    if kind == "artifact":
        if not ev.get("path"):
            return [f"{plugin}:{marker} is kind 'artifact' with no path"]
        return []
    if kind == "receipt":
        writer = ev.get("writtenBy")
        if not writer:
            return [f"{plugin}:{marker} is kind 'receipt' with no writtenBy"]
        wp = root / writer
        if not wp.is_file():
            return [f"{plugin}:{marker} names writtenBy {writer!r}, which does not exist"]
        if marker not in wp.read_text(encoding="utf-8", errors="replace"):
            return [f"{plugin}:{marker} names writtenBy {writer!r}, but that file never mentions "
                    f"the marker -- a receipt nothing writes is the defect this check exists for"]
        return []
    return [f"{plugin}:{marker} has unknown evidence kind {kind!r}"]


def repo_beats(decls: dict, root: Path = None) -> tuple:
    """Compile every plugin's declared `requires` into repo-level takt beats.

    Returns (beats, dropped, refused, malformed).

    FOUR reasons a requirement does not become a beat, and every one of them
    was a real defect before it was a rule:

      dropped    an OPTIONAL requirement whose producing plugin is absent.
                 Enforcing an order against a plugin that cannot run denies
                 forever.
      refused    the requirement carries `alreadyEnforcedBy` -- something in
                 code already enforces it. Two enforcements of one rule is
                 drift waiting to happen, and the second is usually the weaker.
      refused    the producing marker's evidence is kind 'none'. A beat whose
                 evidence nothing can create is an unconditional denial wearing
                 an ordering costume.
      malformed  a requirement naming a marker no installed plugin produces.
    """
    root = root or Path("plugins")
    produced, evidence_of = {}, {}
    malformed = []
    for name, d in decls.items():
        for pr in d.get("produces") or []:
            if not pr.get("marker"):
                continue
            produced[pr["marker"]] = name
            evidence_of[pr["marker"]] = pr
            malformed.extend(check_evidence(name, pr, root.parent if root.name == "plugins" else Path(".")))

    beats, dropped, refused = [], [], []
    for name, d in sorted(decls.items()):
        for req in d.get("requires") or []:
            marker, src, before = req.get("marker"), req.get("from"), req.get("before")
            if not marker or not before:
                continue

            if req.get("alreadyEnforcedBy"):
                refused.append((name, marker, "already enforced in code by "
                                + req["alreadyEnforcedBy"], req.get("why", "")))
                continue

            if src and src not in decls:
                if req.get("optional"):
                    dropped.append((name, marker, src))
                else:
                    malformed.append(f"{name} requires {marker!r} from {src}, which is not installed")
                continue

            if marker not in produced:
                malformed.append(f"{name} requires {marker!r}, which no installed plugin produces")
                continue

            ev = (evidence_of[marker].get("evidence") or {})
            if ev.get("kind") == "none":
                refused.append((name, marker,
                                f"{produced[marker]} cannot evidence it", ev.get("why", "")))
                continue

            # Artifact evidence gates on the REAL path, not on a marker some
            # step must remember to touch. requireKind 'file' closes the
            # `mkdir <path>` bypass that takt's os.path.exists would allow.
            if ev.get("kind") == "artifact":
                require = evidence_path(ev, produced[marker], decls)
                kind = "file"
            else:
                require = f".takt/{marker}"
                kind = "file"

            beats.append({
                "id": f"{before}-after-{marker}",
                "tools": ["Skill", "Task", "Agent"],
                "skills": [before],
                "require": require,
                "requireKind": kind,
                "reason": req.get("reason")
                or f"{before} consumes what '{marker}' records; {produced[marker]} produces it.",
            })
    return beats, dropped, refused, malformed


def render(spec: dict, beats: list) -> str:
    # A repo-level-only declaration carries NO runId: there is nothing per-run
    # in it to namespace, and an invented one would read as a run that never ran.
    payload = {}
    if spec.get("runId") and spec["runId"] != "repo":
        payload["runId"] = spec["runId"]
    payload[PROVENANCE] = {
        "source": ("every plugin's .claude-plugin/beats.json"
                   if payload.get("runId") is None
                   else f"analysis/arbeitsplan/{spec['runId']}/workflow.json "
                        "+ every plugin's .claude-plugin/beats.json"),
        "note": "generated by emit_beats.py; edit the declaration it came from and "
                "re-emit, never this file",
    }
    payload["beats"] = beats
    title = ("repo-level cross-plugin order" if payload.get("runId") is None
             else f"arbeitsplan run {spec['runId']}")
    scope = ("" if payload.get("runId") is None else
             "Markers live under `.takt/" + spec["runId"] + "/`, so a marker from an earlier run\n"
             "cannot satisfy a beat here. A `require` beginning `.takt/` is repo-level and is not\n"
             "namespaced.\n\n")
    return (
        f"# takt beats — {title}\n\n"
        "Generated by `arbeitsplan/scripts/emit_beats.py` from every plugin's\n"
        "`.claude-plugin/beats.json`, plus the workflow spec when one is given.\n\n"
        + scope +
        "**takt is live in this repository while this file exists**, and fail-closed: an\n"
        "internal error denies rather than allowing. Remove the file to make it inert again.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )


def existing_is_ours(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    start = text.find("```json")
    if start == -1:
        return False
    body = text[text.index("\n", start) + 1:]
    end = body.find("```")
    if end == -1:
        return False
    try:
        return PROVENANCE in json.loads(body[:end])
    except (json.JSONDecodeError, ValueError):
        return False


def selftest() -> int:
    import tempfile
    spec = {
        "runId": "ap-t-1",
        "phases": [
            {"id": "build", "requires": [], "marker": "built"},
            {"id": "referee", "requires": ["built"], "marker": "refereed"},
            {"id": "land", "requires": ["refereed"], "marker": "landed"},
        ],
        "delegates": [{"plugin": "compass", "skill": "compass-explore-branches",
                       "beat": "branches-explored", "optional": True}],
    }
    fails = []
    beats = beats_for(spec)
    ids = [b["id"] for b in beats]
    checks = [
        ("build gets no beat (it requires nothing)",
         not any(b["id"].startswith("build-after") for b in beats)),
        ("referee and land each get one", "referee-after-built" in ids and "land-after-refereed" in ids),
        ("the delegate gets one", "delegate-compass-branches-explored" in ids),
        ("every beat gates something", all(b["skills"] and b["require"] for b in beats)),
        ("no beat uses a slash in require under a runId",
         all("/" not in b["require"] for b in beats)),
    ]
    for name, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as raw:
        p = Path(raw) / "takt.local.md"
        p.write_text(render(spec, beats))
        ok = existing_is_ours(p)
        print(f"  {'ok  ' if ok else 'FAIL'} our own output is recognised as ours")
        if not ok:
            fails.append("provenance roundtrip")
        p.write_text("# hand written\n\n```json\n{\"beats\": []}\n```\n")
        ok = not existing_is_ours(p)
        print(f"  {'ok  ' if ok else 'FAIL'} a hand-written declaration is NOT ours")
        if not ok:
            fails.append("foreign detection")

        # The output must satisfy takt's own validator, not just look right.
        val = Path(__file__).resolve().parent.parent.parent / "takt" / "scripts" / "validate_beats.py"
        if val.is_file():
            import subprocess
            p.write_text(render(spec, beats))
            rc = subprocess.run([sys.executable, str(val), str(p)],
                                capture_output=True, text=True)
            ok = rc.returncode == 0
            print(f"  {'ok  ' if ok else 'FAIL'} output passes takt's validate_beats.py")
            if not ok:
                fails.append("takt validation")
                print("        " + rc.stderr.strip()[:300])

    # ---- ACCEPTANCE, round 3 -----------------------------------------
    # Round 2's acceptance test asserted that the andon beat COMPILED. It did,
    # and it was redundant with andon_core.check_ingest_prereqs, weaker than it
    # (one file vs two, exists vs isfile), and harmful -- it fired
    # unconditionally against a default gap_source:self-scan mode that needs no
    # brief. The assertion is now the opposite, and it is on the COUNT, because
    # the bug was a beat that compiled and looked right.
    root = Path(__file__).resolve().parent.parent.parent
    decls = load_declarations(root)
    if decls:
        beats, dropped, refused, malformed = repo_beats(decls, root)
        refused_markers = {m for _, m, _, _ in refused}
        for name, ok_ in [
            ("ACCEPTANCE all 12 plugins declare", len(decls) == 12),
            ("ACCEPTANCE every declaration is well-formed", not malformed),
            ("ACCEPTANCE ZERO beats compile today", len(beats) == 0),
            ("ACCEPTANCE the andon requirement is refused, not compiled",
             "transform-brief-written" in refused_markers),
            ("ACCEPTANCE it is refused for being already enforced in code",
             any("already enforced in code" in r for _, m, r, _ in refused
                 if m == "transform-brief-written")),
        ]:
            print(f"  {'ok  ' if ok_ else 'FAIL'} {name}")
            if not ok_:
                fails.append(name)
        if malformed:
            for m in malformed:
                print(f"        malformed: {m}")

        # A legitimate beat must still compile -- the checks must not have
        # simply broken compilation.
        synthetic = {
            "p1": {"plugin": "p1", "produces": [{"marker": "m1", "after": "s1",
                   "evidence": {"kind": "artifact", "path": "analysis/x/out.json"}}],
                   "requires": []},
            "p2": {"plugin": "p2", "produces": [], "requires": [
                   {"marker": "m1", "from": "p1", "before": "s2", "reason": "r"}]},
        }
        b2, _, _, mal2 = repo_beats(synthetic, root)
        ok_ = len(b2) == 1 and b2[0]["require"] == "analysis/x/out.json" and b2[0]["requireKind"] == "file"
        print(f"  {'ok  ' if ok_ else 'FAIL'} ACCEPTANCE a legitimate artifact beat still compiles, "
              f"gating on the real path")
        if not ok_:
            fails.append("legitimate beat compiles")

        # kind 'none' must be undependable.
        synthetic["p1"]["produces"][0]["evidence"] = {"kind": "none", "why": "nothing durable"}
        b3, _, ref3, _ = repo_beats(synthetic, root)
        ok_ = len(b3) == 0 and any("cannot evidence" in r for _, _, r, _ in ref3)
        print(f"  {'ok  ' if ok_ else 'FAIL'} ACCEPTANCE a kind-'none' marker cannot be depended on")
        if not ok_:
            fails.append("kind none refused")

        # alreadyEnforcedBy must refuse even with perfect evidence.
        synthetic["p1"]["produces"][0]["evidence"] = {"kind": "artifact", "path": "analysis/x/out.json"}
        synthetic["p2"]["requires"][0]["alreadyEnforcedBy"] = "scripts/thing.py:check"
        b4, _, ref4, _ = repo_beats(synthetic, root)
        ok_ = len(b4) == 0 and any("already enforced" in r for _, _, r, _ in ref4)
        print(f"  {'ok  ' if ok_ else 'FAIL'} ACCEPTANCE alreadyEnforcedBy refuses a duplicate beat")
        if not ok_:
            fails.append("alreadyEnforcedBy refused")

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="emit_beats.py",
        description="Compile a workflow.json's phase graph into a takt beat declaration. "
                    "Refuses to overwrite a declaration it did not write.",
        epilog="exit 0 clean, 1 refused, 2 the spec could not be read",
    )
    parser.add_argument("spec", nargs="?", help="path to workflow.json")
    parser.add_argument("--out", default=".claude/takt.local.md",
                        help="declaration path (default: .claude/takt.local.md)")
    parser.add_argument("--write", action="store_true",
                        help="write it; without this the declaration is printed only")
    parser.add_argument("--plugins-root", default="plugins",
                        help="where to read every plugin's .claude-plugin/beats.json "
                             "(default: plugins)")
    parser.add_argument("--repo-only", action="store_true",
                        help="compile only the repo-level beats plugins declare; no spec needed")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.repo_only:
        decls = load_declarations(args.plugins_root)
        beats, dropped, refused, malformed = repo_beats(decls, Path(args.plugins_root))
        for m in malformed:
            print(f"MALFORMED {m}", file=sys.stderr)
        for who, marker, reason, why in refused:
            print(f"refused  {who} requires '{marker}': {reason}")
            if why:
                print("           " + "\n           ".join(
                    __import__("textwrap").wrap(why, 86)))
        for who, marker, src in dropped:
            print(f"dropped  {who}'s optional requirement '{marker}' ({src} not installed)")
        if malformed:
            print(f"{len(malformed)} malformed declaration(s); nothing written", file=sys.stderr)
            return 1
        if not beats:
            print(f"\nno beats compiled from {len(decls)} declaration(s), and that is a RESULT, "
                  f"not an error: every cross-plugin ordering rule this repository has is either "
                  f"already enforced in code or cannot be evidenced. Writing nothing rather than "
                  f"an empty declaration, because creating .claude/takt.local.md makes takt live "
                  f"and fail-closed for no gain.")
            return 0
        spec = {"runId": "repo", "phases": [], "delegates": []}
        text = render(spec, beats)
        out = Path(args.out)
        if out.exists() and not existing_is_ours(out):
            print(f"REFUSED: {out} exists and was not written by arbeitsplan.", file=sys.stderr)
            return 1
        if not args.write:
            print(text)
            return 0
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        print(f"wrote {out} -- {len(beats)} repo-level beat(s) from "
              f"{len(decls)} plugin declaration(s). takt is now live in this repository.")
        return 0
    if not args.spec:
        parser.error("a spec path is required unless --selftest or --repo-only is given")

    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"no such spec: {args.spec}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"spec is not valid JSON: {exc}", file=sys.stderr)
        return 2

    beats = beats_for(spec) + repo_beats(load_declarations(args.plugins_root),
                                         Path(args.plugins_root))[0]
    if not beats:
        print("no phase declares a dependency, so there is no order to enforce; "
              "writing nothing rather than a declaration that gates nothing.")
        return 0

    text = render(spec, beats)
    out = Path(args.out)
    if out.exists() and not existing_is_ours(out):
        print(
            f"REFUSED: {out} exists and was not written by arbeitsplan.\n"
            "takt reads only the first fenced json block, so there is no safe merge, and "
            "replacing it would silently switch off rules somebody meant.\n"
            "Move or fold in the existing declaration by hand, then re-run.",
            file=sys.stderr,
        )
        return 1

    if not args.write:
        print(text)
        print(f"(not written; pass --write. Writing {out} makes takt LIVE and fail-closed "
              "in this repository.)", file=sys.stderr)
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out} -- {len(beats)} beat(s). takt is now live in this repository.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
