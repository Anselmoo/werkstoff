# nacharbeit-preflight-inventory

`plugins/demo` carries one hook script, one skill and one report viewer. The preflight
answer must name both the hook script and the viewer as things a review would measure
(the inventory line prints `hookscript=1` and `viewer=1`), and say whether a fix lock is
open (none is).

PASS = the answer mentions the hook script AND the viewer.
FAIL = a summary that lists only skills, or one that grades anything (preflight writes
nothing and judges nothing).
