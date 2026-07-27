---
name: self-assess-ui-audit
description: This skill should be used when the user asks to "audit UI accessibility", "check our components for a11y issues", "find hardcoded design values", or as part of self-assess-autopilot's CHECK phase. Statically audits JSX/TSX, Vue/Svelte, HTML, and CSS/SCSS source for accessibility, semantic-markup, and design-token problems -- never running or rendering the app.
version: 0.1.0
---

# self-assess-ui-audit

Statically audit UI source for accessibility, semantic markup, and hardcoded design values.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-ui-audit
```

## Step 1: Detect UI files, degrade if none found

Glob for `*.jsx`, `*.tsx`, `*.vue`, `*.svelte`, `*.html`, `*.css`, `*.scss`. If none are found,
write `UI_AUDIT.md` and `ui_audit_summary.json` with `applicable: false` and a one-line reason,
then stop -- this is a degrade to "Not applicable," never an error.

## Step 2: Static audit only

Dispatch `ui-auditor` against the detected files. The agent never runs or builds the app, never
renders a DOM, and never drives a browser -- it reads source only. Look for:

- Accessibility: missing `alt` text, missing form labels/accessible names, non-interactive
  elements used as controls (`<div onClick>`), positive `tabindex`.
- Semantic markup: a clickable `<div>` where `<button>` belongs, skipped heading levels,
  missing landmark elements.
- Hardcoded design values: literal colors/dimensions where the codebase otherwise uses a
  design-token or CSS-variable system.
- Contrast: plausibly low-contrast literal color pairs. This MUST be flagged as a static
  heuristic only -- never compute or assert a real WCAG contrast ratio, since no renderer is
  running to measure actual rendered contrast.

## Step 3: Verify

Unless `skip_verification` is set, re-read each cited location to confirm the finding before it
is reported.

## Step 4: Validate and write

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind ui_audit_summary --file <path-or-inline-json>
```

The validator rejects any `contrast`-kind finding that does not carry `heuristic: true`.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename UI_AUDIT.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename ui_audit_summary.json
```

## Read-only constraint

Never use Write/Edit outside the resolved output paths, never run a dev server, build command,
or browser automation tool.
