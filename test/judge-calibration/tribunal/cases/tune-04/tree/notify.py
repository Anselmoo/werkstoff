import os
import urllib.request


def format_message(user, msg):
    return f"[{user}] {msg}"


def notify(user, msg):
    url = os.environ["MAIL_GATEWAY_URL"]
    req = urllib.request.Request(url, data=format_message(user, msg).encode(), method="POST")
    return urllib.request.urlopen(req).status
