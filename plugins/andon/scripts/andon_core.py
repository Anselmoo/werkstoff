#!/usr/bin/env python3
"""
andon_core.py -- executable enforcement library + CLI for the andon plugin.

This module is the single source of mechanical truth for every rule in the
andon behavioral spec whose "must" says MUST NOT / MUST refuse / MUST halt /
MUST stop. Skills invoke this file as a CLI (subcommands below); hooks import
it as a library. Nothing here is advisory -- every guard either returns a
structured refusal or raises, and callers (skills, hooks) are required to
respect the exit code / JSON "allowed" field rather than re-deciding in prose.

No third-party dependencies (stdlib only) so it runs in any Python 3.8+.
"""

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Named constants (spec numeric bounds -- never re-derive these ad hoc)
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = "analysis/andon"
DEFAULT_LEDGER_DIR = "analysis/andon/ledger"
DEFAULT_AUTHORIZATION_LEVEL = "local+reversible"
DEFAULT_GAP_SOURCE = "self-scan"
DEFAULT_SELF_ASSESS_OUTPUT_DIR = "analysis/self-assess"
DEFAULT_HOUSE_RULES_PATH = ".claude/house-rules.md"
DEFAULT_SKIP_VERIFICATION = False
DEFAULT_ENABLED = True

SETTINGS_PATH = ".claude/andon.local.md"

BLAST_RADIUS_ORDER = ["local+reversible", "hard-to-reverse", "shared-state-visible"]
GAP_KINDS = ["bug", "feature", "wire"]
STAGE_CONFIDENCE_LEVELS = ["self-assess-backed", "heuristic", "single-package"]
GAP_STATUSES = ["open", "closed"]
WIRE_VERDICTS = ["green", "red", "unknown"]
STRATEGY_LETTERS = ["a", "b", "c", "d", "e", "f", "g"]
TIERS = [1, 2, 3]
LANES = ["fast", "slow"]

SUB_CYCLE_REOPEN_LIMIT = 3          # "3 or more times" -> escalate, stop sub-cycling
SUB_CYCLE_UPSTREAM_DEPTH = 2        # N-2 stages back, never further

RUNG_NAMES = {
    0: "type-system",
    1: "static-structural",
    2: "rendered-deterministic",
    3: "headless-dom-aria",
    4: "visual-and-llm",
}
DEFECT_CLASS_MIN_RUNG = {
    "type-or-schema": 0,
    "structure-or-lint": 1,
    "deterministic-behavior": 2,
    "rendered-assertion": 3,
    "subjective-quality": 4,
}

# Strategy check order for the wire classifier. Strategy 'a' (tribunal) is the
# universal, prerequisite-free fallback -- it is NEVER selected by "defaulting",
# only by every other trigger failing to match (strategy-routing-not-default).
CLASSIFIER_ORDER = ["e", "b", "f", "g", "d", "c", "a"]

TRIGGER_FLAG_BY_STRATEGY = {
    "e": "is_structural_claim",
    "b": "is_numerical",
    "f": "is_property_invariant",
    "g": "is_verifier_of_verifier",
    "d": "is_autonomous_reliability",
    "c": "is_epistemic_claim",
    "a": None,  # fallback, no trigger flag required
}

PREREQ_FLAG_BY_STRATEGY = {
    "e": "available_lsp_or_index",
    "b": None,  # no external prerequisite
    "f": "available_property_lib",
    "g": None,
    "d": "available_confab",
    "c": None,
    "a": None,  # tribunal always available (Read/Grep/Glob agents only)
}

# A conservative denylist + pattern set for the NO-PERSONA rule. This is a
# heuristic, not a natural-language understanding system -- it exists to give
# strategy c (and all strategies) a real, code-executed check rather than a
# sentence telling the model not to do it.
NAMED_PERSON_DENYLIST = [
    "robert c. martin", "uncle bob", "martin fowler", "kent beck",
    "alan turing", "albert einstein", "edsger dijkstra", "donald knuth",
    "linus torvalds", "grace hopper", "ada lovelace", "sherlock holmes",
    "richard feynman", "steve jobs", "guido van rossum",
]
AUTHORITY_PHRASE_RE = re.compile(
    r"\b(as|per|according to|quoting|cites?|invoking)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)?)\s+(said|says|once said|argued|put it|would say)",
    re.IGNORECASE,
)
PROPER_NAME_RE = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")

CREDENTIAL_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*([^\s\"']{6,})"),
    re.compile(r"\b[A-Za-z0-9_\-]{20,}\b"),  # long opaque tokens
]


class AndonError(Exception):
    """Raised for any refusal. Callers must catch and surface, never swallow."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def now_iso():
    # Deterministic wall-clock read is fine here (this runs as a real CLI
    # process, not inside a Workflow script), unlike the Workflow sandbox.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Minimal frontmatter codec (no PyYAML dependency; we control both reader and
# writer, so we only need to support the constrained subset OKF docs use).
# ---------------------------------------------------------------------------

def _parse_scalar(raw):
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if raw.lower() in ("null", "~", "none"):
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        items = [x.strip() for x in inner.split(",")]
        return [_parse_scalar(x) for x in items]
    if raw.startswith("{") and raw.endswith("}"):
        # Nested objects (e.g. a gap's `proposal`) are stored as compact JSON,
        # which is a valid YAML flow-mapping -- round-trips as a real dict
        # rather than a stringified repr.
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def parse_frontmatter(text):
    """Returns (fields_dict, body_str). Requires '---' fenced frontmatter."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n")
    if parts[0].strip() != "---":
        return {}, text
    end_idx = None
    for i in range(1, len(parts)):
        if parts[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text
    fm_lines = parts[1:end_idx]
    body = "\n".join(parts[end_idx + 1:]).lstrip("\n")
    fields = {}
    current_list_key = None
    for line in fm_lines:
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            fields[current_list_key].append(_parse_scalar(line[4:]))
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2)
        if raw == "":
            fields[key] = []
            current_list_key = key
        else:
            fields[key] = _parse_scalar(raw)
            current_list_key = None
    return fields, body


