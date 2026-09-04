"""Inventory loading. Also core: no CLI framework here either."""

import json


def load(path):
    """Read an inventory file and return its widget list."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["widgets"]
