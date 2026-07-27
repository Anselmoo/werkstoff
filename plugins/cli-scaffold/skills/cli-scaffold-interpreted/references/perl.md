# Perl CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`Getopt::Long` (core) in the entry point, `Pod::Usage` for help. The core module
**uses no Getopt and never reads `@ARGV`**.

## Project layout (Pillar 2: core separation)
```
<app>/
  Makefile.PL          # ExtUtils::MakeMaker
  lib/App.pm           # pure logic, zero Getopt/@ARGV
  bin/<app>            # thin entry: GetOptions -> App -> format -> exit
  t/help_snapshot.t
  cli-scaffold.manifest.json
```
`core_files: ["lib/App.pm"]`, `entry_file: "bin/<app>"`.

## Help & completions (Pillar 1)
`Pod::Usage` renders `--help` from POD with a Usage section first (document
Arguments and Options in POD). **No first-party completion mechanism** — document
the limitation honestly in the manifest (`completion.supported: false`).

## NO_COLOR (Pillar 3)
Gate ANSI on `$ENV{NO_COLOR}` being undef/empty.

## Exit codes (Pillar 3)
`exit(...)` mapped to the frozen contract. `Getopt::Long` returns false on a bad
flag → exit the usage code (`pod2usage(2)`).

## --json / --no-input (Pillar 5)
`--json` serializes with `JSON::PP` (core). `--no-input` (`-n`) disables prompts;
missing required input then exits the usage code. Use `-t STDIN` to fail fast
when non-interactive.

## stdout / stderr (Pillar 5)
Results via `print STDOUT`; diagnostics via `print STDERR` / `warn`.

## Distribution (Pillar 4)
**CPAN**: `Makefile.PL` (ExtUtils::MakeMaker) with an `EXE_FILES` entry,
installable via `cpanm`.

## Snapshot testing (Pillar 3)
`Test::More` + `Test::Snapshot`: capture `--help` and compare to the snapshot.

## Worked example (sketch)
```perl
# lib/App.pm — no Getopt
package App;
sub greet { my ($name) = @_; die "name required\n" unless defined $name && length $name; return "Hello, $name"; }
1;
```
```perl
#!/usr/bin/env perl
# bin/<app> — thin
use strict; use warnings; use Getopt::Long; use Pod::Usage; use JSON::PP; use lib 'lib'; use App;
my ($json, $no_input, $help);
GetOptions("json" => \$json, "no-input|n" => \$no_input, "help" => \$help) or pod2usage(2);  # bad flag -> exit 2
pod2usage(0) if $help;
my $name = shift @ARGV;
if (!defined $name && ($no_input || !(-t STDIN))) { warn "error: name required\n"; exit 2; }
my $msg = eval { App::greet($name // "") };
if ($@) { warn "error: $@"; exit 1; }
print STDOUT ($json ? encode_json({ message => $msg }) : $msg), "\n";
exit 0;
__END__
=head1 SYNOPSIS

Usage: <app> [options] [name]
```
