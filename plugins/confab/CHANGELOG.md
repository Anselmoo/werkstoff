# Changelog

All notable changes to this plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- **Renamed: plugin `quality` → `confab`** (BREAKING — install target is now
  `confab@werkstoff`, and every skill/agent is renamed `quality-*` → `confab-*`,
  e.g. `confab-dependency-audit`, `confab-cycle`). The `quality` name collided
  with `self-assess` on the shared `code-quality` marketplace keyword; `confab`
  (as in *confabulation*) names the plugin's actual scope — catching where
  AI-authored code makes things up. Cross-plugin references in `andon` were
  updated to match. Keyword `code-quality` → `ai-code-verification` +
  `confabulation-detection`.
- Fixed: `plugin.json` description now mentions `confab-cycle` (was
  drifted from `marketplace.json`'s copy); README intro corrected from
  "one deliberate exception" to "two" (network egress + scoped Edit
  access).
- Added: `confab-code-change`, a diff-scoped pre-commit variant of the
  four domain audits.
- Changed: `confab-cycle` fix mode now also auto-remediates
  `agentic_reliability` excessive-tool-grant findings, and drafts (never
  applies) `assertion_audit` suggestions via a new `draft_domains`
  setting.

## [0.1.0]

- Initial release.
