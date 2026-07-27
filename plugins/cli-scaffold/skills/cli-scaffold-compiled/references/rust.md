# Rust CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`clap` (v4, derive API) for the binary. The core **library never imports clap**.

## Project layout (Pillar 2: core separation)
```
<app>/
  Cargo.toml
  src/lib.rs        # core: pure logic, zero clap/env::args
  src/main.rs       # thin bin: parse -> call lib -> format -> exit code
  tests/help_snapshot.rs
  tests/help.golden
  cli-scaffold.manifest.json
```
`core_files: ["src/lib.rs"]`, `entry_file: "src/main.rs"`.

## Help & completions (Pillar 1)
clap generates `--help` with Usage first, then Arguments, then Options. Use
`clap_complete` (`generate`) for shell completions.

## NO_COLOR (Pillar 3)
clap + `anstream`/`ColorChoice` honor `NO_COLOR` automatically; for your own
output, gate ANSI on `std::env::var_os("NO_COLOR").is_none()`.

## Exit codes (Pillar 3)
Map to the frozen contract with `std::process::exit(...)` (or `ExitCode`). clap's
parse error path already exits with the usage code; wire success/runtime yourself.

## --json / --no-input (Pillar 5)
`--json` serializes results with `serde_json::to_writer`. `--no-input` (`-n`)
disables prompts; combined with missing required input, exit the usage code.
Use `std::io::IsTerminal` to fail fast when not a TTY and `--no-input` is unset.

## stdout / stderr (Pillar 5)
Results via `println!`; diagnostics via `eprintln!`.

## Distribution (Pillar 4)
**crates.io**: a complete `Cargo.toml` (`[package]`, `[[bin]]`), publishable with
`cargo publish`.

## Snapshot testing (Pillar 3)
`insta` or `trycmd`: capture `--help` and compare to `tests/help.golden`.

## Worked example (sketch)
```rust
// src/lib.rs — core, no clap
pub fn greet(name: &str) -> Result<String, String> {
    if name.is_empty() { return Err("name required".into()); }
    Ok(format!("Hello, {name}"))
}
```
```rust
// src/main.rs — thin bin
use std::io::IsTerminal;
use clap::Parser;
#[derive(Parser)]
struct Cli { name: Option<String>, #[arg(long)] json: bool, #[arg(short='n', long="no-input")] no_input: bool }
fn main() {
    let cli = Cli::parse();
    let _no_color = std::env::var_os("NO_COLOR").is_some();
    let name = match cli.name {
        Some(n) => n,
        None if cli.no_input || !std::io::stdin().is_terminal() => { eprintln!("error: name required"); std::process::exit(2); }
        None => { /* prompt */ String::new() }
    };
    match app::greet(&name) {
        Ok(s) if cli.json => { println!("{}", serde_json::json!({"message": s})); std::process::exit(0); }
        Ok(s) => { println!("{s}"); std::process::exit(0); }
        Err(e) => { eprintln!("error: {e}"); std::process::exit(1); }
    }
}
```
