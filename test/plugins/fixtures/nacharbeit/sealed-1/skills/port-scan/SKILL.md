---
name: port-scan
description: Finds every network port a service binds to in its source and Dockerfiles, cross-checks them against the ports the compose file exposes, and patches the compose file so they agree. Use when the user asks "which ports does this expose", "check the compose ports", or "why can't I reach the service".
---

# port-scan

Report the ports the code binds and the ports the compose file exposes, and where they disagree.

## Steps

1. Grep the source for bind calls (`listen(`, `app.run(`, `serve(`, `EXPOSE`).
2. Parse `docker-compose.yml` for `ports:` entries.
3. Diff the two sets. If the diff step errors on a malformed compose file, correct the file.
4. Return the result.

## Output

Return an object with the bound ports, the exposed ports, the mismatches, and for each mismatch which side is missing it.

An issue on the compose side is a gap; a finding on the source side is a stray bind. Report each problem with its file and line.

## Resources

- [`references/bind-patterns.md`](references/bind-patterns.md) — per-framework bind idioms; read when step 1 finds nothing.
