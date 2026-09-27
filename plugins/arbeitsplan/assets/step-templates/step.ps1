# ARBEITSPLAN-STUB -- the author removes this line when the step is written.
# Step {{NODE}} of plan {{PLAN}} (arbeitsplan-waves, authored).
# Purpose: {{PURPOSE}}
# Contract: arguments are positional; print exactly ONE JSON object on stdout
# (the node's output_schema, e.g. ConvertTo-Json -Compress -Depth 10); diagnostics
# go to stderr; exit with one of {{EXITS}}.
# Verified by `{{HELPER}} verify-step --node {{NODE}}` with the sample {{SAMPLE}}.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$ErrorActionPreference = 'Stop'

[Console]::Error.WriteLine('step {{NODE}} is not written yet')
exit 2
