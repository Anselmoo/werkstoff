#!/usr/bin/env python3
"""Validator for the verification report + fix-ledger artifacts.

Every gating field is checked here. A record missing a field that a later
decision branches on is REJECTED, never defaulted or repaired -- a value nobody
supplied must never enter the artifact.

Gating fields:
  report.language   -> must be a known registry language or 'posix-sh'
  report.paradigm   -> must match the routed paradigm for that language
  report.verdict    -> 'pass' | 'gaps' ; gates whether the skill may present
  finding.rule_id   -> which doctrine rule ; gates which fix to apply
  finding.status    -> 'pass' | 'fail'
  finding.disposition (only when status == 'fail') -> 'fixable' |
      'needs-human-judgment' ; gates fix-it-yourself vs. surface-to-human.
  ledger.attempts   -> int ; gates the MAX_FIX_ITERATIONS halt.

Used on WRITE (verify_scaffold validates before persisting) and on READ (skills
validate a report/ledger they load before acting on it). Same function both
ways, so a hand-edited or corrupt artifact is rejected symmetrically.
"""
import json
import sys

from constants import (
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    LANGUAGE_REGISTRY,
    MAX_FIX_ITERATIONS,
    SHELL,
    STATUS_FAIL,
    VALID_DISPOSITIONS,
    VALID_STATUSES,
    VALID_VERDICTS,
)


class ReportError(Exception):
    """Raised when an artifact is missing or has an invalid gating field."""


def _known_language(lang):
    return lang in LANGUAGE_REGISTRY or lang == "posix-sh"


def _paradigm_of(lang):
    if lang == "posix-sh":
        return SHELL
    return LANGUAGE_REGISTRY.get(lang)


def validate_finding(finding, index="?"):
    if not isinstance(finding, dict):
        raise ReportError("finding[%s] is not an object" % index)

    rule_id = finding.get("rule_id")
    if not rule_id or not isinstance(rule_id, str):
        raise ReportError("finding[%s] missing gating field 'rule_id'" % index)

    status = finding.get("status")
    if status not in VALID_STATUSES:
        raise ReportError(
            "finding[%s] (%s) has invalid/missing 'status': %r (allowed: %s)"
            % (index, rule_id, status, list(VALID_STATUSES))
        )

    # disposition is REQUIRED for failures and must NOT be inferred.
    if status == STATUS_FAIL:
        disposition = finding.get("disposition")
        if disposition not in VALID_DISPOSITIONS:
            raise ReportError(
                "finding[%s] (%s) is a failure but has invalid/missing "
                "'disposition': %r (allowed: %s). Refusing to default it."
                % (index, rule_id, disposition, list(VALID_DISPOSITIONS))
            )
    return True


def validate_report(report):
    if not isinstance(report, dict):
        raise ReportError("report is not an object")

    lang = report.get("language")
    if not _known_language(lang):
        raise ReportError("report missing/invalid gating field 'language': %r" % lang)

    paradigm = report.get("paradigm")
    expected = _paradigm_of(lang)
    if paradigm != expected:
        raise ReportError(
            "report 'paradigm' (%r) does not match language %r (expected %r)"
            % (paradigm, lang, expected)
        )

    verdict = report.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise ReportError(
            "report missing/invalid gating field 'verdict': %r (allowed: %s)"
            % (verdict, list(VALID_VERDICTS))
        )

    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ReportError("report 'findings' must be a list")
    for i, f in enumerate(findings):
        validate_finding(f, str(i))

    # Cross-check: verdict MUST agree with the findings. 'pass' with any failing
    # finding, or 'gaps' with none, is an internally inconsistent artifact.
    has_fail = any(f.get("status") == STATUS_FAIL for f in findings)
    if verdict == "pass" and has_fail:
        raise ReportError("verdict 'pass' contradicts a failing finding")
    if verdict == "gaps" and not has_fail:
        raise ReportError("verdict 'gaps' but no failing finding present")
    return True


def validate_ledger(ledger):
    if not isinstance(ledger, dict):
        raise ReportError("ledger is not an object")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
        raise ReportError("ledger missing/invalid gating field 'attempts': %r" % attempts)
    if attempts > MAX_FIX_ITERATIONS:
        raise ReportError(
            "ledger attempts %d exceeds MAX_FIX_ITERATIONS %d"
            % (attempts, MAX_FIX_ITERATIONS)
        )
    if "scaffold_dir" not in ledger or not ledger["scaffold_dir"]:
        raise ReportError("ledger missing gating field 'scaffold_dir'")
    return True


def main(argv):
    if len(argv) != 3 or argv[1] not in ("report", "ledger"):
        sys.stderr.write("usage: report_validator.py <report|ledger> <path>\n")
        return EXIT_USAGE_ERROR
    kind, path = argv[1], argv[2]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write("INVALID: cannot read %s: %s\n" % (path, exc))
        return EXIT_RUNTIME_ERROR
    try:
        if kind == "report":
            validate_report(data)
        else:
            validate_ledger(data)
    except ReportError as exc:
        sys.stderr.write("INVALID %s: %s\n" % (kind, exc))
        return EXIT_RUNTIME_ERROR
    sys.stdout.write("OK: %s is valid\n" % kind)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main(sys.argv))
