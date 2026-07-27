# TypeScript CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`yargs` in the entry point (chosen for its built-in `.completion()`). The core
module **imports no CLI framework and never reads `process.argv`**.

## Project layout (Pillar 2: core separation)
```
<app>/
  package.json
  tsconfig.json
  src/core.ts       # pure logic, zero yargs/process.argv
  src/cli.ts        # thin entry (bin), compiled to dist/cli.js
  test/help.snapshot.test.ts
  cli-scaffold.manifest.json
```
`core_files: ["src/core.ts"]`, `entry_file: "src/cli.ts"`.

## Help & completions (Pillar 1)
yargs renders `--help` (Usage, Positionals, Options). `yargs.completion()`
generates a completion script.

## NO_COLOR (Pillar 3)
Gate ANSI on `process.env.NO_COLOR` being empty (chalk also honors NO_COLOR).

## Exit codes (Pillar 3)
Set `process.exitCode` / `process.exit(...)` mapped to the frozen contract.
yargs `.fail()` / `.demandCommand()` exit the usage code on bad input.

## --json / --no-input (Pillar 5)
`--json` serializes with `JSON.stringify`. `--no-input` (`-n`) disables prompts;
missing required input then exits the usage code. Use `process.stdin.isTTY` to
fail fast when non-interactive.

## stdout / stderr (Pillar 5)
Results via `console.log`; diagnostics via `console.error`.

## Distribution (Pillar 4)
**npm**: `package.json` with a `"bin"` field and `"files"`/`"type"`, published
with `npm publish`.

## Snapshot testing (Pillar 3)
`vitest` (or `jest`) `toMatchSnapshot()` on captured `--help` output.

## Worked example (sketch)
```ts
// core.ts — no yargs
export function greet(name: string): string {
  if (!name) throw new Error("name required");
  return `Hello, ${name}`;
}
```
```ts
// cli.ts — thin
import yargs from "yargs";
import { greet } from "./core";
const argv = yargs(process.argv.slice(2))
  .command("$0 [name]", "greet", y => y.positional("name", { type: "string" }))
  .option("json", { type: "boolean" })
  .option("no-input", { alias: "n", type: "boolean" })
  .strict().parseSync();                              // bad input -> exit 2
const noColor = !!process.env.NO_COLOR;
const name = argv.name as string | undefined;
if (!name && (argv["no-input"] || !process.stdin.isTTY)) {
  console.error("error: name required"); process.exit(2);
}
try {
  const msg = greet(name ?? "");
  console.log(argv.json ? JSON.stringify({ message: msg }) : msg);
  process.exit(0);
} catch (e) { console.error(`error: ${(e as Error).message}`); process.exit(1); }
```
