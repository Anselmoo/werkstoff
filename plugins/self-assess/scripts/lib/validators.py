"""Per-kind artifact validators for `self_assess_cli.py validate-artifact`.

Every validator raises SelfAssessError -- schema violations are treated as
policy refusals ("REFUSED:"), consistent with every gate in gates.py, rather
than a separate ValueError/"ERROR:" path. Per-kind rules below implement
only what's directly evidenced by a skill's SKILL.md or another module's
own docstring; two kinds (docs_drift_summary, file_stage_index) have no
further evidenced rejection condition beyond what's here -- do not invent
additional ones.
"""
from lib.errors import SelfAssessError
from lib.formulas import complexity_index


def _require_fields(data, fields, kind):
    missing = [f for f in fields if f not in data]
    if missing:
        raise SelfAssessError(f"{kind}: missing required field(s) {missing!r}.")


def validate_complexity_score_summary(data):
    for stage in data.get("stages", []):
        if stage.get("status") == "unmeasured":
            continue
        expected = complexity_index(stage.get("ksloc", 0))
        actual = stage.get("complexity_index")
        if actual is None or abs(actual - expected) > 1e-6:
            raise SelfAssessError(
                f"complexity_score_summary: stage {stage.get('stage')!r} "
                f"complexity_index {actual!r} does not match the recomputed "
                f"value {expected!r}."
            )


def validate_business_rules_summary(data):
    for rule in data.get("rules", []):
        if rule.get("priority") == "P0" and rule.get("panel_confirmed") is not True:
            raise SelfAssessError(
                f"business_rules_summary: P0 rule {rule.get('id')!r} is missing "
                "panel_confirmed: true."
            )


def validate_stage_graph(data):
    wires = data.get("wires", [])
    if data.get("edgeCount") != len(wires):
        raise SelfAssessError(
            f"stage_graph: edgeCount {data.get('edgeCount')!r} does not match "
            f"len(wires)={len(wires)}."
        )


def validate_ci_topology_summary(data):
    for finding in data.get("findings", []):
        if "raw_remote_url" in finding:
            raise SelfAssessError(
                "ci_topology_summary: a finding carries raw_remote_url; remote "
                "URLs must be masked before persisting "
                "(rule: credential-masking-in-output)."
            )


def validate_ui_audit_summary(data):
    for finding in data.get("findings", []):
        if finding.get("kind") == "contrast" and not finding.get("heuristic"):
            raise SelfAssessError(
                "ui_audit_summary: a contrast finding is missing heuristic: true."
            )


_ARCH_HEALTH_TYPES = {"god-module", "cycle", "layering-violation"}


def validate_arch_health_summary(data):
    for finding in data.get("findings", []):
        if finding.get("type") not in _ARCH_HEALTH_TYPES:
            raise SelfAssessError(
                f"arch_health_summary: finding type {finding.get('type')!r} is "
                f"not one of {sorted(_ARCH_HEALTH_TYPES)!r}."
            )
        if finding.get("type") == "cycle" and len(finding.get("members", [])) < 2:
            raise SelfAssessError(
                "arch_health_summary: a cycle finding has fewer than 2 members."
            )


_CODE_IDIOM_CATEGORIES = {"modernization", "smell"}


def validate_code_idiom_summary(data):
    for finding in data.get("findings", []):
        if finding.get("category") not in _CODE_IDIOM_CATEGORIES:
            raise SelfAssessError(
                f"code_idiom_summary: finding category "
                f"{finding.get('category')!r} is not one of "
                f"{sorted(_CODE_IDIOM_CATEGORIES)!r}."
            )


def validate_lint_audit_summary(data):
    dispatched = data.get("rules_dispatched", [])
    skipped = data.get("rules_skipped", [])
    max_rules = data.get("max_rules", 12)
    if len(dispatched) + len(skipped) > max_rules and not skipped:
        raise SelfAssessError(
            "lint_audit_summary: rules were extracted beyond the cap but "
            "rules_skipped is empty."
        )


_PREFLIGHT_CHECK_NAMES = {"languages", "tools", "smoke_parse", "house_rules", "git_remotes_ci", "docs"}
_PREFLIGHT_VERDICTS = {"Ready", "Ready-with-gaps", "Not-ready"}


def validate_preflight_summary(data):
    checks = data.get("checks", {})
    missing = _PREFLIGHT_CHECK_NAMES - set(checks)
    if missing:
        raise SelfAssessError(f"preflight_summary: missing check(s) {sorted(missing)!r}.")
    for verdict in data.get("verdicts", {}).values():
        if verdict not in _PREFLIGHT_VERDICTS:
            raise SelfAssessError(
                f"preflight_summary: verdict {verdict!r} is not one of "
                f"{sorted(_PREFLIGHT_VERDICTS)!r}."
            )


_TRANSFORM_DECISIONS = {"Keep", "Keep(1:1)", "Merge", "Split", "Layering-fix"}


def validate_transform_brief_summary(data):
    for phase in data.get("phases", []):
        _require_fields(phase, ("phase_number", "decision", "open_questions", "work_items"), "transform_brief_summary")
        if phase["decision"] not in _TRANSFORM_DECISIONS:
            raise SelfAssessError(
                f"transform_brief_summary: decision {phase['decision']!r} is "
                f"not one of {sorted(_TRANSFORM_DECISIONS)!r}."
            )


_DOCS_DRIFT_STATUSES = {"confirmed", "contradicted", "unverifiable"}


def validate_docs_drift_summary(data):
    for claim in data.get("claims", []):
        status = claim.get("status")
        if status not in _DOCS_DRIFT_STATUSES:
            raise SelfAssessError(
                f"docs_drift_summary: claim status {status!r} is not one of "
                f"{sorted(_DOCS_DRIFT_STATUSES)!r}."
            )


def validate_file_stage_index(data):
    if not isinstance(data, dict):
        raise SelfAssessError("file_stage_index: expected a JSON object mapping file -> stage.")


VALIDATORS = {
    "arch_health_summary": validate_arch_health_summary,
    "ci_topology_summary": validate_ci_topology_summary,
    "code_idiom_summary": validate_code_idiom_summary,
    "complexity_score_summary": validate_complexity_score_summary,
    "docs_drift_summary": validate_docs_drift_summary,
    "business_rules_summary": validate_business_rules_summary,
    "lint_audit_summary": validate_lint_audit_summary,
    "preflight_summary": validate_preflight_summary,
    "stage_graph": validate_stage_graph,
    "file_stage_index": validate_file_stage_index,
    "transform_brief_summary": validate_transform_brief_summary,
    "ui_audit_summary": validate_ui_audit_summary,
}


def validate(kind, data):
    validator = VALIDATORS.get(kind)
    if validator is None:
        raise SelfAssessError(f"validators: unknown artifact kind {kind!r}.")
    validator(data)
