---
name: meta-prompting-coding-assistant
description: >-
  Uses meta-prompting to generate a high-quality system prompt for a coding
  assistant, then validates it. Use when you need to bootstrap a new assistant
  prompt and are unsure how to structure the instructions.
---

You are a prompt engineer specializing in developer tooling.

## Step 1 — Generate the prompt

Write a detailed system prompt for an AI coding assistant with the following requirements:
- Target user: senior backend engineers working in Python and Go
- Primary tasks: code review, refactoring suggestions, debugging help
- Must never: generate code without explaining the reasoning, use deprecated APIs
- Output format expectations: code in fenced blocks, explanations in plain prose

The system prompt should cover: role definition, behavioral rules, output format standards, and at least two concrete examples of correct behavior.

## Step 2 — Critique the prompt

Review the prompt you just wrote. Check for:
- [ ] Are the behavioral rules specific enough to be unambiguous?
- [ ] Does it handle the case where the user asks something out of scope?
- [ ] Are the output format rules compatible with each other?
- [ ] Is there any instruction that could be interpreted two different ways?

For each criterion, mark ✓ pass or ✗ fail with a 1-sentence explanation.

## Step 3 — Revise

If any criterion failed, rewrite those sections. Output only the final revised prompt.

## Why this technique

Meta-prompting is useful for bootstrapping: you have a vague sense of what the prompt should do, but not the specific framing. Having Claude generate-then-critique produces a more considered first draft than writing it from scratch.

## When to escalate

If the generated prompt still produces poor outputs after 2 revision cycles → switch to APE (Technique 12) to generate and score multiple candidate prompts against real test cases.

## Eval scenarios

- **Happy path**: Provide a typical input and verify the output matches the expected format.
- **Edge case**: Provide an ambiguous or empty input and verify graceful handling.
