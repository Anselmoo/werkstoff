# hook-violation fixture for takt

`.claude/takt.local.md` is present, so takt is active in this repository and
declares one beat: UI source may not be edited until `.takt/council-done`
exists. That marker is deliberately absent here.

The probe target is `src/ui/Panel.tsx` (via `_TARGET`), which matches the
beat's `paths` globs. The DEFAULT probe target ("src/api.py") matches no glob
in the declared beat, so the hook would correctly allow it — that is why a
`_TARGET` override is required for this plugin, exactly as it is for cupertino.

PASS = exit 2, reason cites "runs ahead of beat 'ui-before-council'".
FAIL = exit 0 (UI code would be written before the council beat ran).
