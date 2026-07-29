# This directory is committed source, not build output

If you can read this file from a plugin's `scripts/lib/` directory, git
tracking for that directory is working. If it's ever *missing* right after
a fresh clone while the rest of `scripts/lib/` looks populated on an
existing checkout, that's not a merge artifact -- it means `.gitignore` has
started matching this directory again, the same way it silently did for
`plugins/self-assess/scripts/lib/` and `plugins/confab/scripts/lib/` from
the moment they were first written until issue #24 found it: an unanchored
`lib/` line (generic Python-template boilerplate for build output) matched
these directories too, at any depth, so nothing under them was ever
committed -- for months, across dozens of commits, invisible to `git
status` on any machine that already had the (uncommitted, gitignored)
files sitting locally.

This file exists to make that failure mode loud instead of silent:

- It's a real, committed file at `plugins/<name>/scripts/lib/README.md`,
  vendored identically into every plugin that has a `scripts/lib/` package
  via `.rrt.toml`'s `artifact_targets` (same mechanism as
  `build_symbol_index.py`), sourced from this canonical copy.
- `rrt artifacts --check --strict` (wired into `plugin-checks.yml`) hashes
  every vendored copy against `.rrt/artifacts.lock.toml` on every push and
  PR. On a fresh CI checkout, a `.gitignore` regression that swallows a
  `lib/` directory again makes this file (and everything else in that
  directory) simply not exist -- which `rrt artifacts --check` reports as a
  hash mismatch immediately, not months later when a hook starts denying
  every edit.

**If you add a `scripts/lib/` package to a new plugin**, add a matching
`artifact_targets` entry for `plugins/<name>/scripts/lib/README.md` in
`.rrt.toml` (copy an existing self-assess/confab entry), then run
`rrt artifacts --regenerate` to vendor this file and update the lock.
