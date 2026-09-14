# Workflow evidence harness

The academic example projects, and the matrix templates, that the approved-workflow docs are
built from. Nothing here is documented until it has been run: every claim on a
`docs/examples/` page comes from a real headless cell recorded by
`plugins/arbeitsplan/scripts/subrun.py`.

| path | what it is |
|---|---|
| `fixtures/` | six synthetic teaching projects, each with one planted property. Never werkstoff's own code |
| `verify_fixtures.py` | asserts every planted property is still mechanically detectable |
| `matrices/*.template.json` | committed templates carrying placeholders, never absolute paths |
| `build_matrices.py` | resolves the templates for this machine into `analysis/workflows/<runId>/` |
| `check_matrices.py` | proves the resolved matrices are accepted by the runner, via `--dry-run` |

## Running a sweep

```bash
python3 test/workflows/verify_fixtures.py                       # the instrument, first
python3 test/workflows/check_matrices.py                        # token-free
python3 test/workflows/build_matrices.py --out analysis/workflows/<runId>
bash plugins/arbeitsplan/scripts/run_matrix.sh \
  --matrix analysis/workflows/<runId>/plan-haiku.json \
  --out analysis/workflows/<runId>/plan-haiku
```

`verify_fixtures.py` comes first for the reason `calibrate-then-measure` exists: a fixture whose
planted defect has been repaired turns the sweep into a green run over nothing. It has already
caught one such case — a suite that was red because its test package was not importable, rather
than because the feature it wanted was missing.

Cells cost real tokens. Every template caps spend per cell with `max_budget_usd`, and Haiku is
the default tier; `auto-sonnet` exists only because auto mode does not support Haiku.
