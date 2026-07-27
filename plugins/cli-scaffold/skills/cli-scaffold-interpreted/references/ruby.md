# Ruby CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`OptionParser` (stdlib) in the entry point. The core library **requires no CLI
framework and never reads `ARGV`**.

## Project layout (Pillar 2: core separation)
```
<app>/
  <app>.gemspec
  lib/<app>.rb        # pure logic, zero optparse/ARGV
  exe/<app>           # thin entry (gem executable)
  spec/help_snapshot_spec.rb
  cli-scaffold.manifest.json
```
`core_files: ["lib/<app>.rb"]`, `entry_file: "exe/<app>"`.

## Help & completions (Pillar 1)
OptionParser renders `--help` (Usage banner, then Options; document positional
Arguments in the banner). **No first-party completion mechanism** — document the
limitation honestly, or ship an optional hand-written bash-completion file.

## NO_COLOR (Pillar 3)
Gate ANSI on `ENV["NO_COLOR"]` being nil/empty.

## Exit codes (Pillar 3)
`exit(...)` mapped to the frozen contract. `OptionParser::ParseError` (unknown
flag/missing arg) → rescue and exit the usage code.

## --json / --no-input (Pillar 5)
`--json` serializes with `require "json"`. `--no-input` (`-n`) disables prompts;
missing required input then exits the usage code. Use `$stdin.tty?` to fail fast
when non-interactive.

## stdout / stderr (Pillar 5)
Results via `$stdout.puts`; diagnostics via `$stderr.puts` / `warn`.

## Distribution (Pillar 4)
**RubyGems**: a complete `.gemspec` with `spec.executables`, built with
`gem build` and pushed with `gem push`.

## Snapshot testing (Pillar 3)
`rspec` + `rspec-snapshot`: capture `--help` and match the stored snapshot.

## Worked example (sketch)
```ruby
# lib/<app>.rb — no optparse
module App
  def self.greet(name)
    raise ArgumentError, "name required" if name.to_s.empty?
    "Hello, #{name}"
  end
end
```
```ruby
#!/usr/bin/env ruby
# exe/<app> — thin
require "optparse"; require "json"; require_relative "../lib/<app>"
opts = { json: false, no_input: false }
parser = OptionParser.new do |o|
  o.banner = "Usage: <app> [options] [name]"
  o.on("--json") { opts[:json] = true }
  o.on("-n", "--no-input") { opts[:no_input] = true }
end
begin; parser.parse!; rescue OptionParser::ParseError => e; warn e.message; exit 2; end
name = ARGV.shift
if name.nil? && (opts[:no_input] || !$stdin.tty?); warn "error: name required"; exit 2; end
begin
  msg = App.greet(name.to_s)
  $stdout.puts(opts[:json] ? JSON.generate({ message: msg }) : msg); exit 0
rescue ArgumentError => e; warn "error: #{e.message}"; exit 1; end
```
