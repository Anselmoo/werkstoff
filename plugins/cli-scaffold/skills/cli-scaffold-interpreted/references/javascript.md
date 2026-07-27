# JavaScript CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`yargs` in the entry point (built-in `.completion()`). The core module **imports
no CLI framework and never reads `process.argv`**.

## Project layout (Pillar 2: core separation)
```
<app>/
  package.json
  src/core.js       # pure logic, zero yargs/process.argv
  bin/cli.js        # thin entry (bin), shebang #!/usr/bin/env node
  test/help.snapshot.test.js
  cli-scaffold.manifest.json
```
`core_files: ["src/core.js"]`, `entry_file: "bin/cli.js"`.

## Help & completions (Pillar 1)
yargs renders `--help` (Usage, Positionals, Options). `yargs.completion()`
generates a completion script.

## NO_COLOR (Pillar 3)
Gate ANSI on `process.env.NO_COLOR` being empty.

## Exit codes (Pillar 3)
`process.exit(...)` mapped to the frozen contract; yargs `.strict()`/`.fail()`
exit the usage code on bad input.

## --json / --no-input (Pillar 5)
`--json` serializes with `JSON.stringify`. `--no-input` (`-n`) disables prompts;
missing required input then exits the usage code. Use `process.stdin.isTTY` to
fail fast when non-interactive.

## stdout / stderr (Pillar 5)
Results via `console.log`; diagnostics via `console.error`.

## Distribution (Pillar 4)
**npm**: `package.json` with a `"bin"` field, published with `npm publish`.

## Snapshot testing (Pillar 3)
`jest` (or `vitest`) `toMatchSnapshot()` on captured `--help` output.

## Worked example (sketch)
```js
// src/core.js — no yargs
function greet(name) {
  if (!name) throw new Error("name required");
  return `Hello, ${name}`;
}
module.exports = { greet };
```
```js
#!/usr/bin/env node
// bin/cli.js — thin
const yargs = require("yargs");
const { greet } = require("../src/core");
const argv = yargs(process.argv.slice(2))
  .command("$0 [name]", "greet")
  .option("json", { type: "boolean" })
  .option("no-input", { alias: "n", type: "boolean" })
  .strict().parseSync();                              // bad input -> exit 2
const noColor = !!process.env.NO_COLOR;
if (!argv.name && (argv["no-input"] || !process.stdin.isTTY)) {
  console.error("error: name required"); process.exit(2);
}
try {
  const msg = greet(argv.name || "");
  console.log(argv.json ? JSON.stringify({ message: msg }) : msg);
  process.exit(0);
} catch (e) { console.error(`error: ${e.message}`); process.exit(1); }
```
