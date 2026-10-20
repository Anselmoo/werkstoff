#!/usr/bin/env python3
"""Match git tags to changelog headings."""
import re, subprocess
tags = subprocess.run(["git", "tag", "--list"], capture_output=True, text=True).stdout.split()
heads = re.findall(r"^## \[?v?(\d+\.\d+\.\d+)", open("CHANGELOG.md").read(), re.M)
print({"tags_without_heading": sorted(set(t.lstrip("v") for t in tags) - set(heads)),
       "headings_without_tag": sorted(set(heads) - set(t.lstrip("v") for t in tags))})
