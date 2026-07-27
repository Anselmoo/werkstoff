from producer.generate import build_record

def load_record():
    r = build_record()
    # Wire contract: consumer requires 'uuid', producer emits 'id'.
    return r["uuid"]
