#!/usr/bin/env bash
set -euo pipefail
# Usage: extract-changelog-section.sh <changelog-file> <version>
# Prints the body between "## [<version>]" and the next "## [" heading.
CHANGELOG_FILE="$1"
VERSION="$2"
SECTION=$(awk -v ver="$VERSION" '
  /^## \[/ {
    if (found) exit
    if ($0 ~ ("\\[" ver "\\]")) { found=1; next }
  }
  found { print }
' "$CHANGELOG_FILE")
if [ -z "$(echo "$SECTION" | tr -d '[:space:]')" ]; then
  echo "_No CHANGELOG.md entry found for version ${VERSION}._"
else
  echo "$SECTION"
fi
