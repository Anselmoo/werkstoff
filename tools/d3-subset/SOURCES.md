# tools/d3-subset provenance

`inline-d3.html` is a self-contained, minified IIFE bundle exposing
`window.d3`, built by `build.sh` from the following official npm packages:

| Module | Version | License | Source |
|---|---|---|---|
| d3-hierarchy | 3.1.2 | ISC | https://github.com/d3/d3-hierarchy |
| d3-zoom | 3.0.0 | ISC | https://github.com/d3/d3-zoom |
| d3-selection | 3.0.0 | ISC | https://github.com/d3/d3-selection |
| d3-interpolate | 3.0.1 | ISC | https://github.com/d3/d3-interpolate |
| d3-ease | 3.0.1 | BSD-3-Clause | https://github.com/d3/d3-ease |
| d3-force | 3.0.0 | ISC | https://github.com/d3/d3-force |
| d3-scale | 4.0.2 | ISC | https://github.com/d3/d3-scale |

The first 5 modules were originally hand-extracted verbatim from
`anthropics/claude-plugins-official`'s `code-modernization/assets/topology-viewer.html`
reference file. `d3-force` and `d3-scale` are not present in that reference
file at all, so they were sourced independently, directly from npm, pinned
to the same major versions the `d3@7` umbrella package itself depends on
(confirmed via `npm view d3@7 dependencies`) to keep the whole bundle on one
coherent D3 v7 line.

The bundle also includes each package's own transitive D3 dependencies
(`d3-array`, `d3-color`, `d3-dispatch`, `d3-drag`, `d3-format`,
`d3-quadtree`, `d3-time`, `d3-time-format`, `d3-timer`, `d3-transition`,
`internmap`) — all confirmed ISC License. See `package-lock.json` for the
exact transitive version set.

To regenerate: `cd tools/d3-subset && ./build.sh`. To add a module, add it
to both `package.json` devDependencies and the `export * from` list in
`entry.js`, then re-run `build.sh` and re-run this file's version capture.
