"""Exception types shared across self-assess's lib/ and self_assess_cli.py."""


class SelfAssessError(Exception):
    """A rule refusal: self_assess_cli.py reports these as "REFUSED: <msg>"
    (exit 1) and guard_target_edit.py denies the triggering edit."""


class WriteScopeError(SelfAssessError):
    """A resolved write target escapes its configured output_dir.

    Subclasses SelfAssessError (not a bare exception) so that
    self_assess_cli.py's cmd_resolve_output_path surfaces it as a
    "REFUSED:" policy refusal like every other gate, even though
    self_assess_cli.py never imports or catches WriteScopeError by name.
    """
