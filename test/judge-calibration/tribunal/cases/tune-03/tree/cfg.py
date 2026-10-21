class ConfigError(Exception):
    pass


DEFAULTS = {"retries": 3, "verbose": False}


def load_config(raw):
    """Applies defaults to a raw settings mapping."""
    if "name" not in raw:
        raise ConfigError("name is required")
    out = dict(DEFAULTS)
    out.update(raw)
    return out
