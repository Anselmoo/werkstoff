# Changelog

All notable changes to the `spur` plugin are documented here.

## [Unreleased]

## [0.2.0] - 2026-10-30
### Added
- **`spur-trace` skill and `scripts/spur_trace.py`** (#143): run a project's pipeline once
  under a tracer. Each process is a step; per step the run record holds the command, a
  calling-context tree of the project's own functions, every file read and written with its
  sha256, and the step that spawned it. A spawned process that leaves no record is kept as an
  untraced step rather than dropped.
- **Python adapter** (`scripts/spur_boot/sitecustomize.py`): `sys.monitoring` (3.12+) for
  calls, `sys.addaudithook` for `open`, `os.rename`, `os.remove` and spawns. It is loaded
  through `PYTHONPATH` and gated on `SPUR_TRACE_DIR`, so every Python child that inherits the
  environment is traced and no traced code is rewritten. It records no environment value and
  no file content; home paths are redacted.
- **Hash-chain check** with four states (`verified`, `broken`, `unverified`, `source`). A file
  rewritten in place becomes a new version `path@n`, and a consumer is checked against the
  latest version written before it read the file. `unverified` is never a pass.
- **PROV-JSON export** (`prov.json`), parsed by the `prov` 3.2.3 package.
- **Importers** for real `tracing-chrome` 0.7.2 output (Chrome trace events) and
  `node --cpu-prof` profiles (sampled), attached to an untraced root step with `--calls`.
- **Viewer** `assets/spur-viewer.html`, built by `scripts/build_spur_html.py` from the
  committed demo `scripts/fixtures/spur-demo.json` (real output of a tampered run).
- **Acceptance test** `scripts/test_spur_trace.py` over the committed four-step fixture
  pipeline: traced and untraced outputs byte-identical, chain verified, broken on tamper.
