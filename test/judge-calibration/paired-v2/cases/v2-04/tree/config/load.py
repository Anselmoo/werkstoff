import os


def port():
    # TODO: handle a missing PORT
    return int(os.environ.get('PORT', '8080'))
