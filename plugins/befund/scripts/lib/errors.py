"""Exception types shared across befund's lib/ and befund_cli.py."""


class SelfAssessError(Exception):
    """A rule refusal: befund_cli.py reports these as "REFUSED: <msg>"
    (exit 1) and guard_target_edit.py denies the triggering edit."""


class WriteScopeError(SelfAssessError):
    """A resolved write target escapes its configured output_dir.

    Subclasses SelfAssessError (not a bare exception) so that
    befund_cli.py's cmd_resolve_output_path surfaces it as a
    "REFUSED:" policy refusal like every other gate, even though
    befund_cli.py never imports or catches WriteScopeError by name.
    """
