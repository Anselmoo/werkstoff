# Language support — canonical reference

This is the **single source of truth** for self-assess's per-language
detection and extraction knowledge. `self-assess-preflight` Check 1,
`self-assess-stage-map` Step 0, and the `stage-mapper` agent's Find
Protocol all point here instead of maintaining their own copies — that
duplication (three independently-drifting lists, one of them missing
most real-world languages) is the exact bug an internal audit
(`rubber-duck-tribunal`, `longevity` rubric) found and this file fixes.

Two structural exceptions, both plain-JS Workflow scripts with **no
filesystem access at runtime** (confirmed Workflow-tool constraint), so
neither can `Read` this file — each carries its own copy of the relevant
column and a comment pointing back here as the source it must be kept in
sync with by hand:
- `workflows/stage-map-scan.js`'s `LANG_BRIEFS` — the **Extraction idiom**
  column (the import/use-graph extraction hints).
- `workflows/code-idiom-scan.js`'s `LANG_BRIEFS` — the **Deprecated-idiom /
  smell catalog** section below (the modernization-in-place + smell hints).

Every other consumer (the SKILL.md files, the agents) reads this file directly.

Coverage below is the 20 most common general-purpose and scripting
languages. **This list is illustrative, not exhaustive** — any language
with a recognizable manifest file, or ≥3 files of one extension with no
owning manifest (the extension-frequency fallback), is detected and
dispatched even if it isn't in this table; it just runs through the
generic Find-phase brief (`workflows/stage-map-scan.js`'s
`LANG_BRIEFS[lang] || <generic text>`) and the generic package-boundary
heuristic (`stage-mapper.md`'s manifest-less-stack rule) instead of a
hand-tuned one.

| # | Language | Manifest pattern(s) | Extension(s) | Package-boundary rule | Extraction idiom |
|---|---|---|---|---|---|
| 1 | Python | `pyproject.toml`, `setup.py`, `requirements*.txt` | `.py` | Shallowest dir with `__init__.py`, or a `src`-layout root — never the manifest's dir if it covers multiple such dirs | stdlib `ast` module, single inline `python3 -c "..."` |
| 2 | JavaScript | `package.json` | `.js`, `.jsx`, `.mjs`, `.cjs` | Shallowest dir with its own `package.json` `"name"` — a `"workspaces"` root is never itself the boundary | regex/`rg` pass over `import`/`require` |
| 3 | TypeScript | `package.json`, `tsconfig.json` | `.ts`, `.tsx` | Same as JavaScript | regex/`rg` pass over `import`/`export ... from` |
| 4 | Java | `pom.xml`, `build.gradle`, `build.gradle.kts` | `.java` | Shallowest dir with its own `pom.xml`/module `build.gradle` — a multi-module parent POM/settings.gradle root is never itself the boundary | `grep`/`rg` for `import` statements |
| 5 | C# | `*.csproj`, `*.sln` | `.cs` | Shallowest dir with its own `.csproj` — a `.sln` solution root is never itself the boundary | `grep`/`rg` for `using` statements |
| 6 | C++ | `CMakeLists.txt`, `Makefile`, `*.vcxproj` | `.cpp`, `.cc`, `.hpp`, `.h` | Shallowest dir with its own build target definition | `grep`/`rg` for `#include "..."` (local, not `<...>` system headers) |
| 7 | C | `Makefile`, `CMakeLists.txt` | `.c`, `.h` | Same as C++ | `grep`/`rg` for `#include "..."` |
| 8 | Go | `go.mod` | `.go` | Shallowest dir with its own `go.mod` — a multi-module repo's outer `go.mod` is not the only boundary if narrower ones exist deeper | `grep`/`rg` for the `import (...)` block |
| 9 | Rust | `Cargo.toml` | `.rs` | Shallowest dir with a `Cargo.toml` `[package].name` — a `[workspace]` root is never itself the boundary | `grep`/`rg` for `use`/`mod`, plus `Cargo.toml` `[dependencies]` |
| 10 | PHP | `composer.json` | `.php` | Shallowest dir with its own `composer.json` | `grep`/`rg` for `use`/`require`/`include` |
| 11 | Ruby | `Gemfile`, `*.gemspec` | `.rb` | Shallowest dir with its own `Gemfile`/gemspec | `grep`/`rg` for `require`/`require_relative` |
| 12 | Swift | `Package.swift` | `.swift` | Shallowest dir with its own `Package.swift` target | `grep`/`rg` for `import` statements |
| 13 | Kotlin | `build.gradle.kts`, `pom.xml` | `.kt`, `.kts` | Same as Java | `grep`/`rg` for `import` statements |
| 14 | Shell/Bash | *(none — manifest-less)* | `.sh`, `.bash` | Flat repo-root, or a dir signaled by its own README/single entrypoint — see the manifest-less-stack rule in `stage-mapper.md` | `grep`/`rg` for `source`/`.` statements |
| 15 | PowerShell | *(usually none; occasionally `*.psd1`)* | `.ps1`, `.psm1` | A `*.psd1` module manifest's dir if present, else flat per the manifest-less-stack rule | `grep`/`rg` for `Import-Module` / dot-sourcing |
| 16 | R | `DESCRIPTION` (package root) | `.R`, `.r` | Shallowest dir with its own `DESCRIPTION` file | `grep`/`rg` for `library()`/`require()`/`source()` |
| 17 | Scala | `build.sbt` | `.scala` | Shallowest dir with its own `build.sbt` — a multi-project root is never itself the boundary | `grep`/`rg` for `import` statements |
| 18 | Perl | `cpanfile`, `Makefile.PL` | `.pl`, `.pm` | Shallowest dir with its own `cpanfile` | `grep`/`rg` for `use`/`require` statements |
| 19 | Lua | *(usually none; occasionally `*.rockspec`)* | `.lua` | A `*.rockspec` dir if present, else flat per the manifest-less-stack rule | `grep`/`rg` for `require()` statements |
| 20 | Dart | `pubspec.yaml` | `.dart` | Shallowest dir with its own `pubspec.yaml` | `grep`/`rg` for `import` statements |

## The two-pass detection algorithm

Both `self-assess-preflight` Check 1 and `self-assess-stage-map` Step 0
run this identically:

1. **Manifest-based.** For each language above (and any other recognizable
   ecosystem manifest not listed — this table is illustrative), glob for
   its manifest pattern(s). Any match adds that language to `languages`.
2. **Extension-frequency fallback**, for manifest-less stacks. Glob by
   file extension across the repo. Any extension with **≥3 files** whose
   language was **not already added in pass 1** still adds that language
   — this is what makes Shell, and any other language without a
   conventional manifest, actually detectable. Don't skip this pass:
   skipping it is the exact gap a real-repo test found (a repo with real
   Go code and 4 shell scripts detected zero languages under the old,
   manifest-only, three-language-hardcoded version of this check).

## Deprecated-idiom / smell catalog (`self-assess-code-idiom`)

`self-assess-code-idiom` checks each detected language for **deprecated
idioms** (modernization-in-place — only ones the version the repo *actually
targets* supersedes) and **generic smells** (error-swallowing catch/rescue,
magic numbers, overlong functions, deep nesting, missing type coverage in an
otherwise-typed module). The version is read from the manifest per language
(`requires-python`, `Cargo.toml` `edition`/`rust-version`, `tsconfig.json`
`target`, `go.mod` `go`, …) and passed into the scan; an idiom is only
"deprecated" if that version offers the replacement.

The per-language hint list lives in `workflows/code-idiom-scan.js`'s
`LANG_BRIEFS` (which cannot read this file — keep the two in sync by hand,
per the exception noted at the top). Representative modernization idioms:

| Language | Deprecated idiom → modern replacement (version gate) |
|---|---|
| Python | `Optional[X]`/`Union[X,Y]` → `X \| None`/`X \| Y` (≥3.10); `typing.List/Dict` → `list/dict` (≥3.9); `os.path` → `pathlib`; `%`/`.format()` → f-strings; `asyncio.get_event_loop()` deprecated (≥3.10) |
| Rust | `Python::acquire_gil()` → `Python::with_gil` (pyo3 ≥0.15); `#[pyfn]`/`#[pyproto]` → `#[pymethods]`; `try!()` → `?`; `extern crate` unneeded (2018+); `mem::uninitialized` → `MaybeUninit` |
| TypeScript | `var` → `let`/`const`; class components / `componentWill*` lifecycles → hooks; `React.FC` discouraged; `require()` → `import`; `enum` → literal unions |
| JavaScript | `var` → `let`/`const`; ESM `require()` → `import` (`"type":"module"`); `.then()` ladders → `async`/`await`; `Object.assign({})` → spread |
| Go | `ioutil.*` → `os`/`io` (≥1.16); `interface{}` → `any` (≥1.18); pre-generics duplicated helpers |
| Java | raw types → generics; `new Integer()` → `valueOf`; anonymous classes → lambdas (≥8); `java.util.Date` → `java.time` |

Smells are language-agnostic and need **no** house-rules entry to be real:
error-swallowing (`except Exception: pass`, empty `catch {}`, ignored Go
errors), magic numbers, functions/files past a length or nesting threshold,
and untyped public functions in an otherwise-typed module. Anything a repo's
own `house-rules.md` already governs is **out of scope** here — that is
`self-assess-lint-audit`'s job; `code-idiom` is passed the house-rules content
precisely so it can avoid double-reporting.

Any language not in the table above still runs, via `code-idiom-scan.js`'s
generic brief (deprecated idioms the present version supersedes + the
language-agnostic smells) — the same fallback discipline the extraction column
uses.
