# hook-violation fixture for cupertino

`.cupertino/` present (cupertino is active in this repo). The probe target is
`code-handbook.md` at repo root — its filename matches the DOMAINS-handbook.md
artifact pattern `is_cupertino_artifact_path()` recognizes, but it resolves
OUTSIDE `.cupertino/`, so `check_write_scope` must deny it (rule: write-scope
enforced before dispatch). Note the DEFAULT probe target ("src/api.py") does
NOT trigger this hook at all — it doesn't match any cupertino artifact
pattern, so handle_write_or_edit returns immediately without checking scope.
That is why a `_TARGET` override is required for this plugin specifically.

PASS = exit 2, reason cites "resolves outside the plugin's declared output
       directory".
FAIL = exit 0 (the artifact would be written outside .cupertino/ unchecked).
