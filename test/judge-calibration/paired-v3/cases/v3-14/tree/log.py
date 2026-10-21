import json


def save_log(path, events):
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(e) + "\n" for e in events))


def load_log(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f.read().splitlines()]
