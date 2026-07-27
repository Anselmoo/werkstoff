# Go CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`spf13/cobra` for the binary. The core package **never imports cobra/flag/os.Args**.

## Project layout (Pillar 2: core separation)
```
<app>/
  go.mod
  cmd/<app>/main.go   # thin entry: build cobra command, dispatch, exit
  internal/core/core.go  # pure logic, zero cobra/flag imports
  internal/core/core_test.go
  testdata/help.golden
  cli-scaffold.manifest.json
```
`core_files: ["internal/core/core.go"]`, `entry_file: "cmd/<app>/main.go"`.

## Help & completions (Pillar 1)
cobra generates `--help` (Usage, then flags). `cobra completion bash|zsh|fish|powershell`
provides completions out of the box.

## NO_COLOR (Pillar 3)
Gate color on `os.Getenv("NO_COLOR") == ""`.

## Exit codes (Pillar 3)
`os.Exit(...)` from `main` only, mapped to the frozen contract. cobra's arg/flag
errors return the usage code; success and runtime you wire explicitly.

## --json / --no-input (Pillar 5)
`--json` marshals with `encoding/json`. `--no-input` (`-n`) disables prompts;
missing required input then exits the usage code. Detect non-interactive with
`term.IsTerminal(int(os.Stdin.Fd()))` and fail fast.

## stdout / stderr (Pillar 5)
Results via `fmt.Fprintln(os.Stdout, ...)`; diagnostics via `fmt.Fprintln(os.Stderr, ...)`.

## Distribution (Pillar 4)
**Go modules / `go install`**: a proper `go.mod` with a module path so
`go install <module>/cmd/<app>@latest` works.

## Snapshot testing (Pillar 3)
`go test` with a golden file (`-update` convention): capture `--help` and compare
to `testdata/help.golden`.

## Worked example (sketch)
```go
// internal/core/core.go — no cobra
package core
import "errors"
func Greet(name string) (string, error) {
    if name == "" { return "", errors.New("name required") }
    return "Hello, " + name, nil
}
```
```go
// cmd/<app>/main.go — thin
func main() {
    var jsonOut, noInput bool
    root := &cobra.Command{Use: "<app> [name]", RunE: func(c *cobra.Command, args []string) error {
        // dispatch into core.Greet; format; return err -> mapped to exit 1
        return nil
    }}
    root.Flags().BoolVar(&jsonOut, "json", false, "emit JSON")
    root.Flags().BoolVarP(&noInput, "no-input", "n", false, "disable prompts")
    if err := root.Execute(); err != nil { os.Exit(1) }
    os.Exit(0)
}
```
