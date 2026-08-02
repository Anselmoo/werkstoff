#!/usr/bin/env python3
"""Single CLI entry point over scripts/lib/*.

Skills invoke this instead of restating any of the plugin's MUST/MUST NOT
rules in prose. Every subcommand either:
  - prints a JSON result to stdout and exits 0, or
  - prints an error message to stderr and exits 1 (a rule refusal).

A skill that gets a non-zero exit from this CLI MUST stop and surface the
stderr message to the user -- it is not a suggestion, it is the rule firing.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (  # noqa: E402
    attribution,
    credentials,
    edit_scope,
    formulas,
    gates,
    graph,
    language_detect,
    lint_cap,
    p0_panel,
    portfolio,
    rules_loop,
    scope,
    settings as settings_mod,
    skip_verification,
    staleness,
    status,
    transform_routing,
    validators,
    version_detect,
    write_guard,
)
from lib.errors import SelfAssessError  # noqa: E402


def _load_json_arg(value):
    """Accept either a path to a JSON file or an inline JSON string."""
    if value is None:
        return None
    if os.path.isfile(value):
        with open(value, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(value)


def _print(result):
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_check_enabled(args):
    s = settings_mod.load_settings(args.repo)
    settings_mod.require_enabled(s, args.skill)
    _print({"enabled": True, "settings": s})


def cmd_get_settings(args):
    s = settings_mod.load_settings(args.repo)
    _print(s)


def cmd_resolve_output_path(args):
    s = settings_mod.load_settings(args.repo)
    output_dir = args.output_dir or s["output_dir"]
    path = write_guard.resolve_output_path(args.repo, output_dir, args.filename)
    _print({"path": path})


def cmd_ensure_output_dir(args):
    s = settings_mod.load_settings(args.repo)
    output_dir = args.output_dir or s["output_dir"]
    path = write_guard.ensure_output_dir(args.repo, output_dir)
    _print({"output_dir": path})


def cmd_cap_lint_rules(args):
    rules = _load_json_arg(args.rules)
    dispatched, skipped = lint_cap.cap_rules(rules, args.max_rules)
    _print({"dispatched": dispatched, "skipped": skipped, "max_rules": args.max_rules or lint_cap.DEFAULT_MAX_RULES})


def cmd_validate_artifact(args):
    data = _load_json_arg(args.file)
    validators.validate(args.kind, data)
    _print({"valid": True, "kind": args.kind})


def cmd_dirty_tree_gate(args):
    lines = gates.check_dirty_tree(args.repo, require_clean_tree=not args.allow_dirty)
    _print({"clean": len(lines) == 0, "changed_paths": lines})


def cmd_transform_mode_gate(args):
    s = settings_mod.load_settings(args.repo)
    gates.check_transform_mode(s)
    gates.check_phase_authorized(s, args.phase)
    _print({"authorized": True, "phase": args.phase})


def cmd_open_questions_gate(args):
    open_questions = _load_json_arg(args.open_questions)
    resolutions = _load_json_arg(args.resolutions) or {}
    gates.check_open_questions_resolved(open_questions, resolutions)
    _print({"resolved": True})


def cmd_keep_phase_gate(args):
    gates.check_not_keep_phase(args.decision)
    _print({"executable": True, "decision": args.decision})


def cmd_idiom_fix_mode_gate(args):
    s = settings_mod.load_settings(args.repo)
    gates.check_idiom_fix_mode(s)
    _print({"authorized": True})


def cmd_filter_idiom_findings(args):
    findings = _load_json_arg(args.findings)
    eligible, skipped = gates.filter_eligible_idiom_findings(findings)
    _print({"eligible": eligible, "skipped": skipped})


def cmd_portfolio_scope_gate(args):
    gates.check_portfolio_scope(args.cwd, args.explicit_dir)
    _print({"scope_ok": True, "portfolio_dir": args.explicit_dir or args.cwd})


def cmd_mask_text(args):
    _print({"masked": credentials.mask_text(args.text)})


def cmd_complexity_index(args):
    _print({"ksloc": args.ksloc, "complexity_index": formulas.complexity_index(args.ksloc)})


def cmd_work_item_rank(args):
    rank = formulas.work_item_rank(args.severity, args.complexity_weight)
    _print({"severity": args.severity, "complexity_weight": args.complexity_weight, "rank": rank})


def cmd_detect_languages(args):
    manifests = _load_json_arg(args.manifests)
    ext_counts = _load_json_arg(args.extension_counts)
    _print(language_detect.detect_languages(manifests, ext_counts))


def cmd_find_cycles(args):
    graph_data = _load_json_arg(args.stage_graph)
    cycles = graph.find_cycles(graph_data["stages"], [tuple(w) for w in graph_data["wires"]])
    _print({"cycles": [sorted(c) for c in cycles]})


def cmd_find_god_modules(args):
    graph_data = _load_json_arg(args.stage_graph)
    result = graph.find_god_modules(graph_data["stages"], [tuple(w) for w in graph_data["wires"]])
    _print({"god_modules": [{"stage": s, "fan_in": c} for s, c in result]})


def cmd_rules_loop_check(args):
    controller = rules_loop.RuleLoopController(args.max_rounds)
    controller.round_number = args.round_number
    controller.consecutive_dry_rounds = args.consecutive_dry_rounds
    should_continue = controller.should_continue()
    _print({"should_continue": should_continue, "stopped_reason": controller.stopped_reason})


def cmd_p0_confirm(args):
    rule = _load_json_arg(args.rule)
    judges = _load_json_arg(args.judges)
    _print(p0_panel.confirm_p0_rule(rule, judges))


def cmd_label_findings(args):
    findings = _load_json_arg(args.findings)
    s = settings_mod.load_settings(args.repo)
    skip = s.get("skip_verification", False)
    _print({"findings": skip_verification.label_findings(findings, skip)})


def cmd_status_present_artifacts(args):
    s = settings_mod.load_settings(args.repo)
    output_dir = args.output_dir or s["output_dir"]
    output_abs = os.path.join(os.path.realpath(args.repo), output_dir)
    present = status.build_present_artifacts(output_abs)
    structural = status.build_structural_artifacts(output_abs)
    recommend_brief = status.recommend_transform_brief(output_abs)
    _print({"present": present, "structural": structural, "recommend_transform_brief": recommend_brief})


def cmd_grade_repo(args):
    _print({"grade": portfolio.grade_repo(args.has_artifacts, args.has_high, args.has_medium_or_gaps)})


def cmd_require_git_repo(args):
    gates.require_git_repo(args.repo, args.caller)
    _print({"under_git": True})


def cmd_exclude_ci_claims(args):
    claims = _load_json_arg(args.claims)
    in_scope, excluded = scope.exclude_ci_claims(claims)
    _print({"in_scope": in_scope, "excluded_to_ci_topology": excluded})


def cmd_attribute_citation(args):
    file_stage_index = _load_json_arg(args.file_stage_index) if args.file_stage_index else None
    _print({"stage": attribution.attribute(args.citation, file_stage_index)})


def cmd_route_confab_finding(args):
    finding = _load_json_arg(args.finding)
    _print({"route": transform_routing.route_confab_finding(finding)})


def cmd_flag_p0_blockers(args):
    rules = _load_json_arg(args.rules)
    _print({"blockers": transform_routing.flag_p0_blockers(rules)})


def cmd_detect_language_version(args):
    _print({"version": version_detect.detect_language_version(args.repo, args.language)})


def cmd_staleness_check(args):
    ts = staleness.latest_commit_timestamp(args.repo)
    result = {}
    for artifact_path in args.artifact:
        result[artifact_path] = staleness.is_stale(artifact_path, ts)
    _print({"latest_commit_ts": ts, "stale": result})


def cmd_stage_map_fresh_check(args):
    s = settings_mod.load_settings(args.repo)
    output_dir = args.output_dir or s["output_dir"]
    output_abs = os.path.join(os.path.realpath(args.repo), output_dir)
    fresh = staleness.stage_map_fresh(output_abs, args.repo)
    _print({"fresh": fresh, "required_artifacts": list(staleness.STAGE_MAP_REQUIRED_ARTIFACTS)})


def cmd_autopilot_fix_gate(args):
    s = settings_mod.load_settings(args.repo)
    gates.check_autopilot_fix_approved(s)
    _print({"fix_approved": True})


def cmd_open_edit_scope(args):
    s = settings_mod.load_settings(args.repo)
    if args.mode == "idiom_fix":
        gates.check_idiom_fix_mode(s)
    else:
        gates.check_transform_mode(s)
    path, resolved = edit_scope.open_scope(args.repo, mode=args.mode, allowed_files=args.files)
    _print({"scopePath": path, "allowedFiles": resolved})


def cmd_close_edit_scope(args):
    edit_scope.close_scope(args.repo)
    _print({"closed": True})


def build_parser():
    parser = argparse.ArgumentParser(prog="self_assess_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-enabled")
    p.add_argument("--repo", required=True)
    p.add_argument("--skill", required=True)
    p.set_defaults(func=cmd_check_enabled)

    p = sub.add_parser("get-settings")
    p.add_argument("--repo", required=True)
    p.set_defaults(func=cmd_get_settings)

    p = sub.add_parser("resolve-output-path")
    p.add_argument("--repo", required=True)
    p.add_argument("--output-dir")
    p.add_argument("--filename", required=True)
    p.set_defaults(func=cmd_resolve_output_path)

    p = sub.add_parser("ensure-output-dir")
    p.add_argument("--repo", required=True)
    p.add_argument("--output-dir")
    p.set_defaults(func=cmd_ensure_output_dir)

    p = sub.add_parser("cap-lint-rules")
    p.add_argument("--rules", required=True, help="JSON file or inline JSON list")
    p.add_argument("--max-rules", type=int)
    p.set_defaults(func=cmd_cap_lint_rules)

    p = sub.add_parser("validate-artifact")
    p.add_argument("--kind", required=True, choices=sorted(validators.VALIDATORS))
    p.add_argument("--file", required=True, help="JSON file or inline JSON")
    p.set_defaults(func=cmd_validate_artifact)

    p = sub.add_parser("dirty-tree-gate")
    p.add_argument("--repo", required=True)
    p.add_argument("--allow-dirty", action="store_true")
    p.set_defaults(func=cmd_dirty_tree_gate)

    p = sub.add_parser("transform-mode-gate")
    p.add_argument("--repo", required=True)
    p.add_argument("--phase", required=True, type=int)
    p.set_defaults(func=cmd_transform_mode_gate)

    p = sub.add_parser("open-questions-gate")
    p.add_argument("--open-questions", required=True)
    p.add_argument("--resolutions", required=True)
    p.set_defaults(func=cmd_open_questions_gate)

    p = sub.add_parser("keep-phase-gate")
    p.add_argument("--decision", required=True)
    p.set_defaults(func=cmd_keep_phase_gate)

    p = sub.add_parser("idiom-fix-mode-gate")
    p.add_argument("--repo", required=True)
    p.set_defaults(func=cmd_idiom_fix_mode_gate)

    p = sub.add_parser("filter-idiom-findings")
    p.add_argument("--findings", required=True)
    p.set_defaults(func=cmd_filter_idiom_findings)

    p = sub.add_parser("portfolio-scope-gate")
    p.add_argument("--cwd", required=True)
    p.add_argument("--explicit-dir")
    p.set_defaults(func=cmd_portfolio_scope_gate)

    p = sub.add_parser("mask-text")
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_mask_text)

    p = sub.add_parser("complexity-index")
    p.add_argument("--ksloc", required=True, type=float)
    p.set_defaults(func=cmd_complexity_index)

    p = sub.add_parser("work-item-rank")
    p.add_argument("--severity", required=True)
    p.add_argument("--complexity-weight", type=float)
    p.set_defaults(func=cmd_work_item_rank)

    p = sub.add_parser("detect-languages")
    p.add_argument("--manifests", required=True)
    p.add_argument("--extension-counts", required=True)
    p.set_defaults(func=cmd_detect_languages)

    p = sub.add_parser("find-cycles")
    p.add_argument("--stage-graph", required=True)
    p.set_defaults(func=cmd_find_cycles)

    p = sub.add_parser("find-god-modules")
    p.add_argument("--stage-graph", required=True)
    p.set_defaults(func=cmd_find_god_modules)

    p = sub.add_parser("rules-loop-check")
    p.add_argument("--round-number", required=True, type=int)
    p.add_argument("--consecutive-dry-rounds", required=True, type=int)
    p.add_argument("--max-rounds", type=int)
    p.set_defaults(func=cmd_rules_loop_check)

    p = sub.add_parser("p0-confirm")
    p.add_argument("--rule", required=True)
    p.add_argument("--judges", required=True)
    p.set_defaults(func=cmd_p0_confirm)

    p = sub.add_parser("label-findings")
    p.add_argument("--repo", required=True)
    p.add_argument("--findings", required=True)
    p.set_defaults(func=cmd_label_findings)

    p = sub.add_parser("status-present-artifacts")
    p.add_argument("--repo", required=True)
    p.add_argument("--output-dir")
    p.set_defaults(func=cmd_status_present_artifacts)

    p = sub.add_parser("grade-repo")
    p.add_argument("--has-artifacts", action="store_true")
    p.add_argument("--has-high", action="store_true")
    p.add_argument("--has-medium-or-gaps", action="store_true")
    p.set_defaults(func=cmd_grade_repo)

    p = sub.add_parser("require-git-repo")
    p.add_argument("--repo", required=True)
    p.add_argument("--caller", required=True)
    p.set_defaults(func=cmd_require_git_repo)

    p = sub.add_parser("exclude-ci-claims")
    p.add_argument("--claims", required=True)
    p.set_defaults(func=cmd_exclude_ci_claims)

    p = sub.add_parser("attribute-citation")
    p.add_argument("--citation", required=True)
    p.add_argument("--file-stage-index")
    p.set_defaults(func=cmd_attribute_citation)

    p = sub.add_parser("route-confab-finding")
    p.add_argument("--finding", required=True)
    p.set_defaults(func=cmd_route_confab_finding)

    p = sub.add_parser("flag-p0-blockers")
    p.add_argument("--rules", required=True)
    p.set_defaults(func=cmd_flag_p0_blockers)

    p = sub.add_parser("detect-language-version")
    p.add_argument("--repo", required=True)
    p.add_argument("--language", required=True)
    p.set_defaults(func=cmd_detect_language_version)

    p = sub.add_parser("staleness-check")
    p.add_argument("--repo", required=True)
    p.add_argument("--artifact", required=True, action="append")
    p.set_defaults(func=cmd_staleness_check)

    p = sub.add_parser("stage-map-fresh-check")
    p.add_argument("--repo", required=True)
    p.add_argument("--output-dir")
    p.set_defaults(func=cmd_stage_map_fresh_check)

    p = sub.add_parser("autopilot-fix-gate")
    p.add_argument("--repo", required=True)
    p.set_defaults(func=cmd_autopilot_fix_gate)

    p = sub.add_parser("open-edit-scope")
    p.add_argument("--repo", required=True)
    p.add_argument("--mode", required=True, choices=("idiom_fix", "transform"))
    p.add_argument("--files", required=True, nargs="+")
    p.set_defaults(func=cmd_open_edit_scope)

    p = sub.add_parser("close-edit-scope")
    p.add_argument("--repo", required=True)
    p.set_defaults(func=cmd_close_edit_scope)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except SelfAssessError as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
