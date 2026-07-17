# Ruby CLI generation reference

Pin every generated Ruby CLI to this shape. Deviate only when the user's
explicit request contradicts a specific rule below — never silently blend
the two framework paths.

## 1. Framework

Default to **Thor**. Switch to stdlib **OptionParser** only when the user
explicitly asks for zero external dependencies. Pick exactly one path per
generation; never mix Thor DSL calls with a hand-rolled `OptionParser`
instance in the same executable.

**Thor path (default).** Add `gem "thor"` to the gemspec's runtime
dependencies. Define one `Thor` subclass per CLI, with each subcommand as a
public method preceded by a `desc` call:

```ruby
require "thor"
require_relative "../<app>/core"

module <App>
  class CLI < Thor
    desc "run NAME", "Run the thing for NAME"
    def run(name)
      puts <App>::Core.run(name)
    end
  end
end
```

**OptionParser path (opt-in, zero-dependency).** Parse `ARGV` by hand with
`require "optparse"`, build an options `Hash`, then dispatch on
`ARGV.shift` (the subcommand) inside the executable itself — there is no
class to subclass. Document this path in a comment at the top of the
executable (`# Zero-dependency build: stdlib OptionParser, no Thor.`) so a
future regeneration doesn't quietly reintroduce Thor calls into it.

## 2. Project layout

```
<app>/
├── exe/
│   └── <app>              # thin Thor CLI entry point, executable bit set
├── lib/
│   └── <app>/
│       ├── core.rb        # all business logic, zero Thor/CLI imports
│       └── version.rb     # VERSION constant, required by gemspec + core
├── spec/
│   ├── spec_helper.rb
│   ├── <app>_core_spec.rb
│   └── cli_spec.rb        # Aruba snapshot spec for --help
├── <app>.gemspec
├── Gemfile
└── README.md
```

Use `exe/`, never `bin/` — modern Bundler convention avoids the PATH
collision `bin/` causes during `bundle install` (Bundler itself writes
binstubs to `bin/`).

## 3. Help text and completions

Let Thor auto-generate help from `desc`/`long_desc`: `desc` supplies the
one-line summary shown in the command list; `long_desc` supplies the
extended body shown by `<app> help <command>`. Write both for every
subcommand — never leave `long_desc` off a command with more than one
argument or flag. `thor help` and `<app> help` are equivalent entry
points; document `<app> help <command>` in the README as the per-command
lookup.

State the shell-completion gap honestly: **Ruby and Thor have no
first-party shell-completion generator.** Do not invent one. Handle it one
of two ways, and say in the generated README which was chosen:

- **Default fallback**: ship a hand-written `completions/<app>.bash`
  (plain `complete -W "list of subcommands" <app>`) alongside the gem, and
  document sourcing it from `.bashrc`. This is static and must be
  hand-updated when subcommands change — say so in a comment at the top
  of the file.
- **Only if the user asks for real completion generation**: point them at
  the `bashly` project's completion-generation pattern as a separate build
  tool, not as something Thor itself provides. Do not silently pull
  `bashly` into a Thor-based project — it is a different, incompatible
  scaffolding generator.

## 4. NO_COLOR-aware output

Check `ENV["NO_COLOR"]` explicitly before emitting any ANSI color — Thor's
`say`/`set_color` helpers do not check it automatically. Compute a single
`color_enabled?` boolean once, near the top of `core.rb` or a small
`lib/<app>/output.rb` helper, and gate every colored call on it:

```ruby
def color_enabled?
  ENV["NO_COLOR"].nil? || ENV["NO_COLOR"].empty?
end
```

Use the `pastel` gem (`Pastel.new(enabled: color_enabled?)`) when adding
`pastel` as a dependency is acceptable, since `Pastel#enabled` already
degrades to plain strings when passed `enabled: false`. When staying
zero-dependency, wrap raw ANSI codes in a helper that returns the plain
string unchanged when `color_enabled?` is false — never emit raw escape
codes inline in command methods.

## 5. Exit codes

Use the frozen cross-paradigm contract everywhere in this plugin:

- `0` — success
- `1` — general/runtime error
- `2` — usage/argument error

Call `exit(N)` explicitly at the point of failure; never rely on Ruby's
default of exiting 1 on an uncaught exception, since that conflates
runtime errors with usage errors. Thor does **not** default its own
argument errors to exit code 2 the way Click/Cobra do — Thor raises
`Thor::UndefinedCommandError` or `Thor::InvocationError` and, left
uncaught, this triggers Ruby's default uncaught-exception exit code (1).
Rescue those explicitly in the executable and remap them:

