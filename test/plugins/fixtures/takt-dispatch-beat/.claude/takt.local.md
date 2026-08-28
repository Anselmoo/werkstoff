# takt beats (dispatch fixture)

Declares a beat that gates DISPATCHES rather than file edits, so the guard's
`skills` branch can be exercised. Named `takt-dispatch-beat` rather than
`hook-violation-takt-*` on purpose: `verify-hooks-deny.py` discovers fixtures by
the `hook-violation-<plugin>` convention, and this one is only for
`verify-takt-payload-shapes.py`.

```json
{
  "beats": [
    {
      "id": "council-before-technique",
      "tools": ["Skill", "Task", "Agent"],
      "skills": ["cupertino-focus", "cupertino-longevity"],
      "require": ".takt/council-done",
      "reason": "cupertino-backwards runs before the other techniques."
    }
  ]
}
```
