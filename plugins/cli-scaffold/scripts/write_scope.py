#!/usr/bin/env python3
"""Write-scope guard: the plugin may only write inside its declared output dir.

Enforces (in code, before any dispatch/write can happen):
  * Reject absolute target paths.
  * Reject path traversal (any component that escapes the output root, e.g. '..').
  * Reject targets that resolve outside CWD/<OUTPUT_ROOT>/.
  * Reject empty / whitespace-only app names and names with path separators.

`resolve_target` RAISES on any violation -- it never sanitises-and-continues,
because a silently-repaired path is exactly the failure mode this guard exists
to stop. Skills call this before writing a single scaffold file.

Usage:
    write_scope.py <app-name> [--base <dir>] [--output-root <name>]
        prints the validated absolute target directory, or exits 2 on violation.
"""
import argparse
import os
import sys

from constants import EXIT_SUCCESS, EXIT_USAGE_ERROR, OUTPUT_ROOT


class WriteScopeError(Exception):
    """Raised when a requested write target is outside the sanctioned scope."""


_FORBIDDEN_NAME_CHARS = set('/\\:\x00')


def _validate_app_name(app_name):
    if app_name is None:
        raise WriteScopeError("app name is required")
    name = app_name.strip()
    if name == "":
        raise WriteScopeError("app name must not be empty or whitespace")
    if name in (".", ".."):
        raise WriteScopeError("app name must not be '.' or '..'")
    if any(ch in _FORBIDDEN_NAME_CHARS for ch in name):
        raise WriteScopeError(
            "app name %r must not contain path separators or NUL" % name
        )
    if name.startswith("-"):
        raise WriteScopeError("app name %r must not start with '-'" % name)
    return name


def resolve_target(app_name, base=None, output_root=OUTPUT_ROOT):
    """Return the absolute, validated directory the scaffold may be written to.

    Raises WriteScopeError on absolute paths, traversal, or any target that
    would land outside <base>/<output_root>/.
    """
    name = _validate_app_name(app_name)

    base_dir = os.path.abspath(base if base is not None else os.getcwd())
    scope_root = os.path.abspath(os.path.join(base_dir, output_root))

    # The candidate is ALWAYS built by joining the (separator-free) app name onto
    # the scope root. We still re-verify containment via realpath/commonpath so a
    # symlink or a sneaky name cannot escape.
    candidate = os.path.abspath(os.path.join(scope_root, name))

    # Reject absolute smuggling: os.path.join drops scope_root if `name` were
    # absolute, but _validate_app_name already forbids separators, so an absolute
    # path can't reach here. This is defense in depth.
    if os.path.isabs(name):
        raise WriteScopeError("absolute target paths are not permitted: %r" % name)

    scope_real = os.path.realpath(scope_root)
    candidate_real = os.path.realpath(candidate)

    try:
        common = os.path.commonpath([scope_real, candidate_real])
    except ValueError:
        # Different drives (Windows) -> definitely out of scope.
        raise WriteScopeError("target escapes output scope: %r" % candidate)

    if common != scope_real:
        raise WriteScopeError(
            "target %r escapes declared output scope %r" % (candidate_real, scope_real)
        )
    if candidate_real == scope_real:
        raise WriteScopeError("target must be a subdirectory of the output root")

    return candidate_real


def main(argv):
    parser = argparse.ArgumentParser(prog="write_scope.py")
    parser.add_argument("app_name")
    parser.add_argument("--base", default=None)
    parser.add_argument("--output-root", default=OUTPUT_ROOT)
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit:
        return EXIT_USAGE_ERROR

    try:
        target = resolve_target(args.app_name, base=args.base, output_root=args.output_root)
    except WriteScopeError as exc:
        sys.stderr.write("WRITE-SCOPE VIOLATION: %s\n" % exc)
        return EXIT_USAGE_ERROR

    sys.stdout.write(target + "\n")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main(sys.argv))
