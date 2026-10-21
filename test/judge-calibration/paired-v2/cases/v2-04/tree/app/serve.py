from config.load import port


def bind_address():
    return ('0.0.0.0', port())