def _dump_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, dict):
        return json.dumps(value)  # compact JSON is a valid YAML flow-mapping
    s = str(value)
    if any(c in s for c in [":", "#", "[", "]", "{", "}", '"']) or s == "":
        return json.dumps(s)
    return s


def dump_frontmatter(fields, body=""):
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_dump_scalar(item)}")
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    lines.append("---")
    text = "\n".join(lines) + "\n"
    if body:
        text += body if body.startswith("\n") else "\n" + body
    return text


# ---------------------------------------------------------------------------
# Settings (rule: settings-read-honored)
# ---------------------------------------------------------------------------

def default_settings():
    return {
        "enabled": DEFAULT_ENABLED,
        "output_dir": DEFAULT_OUTPUT_DIR,
        "ledger_dir": DEFAULT_LEDGER_DIR,
        "authorization_level": DEFAULT_AUTHORIZATION_LEVEL,
        "skip_verification": DEFAULT_SKIP_VERIFICATION,
        "gap_source": DEFAULT_GAP_SOURCE,
        "self_assess_output_dir": DEFAULT_SELF_ASSESS_OUTPUT_DIR,
        "house_rules_path": DEFAULT_HOUSE_RULES_PATH,
    }


def load_settings(repo_root):
    """Reads .claude/andon.local.md if present; else documented defaults.
    Returns dict with an extra '_settings_file_present' bool key.
    """
    settings = default_settings()
    path = os.path.join(repo_root, SETTINGS_PATH)
    if not os.path.isfile(path):
        settings["_settings_file_present"] = False
        return settings
    with io.open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    fields, _ = parse_frontmatter(text)
    for key in list(settings.keys()):
        if key in fields:
            settings[key] = fields[key]
    settings["_settings_file_present"] = True
    return settings


def enforce_enabled_or_halt(settings):
    """MUST halt immediately without running any phase if enabled: false."""
    if settings.get("enabled", DEFAULT_ENABLED) is False:
        raise AndonError(
            "DISABLED",
            "andon is disabled via .claude/andon.local.md (enabled: false). "
            "Halting before running any phase. Set enabled: true (or remove "
            "the file) to re-enable.",
        )


# ---------------------------------------------------------------------------
# Write-scope enforcement (rule: write-scope enforced before dispatch)
# ---------------------------------------------------------------------------

def validate_write_path(raw_path, repo_root, allowed_dir):
    """Rejects path traversal, absolute paths, and targets outside allowed_dir.
    Returns the safe absolute path on success; raises AndonError otherwise.
    """
    if os.path.isabs(raw_path):
        raise AndonError(
            "WRITE_SCOPE_ABSOLUTE",
            f"Refusing to write to absolute path {raw_path!r}; andon only "
            f"writes relative paths inside its declared directories.",
        )
    if ".." in raw_path.replace("\\", "/").split("/"):
        raise AndonError(
            "WRITE_SCOPE_TRAVERSAL",
            f"Refusing to write to {raw_path!r}: contains a '..' path-traversal segment.",
        )
    allowed_abs = os.path.realpath(os.path.join(repo_root, allowed_dir))
    target_abs = os.path.realpath(os.path.join(repo_root, raw_path))
    if os.path.commonpath([allowed_abs, target_abs]) != allowed_abs:
        raise AndonError(
            "WRITE_SCOPE_OUTSIDE",
            f"Refusing to write to {raw_path!r}: resolves outside the declared "
            f"output directory {allowed_dir!r}.",
        )
    return target_abs


# ---------------------------------------------------------------------------
# OKF ledger schema validation (rule: okf-ledger-schema-conformance,
# fields-that-gate-a-decision-are-first-class-keys, persisted-state-validated)
# ---------------------------------------------------------------------------

REQUIRED_BY_TYPE = {
    "stage": ["type", "title", "order", "confidence"],
    "gap": ["type", "title", "stage", "kind", "status"],
    "evidence": ["type", "title", "wire", "strategy", "verdict"],
}


def validate_doc(fields):
    """Rejects a record missing a field that gates a decision. Never infers,
    defaults, or repairs a missing gating value.
    """
    doc_type = fields.get("type")
    if doc_type not in REQUIRED_BY_TYPE:
        raise AndonError(
            "SCHEMA_BAD_TYPE",
            f"OKF doc 'type' must be one of {list(REQUIRED_BY_TYPE)}, got {doc_type!r}.",
        )
    missing = [k for k in REQUIRED_BY_TYPE[doc_type] if fields.get(k) in (None, "")]
    if missing:
        raise AndonError(
            "SCHEMA_MISSING_FIELD",
            f"OKF {doc_type} doc is missing required gating field(s): {missing}. "
            f"Refusing to write -- a value nobody supplied must never enter the ledger.",
        )

    if doc_type == "stage":
        if fields["confidence"] not in STAGE_CONFIDENCE_LEVELS:
            raise AndonError(
                "SCHEMA_BAD_CONFIDENCE",
                f"stage confidence must be one of {STAGE_CONFIDENCE_LEVELS}, got {fields['confidence']!r}.",
            )

    if doc_type == "gap":
        if fields["kind"] not in GAP_KINDS:
            raise AndonError("SCHEMA_BAD_KIND", f"gap kind must be one of {GAP_KINDS}, got {fields['kind']!r}.")
        if fields["status"] not in GAP_STATUSES:
            raise AndonError("SCHEMA_BAD_STATUS", f"gap status must be one of {GAP_STATUSES}, got {fields['status']!r}.")
        if fields["status"] == "closed" and not fields.get("resolved_by"):
            raise AndonError(
                "SCHEMA_CLOSED_WITHOUT_EVIDENCE",
                "gap status:closed requires a 'resolved_by' wiki-link to the proving evidence doc.",
            )
        if fields.get("proposal") is not None:
            validate_blast_radius_tag(fields.get("blast_radius"))

    if doc_type == "evidence":
        if fields["verdict"] not in WIRE_VERDICTS:
            raise AndonError("SCHEMA_BAD_VERDICT", f"evidence verdict must be one of {WIRE_VERDICTS}, got {fields['verdict']!r}.")
        if fields["strategy"] not in STRATEGY_LETTERS:
            raise AndonError("SCHEMA_BAD_STRATEGY", f"evidence strategy must be one of {STRATEGY_LETTERS}, got {fields['strategy']!r}.")
        tier = fields.get("tier")
        if fields["strategy"] == "e":
            if tier not in TIERS:
                raise AndonError("SCHEMA_MISSING_TIER", "evidence for strategy e must record tier (1|2|3).")
            if tier == 1 and fields.get("non_overridable") is not True:
                raise AndonError(
                    "SCHEMA_TIER1_MUST_BE_NON_OVERRIDABLE",
                    "Tier 1 structural-evidence contradictions must be labeled non_overridable: true.",
                )
        else:
            if tier is not None:
                raise AndonError("SCHEMA_TIER_ONLY_FOR_E", "tier tag is only valid when strategy is 'e'.")

    # kebab-case tag conformance (rule: okf-ledger-schema-conformance)
    for tag in fields.get("tags", []) or []:
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*(:[a-z0-9+.\-]+)?", str(tag)):
            raise AndonError("SCHEMA_BAD_TAG", f"tag {tag!r} is not kebab-case OKF tag syntax.")

    return True


