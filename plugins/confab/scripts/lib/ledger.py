"""confab-cycle's per-repo finding ledger: cross-pass state (open/closed/
escalated findings, pass history) persisted at analysis/confab/ledger.json."""
import json
import os

from lib.paths import ensure_parent_dir, safe_output_path
from lib.remediation_scope import is_fixable as _shared_is_fixable

LEDGER_FILENAME = "ledger.json"
DEFAULT_MAX_PASSES = 5
DEFAULT_MAX_REOPENS = 3


class CycleBoundExceededError(Exception):
    """The cycle's max-passes bound has already been reached."""


def _ledger_path(repo_root):
    return safe_output_path(repo_root, LEDGER_FILENAME)


def load_ledger(repo_root):
    """A fresh, empty-shaped ledger if none exists yet -- plan-next-pass is
    the first command of a cycle and must succeed with nothing on disk."""
    path = _ledger_path(repo_root)
    if not os.path.isfile(path):
        return {"findings": {}, "totalPasses": 0, "passes": []}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_ledger(repo_root, ledger):
    path = _ledger_path(repo_root)
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2, sort_keys=True)


def resolve_max_passes(max_passes):
    # The "never above 20" ceiling in confab-cycle's SKILL.md is guidance to
    # the orchestrating session, not a runtime-enforced clamp here -- the
    # actual enforcement point is begin_pass's bound check below.
    return max_passes if max_passes else DEFAULT_MAX_PASSES


def resolve_max_reopens(max_reopens):
    return max_reopens if max_reopens else DEFAULT_MAX_REOPENS


def begin_pass(ledger, max_passes):
    """Read-only: predicts the next pass number and gates on the cap, but
    does not mutate ledger or persist anything -- record_pass is what
    actually increments totalPasses, once the pass has really run."""
    total_passes = ledger.get("totalPasses", 0)
    if total_passes >= max_passes:
        raise CycleBoundExceededError(
            f"cycle has already reached its max-passes bound ({max_passes}) "
            "(rule: cycle-max-passes)."
        )
    return total_passes + 1


def is_fixable(domain, category):
    """Thin wrapper over the same DRAFT_ONLY_DOMAINS/FIXABLE_DOMAINS check
    lib.remediation_scope.open_scope uses, so record-pass-result's gate and
    the remediation-scope lock's own check never drift apart."""
    return _shared_is_fixable(domain, category)


def upsert_finding(ledger, finding_id, *, domain, category, evidence, severity):
    findings = ledger.setdefault("findings", {})
    record = findings.setdefault(finding_id, {"status": "open", "reopenCount": 0})
    record.update(domain=domain, category=category, evidence=evidence, severity=severity)


def apply_outcome(ledger, finding_id, outcome, *, max_reopens):
    """Transition a finding's status. A reopen that pushes the per-finding
    reopen count past max_reopens transitions to "escalated" rather than
    raising -- cycle_engine.py's own constraint-domain picker treats
    "escalated" as a first-class status, and its one call to this function
    isn't wrapped in a try/except, so a raising contract here would crash
    the whole pass instead of just flagging the one finding."""
    record = ledger["findings"][finding_id]
    if outcome == "fixed":
        record["status"] = "closed"
    elif outcome in ("blocked", "drafted"):
        record["status"] = "open"
    elif outcome == "reopened":
        record["reopenCount"] = record.get("reopenCount", 0) + 1
        record["status"] = "escalated" if record["reopenCount"] > max_reopens else "open"
    return record


def pass_converged(closed, fix_or_draft_outcomes):
    return closed == 0 and fix_or_draft_outcomes == 0


def record_pass(ledger, pass_number, domain, closed, fix_or_draft_outcomes):
    """Appends the pass record AND is what actually persists totalPasses --
    begin_pass only predicted/gated it."""
    ledger.setdefault("passes", []).append(
        {
            "passNumber": pass_number,
            "domain": domain,
            "closed": closed,
            "fixOrDraftOutcomes": fix_or_draft_outcomes,
        }
    )
    ledger["totalPasses"] = ledger.get("totalPasses", 0) + 1
