# Adapters per stack

What spur can record for each stack, what each tracer actually emits, and what was
verified. Only Python is traced in-process. For the others spur attaches a call tree
the program's own tracer wrote (`--calls`) to the root step, and hashes the files you
declare (`--reads`/`--writes`): declared I/O, marked `"io": "declared"` in the record,
not observed I/O.

| stack | calls | file I/O | status |
|---|---|---|---|
| Python ≥ 3.12 | `sys.monitoring`, every function under the project root | `sys.addaudithook`: `open`, `os.rename`, `os.remove`, spawns | **built**; acceptance test passes on 3.12, 3.13, 3.14, 3.15 |
| Python 3.11 | none (no `sys.monitoring`; the page says so) | as above | built; calls unavailable by design |
| Rust | `tracing` spans written by `tracing-chrome` | declared only | **importer built**, tested on real `tracing-chrome` 0.7.2 output |
| Node | `node --cpu-prof` V8 profile, **sampled** | declared only | **importer built**, tested on a live `node --cpu-prof` run (Node 26) |
| Go | none | declared only | **not built** — see below |

## Python

Nothing to wire: `spur_trace.py run -- <command>` prepends `scripts/spur_boot/` to
`PYTHONPATH` and sets `SPUR_TRACE_DIR`, so `site` imports spur's `sitecustomize` in the
root process and in every Python child that inherits the environment. A project's own
`sitecustomize`, if any, still runs: spur's chains to it.

Audit events confirmed by running them on 3.12, 3.13 and 3.15 (the CPython docs tool
does not carry the audit table): `os.replace` raises `os.rename`, `os.unlink` raises
`os.remove`, `os.open` raises `open` with mode `None` and the flags, and imports raise
`open` for each `.py` and `__pycache__/*.pyc` — which is why code files are listed apart
from data and never enter the chain.

Not observable: `python -I`, `-E` or `-S`, a child given its own `env=` without
`PYTHONPATH`, and `os._exit` (no atexit: the step's record is missing, so it shows as an
untraced step).

## Rust: `tracing-chrome`

`tracing-chrome` is a `tracing-subscriber` layer that writes Chrome trace events
(docs.rs, 0.7.2). `ChromeLayerBuilder::new().build()` returns the layer and a
`FlushGuard`; the file is complete only when the guard is dropped. Only functions with a
span appear — `#[tracing::instrument]` or a manual span — so the tree is the
instrumented subset, not every call.

```rust
let (chrome_layer, _guard) = ChromeLayerBuilder::new().file("trace.json").build();
tracing_subscriber::registry().with(chrome_layer).init();
```

```bash
python3 spur_trace.py run --calls chrome:trace.json --reads 'data/*' --writes 'out/*' -- cargo run --release
```

The real output it was tested on is `scripts/fixtures/adapters/rust/tracing-chrome-0.7.2.json`,
from `main.rs` and `Cargo.toml` beside it: `B`/`E` pairs carrying `.file` and `.line`. The
importer also reads `X` complete events and the `{"traceEvents": [...]}` object form.

## Node: `--cpu-prof`

`node --cpu-prof` starts the V8 CPU profiler and writes the profile before exit, into
`--cpu-prof-dir` (default the working directory) under `--cpu-prof-name` (default
`CPU.<date>.<time>.<pid>.<tid>.<seq>.cpuprofile`). This is a **V8 `.cpuprofile`**
(`nodes`, `samples`, `timeDeltas`), not Chrome trace events, and it is **sampled**: the
tree's counts are samples, not calls, and a short function can be missing. Only frames
whose script URL is under the project root are kept.

```bash
python3 spur_trace.py run --calls cpuprofile:prof -- node --cpu-prof --cpu-prof-dir=prof app.js
```

## Go: not built

`runtime/trace` (`trace.Start`/`trace.Stop`, regions via `trace.StartRegion` or
`trace.WithRegion`) writes Go's own binary execution trace, read by `go tool trace`. It is
not the Chrome trace format, and its format is documented as unstable, so spur has no
importer. A Go step can still be traced for declared I/O and the chain check; its call
tree stays empty and the page says so.

## File I/O outside Python

The issue that proposed spur names `strace` for Rust and Go. That is Linux-only and is not
built; on macOS the equivalent needs System Integrity Protection relaxed. Use `--reads`
and `--writes`: the runner hashes the declared reads before the command starts and the
declared writes after it exits.
