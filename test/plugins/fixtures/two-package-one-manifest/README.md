# Fixture: two-package-one-manifest

Regression case for the andon-loop bug this plugin's `self-assess-stage-map`
exists to fix: `scripts/stream_scan.py` in `andon-loop` keys stages by
nearest-manifest-directory (`seen.setdefault(s["dir"], s)`), so `producer/`
and `consumer/` — two distinct Python packages sharing the one
`pyproject.toml` at this directory's root — collapse into a single stage,
and the `consumer.process` → `producer.generate` import is never proposed
as a wire.

**Expected result from `self-assess-stage-map`:** 2 stages (`producer`,
`consumer`), 1 wire (`consumer/process.py` → `producer/generate.py`, the
`OrderEvent` data contract).

Not a runnable/installable package — Pyright's "import could not be
resolved" on `consumer/process.py` is expected and irrelevant; this
fixture exists to be statically analyzed, not executed.
