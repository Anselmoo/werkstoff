#!/usr/bin/env ruby
# frozen_string_literal: true

# ARBEITSPLAN-STUB -- the author removes this line when the step is written.
# Step {{NODE}} of plan {{PLAN}} (arbeitsplan-waves, authored).
# Purpose: {{PURPOSE}}
# Contract: arguments are positional (ARGV); print exactly ONE JSON object on
# stdout (the node's output_schema); diagnostics go to $stderr; exit with one of
# {{EXITS}}.
# Verified by `{{HELPER}} verify-step --node {{NODE}}` with the sample {{SAMPLE}}.
require 'json'

def main(_argv)
  warn 'step {{NODE}} is not written yet'
  2
end

exit(main(ARGV))
