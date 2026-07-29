"""confab's internal support library.

Reconstructed for issue #24: this package existed only in the working tree
of the "rebuild all six plugins from behavior specs" commit and was silently
excluded from every commit since by an unanchored `lib/` line in the repo's
root .gitignore -- see that file's history for the fix. Every module here is
a fresh implementation grounded in call-site evidence (every scripts/*.py
entry point, every skill's SKILL.md, every agent's Output contract, and the
hook-violation-confab fixture's actual remediation_scope.json), not a
restored original.
"""
