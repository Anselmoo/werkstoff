# TypeScript/JavaScript CLI generation reference

Pinned idioms for generating a production-grade CLI in TypeScript or
JavaScript. Generate fresh every time from these rules — there is no stored
template to copy. Default to TypeScript; only generate plain JavaScript if
the user explicitly asks for it.

## 1. Framework

Use oclif. Treat it as the full framework and the distribution mechanism,
not merely a flag parser — do not hand-roll flag parsing, help generation,
or a `bin/` entry when oclif already owns all three.

Scaffold with the official generator, never by hand:

```bash
npx oclif generate <cli-name>
```

`oclif generate` always scaffolds TypeScript — there is no `--javascript`
flag or JS-selection prompt to answer. If the user explicitly asked for
plain JavaScript, generate the TypeScript scaffold as normal and then
either compile it (`tsc`) and ship the `lib/` output, or manually convert
the generated `src/` sources to plain `.js` — do not invent generator
flags that don't exist.

Generate each command as a class extending `Command`, with `static flags`,
`static args`, `static description`, and a `run()` method that only parses
input and delegates — never one that contains business logic:

```typescript
import {Command, Flags} from '@oclif/core'

export default class Hello extends Command {
  static description = 'describe what this command does'
  static flags = {
    name: Flags.string({char: 'n', description: 'name to greet'}),
  }

  async run(): Promise<void> {
    const {flags} = await this.parse(Hello)
    this.log(`hello ${flags.name}`)
  }
}
```

Add further commands with `npx oclif generate command <name>`, never by
copy-pasting an existing command file by hand.

## 2. Project layout

Generate exactly this tree (oclif's generator produces the skeleton; fill
in `src/lib/` yourself since oclif has no opinion on it):

```
<cli-name>/
├── bin/
│   ├── run.js          # production entry point, calls @oclif/core run()
│   └── dev.js          # dev entry point, ts-node/tsx, no build step needed
├── src/
│   ├── commands/
│   │   ├── index.ts    # optional default command
│   │   └── <name>.ts   # one file per command, thin — parse + delegate only
│   └── lib/
│       └── core.ts     # all business logic, plain functions, zero oclif imports
├── test/
│   └── commands/
│       └── <name>.test.ts
├── package.json         # includes the "oclif" config block (see below)
├── tsconfig.json
└── README.md             # oclif can auto-generate command docs into this file
```

Generate `src/commands/<name>.ts` files thin by construction: the `run()`
method's body is parse-flags-then-call-into-`src/lib/`, nothing else. Put
every conditional, validation, transformation, and side effect in
`src/lib/core.ts` (or additional `src/lib/*.ts` modules) as plain exported
functions taking plain arguments and returning plain values — no
`this.log`, no `Flags`, no `Command` subclassing anywhere in `src/lib/`, so
each function is unit-testable by calling it directly with no oclif
scaffolding.

Generate the `oclif` config block in `package.json` exactly as
`oclif generate` produces it — `bin`, `dirname`, `commands`, `plugins`,
`topicSeparator` — and do not hand-edit its shape beyond adding real
command/topic entries as they're generated.

## 3. Help text and completions

Rely on oclif's built-in help — do not generate a custom `--help` handler.
oclif derives topics from directory structure under `src/commands/`
(`src/commands/foo/bar.ts` becomes topic `foo`, command `foo:bar`), and
renders:

- a topic list when the CLI is run with no arguments,
- a commands table per topic,
- a flags table per command generated from `static flags` descriptions.

Write a real `description` (and `summary` where the command needs both a
short and long form) on every command and every flag — oclif's help
renderer surfaces exactly what's declared, so an undocumented flag or
command renders as a blank line, not an omission.

Generate shell completion via oclif's built-in autocomplete plugin, not a
hand-written completion script:

```bash
npm install --save @oclif/plugin-autocomplete
```

Add `'@oclif/plugin-autocomplete'` to the `oclif.plugins` array in
`package.json`. This gives the CLI a working `<bin> autocomplete` command
that generates bash and zsh completion scripts — do not write a separate
`completions/` directory by hand.