```ruby
begin
  <App>::CLI.start(ARGV)
rescue Thor::UndefinedCommandError, Thor::InvocationError => e
  warn e.message
  exit(2)
rescue <App>::Core::Error => e
  warn e.message
  exit(1)
end
```

## 6. `--json` output and `--no-input`

Declare both as `class_option`s on the `Thor` subclass so every subcommand
inherits them:

```ruby
class_option :json, type: :boolean, default: false, desc: "Emit JSON"
class_option :no_input, type: :boolean, default: false, desc: "Disable prompts"
```

For `--json`, branch at the point of output: `require "json"` once at the
top of the executable, and in each command method emit
`JSON.generate(result)` to stdout when `options[:json]` is true, plain
`puts`/`say` formatting otherwise. Keep the JSON-vs-plain branch in the
CLI layer, not in `core.rb` — `core.rb` returns plain Ruby data structures
(Hash/Array), never pre-serialized strings.

For `--no-input`, guard every `ask`/`yes?` call: when `options[:no_input]`
is true and a required value was not supplied as an argument or flag,
skip the prompt and fail immediately with exit code 2 (missing required
input is a usage error, not a runtime error):

```ruby
def run(name = nil)
  if name.nil?
    if options[:no_input]
      warn "NAME is required (no-input mode: cannot prompt)"
      exit(2)
    end
    name = ask("Name?")
  end
  puts <App>::Core.run(name)
end
```

## 7. stdout/stderr discipline

Send results — the data the command exists to produce — to stdout via
`puts` (or Thor's `say` when a color/style helper is wanted). Send
diagnostics, progress, and warnings to stderr via `$stderr.puts` or the
`warn` kernel method. Never let `core.rb` call `puts`/`warn` itself — it
returns values; only `exe/<app>` and the `CLI` class perform I/O. This
keeps `core.rb` requirable and testable without capturing stdout.

## 8. Distribution

Ship as a RubyGem. In `<app>.gemspec`:

```ruby
spec.bindir     = "exe"
spec.executables = ["<app>"]
spec.files      = Dir["lib/**/*.rb", "exe/*"]
spec.add_dependency "thor", "~> 1.3"
```

Build and publish:

```bash
gem build <app>.gemspec
gem push <app>-<version>.gem
```

For local development, run the executable through Bundler without
installing the gem: `bundle exec exe/<app>`. Document both paths in the
generated README — `bundle exec` for contributors, `gem install <app>`
for end users after publishing.

## 9. Snapshot testing `--help`

Use **Aruba** (RSpec-based) to snapshot-test `--help` output. Add
`aruba` and `rspec` as development dependencies, configure
`spec/spec_helper.rb` to `require "aruba/rspec"`, and write the help spec
against the built executable:

```ruby
# spec/cli_spec.rb
require "spec_helper"

RSpec.describe "<app> --help", type: :aruba do
  it "prints the top-level help banner" do
    run_command("<app> --help")
    expect(last_command_started).to have_output(/Commands:/)
    expect(last_command_started).to have_output(/<app> run NAME/)
  end
end
```

Prefer targeted `have_output(/regex/)` assertions over a full literal
snapshot compare when help text includes anything environment-dependent
(gem version, terminal width); use a captured-output equality snapshot
only when the help text is fully static.

## 10. Minimal worked example

Illustrative only — regenerate concrete names, commands, and error
handling to fit the actual CLI being built, do not copy verbatim.

```ruby
# lib/<app>/core.rb
module <App>
  class Core
    class Error < StandardError; end

    def self.run(name)
      raise Error, "name cannot be blank" if name.to_s.strip.empty?
      { greeting: "Hello, #{name}!" }
    end
  end
end

# exe/<app>
#!/usr/bin/env ruby
require "thor"
require "json"
require_relative "../lib/<app>/core"

module <App>
  class CLI < Thor
    class_option :json, type: :boolean, default: false
    class_option :no_input, type: :boolean, default: false

    desc "run NAME", "Greet NAME"
    long_desc "Prints a greeting for NAME, or exits 2 if NAME is missing."
    def run(name = nil)
      if name.nil?
        exit(2) if options[:no_input]
        name = ask("Name?")
      end
      result = <App>::Core.run(name)
      options[:json] ? puts(JSON.generate(result)) : puts(result[:greeting])
    rescue <App>::Core::Error => e
      warn e.message
      exit(1)
    end
  end
end

begin
  <App>::CLI.start(ARGV)
rescue Thor::UndefinedCommandError, Thor::InvocationError => e
  warn e.message
  exit(2)
end
```
