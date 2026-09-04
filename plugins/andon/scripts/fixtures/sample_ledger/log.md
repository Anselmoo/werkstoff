# andon OKF log

Append-only. Never rewritten. See okf-ledger-schema.md.

### Pass 1 (cycle 1)
- stage: ingest
- wire: ingest->normalize
- gap: ingest-schema-drift-detector
- strategy: f
- verdict: green
- next_cursor: normalize::normalize-unit-coercion-silent
- cycle: 1
- pass_number: 1

### Pass 2 (cycle 1)
- stage: normalize
- wire: ingest->normalize
- gap: normalize-unit-coercion-silent
- strategy: b
- verdict: green
- next_cursor: normalize::normalize-timezone-drift
- cycle: 1
- pass_number: 2

### Pass 3 (cycle 1)
- stage: normalize
- wire: normalize->enrich
- gap: normalize-timezone-drift
- strategy: a
- verdict: unknown
- next_cursor: enrich::enrich-null-taxonomy-join
- cycle: 1
- pass_number: 3

### Pass 4 (cycle 1)
- stage: enrich
- wire: normalize->enrich
- gap: enrich-null-taxonomy-join
- strategy: a
- verdict: unknown
- next_cursor: enrich::enrich-missing-provenance-check
- cycle: 1
- pass_number: 4

### Cycle 1 converged after 4 passes

### Pass 5 (cycle 2)
- stage: enrich
- wire: enrich->score
- gap: enrich-missing-provenance-check
- strategy: e
- verdict: red
- next_cursor: enrich::enrich-missing-provenance-check
- cycle: 2
- pass_number: 5

### Sub-cycle: enrich->score reopened (count 1)
- wire: enrich->score
- depth: 1
- reopen_count: 1
- escalated: false

### Pass 6 (cycle 2)
- stage: enrich
- wire: enrich->score
- gap: enrich-missing-provenance-check
- strategy: e
- verdict: red
- next_cursor: enrich::enrich-missing-provenance-check
- cycle: 2
- pass_number: 6

### Sub-cycle: enrich->score reopened (count 2)
- wire: enrich->score
- depth: 2
- reopen_count: 2
- escalated: false

### Pass 7 (cycle 2)
- stage: enrich
- wire: enrich->score
- gap: enrich-missing-provenance-check
- strategy: e
- verdict: red
- next_cursor: enrich::enrich-missing-provenance-check
- cycle: 2
- pass_number: 7

### Sub-cycle: enrich->score reopened (count 3)
- wire: enrich->score
- depth: 2
- reopen_count: 3
- escalated: true