## 4. NO_COLOR-aware output

oclif's own coloring (via `ansis`/chalk-family libraries used internally
by `this.log`, `ux.styledJSON`, table rendering, etc.) already respects
the `NO_COLOR` and `FORCE_COLOR` environment variables — do not add a
custom color-stripping layer on top.

State this behavior explicitly in generated docs/tests rather than
assuming it's self-evident:

- Verify color-off behavior with `NO_COLOR=1 <bin> <command>` and assert
  the captured output contains no ANSI escape sequences.
- Verify color-on behavior (e.g. in a non-TTY CI runner where oclif would
  otherwise auto-disable color) by forcing it with `FORCE_COLOR=1`.
- Never call a raw `chalk`/`ansis` color function directly inside a
  command's `run()` for anything user-facing — route colored output
  through `this.log()` or oclif's `ux` helpers so the `NO_COLOR` check
  stays centralized in one place instead of being reimplemented per
  command.

## 5. Exit codes

Restate and enforce the frozen cross-paradigm contract in every generated
CLI: `0` success, `1` general/runtime error, `2` usage/argument error.

Map it onto oclif's primitives exactly as follows:

- Let a `run()` that resolves normally exit `0` — do not call `this.exit(0)`
  explicitly, it's the default.
- `@oclif/core`'s own default exit code for both the parser and an
  unadorned `this.error(message)` is **`2`**, not `1` — do not assume
  `this.error()` alone gives you the runtime-error branch of the
  contract. For a runtime failure (I/O error, failed operation, caught
  exception with no more specific code), throw `this.error(message,
  {exit: 1})` or a `new CLIError` **with an explicit `{exit: 1}`** —
  never call bare `this.error(message)` for this case, since its default
  would silently misreport a runtime error as a usage error.
- For a usage/argument failure — a required flag/arg missing after
  oclif's own parser accepted the invocation, or a value that parses but
  fails a semantic check — `this.error(message, {exit: 2})` is correct as
  written, and also matches `this.error()`'s own default, so the explicit
  `{exit: 2}` here is for clarity/future-proofing rather than strictly
  required.
- oclif's own flag/arg parser already exits `2` on a parsing failure
  (unknown flag, missing required flag, wrong flag type) before `run()`
  is ever entered — do not add a redundant catch for this; it is already
  contract-compliant out of the box.
- Never call `process.exit()` directly — always go through `this.exit()`
  or a thrown `CLIError`/`this.error()`, so cleanup hooks and error
  formatting still run.

## 6. `--json` output and `--no-input`

Enable oclif's built-in JSON mode instead of hand-rolling a `--json` flag:

```typescript
export default class Status extends Command {
  static enableJsonFlag = true

  async run(): Promise<Record<string, unknown>> {
    const {flags} = await this.parse(Status)
    const result = await getStatus(flags) // src/lib/core.ts
    if (!this.jsonEnabled()) this.log(formatHuman(result))
    return result
  }
}
```

With `enableJsonFlag = true`, oclif adds `--json` automatically, and
whatever `run()` returns is serialized as JSON to stdout when `--json` is
passed — do not manually `JSON.stringify` and `this.log` it yourself in
that branch; return the value and let oclif serialize it. Use
`this.jsonEnabled()` inside `run()` to skip human-formatted `this.log`
calls when `--json` was passed, so stdout carries exactly one artifact,
never both.

Generate a `--no-input` flag on any command that would otherwise prompt
interactively (via `ux.prompt()`, `ux.confirm()`, or an inquirer-style
library):

```typescript
static flags = {
  'no-input': Flags.boolean({description: 'disable interactive prompts', default: false}),
}
```

In `run()`, branch on `flags['no-input']` before any prompt call: if
`true` and a required value is missing, call
`this.error('missing required value: <name>', {exit: 2})` instead of
prompting — never silently fall back to a default when `--no-input` was
explicitly passed and a value is genuinely required.

