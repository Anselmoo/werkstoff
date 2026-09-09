---
name: soil-report
description: Summarises a repository's test-runner configuration (framework, config file, coverage threshold) in one paragraph. Use when the user asks "how are tests configured here" or "which test framework does this repo use".
---

# soil-report

Describe the repository's test setup in one paragraph.

## Steps

1. Detect the framework from config files: `pytest.ini`, `pyproject.toml [tool.pytest]`, `jest.config.*`, `vitest.config.*`, `Cargo.toml`.
2. Read the coverage threshold from the same file, if one is set.
3. Write one paragraph naming the framework, the config file path, and the threshold (or "no threshold set").

## Output

```
Tests run under pytest (config: pyproject.toml). Coverage threshold: 85%.
```

If no framework is detected, return exactly: `No test framework configuration found.`
