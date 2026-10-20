ROUTES = {"/": "home", "/about": "about"}


def route(path):
    if len(path) > 1:
        path = path.rstrip("/")
    return ROUTES.get(path)
