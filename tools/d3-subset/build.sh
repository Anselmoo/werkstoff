#!/usr/bin/env bash
# Regenerates inline-d3.html from the pinned d3 sub-packages in package.json.
# Run from this directory: cd tools/d3-subset && ./build.sh
set -euo pipefail
npm install
npx esbuild entry.js --bundle --minify --format=iife --global-name=d3 --outfile=/tmp/d3-bundle.min.js
{
  echo "<script>"
  echo "/* Inlined d3 v7 subset (d3-hierarchy, d3-zoom, d3-selection, d3-interpolate, d3-ease, d3-force, d3-scale). ISC License (Mike Bostock and D3 contributors) except d3-ease, which is BSD-3-Clause. Bundled via esbuild from official npm releases matching the d3@7 dependency pins; minified; exposed as window.d3. See SOURCES.md for exact versions. */"
  cat /tmp/d3-bundle.min.js
  echo "</script>"
} > inline-d3.html
echo "wrote inline-d3.html ($(wc -c < inline-d3.html) bytes)"
