#!/usr/bin/env python3
"""Inject a compass workflow's JSON result into the reasoning-trace viewer.

Unlike self-assess-stage-map's render_stage_map.py (which reads a JSON file
already written to <output_dir>/stage_map.json), compass has no output_dir
or settings file — every compass-* skill returns its result into the
conversation rather than to disk. So this script reads the JSON result from
stdin instead of a sibling file, and takes the exact output path to write
rather than an output directory.

Usage: render_trace.py <reasoning-trace-viewer.html path> <output path>
       (the workflow's JSON result is piped in on stdin, e.g. via a heredoc)
"""
import json
import sys


def main() -> None:
    tpl_path, out_path = sys.argv[1], sys.argv[2]
    tpl = open(tpl_path).read()
    marker = "/*__TRACE_DATA__*/ null"
    assert marker in tpl, f"injection marker not found in {tpl_path}"

    data = json.dumps(json.load(sys.stdin))
    # The trace JSON is derived from UNTRUSTED source (branch names,
    # candidate prompts, reasoning text originate from LLM- and
    # user-authored content). It's injected into a <script> block, and the
    # HTML parser closes <script> on the literal bytes "</script>" regardless
    # of JS string context, so a branch/candidate named "x</script><script>
    # ..." would execute. json.dumps does NOT escape "<". Escape it
    # (JSON-safe) to kill the breakout — mirrors
    # plugins/self-assess/skills/self-assess-stage-map/scripts/render_stage_map.py's
    # exact approach; do not reimplement this escaping ad hoc elsewhere.
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    open(out_path, "w").write(tpl.replace(marker, "/*__TRACE_DATA__*/ " + data))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
