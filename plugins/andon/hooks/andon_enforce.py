#!/usr/bin/env python3
"""PreToolUse hook: deny a source edit while the andon ledger is in a stop state.

WHY A HOOK AND NOT A SKILL
--------------------------
Measured over ~40 runs, every in-plugin layer degrades to the same thing:

  rule as prose in a SKILL.md            the baseline this was meant to fix
  rule as Python that raises             19 rules enforced, 1 case in 5 moved
  guard behind a fenced `python3` block  invoked 1/3 of runs, not 3/3
  guard inside the Workflow script       workflow dispatched 1 of 14 runs

Each is deterministic once entered, and entering it is a sentence the model
chooses to follow. A PreToolUse hook is the only layer the runtime invokes
unconditionally, so it is the only place a rule can actually hold.

The hook must be `type: "command"`. A `type: "prompt"` hook asks a model to
decide, which puts us straight back where we started.

SAFETY: INERT UNLESS THIS REPO USES ANDON
-----------------------------------------
First action is to look for a ledger in the cwd. No ledger -> exit 0, allow,
print nothing. Without that gate this hook would police every edit in every
repository on the machine. Same state-file gate ralph-loop's stop hook uses.

READ GATING VALUES TOLERANTLY
-----------------------------
The rebuilt schema wants `status`/`kind`/`blast_radius` as frontmatter keys, but
every ledger written so far — including 101 production records in
spectrafit-core — encodes them inside `tags: ["kind:wire", "status:open"]`.
Rejecting the old shape as malformed would deny every edit in every existing
andon repo the moment this ships. So: frontmatter key first, then the tags
array, then genuinely absent.

Absent is NOT repaired. A missing blast radius is a stop, never an inferred
value — the halt must not depend on a rating nobody supplied.

FAIL CLOSED
-----------
An internal error denies, and says why, and names the escape hatch. Three
guards failed silently earlier in this work (`[^\\n]` inside a bracket
expression, `\\b` around punctuation, `[^.]` spanning a filename); each looked
present and enforced nothing. A fail-open hook is that same defect with better
manners. `enforcement: off` in `.claude/andon.local.md` turns it off explicitly.

Contract: reads hook JSON on stdin. Allow: hookSpecificOutput JSON on stdout,
exit 0. Deny: hookSpecificOutput JSON (with permissionDecisionReason) on
stdout AND the reason on stderr AND exit 2 -- both mechanisms, belt-and-
braces (see deny()).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

DEFAULT_LEDGER_DIR = "analysis/andon/ledger"
DEFAULT_AUTHORIZATION = "local+reversible"
BLAST_RANK = {"local+reversible": 1, "hard-to-reverse": 2, "shared-state-visible": 3}
MAX_CONSECUTIVE_REOPENS = 3
# An ALLOWLIST OF GOOD, deliberately, not a denylist of bad.
#
# This was `NON_ADVANCING_VERDICTS = ("red", "unknown")` -- a list of the
# verdicts that halt. Every verdict outside it therefore ADVANCED, so an
# unrecognised value failed OPEN. That was reachable: tools/andon-ledger-
# validator/validate_ledger.py accepted `amber` as a valid verdict, and
# andon_core.compute_wire_status collapses anything non-green/non-red to
# `unknown`, so the board drew such a wire amber and labelled it UNPROVEN
# while this hook waved every edit through. Looks gated, isn't.
#
# Inverted: a wire advances only on an explicit `green`. A typo, a verdict
# from a newer schema, a hand-edited value -- all halt. Consistent with the
# rest of the file, where a missing blast radius is a stop and never an
# inferred value.
ADVANCING_VERDICTS = ("green",)
SETTINGS = ".claude/andon.local.md"
# #70: named literally (not via a variable) in both this constant and the
# os.environ.get() check below -- nacharbeit's H-ESCAPE-HATCH rubric rule
# greps the raw source text for the literal `<NAME>_DISABLE_GUARD` token and
# only clears once it appears at least twice, so an indirection through a
# single named constant would read as "read but never named in a deny
# reason" even though it's the same value at runtime.
REMEDIES = (
    "Remedies, narrowest first: `retire` the stale gap/evidence record (see "
    "`python3 plugins/andon/scripts/andon_core.py retire --help`); set "
    "ANDON_DISABLE_GUARD=1 to bypass this guard for one call; or set "
    "`enforcement: off` in .claude/andon.local.md to disable it wholesale."
)


def allow(message: str | None = None) -> int:
    out: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    if message:
        out["systemMessage"] = message
    print(json.dumps(out))
    return 0


def deny(reason: str) -> int:
    """Deny via BOTH mechanisms the runtime actually honors.

    Experimentally confirmed (tracer hooks): the runtime ignores a
    `permissionDecision: deny` whose JSON is missing `hookEventName` or that
    puts its reason in `systemMessage` instead of `permissionDecisionReason` --
    the deny is silently dropped and the edit proceeds. Two shapes were
    confirmed to actually block: (1) `exit 2` with the reason on stderr and no
    JSON at all, and (2) stdout JSON matching the exact
    hookSpecificOutput/hookEventName/permissionDecision/permissionDecisionReason
    shape. Emitting both here means a future schema drift in one mechanism
    (the JSON contract changes again, gets mistyped, etc.) still can't
    silently disarm the hook -- the exit-2-plus-stderr path holds regardless.
    """
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }))
    print(reason, file=sys.stderr)
    return 2


def frontmatter(text: str) -> dict[str, str | list[str]]:
    """Parse fenced frontmatter, including BLOCK-LIST values.

    This used to be a single line-regex matching `key: value` only. A YAML block
    list --

        tags:
          - kind:bug
          - status:open

    -- gave `tags` an EMPTY string: the `tags:` line matched with an empty
    capture, and the `  - ` lines matched nothing and were dropped. That is the
    form andon_core.dump_frontmatter WRITES, the form okf-ledger-schema.md
    documents, and the form every record in scripts/fixtures/sample_ledger uses,
    so tag_value's documented legacy fallback was dead for everything andon
    produces. It went unnoticed because validate_doc also requires the
    first-class keys and tag_value reads those first -- the fallback was
    redundant rather than load-bearing, right up until a value had no
    first-class key to fall back to.

    Modelled on andon_core.parse_frontmatter:169-203, which has handled both
    forms since the start. This is the third parser of the same format in this
    repo and the last one to learn.
    """
    if not text.startswith("---"):
        return {}
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return {}
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}

    fm: dict[str, str | list[str]] = {}
    current_list_key: str | None = None
    for line in lines[1:end]:
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            fm[current_list_key].append(line[4:].strip().strip("\"'"))  # type: ignore[union-attr]
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1).replace("-", "_").lower()
        raw = m.group(2).strip()
        if raw == "":
            fm[key] = []
            current_list_key = key
        else:
            fm[key] = raw.strip("\"'")
            current_list_key = None
    return fm


def tag_value(fm: dict[str, str], key: str) -> str | None:
    """Read `key` from a frontmatter field, else from the `tags` array.

    Legacy records carry `tags: ["kind:wire", "status:open",
    "blast-radius:local+reversible"]`. Reading only the first shape would treat
    every existing ledger as malformed.
    """
    direct = fm.get(key.replace("-", "_"))
    if isinstance(direct, str) and direct:
        return direct

    # Both list syntaxes are live. A block list arrives as a real list from
    # frontmatter() -- that is what the CLI writes. The inline flow form
    # `tags: ["kind:wire", ...]` arrives as one string and is mined for quoted
    # items; CLAUDE.md records 101 production records in spectrafit-core whose
    # state is ONLY in that form, so it cannot be dropped.
    raw_tags = fm.get("tags", "")
    items = raw_tags if isinstance(raw_tags, list) else re.findall(r'"([^"]+)"', raw_tags)
    for tag in items:
        if ":" in tag:
            k, v = tag.split(":", 1)
            if k.replace("-", "_").lower() == key.replace("-", "_").lower():
                return v
    return None


def settings(root: Path) -> dict[str, str]:
    p = root / SETTINGS
    return frontmatter(p.read_text(encoding="utf-8", errors="replace")) if p.is_file() else {}


def _list_md(d: Path) -> list[Path]:
    """List *.md, RAISING if the directory exists but cannot be read.

    `Path.glob` swallows PermissionError and yields nothing, so an unreadable
    ledger looked exactly like an empty one: no gaps found, no stop condition,
    edit allowed. The hook failed open while appearing to work — the same silent
    failure this whole design is built to avoid. os.listdir raises, so the
    fail-closed handler in main() can actually fire.
    """
    if not d.is_dir():
        return []
    return sorted(d / n for n in os.listdir(d) if n.endswith(".md"))


_RESOLVED_BY_RE = re.compile(r"\[\[(?:evidence/)?([^\]]+)\]\]")


# DUPLICATED FROM andon_core.parse_log_counters (the `sub_cycles` regex). The
# hook is stdlib-only by design -- it imports nothing from the plugin, so that a
# broken or half-installed andon can never make it fail to load, and a hook that
# cannot import denies every call. That rules out reusing the function, so the
# one line is copied instead.
#
# A copied regex is exactly the drift this repo keeps getting bitten by, so it is
# not left to good intentions: test_andon_enforce.py's TestReopenParserAgreement
# feeds the same log text to BOTH parsers and asserts they return the same
# counts. Change one and that test goes red.
REOPEN_LINE_RE = re.compile(r"^### Sub-cycle: (.+?) reopened \(count (\d+)\)", re.MULTILINE)


def reopen_counts(ledger: Path) -> dict[str, int]:
    """Highest recorded reopen count per wire, read from the append-only log.

    The count lives ONLY here. It is written by andon_core.track_subcycle as a
    log line and re-derived by parse_log_counters; no writer ever puts a
    reopen_count field on a gap doc, and the concept is keyed by WIRE, not by
    gap. The hook used to look for `tag_value(fm, "reopen_count")` on each gap
    -- a value nothing produces -- so the sub-cycle escalation stop could not
    fire on any real ledger. It was green only because the test fixture
    hand-wrote an inline tag no writer emits.
    """
    log = ledger / "log.md"
    if not log.is_file():
        return {}
    text = log.read_text(encoding="utf-8", errors="replace")
    counts: dict[str, int] = {}
    for wire, count in REOPEN_LINE_RE.findall(text):
        counts[wire] = max(counts.get(wire, 0), int(count))
    return counts


def parse_iso_date(value: str) -> date | None:
    """Returns a `date`, or None if malformed. Manual digit parsing, not
    `datetime.strptime` -- DTZ007 flags a naive datetime built via
    `strptime`; `date()` here always represents a fixed value the record
    already carries, never a read of the current time (that's
    `datetime.now(timezone.utc).date()` in `is_expired()` below).

    DUPLICATED from andon_core.parse_iso_date for the same reason every
    other duplication in this file exists: the hook is stdlib-only and
    imports nothing from the plugin.
    """
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    year, month, day = (int(part) for part in value.split("-"))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def is_expired(valid_until: str) -> tuple[bool, str | None]:
    """(expired, error). `error` is set when valid_until is unparseable --
    the contract is 'an unparseable valid_until read by the hook denies',
    i.e. fail closed rather than silently treating it as not-yet-due."""
    parsed = parse_iso_date(valid_until)
    if parsed is None:
        return False, f"{valid_until!r} is not a valid ISO date (YYYY-MM-DD)"
    today = datetime.now(timezone.utc).date()
    return today > parsed, None


class ChainResolutionError(Exception):
    """A superseded_by chain is broken: a dangling link or a cycle.

    DUPLICATED in andon_core.resolve_chain_head -- this hook is stdlib-only
    and imports nothing from the plugin (see the module docstring), so a
    broken/half-installed andon can never stop it loading. Both functions
    are fed the same input by TestChainHeadResolutionAgreement in
    test_andon_enforce.py, which asserts they agree.
    """


def resolve_chain_head(start_slug: str, superseded_by_of: dict[str, str | None]) -> str:
    """Follow `superseded_by` from `start_slug` to the head of its
    supersession chain -- a record nobody supersedes further (#72:
    chain-head-resolution). `superseded_by_of` maps every known evidence
    slug to its `superseded_by` value (falsy if none). Raises
    ChainResolutionError on a dangling link (points to a slug not in
    `superseded_by_of`) or a cycle, wherever in the chain it occurs -- never
    silently falls back to the unresolved leaf's own verdict.
    """
    seen = {start_slug}
    cursor = start_slug
    while True:
        nxt = superseded_by_of.get(cursor)
        if not nxt:
            return cursor
        if nxt not in superseded_by_of:
            raise ChainResolutionError(
                f"'{cursor}' is superseded_by {nxt!r}, which does not exist "
                f"(dangling link)."
            )
        if nxt in seen:
            raise ChainResolutionError(
                f"supersession cycle detected starting at {start_slug!r}: "
                f"reaches {nxt!r} again."
            )
        seen.add(nxt)
        cursor = nxt


def stop_reason(ledger: Path, authorization: str) -> str | None:
    """The first stop condition that holds, or None. Contract §3 + §9.2."""
    gaps = _list_md(ledger / "gaps")
    # #68a: an evidence doc carries no back-link to the gap it resolved -- the
    # only join is the *gap's* `resolved_by: "[[evidence/<slug>]]"`. Collect
    # the evidence slugs that a CLOSED gap already points at here, in the same
    # pass that already walks every gap, so the evidence loop below can skip
    # them instead of gating forever after the gap that raised them closed.
    closed_evidence_slugs: set[str] = set()
    for p in gaps:
        fm = frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        # Skip on an explicit `closed` ONLY. This read `not in ("open",
        # "reopened")`, which also skipped every other status -- a typo, a value
        # from a newer schema -- so an unrecognised status silently stopped
        # gating. Same fail-open shape as the verdict denylist two commits back.
        # `reopened` is not a legal status either: andon_core.GAP_STATUSES and
        # okf-ledger-schema.md:51 both say open or closed.
        status = tag_value(fm, "status")
        if status and status.lower() == "closed":
            resolved_by = fm.get("resolved_by")
            if resolved_by:
                m = _RESOLVED_BY_RE.search(str(resolved_by))
                if m:
                    closed_evidence_slugs.add(m.group(1).strip())
            continue  # closed gaps do not gate anything

        blast = tag_value(fm, "blast_radius") or tag_value(fm, "blast-radius")
        if not blast:
            return (f"STOP (required-field integrity, contract §9.2): gap "
                    f"'{p.name}' carries no blast-radius value, so the "
                    f"authorization ceiling has no input to check. This value is "
                    f"never inferred — a human must supply one of "
                    f"{', '.join(BLAST_RANK)}. Source edits are denied until then.")
        if blast not in BLAST_RANK:
            return (f"STOP: gap '{p.name}' has blast-radius {blast!r}, which is "
                    f"not one of {', '.join(BLAST_RANK)}.")
        if BLAST_RANK[blast] > BLAST_RANK.get(authorization, 1):
            return (f"STOP (andon rule / condition 2): gap '{p.name}' has blast "
                    f"radius {blast!r}, exceeding authorization_level "
                    f"{authorization!r}. A human must raise authorization for "
                    f"this one fix.")
        reopens = tag_value(fm, "reopen_count") or tag_value(fm, "reopen-count")
        if reopens and reopens.isdigit() and int(reopens) >= MAX_CONSECUTIVE_REOPENS:
            return (f"STOP (sub-cycle escalation): gap '{p.name}' has reopened "
                    f"{reopens} times, reaching the threshold of "
                    f"{MAX_CONSECUTIVE_REOPENS}. It is the stream's constraint "
                    f"now, not a sub-cycle — escalate rather than retry.")

    # #68c: supersede -- group evidence by wire and judge only the latest doc
    # per wire, matching compute_wire_status() in andon_core.py (same
    # filename-sorted ordering, `[-1]` wins). Without this, an old red/unknown
    # verdict superseded by a later green re-verify still gated here even
    # though andon-status's own board already reports the wire green -- the
    # hook and the CLI disagreeing about the same data. A doc with no `wire`
    # field (malformed or pre-schema) can't be grouped, so it is judged on its
    # own, same as before.
    # Sub-cycle escalation, per WIRE, from the log -- see reopen_counts(). The
    # per-gap branch above is kept for a legacy record that carries the value
    # inline, but production ledgers record it here and only here.
    for wire, count in sorted(reopen_counts(ledger).items()):
        if count >= MAX_CONSECUTIVE_REOPENS:
            return (f"STOP (sub-cycle escalation): wire {wire!r} has reopened "
                    f"{count} times, reaching the threshold of "
                    f"{MAX_CONSECUTIVE_REOPENS}. It is the stream's constraint "
                    f"now, not a sub-cycle -- escalate rather than retry.")

    ev = _list_md(ledger / "evidence")
    latest_by_wire: dict[str, Path] = {}
    unwired: list[Path] = []
    evidence_fm: dict[str, dict] = {}
    evidence_text: dict[str, str] = {}
    for p in ev:
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = frontmatter(text)
        evidence_fm[p.stem] = fm
        evidence_text[p.stem] = text
        wire = tag_value(fm, "wire")
        if wire:
            latest_by_wire[wire] = p  # ev is filename-sorted; last assignment wins
        else:
            unwired.append(p)

    # #72: superseded_by is resolved across ALL evidence in the ledger, not
    # just the docs for one wire -- the pointer is a bare slug, not scoped
    # to a wire, and a dangling/cyclic chain must fail closed regardless of
    # what wire either end happens to claim.
    superseded_by_of = {slug: tag_value(fm, "superseded_by") for slug, fm in evidence_fm.items()}

    for p in list(latest_by_wire.values()) + unwired:
        if p.stem in closed_evidence_slugs:
            continue  # #68a: the gap this evidence resolved is already closed

        # #72 (chain-head-resolution): judge the HEAD of this record's
        # supersession chain, never the unresolved leaf -- a record naming
        # an existing successor stops gating on its own verdict. A dangling
        # link or a cycle anywhere along the way denies outright, fail
        # closed, rather than falling back to the leaf's own verdict.
        try:
            head_slug = resolve_chain_head(p.stem, superseded_by_of)
        except ChainResolutionError as exc:
            return (f"STOP (andon rule / lifecycle, #72): evidence '{p.name}' "
                    f"has a broken supersession chain: {exc}. A wire must "
                    f"never be un-gated by a superseded_by reference that "
                    f"cannot be resolved.")
        head_fm = evidence_fm[head_slug]
        head_text = evidence_text[head_slug]
        measured_against = tag_value(head_fm, "measured_against")
        suffix = f" (measured_against {measured_against!r})" if measured_against else ""

        # Expiry (valid_until) is judged on the chain HEAD only.
        valid_until = tag_value(head_fm, "valid_until")
        if valid_until:
            expired, err = is_expired(valid_until)
            if err:
                return (f"STOP (andon rule / lifecycle, #72): evidence "
                        f"'{head_slug}.md' (chain head for '{p.name}') has an "
                        f"unparseable valid_until {valid_until!r}: {err}. Fail "
                        f"closed -- the record gates as verdict unknown.")
            if expired:
                return (f"STOP (andon rule / lifecycle, #72): evidence "
                        f"'{head_slug}.md' (chain head for '{p.name}') expired "
                        f"on {valid_until} -- it now gates as verdict unknown, "
                        f"even though it may still read green{suffix}. The "
                        f"wire is not proven; the loop may not advance past it.")

        verdict = tag_value(head_fm, "verdict")
        if not verdict:
            m = re.search(r"^\s*[-*]\s*Verdict:\s*(\S+)", head_text, re.MULTILINE)
            verdict = m.group(1).strip("`*.,") if m else None
        if verdict and verdict.lower() not in ADVANCING_VERDICTS:
            return (f"STOP (andon rule / condition 1): evidence '{head_slug}.md' "
                    f"(chain head for '{p.name}') records verdict {verdict!r}, "
                    f"which is not {' or '.join(ADVANCING_VERDICTS)}{suffix}. The "
                    f"wire is not proven; the loop may not advance past it.")
    return None


def main() -> int:
    # #70: checked first, before stdin is even read, matching
    # plugins/nacharbeit/hooks/nacharbeit_guard.py's ESCAPE_HATCH pattern --
    # the narrowest of the three remedies named in the deny messages below.
    # andon's allow() prints the hookSpecificOutput JSON and returns an int
    # rather than exiting directly (unlike nacharbeit's), so this must be a
    # `return`, not a bare call.
    if os.environ.get("ANDON_DISABLE_GUARD") == "1":
        return allow()

    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    try:
        cwd = Path(event.get("cwd") or ".").resolve()
        cfg = settings(cwd)
        if (cfg.get("enforcement") or "").lower() in ("off", "false", "disabled"):
            return allow()

        ledger = cwd / (cfg.get("ledger_dir") or DEFAULT_LEDGER_DIR)
        if not ledger.is_dir():
            return allow()          # not an andon repo — say nothing at all

        target = (event.get("tool_input") or {}).get("file_path") or ""
        if target:
            try:
                target_path = Path(target) if Path(target).is_absolute() else (cwd / target)

                # #69: containment, before anything else. This hook's rules
                # are about the andon ledger under `cwd` -- a write outside
                # the repository is none of its business, whatever the
                # ledger's stop conditions say. Lexical containment (normpath,
                # no filesystem access) is necessary but NOT sufficient: a
                # symlink inside the tree can point outside it, so a target
                # that lexically looks contained can still resolve elsewhere.
                # Reasoning and the double test copied from
                # plugins/arbeitsplan/hooks/arbeitsplan_guard.py's containment
                # check -- same shape, opposite direction: that guard DENIES
                # an escape lexically-inside-but-resolves-outside a worktree;
                # this one only ALLOWS the "outside cwd" bypass when BOTH the
                # lexical and the resolved test agree the target is outside,
                # so a symlink that merely *looks* like an escape still stays
                # gated (fail closed) rather than silently skipping the rule.
                lexical = os.path.normpath(str(target_path))
                cwd_str = str(cwd)
                lexically_outside = not (
                    lexical == cwd_str or lexical.startswith(cwd_str + os.sep)
                )
                resolved = target_path.resolve()
                really_outside = not (resolved == cwd or cwd in resolved.parents)
                if lexically_outside and really_outside:
                    return allow()  # nothing outside this repo is this hook's business

                if resolved == ledger or ledger in resolved.parents:
                    return allow()  # the loop must always be able to record its halt
            except OSError:
                pass

        reason = stop_reason(ledger, cfg.get("authorization_level") or DEFAULT_AUTHORIZATION)
        if reason:
            return deny(reason + "\n\n(andon enforcement hook. " + REMEDIES + ")")
        return allow()
    except Exception as exc:                                    # fail CLOSED
        return deny(
            f"andon enforcement hook failed: {type(exc).__name__}: {exc}. "
            f"Denying rather than silently dropping enforcement. " + REMEDIES)


if __name__ == "__main__":
    sys.exit(main())
