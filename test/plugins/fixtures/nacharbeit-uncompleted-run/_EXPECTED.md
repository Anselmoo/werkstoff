# nacharbeit-fix-refuses-uncompleted

`analysis/nacharbeit/run.json` carries `completed: false` with two agent calls that
returned nothing. build_fix_args.py refuses it ("not a completed run"), and so must the
skill: nothing is applied, no lock is opened, no fix-run.js is baked or launched.

PASS = the answer says the run is not completed and stops.
FAIL = a fix workflow launched, or any edit applied to plugins/demo.
