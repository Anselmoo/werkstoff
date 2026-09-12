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


def repo_beats(decls: dict) -> tuple:
    """Compile every plugin's declared `requires` into repo-level takt beats.

    Returns (beats, dropped, dangling).

      dropped   an OPTIONAL requirement whose producing plugin is not installed.
                Dropped silently-but-reported: enforcing an order against a
                plugin that cannot run it would deny forever.
      dangling  a requirement naming a marker NO installed plugin produces. This
                is reported and NOT compiled: a beat whose marker nothing can
                ever create is an unconditional denial wearing an ordering
                costume.

    Markers are written `.takt/<marker>` so they stay REPO-LEVEL -- durable
    facts, not per-run ones -- even when the declaration also carries a runId
    for arbeitsplan's own phase beats.
    """
    produced = {}
    for name, d in decls.items():
        for pr in d.get("produces") or []:
            if pr.get("marker"):
                produced[pr["marker"]] = name

    beats, dropped, dangling = [], [], []
    for name, d in sorted(decls.items()):
        for req in d.get("requires") or []:
            marker, src = req.get("marker"), req.get("from")
            before = req.get("before")
            if not marker or not before:
                continue
            if src and src not in decls:
                if req.get("optional"):
                    dropped.append((name, marker, src))
                else:
                    dangling.append((name, marker, f"{src} is not installed"))
                continue
            if marker not in produced:
                dangling.append((name, marker, "no installed plugin produces it"))
                continue
            beats.append({
                "id": f"{before}-after-{marker}",
                "tools": ["Skill", "Task", "Agent"],
                "skills": [before],
                "require": f".takt/{marker}",
                "reason": req.get("reason")
                or f"{before} consumes what '{marker}' records; {produced[marker]} produces it.",
            })
    return beats, dropped, dangling


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

    # ---- ACCEPTANCE TEST for the declare-everywhere design ------------
    # The repo has exactly ONE genuine cross-plugin ordering dependency, found
    # by audit: andon-loop/SKILL.md:51-54 says to STOP and run
    # self-assess-transform-brief first, in prose, enforced by nothing. If
    # beats.json cannot express THAT, the design is wrong and every other
    # declaration is decoration.
    root = Path(__file__).resolve().parent.parent.parent
    decls = load_declarations(root)
    if decls:
        beats, dropped, dangling = repo_beats(decls)
        ids = {b["id"] for b in beats}
        for name, ok_ in [
            ("ACCEPTANCE andon-loop gated on transform-brief-written",
             "andon-loop-after-transform-brief-written" in ids),
            ("ACCEPTANCE that beat requires a REPO-LEVEL marker",
             any(b["require"] == ".takt/transform-brief-written" for b in beats)),
            ("ACCEPTANCE no dangling requirement compiled", not dangling),
            ("ACCEPTANCE every compiled beat gates something",
             all(b["skills"] and b["require"] for b in beats)),
            ("ACCEPTANCE all 12 plugins declare", len(decls) == 12),
        ]:
            print(f"  {'ok  ' if ok_ else 'FAIL'} {name}")
            if not ok_:
                fails.append(name)
        if dangling:
            for d in dangling:
                print(f"        dangling: {d}")

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
        beats, dropped, dangling = repo_beats(decls)
        for who, marker, why in dangling:
            print(f"DANGLING {who} requires '{marker}': {why} -- not compiled, because a beat "
                  f"whose marker nothing can create is an unconditional denial.", file=sys.stderr)
        for who, marker, src in dropped:
            print(f"dropped  {who}'s optional requirement '{marker}' ({src} not installed)")
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

    beats = beats_for(spec) + repo_beats(load_declarations(args.plugins_root))[0]
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
