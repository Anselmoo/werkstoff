import json


def write_records(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return [json.loads(line) for line in text.splitlines() if line]
