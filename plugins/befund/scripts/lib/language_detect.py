"""Two-pass language detection: manifest presence, then extension counts."""

MIN_FILES_FOR_DETECTION = 3

MANIFEST_LANGUAGE = {
    "package.json": "javascript",
    "pyproject.toml": "python",
    "setup.py": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
}

EXTENSION_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
}


def detect_languages(manifests, extension_counts):
    """Pass 1: a present manifest directly assigns its language. Pass 2: an
    extension only promotes a language if its count >= MIN_FILES_FOR_DETECTION
    AND no manifest already claimed that language. The returned shape
    distinguishes how each language was detected, since downstream preflight
    grading depends on manifest-detected vs. extension-only-detected."""
    languages = {}
    for manifest in manifests:
        lang = MANIFEST_LANGUAGE.get(manifest)
        if lang and lang not in languages:
            languages[lang] = {"source": "manifest", "manifest": manifest}
    for ext, count in extension_counts.items():
        lang = EXTENSION_LANGUAGE.get(ext)
        if lang and lang not in languages and count >= MIN_FILES_FOR_DETECTION:
            languages[lang] = {"source": "extension_count", "count": count}
    return {"languages": languages}
