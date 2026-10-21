DB = {1: "ann"}
_cache = {}


def get_name(uid):
    if uid not in _cache:
        _cache[uid] = DB[uid]
    return _cache[uid]


def rename(uid, name):
    DB[uid] = name
