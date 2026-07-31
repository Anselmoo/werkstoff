#!/usr/bin/env python3
"""confab-cycle engine: the bounded self-optimization loop's enforcement
layer. The orchestrating Claude session drives the actual work (dispatching
domain-audit skills/agents and confab-remediator per pass); this script is
called once per pass boundary to (a) decide/validate what that pass may do
and (b) persist the result, with every numeric bound and domain-gating rule
enforced as code that raises rather than prose the session might forget.

Rules enforced here:
  * cycle-max-passes — plan-next-pass refuses (raises, exit 2) to start a
    pass once ledger.begin_pass's bound is hit.
  * cycle-max-reopens — thrash guard applied inside lib.ledger.apply_outcome,
    called from record-pass-result.
  * fixable-domains-in-cycle / draft-domains-in-cycle — record-pass-result
    rejects (raises, exit 2) any "fixed" outcome for a finding that
    lib.ledger.is_fixable() says is not fixable, and any "fixed" outcome
    at all when mode == "propose".
  * cycle-convergence-stop — record-pass-result reports converged=true and
    the CLI's exit code signals "stop" so the calling session's loop
    cannot mistake "converged" for "keep going."
  * shared-finding-schema (checkpoint 5 of 5) — every finding upserted
    into the ledger passes through lib.schema before lib.ledger accepts it
    (lib.ledger's own _validate_ledger_finding_record is the schema for
    ledger records specifically; findings arriving from a domain
    *_summary.json sidecar were already validated at the point they were
    written by that domain's own writer script).
  * cycle-first-pass-uses-existing-audit-findings — on a ledger with no
    findings recorded yet (a fresh cycle, or one where nothing has been
    upserted into it), plan-next-pass reads each domain's own standalone
    *_summary.json sidecar (the artifact a domain audit skill run before
    or outside the cycle already wrote) to pick the constraint domain,
    instead of always defaulting to DOMAIN_ORDER_FALLBACK[0] regardless of
    what's actually sitting on disk.

Subcommands:
    plan-next-pass <repo_root> [--max-passes N] [--mode fix|propose]
        Prints JSON {passNumber, domain, mode} or exits 2 with a message
        if the pass cap is already reached.

    record-pass-result <repo_root> --pass-json <path> [--max-reopens N]
        pass-json: {"passNumber": N, "domain": "...", "mode": "fix"|"propose",
                     "outcomes": [{"findingId", "category", "evidence",
                                   "severity", "outcome"}, ...]}
        Prints JSON {"converged": bool, "totalPasses": N, "shouldContinue": bool}.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.ledger import (  # noqa: E402
    CycleBoundExceededError,
    apply_outcome,
    begin_pass,
    is_fixable,
    load_ledger,
    pass_converged,
    record_pass,
    resolve_max_passes,
    resolve_max_reopens,
    save_ledger,
    upsert_finding,
)
from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402

DOMAIN_ORDER_FALLBACK = ["dependency_audit", "contract_drift", "agentic_reliability", "assertion_audit"]


def _load_domain_summary_counts(repo_root: str) -> dict:
    """Best-effort read of each domain's standalone *_summary.json sidecar
    (written by that domain's own audit script, e.g. dependency_audit.py),
    used only to pick a constraint domain when the ledger itself has no
    findings recorded yet. A missing, unreadable, or malformed sidecar is
    treated as "no data for that domain" rather than an error -- plan-next-
    pass is the first command of a cycle and must still succeed when no
    domain audit has ever been run.

    Findings here have no ledger "status" (they haven't been triaged by a
    cycle pass yet) or "escalated" state (escalation only exists after a
    reopen inside the ledger) -- so only open_high/open_total are counted,
    matching what these findings would look like the moment they're first
    upserted into the ledger.
    """
    counts = {}
    for domain in DOMAIN_ORDER_FALLBACK:
        path = safe_output_path(repo_root, f"{domain}_summary.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                summary = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        findings = summary.get("findings")
        if not isinstance(findings, list) or not findings:
            continue
        open_high = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "High")
        counts[domain] = {"open_high": open_high, "open_total": len(findings)}
    return counts


def _pick_constraint_domain(ledger: dict, repo_root: str) -> str:
    """"whichever domain is 'constraint' (escalated findings first, then
    most open High findings, then most total open)". When the ledger has
    no findings of its own yet, falls back to each domain's own standalone
    *_summary.json sidecar (rule: cycle-first-pass-uses-existing-audit-
    findings) so a fresh cycle's first pass targets the domain that
    already has real, on-disk findings rather than always starting with
    DOMAIN_ORDER_FALLBACK[0]. Only when no domain has any sidecar data
    either does it fall back to that fixed canonical order (design
    decision, documented in README — the spec does not state a
    first-pass tiebreak).
    """
    findings = ledger["findings"]
    if not findings:
        summary_counts = _load_domain_summary_counts(repo_root)
        if summary_counts:
            high_domains = {d: c for d, c in summary_counts.items() if c["open_high"] > 0}
            if high_domains:
                return max(high_domains, key=lambda d: high_domains[d]["open_high"])
            return max(summary_counts, key=lambda d: summary_counts[d]["open_total"])
        return DOMAIN_ORDER_FALLBACK[0]

    by_domain = {}
    for record in findings.values():
        by_domain.setdefault(record["domain"], {"escalated": 0, "open_high": 0, "open_total": 0})
        bucket = by_domain[record["domain"]]
        if record["status"] == "escalated":
            bucket["escalated"] += 1
        if record["status"] == "open":
            bucket["open_total"] += 1
            if record["severity"] == "High":
                bucket["open_high"] += 1

    escalated_domains = {d: b for d, b in by_domain.items() if b["escalated"] > 0}
    if escalated_domains:
        return max(escalated_domains, key=lambda d: escalated_domains[d]["escalated"])

    high_domains = {d: b for d, b in by_domain.items() if b["open_high"] > 0}
    if high_domains:
        return max(high_domains, key=lambda d: high_domains[d]["open_high"])

    open_domains = {d: b for d, b in by_domain.items() if b["open_total"] > 0}
    if open_domains:
        return max(open_domains, key=lambda d: open_domains[d]["open_total"])

    for d in DOMAIN_ORDER_FALLBACK:
        if d not in by_domain:
            return d
    return DOMAIN_ORDER_FALLBACK[0]


def cmd_plan_next_pass(args) -> int:
    repo_root = os.path.abspath(args.repo_root)
    ledger = load_ledger(repo_root)
    max_passes = resolve_max_passes(args.max_passes)

    try:
        pass_number = begin_pass(ledger, max_passes)
    except CycleBoundExceededError as exc:
        print(json.dumps({"error": str(exc), "maxPasses": max_passes}), file=sys.stderr)
        return 2

    domain = _pick_constraint_domain(ledger, repo_root)
    plan = {"passNumber": pass_number, "domain": domain, "mode": args.mode, "maxPasses": max_passes}
    print(json.dumps(plan, indent=2))
    return 0


def cmd_record_pass_result(args) -> int:
    repo_root = os.path.abspath(args.repo_root)
    ledger = load_ledger(repo_root)
    max_reopens = resolve_max_reopens(args.max_reopens)

    with open(args.pass_json, "r", encoding="utf-8") as fh:
        pass_result = json.load(fh)

    for field in ("passNumber", "domain", "mode", "outcomes"):
        if field not in pass_result:
            print(f"pass-json missing required field {field!r}", file=sys.stderr)
            return 2

    domain = pass_result["domain"]
    mode = pass_result["mode"]
    if mode not in ("fix", "propose"):
        print(f"pass-json.mode must be 'fix' or 'propose', got {mode!r}", file=sys.stderr)
        return 2

    closed = 0
    fix_or_draft_outcomes = 0

    for entry in pass_result["outcomes"]:
        for field in ("findingId", "category", "evidence", "severity", "outcome"):
            if field not in entry:
                print(f"outcome entry missing required field {field!r}: {entry}", file=sys.stderr)
                return 2

        finding_id = entry["findingId"]
        category = entry["category"]
        outcome = entry["outcome"]

        # rule remediator-blocks-on-ambiguity: a "blocked" outcome is only
        # persisted if it carries a non-empty reason — this is the ledger
        # half of "MUST return status='blocked' with a reason rather than
        # guessing": a blocked outcome with no reason is rejected here
        # exactly like a missing gating field anywhere else in this
        # plugin, never silently accepted or defaulted to "no reason
        # given."
        if outcome == "blocked" and not str(entry.get("blockReason", "")).strip():
            print(
                f"refusing outcome=blocked for finding {finding_id!r}: missing non-empty "
                "'blockReason' (rule: remediator-blocks-on-ambiguity)",
                file=sys.stderr,
            )
            return 2

        # rules fixable-domains-in-cycle / draft-domains-in-cycle: enforced
        # here, in code, immediately before the outcome can be persisted —
        # not left to the caller's good behavior.
        if outcome == "fixed":
            if mode != "fix":
                print(
                    f"refusing outcome=fixed for finding {finding_id!r}: pass mode is "
                    f"{mode!r}, not 'fix'",
                    file=sys.stderr,
                )
                return 2
            if not is_fixable(domain, category):
                print(
                    f"refusing outcome=fixed for finding {finding_id!r}: domain={domain!r} "
                    f"category={category!r} is not in the fixable set "
                    "(rule: fixable-domains-in-cycle / draft-domains-in-cycle)",
                    file=sys.stderr,
                )
                return 2

        upsert_finding(
            ledger,
            finding_id,
            domain=domain,
            category=category,
            evidence=entry["evidence"],
            severity=entry["severity"],
        )
        apply_outcome(ledger, finding_id, outcome, max_reopens=max_reopens)

        if outcome == "fixed":
            closed += 1
            fix_or_draft_outcomes += 1
        elif outcome == "drafted":
            fix_or_draft_outcomes += 1

    record_pass(ledger, pass_result["passNumber"], domain, closed, fix_or_draft_outcomes)
    save_ledger(repo_root, ledger)

    converged = pass_converged(closed, fix_or_draft_outcomes)
    max_passes = resolve_max_passes(args.max_passes)
    should_continue = (not converged) and (ledger["totalPasses"] < max_passes)

    result = {
        "converged": converged,
        "totalPasses": ledger["totalPasses"],
        "shouldContinue": should_continue,
        "closed": closed,
        "fixOrDraftOutcomes": fix_or_draft_outcomes,
    }

    log_path = safe_output_path(repo_root, "reports/CONFAB_CYCLE.md")
    ensure_parent_dir(log_path)
    line = (
        f"- Pass {pass_result['passNumber']} | domain={domain} | mode={mode} | "
        f"closed={closed} | fix/draft outcomes={fix_or_draft_outcomes} | "
        f"converged={converged}\n"
    )
    header = "# confab Cycle\n\n"
    if os.path.exists(log_path):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line)
    else:
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(header)
            fh.write(line)

    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan-next-pass")
    p_plan.add_argument("repo_root")
    p_plan.add_argument("--max-passes", type=int, default=None)
    p_plan.add_argument("--mode", choices=["fix", "propose"], default="propose")
    p_plan.set_defaults(func=cmd_plan_next_pass)

    p_record = sub.add_parser("record-pass-result")
    p_record.add_argument("repo_root")
    p_record.add_argument("--pass-json", required=True)
    p_record.add_argument("--max-reopens", type=int, default=None)
    p_record.add_argument("--max-passes", type=int, default=None)
    p_record.set_defaults(func=cmd_record_pass_result)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
