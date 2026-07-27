# PowerShell CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
Advanced function with `[CmdletBinding()]` + `param(...)` in the entry script.
The module holds only exported functions (the core).

## Project layout (Pillar 2: core separation)
```
<App>/
  <App>.psd1           # module manifest (distribution metadata)
  <App>.psm1           # core module: pure functions, no param()/arg parsing
  bin/<app>.ps1        # thin entry: param() -> call module -> format -> exit
  test/Help.Tests.ps1  # Pester
  cli-scaffold.manifest.json
```
`core_files: ["<App>.psm1"]`, `entry_file: "bin/<app>.ps1"`.

## Help & completions (Pillar 1)
Comment-based help (`.SYNOPSIS`/`.PARAMETER`) drives `Get-Help` and `--help`
(map `-?`/`--help` to Usage first). First-party completion via
`Register-ArgumentCompleter`.

## NO_COLOR (Pillar 3)
Honor `$env:NO_COLOR`; set `$PSStyle.OutputRendering = 'PlainText'` when present.

## Exit codes (Pillar 3)
`exit <code>` mapped to the frozen contract; a `[Parameter(Mandatory)]` gap or a
`throw` in `param` binding surfaces the usage code.

## --json / --no-input (Pillar 5)
`--json` (a `[switch]$Json`) serializes with `ConvertTo-Json`. `-NoInput` /
`--no-input` (`-n`) disables prompts; missing required input then exits the usage
code. Use `[Environment]::UserInteractive` / `$Host.UI.RawUI` to fail fast.

## stdout / stderr (Pillar 5)
Results via `Write-Output`; diagnostics via `Write-Error` / `$Host.UI.WriteErrorLine`.

## Distribution (Pillar 4)
**PowerShell Gallery**: the `.psd1` manifest, published with `Publish-Module`.

## Snapshot testing (Pillar 3)
`Pester`: capture `--help`/`Get-Help` output and compare to a stored snapshot.

## Worked example (sketch)
```powershell
# <App>.psm1 — core, no param parsing
function Get-Greeting {
    param([string]$Name)
    if ([string]::IsNullOrEmpty($Name)) { throw 'name required' }
    "Hello, $Name"
}
Export-ModuleMember -Function Get-Greeting
```
```powershell
# bin/<app>.ps1 — thin entry
[CmdletBinding()]
param([Parameter(Position=0)][string]$Name, [switch]$Json, [Alias('n')][switch]$NoInput)
Import-Module "$PSScriptRoot/../<App>.psm1"
if ($env:NO_COLOR) { $PSStyle.OutputRendering = 'PlainText' }
if (-not $Name -and ($NoInput -or -not [Environment]::UserInteractive)) {
    Write-Error 'error: name required'; exit 2
}
try {
    $msg = Get-Greeting -Name $Name
    if ($Json) { Write-Output (@{ message = $msg } | ConvertTo-Json -Compress) } else { Write-Output $msg }
    exit 0
} catch { Write-Error "error: $_"; exit 1 }
```
