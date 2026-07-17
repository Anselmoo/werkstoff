#!/usr/bin/env python3
"""Inject <output_dir>/findings_dashboard_data.json into the findings dashboard template.

Usage: render_dashboard.py <findings-dashboard.html path> <output dir>
Reads <output dir>/findings_dashboard_data.json, writes
<output dir>/findings-dashboard.html.

Mirrors self-assess-stage-map/scripts/render_stage_map.py's injection
mechanism (same marker-replace-plus-JSON-safe-escape approach, applied to
a different template/marker/payload).
"""
import json
import sys


def main() -> None:
    tpl_path, out_dir = sys.argv[1], sys.argv[2]
    tpl = open(tpl_path).read()
    marker = "/*__QUALITY_DASHBOARD_DATA__*/ null"
    assert marker in tpl, f"injection marker not found in {tpl_path}"

    data = json.dumps(json.load(open(f"{out_dir}/findings_dashboard_data.json")))
    # findings_dashboard_data.json is derived from UNTRUSTED source (finding
    # titles/evidence ultimately trace back to analyzed repo content: package
    # names, contract types, category labels). It's injected into a <script>
    # block, and the HTML parser closes <script> on the literal bytes
    # "</script>" regardless of JS string context, so a value containing
    # "x</script><script>..." would execute. json.dumps does NOT escape "<".
    # Escape it (JSON-safe) to kill the breakout.
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    open(f"{out_dir}/findings-dashboard.html", "w").write(
        tpl.replace(marker, "/*__QUALITY_DASHBOARD_DATA__*/ " + data)
    )
    print(f"wrote {out_dir}/findings-dashboard.html")


if __name__ == "__main__":
    main()
