"""Frozen doctrine constants for cli-scaffold.

This module is the single source of truth in *code* for every numeric bound and
every enumerated set the plugin's skills branch on. Nothing here is prose the
model may reinterpret: the invariants are asserted at import time, so importing
this module on a corrupted registry raises immediately instead of silently
degrading.

Rule coverage (spec rule id -> enforcement):
  * language-support-count  -> LANGUAGE_COUNT + assertion below
  * paradigm-count          -> PARADIGM_COUNT + assertion below
  * five-pillars-enforced   -> PILLARS (len == 5) + assertion below
  * exit-code-*             -> EXIT_* constants (the frozen contract)
  * exit-code-frozen-contract -> same EXIT_* reused by every paradigm/language
"""

# --- Frozen exit-code contract (identical across all 12 languages) ----------
# rule: exit-code-success / exit-code-runtime-error / exit-code-usage-error
# rule: exit-code-frozen-contract -- these three integers are the ONLY sanctioned
# terminal codes a generated CLI may map its outcomes onto, in every language.
EXIT_SUCCESS = 0        # successful invocation with valid arguments
EXIT_RUNTIME_ERROR = 1  # runtime error: failed operation / caught exception
EXIT_USAGE_ERROR = 2    # usage error: bad flags, missing arg, type mismatch

FROZEN_EXIT_CONTRACT = {
    "success": EXIT_SUCCESS,
    "runtime_error": EXIT_RUNTIME_ERROR,
    "usage_error": EXIT_USAGE_ERROR,
}

# --- The five pillars (rule: five-pillars-enforced, checkpoints: 5) ---------
PILLARS = (
    "ux-discoverability",       # 1. UX / discoverability
    "backend-core-separation",  # 2. backend / core separation
    "stability",                # 3. stability
    "idiomatic-distribution",   # 4. idiomatic per-ecosystem distribution
    "unix-composability",       # 5. Unix composability
)

# --- The frozen language registry (rule: language-support-count == 12) -------
# canonical language id -> paradigm. Exactly 12 entries. POSIX sh is deliberately
# NOT here: it is a shell *dialect* (see SHELL_DIALECTS), not one of the 12
# counted languages.
COMPILED = "compiled"
INTERPRETED = "interpreted"
SHELL = "shell"

LANGUAGE_REGISTRY = {
    # interpreted
    "python": INTERPRETED,
    "typescript": INTERPRETED,
    "javascript": INTERPRETED,
    "ruby": INTERPRETED,
    "php": INTERPRETED,
    "perl": INTERPRETED,
    # compiled
    "dotnet": COMPILED,
    "rust": COMPILED,
    "go": COMPILED,
    # shell
    "bash": SHELL,
    "zsh": SHELL,
    "powershell": SHELL,
}

# Shell dialects the shell paradigm skill accepts. POSIX sh routes to the shell
# paradigm but does not add to LANGUAGE_COUNT.
SHELL_DIALECTS = ("bash", "zsh", "powershell", "posix-sh")

# Human display names, used when listing supported options in a clarification.
DISPLAY_NAMES = {
    "python": "Python",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "ruby": "Ruby",
    "php": "PHP",
    "perl": "Perl",
    "dotnet": ".NET",
    "rust": "Rust",
    "go": "Go",
    "bash": "Bash",
    "zsh": "Zsh",
    "powershell": "PowerShell",
}

# Aliases -> canonical id. An alias never invents support; it only normalises a
# spelling of something already in LANGUAGE_REGISTRY (or the posix-sh dialect).
ALIASES = {
    "py": "python",
    "python3": "python",
    "ts": "typescript",
    "js": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    "rb": "ruby",
    "pl": "perl",
    "c#": "dotnet",
    "csharp": "dotnet",
    "cs": "dotnet",
    ".net": "dotnet",
    "net": "dotnet",
    "dotnet": "dotnet",
    "golang": "go",
    "rustlang": "rust",
    "pwsh": "powershell",
    "posix": "posix-sh",
    "posixsh": "posix-sh",
    "posix-sh": "posix-sh",
    "sh": "posix-sh",
}

