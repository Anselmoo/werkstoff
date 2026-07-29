"""Detect the target language version from a repo's manifest files.
Covers exactly the 4 languages self-assess-preflight/self-assess-code-idiom
document; any other language returns None."""
import json
import os
import re


def _detect_python(repo):
    pyproject = os.path.join(repo, "pyproject.toml")
    if os.path.isfile(pyproject):
        content = open(pyproject, "r", encoding="utf-8").read()
        for pattern in (r'requires-python\s*=\s*"([^"]+)"', r'python\s*=\s*"([^"]+)"'):
            match = re.search(pattern, content)
            if match:
                return match.group(1)
    setup_py = os.path.join(repo, "setup.py")
    if os.path.isfile(setup_py):
        content = open(setup_py, "r", encoding="utf-8").read()
        match = re.search(r'python_requires\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    return None


def _detect_javascript(repo):
    package_json = os.path.join(repo, "package.json")
    if not os.path.isfile(package_json):
        return None
    try:
        with open(package_json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    return (data.get("engines") or {}).get("node")


def _detect_go(repo):
    go_mod = os.path.join(repo, "go.mod")
    if not os.path.isfile(go_mod):
        return None
    with open(go_mod, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("go "):
                return line.split(maxsplit=1)[1]
    return None


def _detect_java(repo):
    pom = os.path.join(repo, "pom.xml")
    if not os.path.isfile(pom):
        return None
    content = open(pom, "r", encoding="utf-8").read()
    for pattern in (r"<maven\.compiler\.source>([^<]+)</maven\.compiler\.source>", r"<java\.version>([^<]+)</java\.version>"):
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    return None


_DETECTORS = {
    "python": _detect_python,
    "javascript": _detect_javascript,
    "typescript": _detect_javascript,
    "go": _detect_go,
    "java": _detect_java,
}


def detect_language_version(repo, language):
    detector = _DETECTORS.get(language)
    return detector(repo) if detector else None
