"""Three-way reconcile of Find-phase findings against Verify-phase answers.

A verifier answer has exactly three meanings, never two:

  * ``confirmed`` is the literal ``True``   -> CONFIRMED: the finding survives.
  * ``confirmed`` is the literal ``False``  -> REFUTED: the finding is dropped.
  * anything else (key missing, ``"yes"``, ``1``, ``null``, no record at all for
    the finding, conflicting records)       -> UNVERIFIED: the verifier did not
    give a usable answer. That is an abstain, and an abstain is never a pass.

Dropping the third bucket silently made a verifier that failed to answer look
identical to one that refuted everything: the summary read clean and the cycle
counted the domain as having nothing open. UNVERIFIED findings are therefore
KEPT, marked ``verification: "unverified"``, warned about on stderr with the
count, and counted in the summary's ``unverifiedCount`` -- which
``cycle_engine.py`` reads and refuses to call converged past.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from lib.paths import safe_output_path

CONFIRMED = "confirmed"
REFUTED = "refuted"
UNVERIFIED = "unverified"


def verdict_for(evidence, verify_findings) -> str:
    """Classify one Find-phase finding's evidence key against all verify records."""
    if not isinstance(evidence, str) or not evidence:
        return UNVERIFIED  # nothing to match a verifier answer against
    answers = [
        record.get("confirmed", None)
        for record in verify_findings
        if isinstance(record, dict) and record.get("evidence") == evidence
    ]
    if not answers:
        return UNVERIFIED  # the verifier never answered for this finding
    if all(a is True for a in answers):
        return CONFIRMED
    if all(a is False for a in answers):
        return REFUTED
    return UNVERIFIED  # malformed or contradictory answers


def reconcile_three_way(find_findings, verify_findings, *, domain: str) -> list:
    """Return confirmed findings plus unverified ones (copied and marked)."""
    survivors = []
    unverified = []
    for finding in find_findings:
        verdict = verdict_for(finding.get("evidence"), verify_findings)
        if verdict == CONFIRMED:
            survivors.append(finding)
        elif verdict == UNVERIFIED:
            marked = dict(finding)
            marked["verification"] = UNVERIFIED
            survivors.append(marked)
            unverified.append(marked)
    if unverified:
        print(
            f"WARNING: {domain}: {len(unverified)} finding(s) could not be verified "
            "(verifier gave no literal true/false `confirmed`); kept as "
            "verification=unverified and the domain cannot be called converged "
            "until they are re-verified",
            file=sys.stderr,
        )
    return survivors


def verify_payload_list(raw):
    """Unwrap a loaded verify-json document into a record list, or None.

    Accepts a bare list or ``{"findings": [...]}``. Anything else -- ``null``,
    ``{"findings": null}``, a scalar, a dict without a list -- is NOT a verifier
    answer: it returns None so the caller treats every finding as unverified
    instead of mistaking a missing payload for "verification was skipped".
    """
    if isinstance(raw, dict):
        raw = raw.get("findings")
    return raw if isinstance(raw, list) else None


def reconcile_requested(find_findings, raw_verify, *, skip_verification: bool, domain: str) -> list:
    """Decide skip-vs-verify from the CLI flag, never from the loaded value.

    ``skip_verification`` True is the only way to bypass reconcile. When
    verification was requested and the payload is unusable, every finding is
    reconciled against zero records, i.e. marked ``verification: "unverified"``.
    """
    if skip_verification:
        return find_findings
    records = verify_payload_list(raw_verify)
    if records is None:
        records = []
    return reconcile_three_way(find_findings, records, domain=domain)


def begin_run(repo_root: str, domain: str) -> None:
    """Invalidate the domain sidecar before a run, so a failed run cannot leave
    the previous run's (possibly clean) sidecar to be read as current.

    The placeholder has no integer ``unverifiedCount``, which
    ``unverified_blockers`` treats as a blocker; ``write_summary`` replaces it
    atomically only when the run completes.
    """
    path = Path(safe_output_path(repo_root, f"{domain}_summary.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"domain": domain, "incomplete": True}), encoding="utf-8")


def write_summary(path: str, summary: dict) -> None:
    """Write the sidecar atomically (temp file + replace)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, target)


def is_unverified(finding) -> bool:
    return isinstance(finding, dict) and finding.get("verification") == UNVERIFIED


def unverified_evidence(survivors) -> list:
    return [f.get("evidence") for f in survivors if is_unverified(f)]


# Domains whose writer reconciles Find against a mandatory Verify phase and so
# can end up holding findings the verifier abstained on.
VERIFIED_DOMAINS = ("assertion_audit", "contract_drift", "agentic_reliability")


def unverified_blockers(repo_root: str) -> list:
    """Reasons convergence must be refused, one per offending domain sidecar.

    Fail-closed on purpose: only a sidecar that is absent (the domain was never
    audited, so there is nothing it could be hiding) is skipped. One that exists
    but cannot be read, or lacks an integer `unverifiedCount`, is a blocker --
    a guard that only fires when the field it checks is present never fires for
    the very writer that forgot to emit it.
    """
    blockers = []
    for domain in VERIFIED_DOMAINS:
        path = Path(safe_output_path(repo_root, f"{domain}_summary.json"))
        if not path.is_file():
            continue
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            blockers.append({"domain": domain, "reason": f"sidecar unreadable: {exc.__class__.__name__}"})
            continue
        if isinstance(summary, dict) and summary.get("incomplete") is True:
            blockers.append({"domain": domain, "reason": "previous run did not complete; re-run the domain"})
            continue
        count = summary.get("unverifiedCount") if isinstance(summary, dict) else None
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            blockers.append({"domain": domain, "reason": "sidecar has no valid integer unverifiedCount"})
        elif count > 0:
            blockers.append({"domain": domain, "reason": f"{count} unverified finding(s)", "unverifiedCount": count})
    return blockers
