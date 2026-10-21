import json


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
