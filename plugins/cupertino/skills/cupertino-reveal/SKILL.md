---
name: cupertino-reveal
description: "Use at ship-time, as the last automatic step for a finished feature, module, tool, or API, to deliver exactly one non-obvious, high-leverage addition in a keynote 'and one more thing' structure. Trigger on 'what's missing here', 'is there anything else this needs before shipping', or automatically as the final stage when cupertino-review runs the full pipeline. Never produces a list — exactly one suggestion, and it must be built, not pitched."
---

Deliver exactly one reveal. Never a numbered list, never a set of alternatives to choose from — the discipline of "and one more thing" is that there is exactly one thing.

## Steps

1. **State plainly what the shipped artifact does** — the baseline, so the gap is legible against it.
2. **Name the gap**: the specific capability or delight that's genuinely missing, that a user would eventually ask for or silently miss without knowing to ask.
3. **"And one more thing"** — the pivot. Name the one idea.
4. **Describe it**: what it is, concretely.
5. **Explain why it wasn't already there** — a real reason (it required the foundation just built, it wasn't obvious until this artifact existed, it's a genuine insight rather than a known backlog item).
6. **Implementation sketch**, then **build it** — production-grade, matched to the artifact's actual stack. Write the code directly into the shipped artifact's actual source tree (the real files that ship, not a separate write-up or scratch file); if the artifact has no editable source tree to write into, say so explicitly and name where the built code lives instead. A reveal that stays pitched as a roadmap item is not a reveal; "real artists ship."
7. **Impact sentence**: one sentence on what this actually changes for the person using the artifact.

## Worked example

A compact instance of the full seven-part shape (a real reveal is longer; this shows the structure, not the length):

````
Baseline: The CLI now parses a config file and runs the pipeline end to end.
Gap: Every run re-reads and re-validates the same config from disk, even
  in a tight retry loop — nothing caches the parsed result.
And one more thing: a process-lifetime config cache, invalidated on mtime change.
Description: Wrap the loader so a second call in the same process returns the
  already-parsed object unless the file's mtime has moved.
Why it wasn't already there: this only pays off once the pipeline is called
  repeatedly in one process, which only became possible once retry-on-failure
  (built this session) existed.

  ```python
  _cache: dict[str, tuple[float, Config]] = {}

  def load_config(path: str) -> Config:
      mtime = os.stat(path).st_mtime
      cached = _cache.get(path)
      if cached and cached[0] == mtime:
          return cached[1]
      config = Config.parse(path)
      _cache[path] = (mtime, config)
      return config
  ```

Impact: retrying a failed run no longer re-parses and re-validates config on
  every attempt — a 20-retry backoff loop does one parse instead of 20.
````

## Validate mechanically

Do not eyeball the "exactly one, and it's built" requirements:

```bash
echo '{"text": "<your full reveal writeup, including the code block>"}' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" reveal-shape
```

This rejects the reveal if it contains a numbered or bulleted list of suggestions (more than one idea presented), or if it has no fenced code block at all (meaning nothing was actually built). If it fails, cut to one idea and build it before presenting again. If it fails validation twice in a row, stop retrying — report the blocker (what failed and why) to the user instead of attempting a third pass.

## Refuse

- Never suggest something already obviously on the user's mental backlog — the reveal must be genuinely surprising.
- Never suggest something trivial ("add type hints", "fix a typo") — it must be non-trivial and high-leverage.
- Never present it as a future consideration rather than working code.
