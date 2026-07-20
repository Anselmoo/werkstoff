# Changelog

All notable changes to this plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Fixed: `plugin.json` description now mentions `quality-cycle` (was
  drifted from `marketplace.json`'s copy); README intro corrected from
  "one deliberate exception" to "two" (network egress + scoped Edit
  access).
- Added: `quality-code-change`, a diff-scoped pre-commit variant of the
  four domain audits.
- Changed: `quality-cycle` fix mode now also auto-remediates
  `agentic_reliability` excessive-tool-grant findings, and drafts (never
  applies) `assertion_audit` suggestions via a new `draft_domains`
  setting.

## [0.1.0]

- Initial release.
