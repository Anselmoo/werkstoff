# Fixture: contract-mismatch

Regression case for `confab-contract-drift`'s core detection scenario: a
declared, machine-checkable contract (a type hint) that does not match how
the function is actually called elsewhere in the same fixture.

`service.py` declares:

```python
def get_user_email(user_id: int) -> str:
    """...
    Args:
        user_id (int): The numeric ID of the user to look up.
    ...
    """
```

`client.py`'s `notify_user` calls it as `get_user_email(user_id=str(user_id))`
— passing a `str` where the declared contract requires an `int`, both in
the type hint and the docstring's `Args:` section.

**Expected result from `confab-contract-drift`:** one confirmed
`TypeSignature` mismatch —

- **Contract:** `get_user_email(user_id: int) -> str`
- **Declared:** `service.py` (type hint + docstring `Args:` block)
- **Actual usage:** `client.py:notify_user` calls it with a `str` argument
- **Confidence:** High

`notify_all`'s call to `notify_user(uid)` passes an `int`, matching
`notify_user`'s own `user_id: int` contract exactly — a **non-finding**,
included so the fixture also proves the checker doesn't flag every call
site indiscriminately, only the one that actually contradicts its
declared contract.

Not a runnable/installable package — this fixture exists to be
statically analyzed, not executed.
