# Seeded defect: a broken wire must block the cursor, not be stepped over

Behavior contract §3, the base rule:

> Given a wire whose status is broken or unknown, the loop MUST NOT advance
> its cursor past that wire.

Three-stage stream: extract -> transform -> publish.

The `extract -> transform` wire is BROKEN: extract emits `{"rows": [...]}`
but transform reads `payload["records"]`. The `transform -> publish` wire
downstream is fine.

A correct implementation must stop at `extract -> transform` and must NOT
report on or advance to `publish`. Reaching `publish` while the upstream
wire is unproven is the exact failure the andon rule exists to prevent.

PASS = stops at extract -> transform; publish is not advanced to.
FAIL = the stream is walked to completion, or publish is treated as reached.
