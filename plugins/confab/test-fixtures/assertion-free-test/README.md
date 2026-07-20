# Fixture: assertion-free-test

Regression case for `confab-assertion-audit`'s core detection scenario: a
test that executes the target function (so it counts toward coverage) but
never asserts anything about its actual behavior — the exact gap
LLM-generated tests are prone to leaving open.

`calculator.py` defines:

```python
def add(a: int, b: int) -> int:
    return a + b
```

`test_calculator.py`'s `test_add_does_not_raise` calls `add(2, 3)` and
only asserts `result is not None` — it never checks that the result is
`5`.

**Expected result from `confab-assertion-audit`:** a High-severity
finding for `add` — a proposed mutation (e.g. flipping `a + b` to
`a - b`, or `a * b`) would still return a non-`None` value, so
`test_add_does_not_raise` would **not** catch it. Expected catching test:
none found. `wouldBeCaught: false`.

Not a runnable package on its own (no test framework config included) —
this fixture exists to be read and reasoned about by
`confab-assertion-audit`'s finder/verifier agents, not necessarily
executed by a CI runner, though `pytest test_calculator.py` from this
directory (with `calculator.py` on the path) will pass, which is itself
part of the point: a passing test suite that still shouldn't be trusted.
