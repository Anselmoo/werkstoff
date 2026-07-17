# PHP: Symfony Console

Pin every generated PHP CLI to this exact shape. Do not substitute another
framework (no `league/climate`, no raw `getopt()`, no bespoke argv parsing) and
do not skip any section below — each one closes off a degree of freedom that
would otherwise cause two generations of "the same app" to diverge.

## 1. Framework

Install Symfony Console as the only CLI dependency:

```bash
composer require symfony/console
```

Generate every command as a class extending `Command`, with argument/option
declaration in `configure()` and all execution in `execute()`. `execute()`
must not contain business logic — it must call straight into `src/Core/` (see
§2) and translate the result into an exit code and output calls.

```php
<?php declare(strict_types=1);

namespace App\Command;

use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

#[AsCommand(name: 'greet', description: 'Print a greeting')]
final class GreetCommand extends Command
{
    protected function configure(): void
    {
        $this->addArgument('name', mode: null, description: 'Name to greet');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $output->writeln('Hello, ' . $input->getArgument('name') . '!');
        return Command::SUCCESS;
    }
}
```

Use the `#[AsCommand]` attribute for name/description, not the deprecated
`static $defaultName` property. Register commands on the `Application` in
`bin/<app>` by instantiating and `add()`-ing each Command class explicitly —
do not rely on directory auto-discovery/globbing for command registration.

## 2. Project layout

Generate exactly this tree — `src/Core/` has zero `use Symfony\Component\Console\...`
imports anywhere, and is unit-testable with plain PHPUnit and no Console
bootstrapping:

```
<app>/
├── bin/
│   └── <app>                  # executable, no .php extension, chmod +x
├── src/
│   ├── Core/                  # plain PSR-4 classes, zero Console imports
│   │   └── Greeter.php
│   └── Command/                # thin Command classes, one per CLI command
│       └── GreetCommand.php
├── tests/
│   ├── Core/
│   │   └── GreeterTest.php
│   └── Command/
│       └── GreetCommandTest.php
├── composer.json
├── box.json                    # Box compile config, see §8
└── phpunit.xml.dist
```

