# .NET CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`System.CommandLine` for the console project. The core project **never
references System.CommandLine**.

## Project layout (Pillar 2: core separation)
```
<App>/
  <App>.sln
  src/<App>.Core/<App>.Core.csproj   # pure logic, no System.CommandLine
  src/<App>.Core/Greeter.cs
  src/<App>.Cli/<App>.Cli.csproj     # thin console: parse, dispatch, exit
  src/<App>.Cli/Program.cs
  tests/<App>.Tests/HelpSnapshotTests.cs
  cli-scaffold.manifest.json
```
`core_files: ["src/<App>.Core/Greeter.cs"]`, `entry_file: "src/<App>.Cli/Program.cs"`.

## Help & completions (Pillar 1)
System.CommandLine generates `--help` (Usage, Arguments, Options). `dotnet-suggest`
provides tab completion.

## NO_COLOR (Pillar 3)
Gate ANSI on `Environment.GetEnvironmentVariable("NO_COLOR")` being null/empty.

## Exit codes (Pillar 3)
Return `int` from `Main` (or `Environment.Exit`), mapped to the frozen contract.
System.CommandLine returns the usage code on parse failure.

## --json / --no-input (Pillar 5)
`--json` serializes with `System.Text.Json`. `--no-input` (`-n`) disables prompts;
missing required input then exits the usage code. Use
`Console.IsInputRedirected` to fail fast when non-interactive.

## stdout / stderr (Pillar 5)
Results via `Console.Out`; diagnostics via `Console.Error`.

## Distribution (Pillar 4)
**NuGet .NET tool**: the CLI `.csproj` sets `<PackAsTool>true</PackAsTool>` and a
`<ToolCommandName>`, installable with `dotnet tool install -g <App>`.

## Snapshot testing (Pillar 3)
`Verify` (VerifyTests) or xUnit golden comparison: capture `--help` and compare
to a committed snapshot.

## Worked example (sketch)
```csharp
// Greeter.cs — core, no System.CommandLine
namespace App.Core;
public static class Greeter {
    public static string Greet(string name) =>
        string.IsNullOrEmpty(name) ? throw new ArgumentException("name required") : $"Hello, {name}";
}
```
```csharp
// Program.cs — thin
var name = new Argument<string?>("name") { Arity = ArgumentArity.ZeroOrOne };
var json = new Option<bool>("--json");
var noInput = new Option<bool>(new[]{"-n","--no-input"});
var root = new RootCommand("<app>") { name, json, noInput };
root.SetHandler((string? n, bool j, bool ni) => {
    // dispatch into Greeter.Greet; format; Environment.Exit(0/1/2)
});
return await root.InvokeAsync(args); // parse errors -> usage code
```
