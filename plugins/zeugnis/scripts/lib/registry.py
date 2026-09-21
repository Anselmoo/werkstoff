"""Read-only, GET-only, bounded-timeout public-registry lookups. Stdlib
only (urllib), never raises for network/timeout failure -- degrades to
"skipped" instead, since a timeout must never produce a false "hallucinated"
or "exists" verdict."""
import urllib.error
import urllib.request

from lib.constants import LOOKUP_NOT_FOUND, LOOKUP_SKIPPED

LOOKUP_EXISTS = "exists"
DEFAULT_TIMEOUT_SECONDS = 10

# Real public registry endpoints, GET-only. Go's module-path escaping rule
# (uppercase letters need "!"-prefixing) is deliberately not implemented --
# no caller in this codebase currently looks up a mixed-case Go module path.
_ENDPOINTS = {
    "pypi": "https://pypi.org/pypi/{name}/json",
    "npm": "https://registry.npmjs.org/{name}",
    "crates": "https://crates.io/api/v1/crates/{name}",
    "go": "https://proxy.golang.org/{name}/@latest",
    "rubygems": "https://rubygems.org/api/v1/gems/{name}.json",
}


def resolve_timeout(timeout_seconds):
    # Same non-clamping treatment as lib.ledger's resolvers -- the "never
    # above 60" ceiling is guidance to the orchestrating session.
    return timeout_seconds if timeout_seconds else DEFAULT_TIMEOUT_SECONDS


def lookup_package(ecosystem, name, *, timeout_seconds):
    template = _ENDPOINTS.get(ecosystem)
    if template is None:
        return {"outcome": LOOKUP_SKIPPED, "reason": f"unknown ecosystem {ecosystem!r}"}
    url = template.format(name=name)
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            if response.status == 200:
                return {"outcome": LOOKUP_EXISTS}
            return {"outcome": LOOKUP_SKIPPED, "reason": f"unexpected status {response.status}"}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"outcome": LOOKUP_NOT_FOUND}
        return {"outcome": LOOKUP_SKIPPED, "reason": f"HTTP {exc.code}"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"outcome": LOOKUP_SKIPPED, "reason": str(exc)}