# Language names that are genuinely ambiguous: they name a family, not a single
# supported target, so the router must ask rather than guess (rule:
# language-routing-accuracy -- "never a silent fallback").
AMBIGUOUS = {
    "shell": "Which shell dialect? (Bash, Zsh, PowerShell, or POSIX sh)",
    "script": "Which language do you mean? Name one of the 12 supported options.",
    "js/ts": "Do you mean JavaScript or TypeScript?",
    "bashorzsh": "Do you mean Bash or Zsh?",
}

# --- Counts (frozen numeric bounds) -----------------------------------------
LANGUAGE_COUNT = 12
PARADIGM_COUNT = 3
PILLAR_COUNT = 5

# rule: fixable-gaps-must-be-fixed -- the verify/fix/re-verify loop is bounded.
# After this many verification attempts still returning gaps, the loop MUST halt
# and surface to a human rather than churn forever.
MAX_FIX_ITERATIONS = 5

# The single declared output directory. Every generated scaffold and every write
# the plugin performs MUST live under CWD/<OUTPUT_ROOT>/... (rule: write scope).
OUTPUT_ROOT = "generated-clis"

# Verification reports & ledgers live here, deliberately OUTSIDE any scaffold so
# the verifier can never touch generated files (rule: verifier-must-not-write).
REPORTS_ROOT = ".cli-scaffold-reports"

# Report/finding vocabulary. `disposition` is a first-class gating key: a later
# decision (fix vs. surface-to-human) branches on it, so it is never prose.
DISPOSITION_FIXABLE = "fixable"
DISPOSITION_NEEDS_HUMAN = "needs-human-judgment"
VALID_DISPOSITIONS = (DISPOSITION_FIXABLE, DISPOSITION_NEEDS_HUMAN)

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
VALID_STATUSES = (STATUS_PASS, STATUS_FAIL)

VERDICT_PASS = "pass"
VERDICT_GAPS = "gaps"
VALID_VERDICTS = (VERDICT_PASS, VERDICT_GAPS)

# POSIX sh forbidden bashisms (rule: posix-sh-bashism-check). Each entry is
# (regex, human label). The verifier flags any match in a posix-sh scaffold.
FORBIDDEN_BASHISMS = [
    (r"\w+=\(",                 "array assignment (name=( ... ))"),
    (r"\[\[",                   "[[ ... ]] test keyword"),
    (r"^\s*function\s+\w+",     "function keyword"),
    (r"\[[^]]*\s==\s[^]]*\]",   "== inside [ ] test (use = )"),
    (r"<<<",                    "here-string (<<<)"),
    (r"<\(",                    "process substitution <( )"),
    (r">\(",                    "process substitution >( )"),
]


# --- Import-time invariants (these are the enforcement, not the comments) ----
def _assert_invariants():
    if len(LANGUAGE_REGISTRY) != LANGUAGE_COUNT:
        raise AssertionError(
            "language registry corrupted: expected %d languages, found %d"
            % (LANGUAGE_COUNT, len(LANGUAGE_REGISTRY))
        )
    paradigms = set(LANGUAGE_REGISTRY.values())
    if len(paradigms) != PARADIGM_COUNT:
        raise AssertionError(
            "paradigm set corrupted: expected %d paradigms, found %d (%s)"
            % (PARADIGM_COUNT, len(paradigms), sorted(paradigms))
        )
    if paradigms != {COMPILED, INTERPRETED, SHELL}:
        raise AssertionError("paradigm names drifted: %s" % sorted(paradigms))
    if len(PILLARS) != PILLAR_COUNT:
        raise AssertionError(
            "pillar set corrupted: expected %d pillars, found %d"
            % (PILLAR_COUNT, len(PILLARS))
        )
    if len(set(FROZEN_EXIT_CONTRACT.values())) != 3:
        raise AssertionError("exit-code contract is not three distinct codes")


_assert_invariants()
