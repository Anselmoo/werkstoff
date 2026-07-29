"""Load and default .claude/self-assess.local.md's YAML frontmatter.

Uses a small hand-written indentation parser rather than a YAML dependency:
every real settings file (all test fixtures, all skills' documented shape)
is at most two levels of nesting with scalar/bool/int leaves and no lists of
mappings, so a full YAML implementation would be unused surface area, not a
correctness improvement.
"""
import copy
import os

from lib.errors import SelfAssessError

DEFAULTS = {
    "enabled": True,
    "output_dir": "analysis/self-assess",
    "skip_verification": False,
    "lint_max_rules": 12,
    "require_clean_tree": True,
    "transform": {"mode": "plan", "authorized_phases": []},
    "idiom_fix": {"mode": "propose"},
    "extract_rules": {"maxRounds": 4},
    "autopilot": {"fix_approved": False, "approved_phases": []},
}


def _parse_scalar(raw):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [] if not inner else [_parse_scalar(item) for item in inner.split(",")]
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw == "null" or raw == "~" or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_block(lines, start, indent):
    result = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        current_indent = len(line) - len(line.lstrip(" "))
        if current_indent < indent:
            break
        stripped = line.strip()
        if ":" not in stripped:
            i += 1
            continue
        key, _, rest = stripped.partition(":")
        key, rest = key.strip(), rest.strip()
        if rest == "":
            child, i = _parse_block(lines, i + 1, current_indent + 2)
            result[key] = child
        else:
            result[key] = _parse_scalar(rest)
            i += 1
    return result, i


def _parse_frontmatter(text):
    lines = text.splitlines()
    delimiters = [idx for idx, line in enumerate(lines) if line.strip() == "---"]
    if len(delimiters) < 2:
        return {}
    body = lines[delimiters[0] + 1 : delimiters[1]]
    parsed, _ = _parse_block(body, 0, 0)
    return parsed


def _deep_merge(base, overrides):
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(repo):
    """Read .claude/self-assess.local.md if present, defaulted onto DEFAULTS.

    Absence of the file is not an error -- it means fully-defaulted config.
    """
    settings_path = os.path.join(repo, ".claude", "self-assess.local.md")
    overrides = {}
    if os.path.isfile(settings_path):
        with open(settings_path, "r", encoding="utf-8") as fh:
            overrides = _parse_frontmatter(fh.read())
    return _deep_merge(DEFAULTS, overrides)


def require_enabled(settings, skill):
    """Raise SelfAssessError if self-assess, or this specific skill, is disabled."""
    if not settings.get("enabled", True):
        raise SelfAssessError(
            "self-assess is disabled (enabled: false) in .claude/self-assess.local.md."
        )
    skill_override = settings.get(skill)
    if isinstance(skill_override, dict) and skill_override.get("enabled") is False:
        raise SelfAssessError(
            f"{skill} is disabled (enabled: false under its own key) in "
            ".claude/self-assess.local.md."
        )
