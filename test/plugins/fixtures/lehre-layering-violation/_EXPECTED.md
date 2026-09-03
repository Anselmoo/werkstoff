# lehre-layering-violation

A repo that has opted into lehre with one seeded blocking violation:
`src/api/handler.py:1` imports `src.db.session`, which `no-api-to-db` forbids.
`src/api/create.py` is clean and must not be reported.

`units` is deliberately empty so the ordering gate cannot fire — this fixture
tests the gauge, not the build-order guard.