def validate_blast_radius_tag(value):
    """Exactly one blast-radius tag: never zero, never multiple, never undefined."""
    if value is None:
        raise AndonError("BLAST_RADIUS_MISSING", "A proposal was recorded with zero blast-radius tags; exactly one is required.")
    if isinstance(value, list):
        raise AndonError("BLAST_RADIUS_MULTIPLE", f"Exactly one blast-radius tag is required, got a list: {value!r}.")
    if value not in BLAST_RADIUS_ORDER:
        raise AndonError("BLAST_RADIUS_UNDEFINED", f"blast_radius must be one of {BLAST_RADIUS_ORDER}, got {value!r}.")
    return value


def build_tags_for_doc(fields):
    """Derives OKF kebab-case tags from first-class fields (single source of truth)."""
    tags = []
    doc_type = fields.get("type")
    if doc_type == "gap":
        tags.append(f"kind:{fields['kind']}")
        tags.append(f"status:{fields['status']}")
        if fields.get("blast_radius"):
            tags.append(f"blast-radius:{fields['blast_radius']}")
        if fields.get("on_constraint"):
            tags.append("on-constraint:true")
    if doc_type == "evidence":
        tags.append(f"strategy:{fields['strategy']}")
        tags.append(f"verdict:{fields['verdict']}")
        if fields.get("tier") is not None:
            tags.append(f"tier:{fields['tier']}")
        if fields.get("lane"):
            tags.append(f"lane:{fields['lane']}")
    return tags


def write_doc(repo_root, ledger_dir, relative_path, fields, body=""):
    """Validates write-scope AND schema before touching disk. Refuses on any failure.

    relative_path is relative to ledger_dir (e.g. "stages/s1.md"), matching
    the on-disk layout ledger_dir/{stages,gaps,evidence}/*.md.
    """
    validate_doc(fields)
    fields = dict(fields)
    fields.setdefault("timestamp", now_iso())
    fields["tags"] = build_tags_for_doc(fields)
    full_relative = os.path.join(ledger_dir, relative_path)
    target_abs = validate_write_path(full_relative, repo_root, ledger_dir)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)
    with io.open(target_abs, "w", encoding="utf-8") as fh:
        fh.write(dump_frontmatter(fields, body))
    return target_abs


# ---------------------------------------------------------------------------
# Ledger init / resume (rule: ledger-init-or-resume, ledger-cursor-reconstruction)
# ---------------------------------------------------------------------------

