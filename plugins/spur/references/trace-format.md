# The run record: `trace.json` (`spur/trace/1`) and `prov.json`

`spur_trace.py run` writes both under `analysis/spur/<runId>/`, beside `spur-report.html`.
The committed demo `scripts/fixtures/spur-demo.json` is a complete instance, real output
of the fixture pipeline's tampered run.

## `trace.json`

```json
{
  "schema": "spur/trace/1", "runId": "demo",
  "command": ["python3", "run_pipeline.py", "--tamper"], "root": "~/proj",
  "started": "2026-10-30T18:30:37.780+00:00", "finished": "…", "exit": 0,
  "chain": {"verdict": "broken", "verified": 2, "broken": 1, "unverified": 1, "source": 1},
  "dropped": 0,
  "steps": [{
    "id": "s5", "traced": true, "parent": "s1", "io": "observed",
    "command": ["python3.15", "summarize.py", "work/records.csv", "out/summary.json"],
    "exit": {"code": 0, "how": "sys.exit"}, "durationMs": 7.45, "python": "3.15.2",
    "why": "", "dropped": 0,
    "inputs": [{"path": "work/records.csv", "sha256": "0fe98b…", "status": "broken",
                "producer": "s3", "version": 2, "expected": "f20e84…",
                "note": "changed after s3 wrote it -- untraced step(s) ran in between: s4"}],
    "outputs": [{"path": "out/summary.json", "version": 1, "sha256": "ebbbaf…",
                 "latest": true, "feeds": ["s6"]}],
    "code": [{"path": "summarize.py", "sha256": "…"}], "removed": [],
    "calls": {"source": "sys.monitoring", "available": true, "unit": "calls",
              "threads": [[{"fn": "<module>", "file": "summarize.py", "line": 1,
                            "calls": 1, "ns": 5150000, "children": ["…"]}]]}
  }]
}
```

- A **step** is one process. `traced: false` is a process the run spawned that left no
  record; `why` says which kind. `parent` is the step that spawned it.
- `io` is `observed` (the Python adapter saw it), `declared` (`--reads`/`--writes` on an
  untraced root) or `none`.
- `exit.how` is `observed by the runner` for the root, else `sys.exit`, `returned`,
  `uncaught <Type>`, `replaced by exec`, or `not observed`.
- `calls.unit` is `samples` for a `v8-cpuprofile` tree: counts are samples, not calls.
- Paths under the root are relative; the home directory is `~`. No environment value and
  no file content is ever written.

## The chain rule, and in-place rewrites

An input is hashed when its step first opens it for reading. An output is hashed when its
step exits and again before each child it spawns; each changed hash is a new version
`path@n`, numbered in commit order across the whole run. A consumer's input is compared
with the latest version committed **before** it read the file:

| status | when |
|---|---|
| `verified` | sha256 equal to that version |
| `broken` | sha256 differs; `note` names untraced steps that started in between |
| `unverified` | no traced producer, but the file's mtime is inside the run; or it could not be hashed |
| `source` | no producer and the file predates the run |

Verdict: `broken` if any input is broken, else `incomplete` if any is unverified, else
`verified` if any link verified, else `empty`. Only `verified` is a pass.

## `prov.json` (W3C PROV-JSON)

| PROV | from |
|---|---|
| `entity` `run:<path>@<n>` | each output version; `@0` for a source; `@unattributed-<sha12>` for a broken or unverified read |
| `activity` `run:step/<id>` | each step, with `prov:startTime` |
| `used` | every input |
| `wasGeneratedBy` | every output version |
| `wasInformedBy` | each verified link, consumer informed by producer |
| `wasDerivedFrom` | only an in-place rewrite: `path@n` from the version the same step read |

It claims no blanket "every output derives from every input": the trace does not observe
that. Validated by parsing with the `prov` package (3.2.3).
