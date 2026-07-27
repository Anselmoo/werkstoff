#!/usr/bin/env python3
"""Resolve a user-supplied language/dialect name to its paradigm skill.

Enforces (in code, not prose):
  * language-routing-accuracy -- an unknown or ambiguous name NEVER silently
    falls back to a paradigm. It exits non-zero with a clarification/refusal,
    which is the only way the caller can proceed.
  * language-support-count / paradigm-count -- inherited from constants import
    (that module asserts the registry has exactly 12 languages / 3 paradigms;
    a corrupted registry raises before any routing happens).

Usage:
    lang_router.py <language-or-dialect>

Exit codes (follow the frozen contract):
    0  resolved       -> prints JSON {"language","paradigm","skill","dialect"}
    1  ambiguous / unsupported -> the request cannot be routed; prints a
       clarification (ambiguous) or a refusal listing the 12 options
       (unsupported) to stderr. Caller MUST stop and ask the user.
    2  usage error    -> wrong number of arguments.
"""
import json
import sys

from constants import (
    ALIASES,
    AMBIGUOUS,
    DISPLAY_NAMES,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    LANGUAGE_REGISTRY,
    SHELL,
)

PARADIGM_SKILL = {
    "compiled": "cli-scaffold-compiled",
    "interpreted": "cli-scaffold-interpreted",
    "shell": "cli-scaffold-shell",
}


class Unsupported(Exception):
    """Raised when a name is not one of the supported targets."""


class Ambiguous(Exception):
    """Raised when a name names a family, not a single target."""


def _normalize(raw):
    return raw.strip().lower().replace("_", "-").replace(" ", "")


def resolve(raw):
    """Return a dict describing the routing, or raise Unsupported/Ambiguous.

    This is the guard: there is no code path that returns a paradigm for an
    input that is not explicitly in the registry / alias table. Anything else
    raises. A caller cannot obtain a silent default.
    """
    if raw is None or _normalize(raw) == "":
        raise Ambiguous("No language given. Name one of the 12 supported options.")

    key = _normalize(raw)

    if key in AMBIGUOUS:
        raise Ambiguous(AMBIGUOUS[key])

    canonical = ALIASES.get(key, key)

    # POSIX sh: a shell dialect that routes to the shell paradigm but is not one
    # of the 12 counted languages.
    if canonical == "posix-sh":
        return {
            "language": "posix-sh",
            "display": "POSIX sh",
            "paradigm": SHELL,
            "skill": PARADIGM_SKILL[SHELL],
            "dialect": "posix-sh",
        }

    if canonical not in LANGUAGE_REGISTRY:
        raise Unsupported(canonical)

    paradigm = LANGUAGE_REGISTRY[canonical]
    return {
        "language": canonical,
        "display": DISPLAY_NAMES[canonical],
        "paradigm": paradigm,
        "skill": PARADIGM_SKILL[paradigm],
        "dialect": canonical if paradigm == SHELL else None,
    }


def _supported_list():
    return ", ".join(DISPLAY_NAMES[k] for k in LANGUAGE_REGISTRY)


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: lang_router.py <language-or-dialect>\n")
        return EXIT_USAGE_ERROR

    try:
        result = resolve(argv[1])
    except Ambiguous as exc:
        sys.stderr.write("AMBIGUOUS: %s\n" % exc)
        # A clarification is required; refuse to route.
        return EXIT_RUNTIME_ERROR
    except Unsupported as exc:
        sys.stderr.write(
            "UNSUPPORTED: '%s' is not a supported target.\n"
            "Supported (12): %s\n"
            "POSIX sh is also accepted as a shell dialect.\n" % (exc, _supported_list())
        )
        return EXIT_RUNTIME_ERROR

    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main(sys.argv))