def read_all_docs(ledger_dir, subdir):
    docs = []
    d = os.path.join(ledger_dir, subdir)
    if not os.path.isdir(d):
        return docs
    for name in sorted(os.listdir(d)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(d, name)
        with io.open(path, "r", encoding="utf-8") as fh:
            fields, body = parse_frontmatter(fh.read())
        docs.append({"path": path, "slug": name[:-3], "fields": fields, "body": body})
    return docs


def init_or_resume_ledger(repo_root, ledger_dir):
    log_path = os.path.join(repo_root, ledger_dir, "log.md")
    abs_ledger = os.path.join(repo_root, ledger_dir)
    if os.path.isfile(log_path):
        stages = read_all_docs(abs_ledger, "stages")
        gaps = read_all_docs(abs_ledger, "gaps")
        evidence = read_all_docs(abs_ledger, "evidence")
        open_gaps = [g for g in gaps if g["fields"].get("status") == "open"]
        stage_order = {s["fields"].get("title"): s["fields"].get("order", 0) for s in stages}
        if open_gaps:
            open_gaps.sort(key=lambda g: stage_order.get(g["fields"].get("stage"), 0))
            cursor = {"state": "open-gap", "stage": open_gaps[0]["fields"].get("stage"), "gap": open_gaps[0]["slug"]}
        else:
            cursor = {"state": "converged, no open gaps"}
        return {
            "resumed": True,
            "stages": stages,
            "gaps": gaps,
            "evidence": evidence,
            "cursor": cursor,
        }
    for sub in ("stages", "gaps", "evidence"):
        os.makedirs(os.path.join(abs_ledger, sub), exist_ok=True)
    with io.open(log_path, "w", encoding="utf-8") as fh:
        fh.write("# andon OKF log\n\nAppend-only. Never rewritten. See okf-ledger-schema.md.\n")
    return {"resumed": False, "stages": [], "gaps": [], "evidence": [], "cursor": {"state": "initialized"}}


# ---------------------------------------------------------------------------
# log.md append-only writer (rule: log-entries-append-only)
# ---------------------------------------------------------------------------

REQUIRED_LOG_FIELDS = {
    "pass": ["stage", "wire", "gap", "strategy", "verdict", "next_cursor", "cycle", "pass_number"],
    "cycle-converged": ["passes", "cycle"],
    "sub-cycle": ["wire", "depth", "reopen_count", "escalated"],
}


def append_log_entry(repo_root, ledger_dir, entry_kind, fields):
    if entry_kind not in REQUIRED_LOG_FIELDS:
        raise AndonError("LOG_BAD_KIND", f"Unknown log entry kind {entry_kind!r}.")
    missing = [k for k in REQUIRED_LOG_FIELDS[entry_kind] if fields.get(k) in (None, "")]
    if missing:
        raise AndonError("LOG_MISSING_FIELD", f"log.md {entry_kind} entry missing required field(s): {missing}.")
    log_path = validate_write_path(os.path.join(ledger_dir, "log.md"), repo_root, ledger_dir)
    ts = now_iso()
    lines = []
    if entry_kind == "pass":
        lines.append(f"### Pass {fields['pass_number']} (cycle {fields['cycle']}) -- {ts}")
        for k in ["stage", "wire", "gap", "strategy", "verdict", "next_cursor"]:
            lines.append(f"- {k.replace('_', '-')}: {fields[k]}")
    elif entry_kind == "cycle-converged":
        lines.append(f"### Cycle {fields['cycle']} converged after {fields['passes']} passes -- {ts}")
        lines.append(f"- stream-state: {fields.get('stream_state', 'all wires green')}")
        lines.append(f"- sub-cycle-count: {fields.get('sub_cycle_count', 0)}")
    elif entry_kind == "sub-cycle":
        lines.append(f"### Sub-cycle: {fields['wire']} reopened (count {fields['reopen_count']}) -- {ts}")
        lines.append(f"- depth: {fields['depth']}")
        lines.append(f"- escalated: {str(fields['escalated']).lower()}")
    lines.append("")
    # append-only: open in 'a' mode, never truncate/rewrite.
    with io.open(log_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return log_path


def parse_log_counters(repo_root, ledger_dir):
    log_path = os.path.join(repo_root, ledger_dir, "log.md")
    if not os.path.isfile(log_path):
        return None
    with io.open(log_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    passes = re.findall(r"^### Pass (\d+) \(cycle (\d+)\)", text, re.MULTILINE)
    cycles = re.findall(r"^### Cycle (\d+) converged after (\d+) passes", text, re.MULTILINE)
    sub_cycles = re.findall(r"^### Sub-cycle: (.+?) reopened \(count (\d+)\)", text, re.MULTILINE)
    total_passes = len(passes)
    current_cycle = int(passes[-1][1]) if passes else (int(cycles[-1][0]) + 1 if cycles else 1)
    pass_in_cycle = sum(1 for p in passes if int(p[1]) == current_cycle)
    reopen_counts = {}
    for wire, count in sub_cycles:
        reopen_counts[wire] = max(reopen_counts.get(wire, 0), int(count))
    return {
        "total_passes": total_passes,
        "current_cycle": current_cycle,
        "pass_in_cycle": pass_in_cycle,
        "cycles_converged": len(cycles),
        "reopen_counts": reopen_counts,
    }


# ---------------------------------------------------------------------------
# Convergence (rule: convergence-zero-gaps-all-green, pass-zero-gaps-convergence)
# ---------------------------------------------------------------------------

def check_convergence(gaps_closed_this_pass, wire_statuses):
    if gaps_closed_this_pass < 0:
        raise AndonError("CONVERGENCE_BAD_COUNT", "gaps_closed_this_pass cannot be negative.")
    all_green = all(status == "green" for status in wire_statuses)
    converged = (gaps_closed_this_pass == 0) and all_green
    return {"converged": converged, "all_wires_green": all_green, "gaps_closed_this_pass": gaps_closed_this_pass}


# ---------------------------------------------------------------------------
# Sub-cycle backtrack bounds (rule: sub-cycle-reopen-limit-three,
# sub-cycle-upstream-depth-n-minus-two)
# ---------------------------------------------------------------------------

def track_subcycle(repo_root, ledger_dir, wire_id, requested_upstream_depth):
    counters = parse_log_counters(repo_root, ledger_dir) or {"reopen_counts": {}}
    prior_count = counters["reopen_counts"].get(wire_id, 0)
    new_count = prior_count + 1
    escalate = new_count >= SUB_CYCLE_REOPEN_LIMIT
    clamped_depth = min(requested_upstream_depth, SUB_CYCLE_UPSTREAM_DEPTH)
    depth_was_clamped = requested_upstream_depth > SUB_CYCLE_UPSTREAM_DEPTH
    return {
        "wire": wire_id,
        "reopen_count": new_count,
        "escalate": escalate,
        "continue_subcycling": not escalate,
        "effective_upstream_depth": clamped_depth,
        "depth_was_clamped": depth_was_clamped,
    }


# ---------------------------------------------------------------------------
# The andon rule: three non-negotiable stop conditions
# ---------------------------------------------------------------------------

def check_stop_conditions(verdict, blast_radius, authorization_level, tier=None,
                           non_overridable=False, user_confirmed_red_override=False,
                           user_confirmed_authorization_raise=False):
    """Returns {"allowed": bool, "blocked_by": [...], "reasons": [...]}.
    Condition 3 (Tier 1 non-overridable) can NEVER be satisfied by any override
    argument -- there is no parameter that bypasses it, by construction.
    """
    blocked_by = []
    reasons = []

    # Condition 3 first: absolute, no override path exists in this function's
    # signature that can waive it.
    if tier == 1 and non_overridable:
        blocked_by.append("condition_3_tier1_non_overridable")
        reasons.append(
            "Tier 1 structural-evidence contradiction (real index query refutes the "
            "claimed edge). This is non-overridable and cannot be waived by any "
            "human or adjudicator action."
        )

    # Condition 1: red verdict halts unless explicit re-run/override was confirmed.
    if verdict == "red" and not user_confirmed_red_override:
        blocked_by.append("condition_1_red_verdict")
        reasons.append(
            "Wire verdict is red (broken/unproven). Advance blocked until an "
            "explicit user re-run of andon-verify with new evidence, or an "
            "explicit user override/defer of the gap."
        )

    # Condition 2: blast radius exceeding authorization_level.
    if blast_radius is not None:
        if blast_radius not in BLAST_RADIUS_ORDER:
            raise AndonError("BLAST_RADIUS_UNDEFINED", f"Unknown blast_radius {blast_radius!r}.")
        if authorization_level not in BLAST_RADIUS_ORDER:
            raise AndonError("AUTHZ_LEVEL_UNDEFINED", f"Unknown authorization_level {authorization_level!r}.")
        exceeds = BLAST_RADIUS_ORDER.index(blast_radius) > BLAST_RADIUS_ORDER.index(authorization_level)
        if exceeds and not user_confirmed_authorization_raise:
            blocked_by.append("condition_2_blast_radius")
            reasons.append(
                f"Proposal blast-radius ({blast_radius}) exceeds current "
                f"authorization_level ({authorization_level}). Blocked until the "
                f"user explicitly confirms raising authorization or skips this gap."
            )

    return {"allowed": len(blocked_by) == 0, "blocked_by": blocked_by, "reasons": reasons}


# ---------------------------------------------------------------------------
# Gap priority ordering (rule: phase-three-gap-priority-ordering)
# ---------------------------------------------------------------------------

_KIND_PRIORITY = {"wire": 0, "bug": 1, "feature": 2}


def select_next_gap(open_gaps):
    """open_gaps: list of {"kind":..., "on_constraint":bool, "blast_radius":str|None, "slug":...}
    Priority: (1) on_constraint:true first, (2) wire<bug<feature, (3) smallest blast radius.
    """
    if not open_gaps:
        return None

    def radius_rank(g):
        br = g.get("blast_radius")
        return BLAST_RADIUS_ORDER.index(br) if br in BLAST_RADIUS_ORDER else len(BLAST_RADIUS_ORDER)

    ranked = sorted(
        open_gaps,
        key=lambda g: (
            0 if g.get("on_constraint") else 1,
            _KIND_PRIORITY.get(g.get("kind"), 99),
            radius_rank(g),
        ),
    )
    return ranked[0]


# ---------------------------------------------------------------------------
# Wire classifier (rule: strategy-routing-not-default,
# strategy-prerequisite-graceful-degrade)
# ---------------------------------------------------------------------------

def route_wire(signals, availability):
    """signals: dict of is_* booleans. availability: dict of available_* booleans.
    Returns {"strategy": letter, "checked_order": [...], "degraded_from": letter|None}.
    Strategy 'a' is only reached when nothing else matches -- never a default.
    """
    checked = []
    chosen = None
    for letter in CLASSIFIER_ORDER:
        checked.append(letter)
        trigger_flag = TRIGGER_FLAG_BY_STRATEGY[letter]
        triggers = True if trigger_flag is None else bool(signals.get(trigger_flag))
        if triggers:
            chosen = letter
            break
    if chosen is None:
        chosen = "a"

    degraded_from = None
    prereq_flag = PREREQ_FLAG_BY_STRATEGY[chosen]
    if prereq_flag is not None and not availability.get(prereq_flag, False):
        degraded_from = chosen
        fallback_order = [letter for letter in CLASSIFIER_ORDER if letter != chosen]
        chosen = None
        for letter in fallback_order:
            p = PREREQ_FLAG_BY_STRATEGY[letter]
            if p is None or availability.get(p, False):
                chosen = letter
                break
        if chosen is None:
            chosen = "a"  # tribunal never hard-fails the run

    return {"strategy": chosen, "checked_order": checked, "degraded_from": degraded_from}


# ---------------------------------------------------------------------------
# Strategy d exact dispatch target (rule: strategy-d-skill-name-exact)
# ---------------------------------------------------------------------------

STRATEGY_D_PREFERRED_SKILL = "confab:confab-agentic-reliability"
STRATEGY_D_ALLOWED_FALLBACK_AGENT = "confab:agentic-reliability-auditor"
STRATEGY_D_REJECTED_TYPOS = [
    "confab:confab-agentic-reliability-auditor",
    "confab-agentic-reliability",
    "confab:agentic-reliability",
]


def check_strategy_d_target(dispatch_name, used_fallback=False):
    """Refuses a strategy-d dispatch that isn't the exact preferred skill name
    (or, only as an explicit fallback, the one named agent).
    """
    if used_fallback:
        if dispatch_name != STRATEGY_D_ALLOWED_FALLBACK_AGENT:
            raise AndonError(
                "STRATEGY_D_BAD_FALLBACK",
                f"Strategy d fallback must be exactly {STRATEGY_D_ALLOWED_FALLBACK_AGENT!r}, "
                f"got {dispatch_name!r}.",
            )
        return {"ok": True, "used_fallback": True}
    if dispatch_name != STRATEGY_D_PREFERRED_SKILL:
        raise AndonError(
            "STRATEGY_D_WRONG_TARGET",
            f"Strategy d must dispatch exactly {STRATEGY_D_PREFERRED_SKILL!r}, "
            f"got {dispatch_name!r}. (If this is a deliberate agent fallback because "
            f"the skill doesn't resolve, pass --used-fallback.)",
        )
    return {"ok": True, "used_fallback": False}


# ---------------------------------------------------------------------------
# Ingest-mode prerequisite (rules: phase-two-gap-source-self-scan-or-ingest,
# ingest-mode-phase-zero-short-circuit-required) -- no silent fallback to
# self-scan when the brief is missing.
# ---------------------------------------------------------------------------

def check_ingest_prereqs(repo_root, gap_source, self_assess_output_dir):
    if gap_source != "self-assess-brief":
        return {"ingest_mode": False, "ok": True}
    brief_path = os.path.join(repo_root, self_assess_output_dir, "MODERNIZATION_BRIEF.md")
    summary_path = os.path.join(repo_root, self_assess_output_dir, "transform_brief_summary.json")
    missing = [p for p in (brief_path, summary_path) if not os.path.isfile(p)]
    if missing:
        raise AndonError(
            "INGEST_PREREQS_MISSING",
            f"gap_source is 'self-assess-brief' but required file(s) are missing: {missing}. "
            f"Refusing to silently fall back to self-scan -- run "
            f"self-assess:self-assess-transform-brief first.",
        )
    return {"ingest_mode": True, "ok": True, "brief_path": brief_path, "summary_path": summary_path}


# ---------------------------------------------------------------------------
# Detection Ladder (rule: detection-ladder-climb-necessity)
# ---------------------------------------------------------------------------

def check_detection_ladder(defect_class, requested_rung, cheaper_rungs_attempted=None):
    if defect_class not in DEFECT_CLASS_MIN_RUNG:
        raise AndonError("LADDER_BAD_DEFECT_CLASS", f"Unknown defect_class {defect_class!r}.")
    minimum_rung = DEFECT_CLASS_MIN_RUNG[defect_class]
    cheaper_rungs_attempted = set(cheaper_rungs_attempted or [])
    if requested_rung > minimum_rung:
        required_cheaper = set(range(minimum_rung, requested_rung))
        missing = required_cheaper - cheaper_rungs_attempted
        if missing:
            raise AndonError(
                "LADDER_SKIPPED_CHEAPER_RUNG",
                f"Refusing rung {requested_rung} ({RUNG_NAMES[requested_rung]}) for "
                f"defect class {defect_class!r}: cheaper rung(s) {sorted(missing)} "
                f"were not attempted first.",
            )
    return {"minimum_rung": minimum_rung, "approved_rung": requested_rung}


# ---------------------------------------------------------------------------
# NO-PERSONA rule (checked in code, not left to model discipline)
# ---------------------------------------------------------------------------

def check_no_persona(text):
    lowered = text.lower()
    hits = []
    for name in NAMED_PERSON_DENYLIST:
        if name in lowered:
            hits.append(name)
    for m in AUTHORITY_PHRASE_RE.finditer(text):
        hits.append(m.group(0))
    if hits:
        raise AndonError(
            "NO_PERSONA_VIOLATION",
            f"Text invokes a named real/fictional person as an appeal to authority: {hits}. "
            f"NO-PERSONA RULE: every criterion must trace to an objectively checkable "
            f"principle or measurement, never borrowed authority from an identified individual.",
        )
    return {"clean": True}


# ---------------------------------------------------------------------------
# Untrusted-content fencing and credential masking
# ---------------------------------------------------------------------------

def fence(content):
    return f"<<<UNTRUSTED\n{content}\nUNTRUSTED>>>"


def mask_credential(value, file_line):
    preview_len = min(4, max(2, len(value) // 4))
    preview = value[:preview_len]
    return f"{preview}***  ({file_line})"


def scan_and_mask_credentials(text, file_line="unknown:0"):
    masked = text
    for pattern in CREDENTIAL_PATTERNS:
        for m in list(pattern.finditer(masked))[::-1]:
            full = m.group(0)
            masked = masked[: m.start()] + mask_credential(full, file_line) + masked[m.end():]
    return masked


# ---------------------------------------------------------------------------
# Preflight checks (read-only; never creates ledger or modifies files beyond
# testing writability of the ledger parent directory)
# ---------------------------------------------------------------------------

def run_preflight(repo_root, settings, self_assess_stage_mapper_present, confab_skill_present,
                   lsp_tool_present, structural_index_present, property_lib_python,
                   property_lib_js, property_lib_other):
    # Check 1: stage legibility
    manifest_hits = 0
    if self_assess_stage_mapper_present:
        stage_legibility = "self-assess-backed"
    else:
        # heuristic Glob-based single vs multi package guess (best-effort, read-only)
        manifest_names = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Gemfile"]
        for _root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "venv")]
            for f in files:
                if f in manifest_names:
                    manifest_hits += 1
        stage_legibility = "single-package" if manifest_hits <= 1 else "heuristic"
    stage_count_estimate = 1 if stage_legibility == "single-package" else max(1, manifest_hits if not self_assess_stage_mapper_present else 2)

    # Check 2: ledger writability -- create parent dir ONLY, to test writability.
    ledger_dir = settings["ledger_dir"]
    ledger_parent = os.path.dirname(os.path.join(repo_root, ledger_dir)) or repo_root
    ledger_writable = False
    try:
        os.makedirs(ledger_parent, exist_ok=True)
        test_path = os.path.join(ledger_parent, ".andon_write_test")
        with io.open(test_path, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(test_path)
        ledger_writable = True
    except OSError:
        ledger_writable = False

    # Check 3: house-rules presence
    house_rules_path = settings.get("house_rules_path", DEFAULT_HOUSE_RULES_PATH)
    house_rules_present = os.path.isfile(os.path.join(repo_root, house_rules_path))

    # Check 4: cross-plugin availability
    cross_plugin = {
        "self_assess_stage_mapper": self_assess_stage_mapper_present,
        "confab_agentic_reliability_skill": confab_skill_present,
        "lsp_tool": lsp_tool_present,
        "structural_index_on_disk": structural_index_present,
        "property_testing_python": property_lib_python,
        "property_testing_js": property_lib_js,
        "property_testing_other": property_lib_other,
    }

    verdicts = {
        "andon-propose": "Ready" if house_rules_present else "Ready-with-gaps",
        "andon-verify": _verify_verdict(cross_plugin),
        "andon-loop": (
            "Not-ready" if not ledger_writable
            else ("Ready-with-gaps" if stage_legibility != "self-assess-backed" else "Ready")
        ),
    }

    summary = {
        "stageLegibility": stage_legibility,
        "stageCountEstimate": stage_count_estimate,
        "ledgerDirWritable": ledger_writable,
        "houseRulesPresent": house_rules_present,
        "crossPluginDependencies": cross_plugin,
        "verdicts": verdicts,
    }
    return summary


def _verify_verdict(cross_plugin):
    degraded = []
    if not cross_plugin["confab_agentic_reliability_skill"]:
        degraded.append("strategy d (agentic-reliability) degrades to agent fallback or unavailable")
    if not (cross_plugin["lsp_tool"] or cross_plugin["structural_index_on_disk"]):
        degraded.append("strategy e (structural-graph) degrades below Tier 1")
    if not (cross_plugin["property_testing_python"] or cross_plugin["property_testing_js"] or cross_plugin["property_testing_other"]):
        degraded.append("strategy f (property/invariant) unavailable -- will return unknown with explicit note")
    if degraded:
        return "Ready-with-gaps: " + "; ".join(degraded)
    return "Ready"


# ---------------------------------------------------------------------------
# ANDON_BOARD.md rendering (read-only)
# ---------------------------------------------------------------------------

def compute_wire_status(evidence_docs_for_wire):
    """Wire status MUST be derived from linked evidence tags, never inferred."""
    if not evidence_docs_for_wire:
        return "unknown"
    latest = evidence_docs_for_wire[-1]
    verdict = latest["fields"].get("verdict")
    if verdict == "green":
        return "green"
    if verdict == "red":
        return "red"
    return "unknown"


def render_board(repo_root, ledger_dir):
    log_path = os.path.join(repo_root, ledger_dir, "log.md")
    if not os.path.isfile(log_path):
        return None  # caller must report "never run" and suggest preflight -> loop

    abs_ledger = os.path.join(repo_root, ledger_dir)
    # read_all_docs sorts by filename, not stream position -- a stage doc's
    # `order` field is the only authoritative sequence, so sort by it
    # explicitly rather than relying on filenames happening to be numbered
    # in stream order (true today only by naming coincidence, not by
    # anything enforced).
    stages = sorted(read_all_docs(abs_ledger, "stages"), key=lambda s: s["fields"].get("order", 0))
    gaps = read_all_docs(abs_ledger, "gaps")
    evidence = read_all_docs(abs_ledger, "evidence")
    counters = parse_log_counters(repo_root, ledger_dir)

    evidence_by_wire = {}
    for e in evidence:
        wire = e["fields"].get("wire")
        evidence_by_wire.setdefault(wire, []).append(e)

    wire_rows = []
    for wire_id, docs in evidence_by_wire.items():
        wire_rows.append({"wire": wire_id, "status": compute_wire_status(docs)})

    open_gaps = [g for g in gaps if g["fields"].get("status") == "open"]
    by_kind = {"bug": 0, "feature": 0, "wire": 0}
    by_radius = {r: 0 for r in BLAST_RADIUS_ORDER}
    for g in open_gaps:
        k = g["fields"].get("kind")
        if k in by_kind:
            by_kind[k] += 1
        r = g["fields"].get("blast_radius")
        if r in by_radius:
            by_radius[r] += 1

    strategy_counts = {s: 0 for s in STRATEGY_LETTERS}
    non_overridable_holds = []
    for e in evidence:
        s = e["fields"].get("strategy")
        if s in strategy_counts:
            strategy_counts[s] += 1
        if e["fields"].get("tier") == 1 and e["fields"].get("non_overridable"):
            non_overridable_holds.append(e)

    reopen_counts = (counters or {}).get("reopen_counts", {})
    if reopen_counts:
        constraint = max(reopen_counts.items(), key=lambda kv: kv[1])
        constraint_desc = f"{constraint[0]} (reopened {constraint[1]}x)"
    elif open_gaps:
        constraint_desc = f"{open_gaps[0]['fields'].get('stage')} / {open_gaps[0]['slug']} (oldest open gap)"
    else:
        constraint_desc = "none"

    cursor = "converged" if not open_gaps else f"{open_gaps[0]['fields'].get('stage')}::{open_gaps[0]['slug']}"

    return {
        "stages": [s["fields"].get("title") for s in stages],
        "wire_rows": wire_rows,
        "cursor": cursor,
        "counters": counters or {"total_passes": 0, "current_cycle": 1, "pass_in_cycle": 0, "cycles_converged": 0},
        "constraint": constraint_desc,
        "open_gap_counts_by_kind": by_kind,
        "open_gap_counts_by_radius": by_radius,
        # Additive, backward-compatible: existing consumers of render-board's
        # JSON that only read the counts above are unaffected. Drill-down
        # views (e.g. the HTML board) need the actual gaps behind a count,
        # not just the number.
        "open_gaps": [
            {
                "title": g["fields"].get("title"),
                "stage": g["fields"].get("stage"),
                "kind": g["fields"].get("kind"),
                "blast_radius": g["fields"].get("blast_radius"),
                "slug": g["slug"],
            }
            for g in open_gaps
        ],
        "strategy_counts": strategy_counts,
        "non_overridable_holds": [
            {"wire": e["fields"].get("wire"), "slug": e["slug"]} for e in non_overridable_holds
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_json(obj):
    print(json.dumps(obj, indent=2, default=str))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="andon_core.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("load-settings")
    p.add_argument("repo_root")

    p = sub.add_parser("enforce-enabled")
    p.add_argument("repo_root")

    p = sub.add_parser("init-or-resume")
    p.add_argument("repo_root")
    p.add_argument("ledger_dir")

    p = sub.add_parser("write-doc")
    p.add_argument("repo_root")
    p.add_argument("ledger_dir")
    p.add_argument("relative_path")
    p.add_argument("fields_json", help="JSON object of frontmatter fields")
    p.add_argument("--body", default="")

    p = sub.add_parser("validate-doc")
    p.add_argument("fields_json")

    p = sub.add_parser("validate-write-path")
    p.add_argument("raw_path")
    p.add_argument("repo_root")
    p.add_argument("allowed_dir")

    p = sub.add_parser("append-log")
    p.add_argument("repo_root")
    p.add_argument("ledger_dir")
    p.add_argument("entry_kind", choices=list(REQUIRED_LOG_FIELDS))
    p.add_argument("fields_json")

    p = sub.add_parser("log-counters")
    p.add_argument("repo_root")
    p.add_argument("ledger_dir")

    p = sub.add_parser("check-convergence")
    p.add_argument("gaps_closed_this_pass", type=int)
    p.add_argument("wire_statuses_json")

    p = sub.add_parser("track-subcycle")
    p.add_argument("repo_root")
    p.add_argument("ledger_dir")
    p.add_argument("wire_id")
    p.add_argument("requested_upstream_depth", type=int)

    p = sub.add_parser("check-stop-conditions")
    p.add_argument("--verdict", required=True)
    p.add_argument("--blast-radius", default=None)
    p.add_argument("--authorization-level", required=True)
    p.add_argument("--tier", type=int, default=None)
    p.add_argument("--non-overridable", action="store_true")
    p.add_argument("--confirm-red-override", action="store_true")
    p.add_argument("--confirm-authorization-raise", action="store_true")

    p = sub.add_parser("select-next-gap")
    p.add_argument("open_gaps_json")

    p = sub.add_parser("route-wire")
    p.add_argument("signals_json")
    p.add_argument("availability_json")

    p = sub.add_parser("check-detection-ladder")
    p.add_argument("defect_class")
    p.add_argument("requested_rung", type=int)
    p.add_argument("--cheaper-rungs", default="[]")

    p = sub.add_parser("check-strategy-d-target")
    p.add_argument("dispatch_name")
    p.add_argument("--used-fallback", action="store_true")

    p = sub.add_parser("check-ingest-prereqs")
    p.add_argument("repo_root")
    p.add_argument("gap_source")
    p.add_argument("self_assess_output_dir")

    p = sub.add_parser("check-no-persona")
    p.add_argument("text_file")

    p = sub.add_parser("mask-credentials")
    p.add_argument("text_file")
    p.add_argument("--file-line", default="unknown:0")

    p = sub.add_parser("preflight")
    p.add_argument("repo_root")
    p.add_argument("--self-assess-stage-mapper", action="store_true")
    p.add_argument("--confab-skill", action="store_true")
    p.add_argument("--lsp-tool", action="store_true")
    p.add_argument("--structural-index", action="store_true")
    p.add_argument("--property-lib-python", action="store_true")
    p.add_argument("--property-lib-js", action="store_true")
    p.add_argument("--property-lib-other", action="store_true")

    p = sub.add_parser("render-board")
    p.add_argument("repo_root")
    p.add_argument("ledger_dir")

    args = parser.parse_args(argv)

    try:
        if args.command == "load-settings":
            _print_json(load_settings(args.repo_root))

        elif args.command == "enforce-enabled":
            settings = load_settings(args.repo_root)
            enforce_enabled_or_halt(settings)
            _print_json({"allowed": True, "settings": settings})

        elif args.command == "init-or-resume":
            _print_json(init_or_resume_ledger(args.repo_root, args.ledger_dir))

        elif args.command == "write-doc":
            fields = json.loads(args.fields_json)
            path = write_doc(args.repo_root, args.ledger_dir, args.relative_path, fields, args.body)
            _print_json({"written": path})

        elif args.command == "validate-doc":
            validate_doc(json.loads(args.fields_json))
            _print_json({"valid": True})

        elif args.command == "validate-write-path":
            target = validate_write_path(args.raw_path, args.repo_root, args.allowed_dir)
            _print_json({"allowed": True, "target": target})

        elif args.command == "append-log":
            path = append_log_entry(args.repo_root, args.ledger_dir, args.entry_kind, json.loads(args.fields_json))
            _print_json({"appended_to": path})

        elif args.command == "log-counters":
            _print_json(parse_log_counters(args.repo_root, args.ledger_dir))

        elif args.command == "check-convergence":
            _print_json(check_convergence(args.gaps_closed_this_pass, json.loads(args.wire_statuses_json)))

        elif args.command == "track-subcycle":
            _print_json(track_subcycle(args.repo_root, args.ledger_dir, args.wire_id, args.requested_upstream_depth))

        elif args.command == "check-stop-conditions":
            result = check_stop_conditions(
                verdict=args.verdict,
                blast_radius=args.blast_radius,
                authorization_level=args.authorization_level,
                tier=args.tier,
                non_overridable=args.non_overridable,
                user_confirmed_red_override=args.confirm_red_override,
                user_confirmed_authorization_raise=args.confirm_authorization_raise,
            )
            _print_json(result)
            if not result["allowed"]:
                sys.exit(1)

        elif args.command == "select-next-gap":
            _print_json(select_next_gap(json.loads(args.open_gaps_json)))

        elif args.command == "route-wire":
            _print_json(route_wire(json.loads(args.signals_json), json.loads(args.availability_json)))

        elif args.command == "check-detection-ladder":
            cheaper = json.loads(args.cheaper_rungs)
            _print_json(check_detection_ladder(args.defect_class, args.requested_rung, cheaper))

        elif args.command == "check-strategy-d-target":
            _print_json(check_strategy_d_target(args.dispatch_name, args.used_fallback))

        elif args.command == "check-ingest-prereqs":
            _print_json(check_ingest_prereqs(args.repo_root, args.gap_source, args.self_assess_output_dir))

        elif args.command == "check-no-persona":
            with io.open(args.text_file, "r", encoding="utf-8") as fh:
                text = fh.read()
            _print_json(check_no_persona(text))

        elif args.command == "mask-credentials":
            with io.open(args.text_file, "r", encoding="utf-8") as fh:
                text = fh.read()
            print(scan_and_mask_credentials(text, args.file_line))

        elif args.command == "preflight":
            settings = load_settings(args.repo_root)
            _print_json(run_preflight(
                args.repo_root, settings,
                args.self_assess_stage_mapper, args.confab_skill,
                args.lsp_tool, args.structural_index,
                args.property_lib_python, args.property_lib_js, args.property_lib_other,
            ))

        elif args.command == "render-board":
            board = render_board(args.repo_root, args.ledger_dir)
            if board is None:
                _print_json({"never_run": True})
            else:
                _print_json(board)

    except AndonError as e:
        print(json.dumps({"allowed": False, "error_code": e.code, "error": e.message}, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
