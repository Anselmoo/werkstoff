#!/usr/bin/env python3
"""Inject analysis/self-assess/stage_map.json into the topology viewer template.

Usage: render_stage_map.py <topology-viewer.html path> <output dir>
Reads <output dir>/stage_map.json, writes <output dir>/STAGE_MAP.html.
"""
import json
import sys


def main() -> None:
    tpl_path, out_dir = sys.argv[1], sys.argv[2]
    tpl = open(tpl_path).read()
    marker = "/*__TOPOLOGY_DATA__*/ null"
    assert marker in tpl, f"injection marker not found in {tpl_path}"

    data = json.dumps(json.load(open(f"{out_dir}/stage_map.json")))
    # stage_map.json is derived from UNTRUSTED source (file paths, stage/wire
    # names come from analyzed code). It's injected into a <script> block, and
    # the HTML parser closes <script> on the literal bytes "</script>"
    # regardless of JS string context, so a stage/file named
    # "x</script><script>..." would execute. json.dumps does NOT escape "<".
    # Escape it (JSON-safe) to kill the breakout.
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    open(f"{out_dir}/STAGE_MAP.html", "w").write(
        tpl.replace(marker, "/*__TOPOLOGY_DATA__*/ " + data)
    )
    print(f"wrote {out_dir}/STAGE_MAP.html")


if __name__ == "__main__":
    main()
