---
name: cupertino-prototype
description: "Use at build-time, parallel to cupertino-council, whenever a specific empirical uncertainty needs settling by actually building and running a throwaway version rather than debating it in the abstract. Trigger on 'not sure if this approach will actually work', 'let's spike this', 'will this library even do what we need', or any disagreement that a small runnable experiment would resolve faster than continued discussion. Never use for general feasibility studies — only for one specific, answerable question."
---

Settle one specific empirical question by building and running something real — never by describing what you expect would happen.

## Steps

1. **State the question precisely**: phrase it so a single run of code either answers it or doesn't. "Will this rate limit handle our peak load pattern?" is answerable; "will this be fast enough" is not — narrow it until it is.
2. **Build the minimal spike**: the smallest real, runnable artifact that can answer the question. Do not architect it for reuse — no clean interfaces, no error handling beyond what's needed to observe the result, no tests. It is disposable by default.
3. **Run it — actually run it.** This is mechanically checked, not optional:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/run_prototype.sh" <path-to-spike-file> [args...]
   ```
   This script rejects anything that isn't a real, executable file (no runner registered = the spike wasn't runnable, which fails the technique outright) and reports the actual exit code and captured output. A prototype that only exists as a description, a wireframe, or a "here's what the code would look like" mockup has not satisfied this technique, even if it looks plausible.
4. **Report what running it actually showed** — the real output and exit status, not a prediction of what it would likely show.
5. **Decide the spike's fate explicitly.** After observing the run, choose one:
   - **Discard**: the question is answered, the code has no further purpose, delete it.
   - **Deliberately promote pieces**: name exactly which parts are worth carrying into production code, and note that they now need the rigor (tests, error handling, review) they were exempted from as a spike.

   Never silently keep using spike code in the real build without making this choice out loud — that is how throwaway code quietly becomes load-bearing and unreviewed.

## Output format

The question → the spike code → the actual run output (via the script above) → the observation → the explicit fate decision. If the script reports a non-zero exit or "no runner registered," that failure *is* the empirical observation — report it as such rather than fixing the spike until it passes, unless fixing it is itself what the question was about.
