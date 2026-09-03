# lehre-unparseable

`src/good.py` is clean. `src/broken.py` has a syntax error, so the blocking
`no-bare-except` rule cannot be decided for it.

Correct behaviour is to report `src/broken.py` as UNEVALUATED — not judged, and
therefore not clean. `lehre_cli.py gauge --json` keeps `unevaluated_unparseable`
as its own key precisely so a summary can keep them apart; folding it into the
pass count is how a sweep quietly under-reports.
