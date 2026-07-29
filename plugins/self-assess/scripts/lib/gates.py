"""Rule-refusal gates. Every function here raises SelfAssessError on refusal
and returns normally (never a sentinel) on authorization -- this is what
lets self_assess_cli.py's single top-level except SelfAssessError handler
cover all of them uniformly.
"""
import subprocess

from lib.errors import SelfAssessError

KEEP_DECISIONS = {"Keep", "Keep(1:1)"}


def _is_git_repo(path):
    result = subprocess.run(
        ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def check_dirty_tree(repo, require_clean_tree):
    """Return the list of changed paths. Raise when dirty and
    require_clean_tree is True. Raise (fail closed) on a non-git directory,
    since cleanliness can't be determined there at all."""
    if not _is_git_repo(repo):
        raise SelfAssessError(
            f"{repo!r} is not a git repository; tree cleanliness cannot be "
            "determined (rule: dirty-tree-gate-ask-before-edit)."
        )
    result = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    changed = [line[3:] for line in result.stdout.splitlines() if line.strip()]
    if changed and require_clean_tree:
        raise SelfAssessError(
            f"working tree has {len(changed)} uncommitted change(s); refuse to "
            "edit until it's clean, or set require_clean_tree: false "
            "(rule: dirty-tree-gate-ask-before-edit)."
        )
    return changed


def check_transform_mode(settings):
    mode = (settings.get("transform") or {}).get("mode")
    if mode != "execute":
        raise SelfAssessError(
            f"transform.mode is {mode!r}, not 'execute'; "
            "self-assess-transform-execute is not authorized to run "
            "(rule: transform-execute-gate-transform-mode)."
        )


def check_phase_authorized(settings, phase):
    authorized = (settings.get("transform") or {}).get("authorized_phases") or []
    if phase not in authorized:
        raise SelfAssessError(
            f"phase {phase} is not in transform.authorized_phases {authorized!r} "
            "(rule: transform-execute-gate-transform-mode)."
        )


def _question_key(question):
    if isinstance(question, dict):
        return question.get("id", question.get("question"))
    return question


def check_open_questions_resolved(open_questions, resolutions):
    unresolved = [q for q in open_questions if _question_key(q) not in resolutions]
    if unresolved:
        raise SelfAssessError(
            f"{len(unresolved)} Open Question(s) have no resolution: "
            f"{[_question_key(q) for q in unresolved]!r} "
            "(rule: transform-open-questions-resolved-gate)."
        )


def check_not_keep_phase(decision):
    if decision in KEEP_DECISIONS:
        raise SelfAssessError(
            f"decision {decision!r} is a Keep phase, which is not executable "
            "by self-assess-transform-execute (rule: transform-keep-phase-not-executable)."
        )


def check_idiom_fix_mode(settings):
    mode = (settings.get("idiom_fix") or {}).get("mode")
    if mode != "fix":
        raise SelfAssessError(
            f"idiom_fix.mode is {mode!r}, not 'fix'; self-assess-idiom-fix is "
            "not authorized to apply changes (rule: idiom-fix-mode-fix-gate)."
        )


def filter_eligible_idiom_findings(findings):
    eligible, skipped = [], []
    for finding in findings:
        if finding.get("category") != "modernization":
            skipped.append({**finding, "skipReason": "category!=modernization"})
        elif finding.get("severityNote"):
            skipped.append({**finding, "skipReason": "severityNote present"})
        else:
            eligible.append(finding)
    return eligible, skipped


def check_portfolio_scope(cwd, explicit_dir):
    if not explicit_dir and _is_git_repo(cwd):
        raise SelfAssessError(
            f"{cwd!r} is itself a git repository; self-assess-portfolio needs "
            "an explicit portfolio directory when run from inside one "
            "(rule: portfolio-cwd-git-repo-check)."
        )


def require_git_repo(repo, caller):
    if not _is_git_repo(repo):
        raise SelfAssessError(
            f"{repo!r} is not a git repository; {caller} requires git."
        )


def check_autopilot_fix_approved(settings):
    if not (settings.get("autopilot") or {}).get("fix_approved"):
        raise SelfAssessError(
            "autopilot.fix_approved is not true in .claude/self-assess.local.md; "
            "self-assess-autopilot is not authorized to apply fixes "
            "(rule: autopilot-fix-approval-gate)."
        )
