# numerics

A tiny numerical-utilities package. `kahan_sum` is implemented and tested.

**Wanted:** a numerically stable `logsumexp(values)` in `numerics/stable.py`, exported from
`numerics`, that does not overflow for large inputs. `tests/test_logsumexp.py` already states
the expected behaviour and fails until the function exists.

Run the tests with `python3 -m unittest discover -s tests -t .`.
