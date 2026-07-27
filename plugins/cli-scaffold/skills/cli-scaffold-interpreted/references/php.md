# PHP CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`symfony/console` for the entry command. The core class **uses no
symfony/console and never reads `$argv`/`getopt`**.

## Project layout (Pillar 2: core separation)
```
<app>/
  composer.json
  src/Greeter.php        # pure logic, zero Symfony\Component\Console
  src/GreetCommand.php   # thin Command: parse -> Greeter -> format -> exit
  bin/<app>              # thin entry that boots the Console Application
  tests/HelpSnapshotTest.php
  cli-scaffold.manifest.json
```
`core_files: ["src/Greeter.php"]`, `entry_file: "bin/<app>"`.

## Help & completions (Pillar 1)
symfony/console renders `--help` (Usage, Arguments, Options). It ships a
near-first-party `completion` command (bash/zsh/fish).

## NO_COLOR (Pillar 3)
symfony/console honors `NO_COLOR`; for your own output gate on
`getenv("NO_COLOR")` being false/empty.

## Exit codes (Pillar 3)
`Command::execute` returns an int mapped to the frozen contract; the framework
returns the usage code on invalid input.

## --json / --no-input (Pillar 5)
`--json` serializes with `json_encode`. symfony's global `--no-interaction`
(`-n`) disables prompts; missing required input then exits the usage code. Use
`$input->isInteractive()` / `stream_isatty(STDIN)` to fail fast.

## stdout / stderr (Pillar 5)
Results via `$output` (stdout); diagnostics via
`$output->getErrorOutput()` / `STDERR`.

## Distribution (Pillar 4)
**Packagist / Composer**: `composer.json` with a `"bin"` entry, installable via
`composer global require`.

## Snapshot testing (Pillar 3)
`phpunit` + `spatie/phpunit-snapshot-assertions`: capture `--help` and match.

## Worked example (sketch)
```php
// src/Greeter.php — no Console
final class Greeter {
    public static function greet(string $name): string {
        if ($name === '') { throw new \InvalidArgumentException('name required'); }
        return "Hello, {$name}";
    }
}
```
```php
// src/GreetCommand.php — thin
protected function execute(InputInterface $in, OutputInterface $out): int {
    if (getenv('NO_COLOR') !== false) { $out->setDecorated(false); }
    $name = $in->getArgument('name');
    if ($name === null && (!$in->isInteractive())) {
        $out->getErrorOutput()->writeln('error: name required'); return 2;
    }
    try {
        $msg = Greeter::greet((string) $name);
        $out->writeln($in->getOption('json') ? json_encode(['message' => $msg]) : $msg);
        return 0;
    } catch (\InvalidArgumentException $e) {
        $out->getErrorOutput()->writeln('error: '.$e->getMessage()); return 1;
    }
}
```
