"""Mask credentials before any self-assess report persists them."""
import re
from urllib.parse import urlsplit, urlunsplit

_USERINFO_RE = re.compile(r"://([^/@\s:]+(?::[^/@\s]+)?)@")
_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{12,}\b")


def _preview_len(secret):
    # No call site pins an exact number; 4 chars for anything long enough to
    # not be trivially guessable from the preview alone, 2 otherwise.
    return 4 if len(secret) >= 8 else 2


def _mask(secret):
    return secret[: _preview_len(secret)] + "***"


def mask_text(text):
    """Mask userinfo embedded in URLs and any long token-shaped substring in
    free text (e.g. `git remote -v` output)."""
    masked = _USERINFO_RE.sub(lambda m: "://" + _mask(m.group(1)) + "@", text)
    return _TOKEN_RE.sub(lambda m: _mask(m.group(0)), masked)


def mask_url(url):
    """URL-aware masking: only the userinfo component, structure preserved."""
    parts = urlsplit(url)
    if not parts.username:
        return url
    userinfo = _mask(parts.username)
    if parts.password:
        userinfo += ":***"
    host = parts.hostname or ""
    netloc = f"{userinfo}@{host}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