## 7. stdout/stderr discipline

Route every command's primary result/data output through `this.log()`
(stdout) — this is what `--json` serialization and snapshot tests capture.

Route all diagnostics through stderr-bound helpers:

- `this.warn(message)` for non-fatal warnings — logs to stderr, execution
  continues.
- `this.error(message, {exit})` for fatal errors — logs to stderr, then
  exits with the given code (default `2`, not `1` — see §5; pass
  `{exit: 1}` explicitly for a runtime-error call site).
- Plain `console.error(...)` only for output that must bypass oclif's
  error-formatting machinery entirely (rare — prefer `this.warn`/
  `this.error` in nearly all cases).

Never write diagnostic or progress text via `this.log()` or
`console.log()` — that pollutes stdout for any caller piping or parsing
the command's output, and breaks `--json` mode's guarantee of a single
JSON artifact on stdout.

## 8. Distribution

Ship via npm as the default distribution path:

```bash
npm publish
```

`oclif generate` already wires the `package.json` `bin` field to
`bin/run.js`, so `npm install -g <cli-name>` (or `npx <cli-name>`) works
immediately post-publish with no extra packaging step.

For standalone installers that don't require a Node.js install on the
target machine, use oclif's own packer rather than a third-party bundler:

```bash
npx oclif pack macos    # .pkg installer
npx oclif pack win      # Windows installer/exe
npx oclif pack deb      # Debian/Ubuntu .deb package
npx oclif pack tarballs # cross-platform tarballs (includes a Node runtime)
```

Document the prerequisite for each: `oclif pack macos` needs a macOS
signing identity for a distributable-outside-Gatekeeper build,
`oclif pack win` needs `makensis` (NSIS) on the packing machine,
`oclif pack deb` needs `dpkg`/`fakeroot` available (typically only
practical from a Linux CI runner).

## 9. Snapshot testing `--help`

Use vitest as the test runner and `@oclif/test`'s `runCommand` helper to
invoke the CLI in-process and capture stdout, rather than shelling out to
a built binary.

```bash
npm install --save-dev vitest @oclif/test
```

```typescript
import {describe, expect, it} from 'vitest'
import {runCommand} from '@oclif/test'

describe('<name> --help', () => {
  it('matches the snapshot', async () => {
    const {stdout} = await runCommand(['<name>', '--help'])
    expect(stdout).toMatchSnapshot()
  })
})
```

Generate one such snapshot test per command (and one for the bare
topic/root help) so any unintentional change to a flag description,
summary, or examples list fails CI with a visible diff instead of
drifting silently. Commit the generated `__snapshots__/*.snap` file;
regenerate it deliberately with `vitest -u` only when the help text
change is intentional, never as a blanket pre-commit habit.

## 10. Minimal worked example

Illustrative only — do not copy verbatim, regenerate names/flags/logic to
fit the actual CLI being built.

`src/lib/core.ts`:

```typescript
export interface GreetOptions {
  name: string
  shout?: boolean
}

export function buildGreeting({name, shout}: GreetOptions): string {
  const text = `hello, ${name}`
  return shout ? text.toUpperCase() : text
}
```

`src/commands/greet.ts`:

```typescript
import {Command, Flags} from '@oclif/core'
import {buildGreeting} from '../lib/core.js'

export default class Greet extends Command {
  static description = 'print a greeting for <name>'
  static enableJsonFlag = true
  static flags = {
    name: Flags.string({char: 'n', description: 'name to greet', required: true}),
    shout: Flags.boolean({description: 'uppercase the greeting', default: false}),
  }

  async run(): Promise<{greeting: string}> {
    const {flags} = await this.parse(Greet)
    const greeting = buildGreeting({name: flags.name, shout: flags.shout})
    if (!this.jsonEnabled()) this.log(greeting)
    return {greeting}
  }
}
```

`buildGreeting` is unit-testable with zero oclif imports; `Greet.run()`
is the thin oclif-facing shell around it.