Declare `src/` under a single PSR-4 namespace root (`App\`) in `composer.json`:

```json
{
    "autoload": { "psr-4": { "App\\": "src/" } },
    "autoload-dev": { "psr-4": { "App\\Tests\\": "tests/" } }
}
```

## 3. Help text and completions

Rely entirely on Symfony Console's built-in help generation — do not hand-write
`--help` text. Every registered Command automatically gets a `--help`/`-h`
flag rendering Usage, Arguments, Options, and Help sections derived from
`configure()`'s argument/option declarations and their `description` values;
write precise `description` strings on every argument and option since they
are the only source of the rendered help. The bare `Application` (no command
given) automatically renders the global `list` command showing every
registered command grouped and described.

For shell completion, add Symfony Console's native `completion` command to
the `Application` — do not hand-roll a completion script. It ships built in
(`Symfony\Component\Console\Command\DumpCompletionCommand`, registered
under the `completion` command name — the class is *not* named
`CompletionCommand`) and Console auto-registers it; instruct end users to
wire it up per-shell with:

```bash
<app> completion bash > /etc/bash_completion.d/<app>
<app> completion zsh  > "${fpath[1]}/_<app>"
<app> completion fish > ~/.config/fish/completions/<app>.fish
```

If a command should be hidden from completion/listing under a runtime
condition (e.g. feature-flagged), override `Command::isEnabled(): bool` rather
than conditionally registering it on the `Application`.

## 4. NO_COLOR-aware output

Do not hand-roll `NO_COLOR` detection. Construct output as
`new ConsoleOutput()` in `bin/<app>` and let Symfony Console's own decoration
logic decide: `ConsoleOutput` checks the `NO_COLOR` env var, the `TERM`
value, and whether the underlying stream is a TTY, and disables ANSI
decoration automatically when appropriate. Do not call
`$output->setDecorated(true)` unconditionally anywhere — that overrides and
defeats this detection.

To let a user force the behavior explicitly, rely on Symfony Console's global
`--no-ansi` / `--ansi` flags (already present on every `Application` without
extra code) rather than adding a bespoke `--no-color` option. To verify
decoration state programmatically (e.g. in a test or a Core formatter that
needs to know), call `$output->isDecorated(): bool` — never re-derive it from
`getenv('NO_COLOR')` directly outside of Console's own detection path.

## 5. Exit codes

Honor the frozen cross-paradigm contract: `0` success, `1` general/runtime
error, `2` usage/argument error. Symfony Console already codes this in:

- Return `Command::SUCCESS` (`0`) on success and `Command::FAILURE` (`1`) on
  a handled runtime error from `execute()`. Never return a raw int literal —
  use the class constants.
- A missing required argument or unknown option raises
  `Symfony\Component\Console\Exception\RuntimeException` (or a subclass)
  before `execute()` ever runs. `Application::run()` catches it and exits
  with code **`1`**, not `2` — Console does not auto-emit `2` for
  parse-level usage errors, despite that being a natural assumption. To
  honor this reference's own `0`/`1`/`2` contract, a usage-error condition
  that Console's own parser can't catch on its own (e.g. two mutually
  exclusive options both set, or a value that's syntactically valid but
  semantically wrong) must be detected and mapped explicitly in
  `execute()` by `return Command::INVALID;` (`2`) — never left to Console's
  default exception handling, which stops at `1`.
- For a domain-level runtime error surfaced from `src/Core/`, catch the Core
  exception in `execute()`, write a message to
  `$output->getErrorOutput()` (see §7), and `return Command::FAILURE`.

## 6. `--json` output and `--no-input`

Declare a `--json` `InputOption` (`VALUE_NONE`) on any command that produces
structured results. Branch at the end of `execute()` on whether it was
passed, and render with `json_encode()`, `JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR`:

```php
if ($input->getOption('json')) {
    $output->writeln(json_encode($result, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR));
} else {
    $output->writeln((string) $result);
}
```

Do not add a bespoke `--no-input` option. Symfony Console's `Application`
already exposes a global `--no-interaction` / `-n` flag; treat it as
`--no-input`'s semantics directly. Any prompt built with
`Symfony\Component\Console\Helper\QuestionHelper` (or `SymfonyStyle::ask()`,
`::confirm()`, `::choice()`) automatically skips the prompt and returns the
question's declared default when `--no-interaction` is set. If a command
requires a value that has no safe default and would otherwise have been
prompted for, check `$input->isInteractive()` explicitly in `execute()`;
when it is `false` and the value is missing, write an error to stderr and
`return Command::INVALID` (`2`) — do not silently proceed with a null value.

## 7. stdout/stderr discipline

Write all normal command output — results, data, anything meant to be piped
or parsed — via `$output->writeln(...)` (stdout). Write all diagnostics, logs,
progress, and warnings via Symfony Console's built-in stderr channel:

```php
protected function execute(InputInterface $input, OutputInterface $output): int
{
    $errOutput = $output instanceof ConsoleOutputInterface
        ? $output->getErrorOutput()
        : $output;

    $errOutput->writeln('<comment>Fetching…</comment>');
    $output->writeln($result);
    return Command::SUCCESS;
}
```

`ConsoleOutput` implements `ConsoleOutputInterface` and its
`getErrorOutput()` returns a second `OutputInterface` bound to the process's
real stderr stream — do not open `php://stderr` by hand. Guard with the
`instanceof ConsoleOutputInterface` check shown above so the Command still
works under `CommandTester`, whose output object does not implement it.

## 8. Distribution

Document both distribution paths; generate config for both.

**Composer/Packagist** (library-style install): ensure `composer.json` has a
correct `bin` entry pointing at `bin/<app>` so `composer require <vendor>/<app>`
symlinks it into the consumer's `vendor/bin/`:

```json
{
    "name": "<vendor>/<app>",
    "bin": ["bin/<app>"]
}
```

**Box `.phar`** (standalone, no-PHP-install-assumptions distribution):

```bash
composer require --dev humbug/box
```

Generate a `box.json` at the project root:

```json
{
    "main": "bin/<app>",
    "output": "<app>.phar",
    "compression": "GZ",
    "chmod": "0755"
}
```

Build with:

```bash
php box.phar compile
# or, if installed via Composer: vendor/bin/box compile
```

Ship the resulting `<app>.phar` as the standalone artifact; document
`php <app>.phar <command>` (or a `chmod +x <app>.phar && ./<app>.phar <command>`
with the `#!/usr/bin/env php` shebang box preserves from `bin/<app>`) as the
end-user invocation.

## 9. Snapshot testing `--help`

Install PHPUnit and the spatie snapshot package:

```bash
composer require --dev phpunit/phpunit spatie/phpunit-snapshot-assertions
```

Drive the command through Symfony Console's `CommandTester`, request
`--help`, and assert the captured output against a stored snapshot with
`assertMatchesTextSnapshot()`:

```php
<?php declare(strict_types=1);

namespace App\Tests\Command;

use App\Command\GreetCommand;
use PHPUnit\Framework\TestCase;
use Spatie\Snapshots\MatchesSnapshots;
use Symfony\Component\Console\Application;
use Symfony\Component\Console\Tester\CommandTester;

final class GreetCommandTest extends TestCase
{
    use MatchesSnapshots;

    public function testHelpOutputMatchesSnapshot(): void
    {
        $application = new Application();
        $application->add(new GreetCommand());

        $command = $application->find('greet');
        $tester = new CommandTester($command);
        $tester->execute(['--help' => true]);

        $this->assertMatchesTextSnapshot($tester->getDisplay());
    }
}
```

Run `vendor/bin/update-snapshots` once to record the initial snapshot file
under `tests/Command/__snapshots__/`; commit it. (`--update-snapshots` is
not a real PHPUnit/spatie flag — the package ships its own separate
`update-snapshots` binary for this; alternatively set the
`UPDATE_SNAPSHOTS=true` environment variable when running
`vendor/bin/phpunit` directly.) Regenerate only when a deliberate
help-text change is made — an unreviewed snapshot diff means the CLI
surface drifted.

## 10. Minimal worked example

Illustrative only — do not copy verbatim as a template; regenerate names,
namespaces, and logic to fit the actual app being built.

```php
<?php declare(strict_types=1);
// src/Core/Greeter.php — zero Console imports, plain unit-testable class.
namespace App\Core;

final class Greeter
{
    public function greet(string $name): string
    {
        if (trim($name) === '') {
            throw new \InvalidArgumentException('Name must not be empty.');
        }
        return "Hello, {$name}!";
    }
}
```

```php
<?php declare(strict_types=1);
// src/Command/GreetCommand.php — thin: parses input, delegates, formats output.
namespace App\Command;

use App\Core\Greeter;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputArgument;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

#[AsCommand(name: 'greet', description: 'Print a greeting for NAME')]
final class GreetCommand extends Command
{
    public function __construct(private readonly Greeter $greeter = new Greeter())
    {
        parent::__construct();
    }

    protected function configure(): void
    {
        $this->addArgument('name', InputArgument::REQUIRED, 'Name to greet');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        try {
            $output->writeln($this->greeter->greet($input->getArgument('name')));
            return Command::SUCCESS;
        } catch (\InvalidArgumentException $e) {
            $err = method_exists($output, 'getErrorOutput') ? $output->getErrorOutput() : $output;
            $err->writeln('<error>' . $e->getMessage() . '</error>');
            return Command::FAILURE;
        }
    }
}
```
