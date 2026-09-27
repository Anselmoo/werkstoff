#!/usr/bin/env node
// ARBEITSPLAN-STUB -- the author removes this line when the step is written.
// Step {{NODE}} of plan {{PLAN}} (arbeitsplan-waves, authored).
// Purpose: {{PURPOSE}}
// Contract: arguments are positional (process.argv.slice(2)); print exactly ONE
// JSON object on stdout (the node's output_schema); diagnostics go to stderr;
// exit with one of {{EXITS}}. `.mjs`, never `.js`: every .js under
// .claude/workflows/ is a workflow to Claude Code.
// Verified by `{{HELPER}} verify-step --node {{NODE}}` with the sample {{SAMPLE}}.

function main(_argv) {
  process.stderr.write('step {{NODE}} is not written yet\n')
  return 2
}

process.exitCode = main(process.argv.slice(2))
